"""RepoSitter orchestration.

One triage run is four stages sharing one OpenMinion runtime and one
session:

1. scan     - a parent agent loads the triage-rubric skill, fetches the
              repo's open items with the read-only fetch tool, searches
              agent memory for earlier triage records, and returns a typed
              ScanReport saying which items are new.
2. classify - each new item is delegated to a bounded classifier subagent
              that returns a typed TriageReport (delegation block).
3. record   - the parent agent writes one memory record per report, so the
              next run's scan can skip those items (memory block).
4. propose  - optionally, the parent asks to apply the top report's label
              through the dangerous write tool. With no approval callback
              the runtime action policy holds the run at a confirmation
              prompt (permissions block). With --approve-write the
              operator answers "yes" on the held thread and the write
              executes, then is verified by reading the issue back.
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from openminion import Agent, subagent
from openminion.api.runtime import APIRuntime

from . import github_api, tools as triage_tools
from .relay import start_relay
from .schemas import ScanReport, TriageReport

RUBRIC_PATH = Path(__file__).resolve().parent.parent / "skills" / "triage-rubric" / "SKILL.md"

SCAN_INSTRUCTIONS = """You are RepoSitter, a GitHub triage agent. Follow this protocol exactly:
1. Call skill.get with skill_id "triage_rubric" to load the triage rubric skill. If the skill cannot be loaded, continue without it.
2. Call fetch_open_items to get the open issues and pull requests of the configured repo.
3. Call memory.search with the query "triaged {repo}" to find items already triaged in earlier runs.
4. Compare: an item is already triaged only when a memory record clearly names that repo and item number. Everything else is new.
5. Answer with the ScanReport JSON only: fetched_count, new_item_numbers, already_triaged_numbers, notes.
Do not classify items in this stage and do not call any write tool."""

OPS_INSTRUCTIONS = """You are RepoSitter, a GitHub triage agent. You record finished triage reports
in memory and, when asked, propose GitHub writes. Memory records use
record_type "fact", key "triaged:<owner>/<repo>#<number>", and content of one
line: "Triaged <owner>/<repo> <kind> #<number> '<title>': category=<category>
priority=<priority> labels=<comma separated labels> on <date>". The content
must name the full <owner>/<repo> so later searches can match it. Write
exactly the records you are given, one memory.write call per report, then
summarise in plain text."""

CLASSIFIER_INSTRUCTIONS = """You are a classification subagent for a GitHub triage system.
Classify exactly one issue or pull request using the triage rubric below.

Output rules, all mandatory:
- Answer with ONLY one JSON object. No prefix, no code fences, no commentary.
- The object must have exactly these fields: item_number (integer),
  item_kind ("issue" or "pull_request"), title (string), category (one of
  bug, feature, question, docs, other), priority (one of critical, high,
  medium, low), summary (string, two or three sentences),
  suggested_labels (array of strings from the rubric vocabulary),
  suggested_next_action (string).

{rubric}"""

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class ProjectConfig:
    owner: str = "openminion"
    repo: str = "openminion"
    # Primary provider route: Groq via the loopback relay (see
    # repositter/relay.py PROVIDERS). Earlier routes kept wired:
    # "gemini" / "gemini-3.6-flash" and the "openrouter" fallback with
    # model "cohere/north-mini-code:free".
    provider: str = "groq"
    model: str = "openai/gpt-oss-120b"
    max_items: int = 3
    relay_port: int = 8377
    propose_label: bool = True
    load_skill: bool = True


@dataclass
class RunOutcome:
    summary: dict = field(default_factory=dict)


def _extract_json_object(text: str) -> dict | None:
    """Return the first balanced {...} object in text parsed as JSON, if any."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : idx + 1])
                    except Exception:
                        break
                    return parsed if isinstance(parsed, dict) else None
        start = text.find("{", start + 1)
    return None


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _result_payload(result: object) -> dict:
    return {
        "text": getattr(result, "text", None),
        "run_id": getattr(result, "run_id", None),
        "run_state": getattr(result, "run_state", None),
        "session_id": getattr(result, "session_id", None),
        "thread_id": getattr(result, "thread_id", None),
        "metadata": getattr(result, "metadata", {}),
        "stats": getattr(result, "stats", {}),
    }


def run_triage(
    cfg: ProjectConfig,
    *,
    project_dir: Path,
    run_name: str,
    approve_write: bool = False,
    use_relay: bool = True,
) -> dict:
    """Execute one full triage run and write artifacts under runs/<run_name>."""
    started = time.time()
    run_dir = project_dir / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "run_name": run_name,
        "target": f"{cfg.owner}/{cfg.repo}",
        "provider": cfg.provider,
        "model": cfg.model,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stages": {},
    }
    triage_tools.configure(cfg.owner, cfg.repo)
    rubric = RUBRIC_PATH.read_text(encoding="utf-8")

    relay_server = None
    relay_state = None
    if use_relay:
        relay_server, relay_state = start_relay(
            cfg.relay_port, project_dir / "runs" / "relay.log", provider=cfg.provider
        )
        time.sleep(0.3)
    summary["relay_requests_before"] = relay_state.count if relay_state else None

    runtime = APIRuntime.from_config_path(
        str(project_dir / ".openminion" / "agents.json"), logging_mode="interactive"
    )
    session_id = f"repositter-{cfg.owner}-{cfg.repo}-{run_name}"
    try:
        # --- stage 1: scan -------------------------------------------------
        scan_tools: list = [triage_tools.fetch_open_items, "memory.search"]
        if cfg.load_skill:
            scan_tools += ["skill.get"]
        scan_agent = Agent(
            runtime=runtime,
            instructions=SCAN_INSTRUCTIONS.format(repo=f"{cfg.owner}/{cfg.repo}"),
            tools=scan_tools,
            forced_tools=["fetch_open_items"],
            output_type=ScanReport,
            model=cfg.model,
            session_id=session_id,
        )
        scan_prompt = (
            f"Run a triage scan of {cfg.owner}/{cfg.repo} now. "
            "Follow the protocol in your instructions."
        )
        try:
            scan_result = scan_agent.run(scan_prompt, timeout_seconds=900)
            _dump(run_dir / "scan_result.json", _result_payload(scan_result))
            scan: ScanReport | None = scan_result.output
            summary["stages"]["scan"] = {"ok": True, "run_id": scan_result.run_id}
        except Exception as exc:  # typed-output failure: try to salvage the JSON
            scan = None
            raw_text = getattr(exc, "raw_text", "") or ""
            salvaged = _extract_json_object(raw_text)
            if salvaged is not None:
                try:
                    scan = ScanReport.model_validate(salvaged)
                    summary["stages"]["scan"] = {"ok": True, "salvaged": True}
                except Exception:
                    scan = None
            if scan is None:
                summary["stages"]["scan"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                _dump(run_dir / "scan_error.json", {"error": traceback.format_exc()})
        if relay_state is not None:
            summary["stages"]["scan"]["relay_requests"] = relay_state.count - (summary["relay_requests_before"] or 0)
        fetched = triage_tools.last_fetch()
        summary["fetched_count"] = len(fetched)
        if scan is not None:
            _dump(run_dir / "scan.json", scan.model_dump())
            new_numbers = [n for n in scan.new_item_numbers if any(it["number"] == n for it in fetched)]
            known_numbers = list(scan.already_triaged_numbers)
        else:
            new_numbers = [it["number"] for it in fetched]
            known_numbers = []
        new_numbers = new_numbers[: cfg.max_items]
        summary["new_item_numbers"] = new_numbers
        summary["already_triaged_numbers"] = known_numbers

        # --- stage 2: classify via delegated subagent ----------------------
        reports: list[TriageReport] = []
        classify_log: list[dict] = []
        if new_numbers:
            parent = Agent(runtime=runtime, name="repositter-parent", session_id=session_id)
            classifier = subagent(
                parent,
                name="classifier",
                instructions=CLASSIFIER_INSTRUCTIONS.format(rubric=rubric),
                output_type=TriageReport,
                model=cfg.model,
                timeout_seconds=600,
            )
            by_number = {it["number"]: it for it in fetched}
            for number in new_numbers:
                item = by_number[number]
                prompt = (
                    f"Classify this {item['kind']} from {cfg.owner}/{cfg.repo}.\n"
                    f"Number: {item['number']}\nTitle: {item['title']}\n"
                    f"Author: {item['author']}\nCreated: {item['created_at']}\n"
                    f"Current labels: {item['labels']}\nComments: {item['comments']}\n"
                    f"Body:\n{item['body_excerpt']}"
                )
                try:
                    result = classifier.run(prompt)
                    report: TriageReport = result.output
                    reports.append(report)
                    _dump(run_dir / "reports" / f"{item['kind']}-{number}.json", report.model_dump())
                    classify_log.append({"number": number, "ok": True, "run_id": result.run_id})
                except Exception as exc:
                    # Salvage: the model often wraps its JSON in prose. The
                    # orchestrator owns the identity fields (number, kind,
                    # title) from the fetch, so merge those over whatever
                    # judgment fields the model produced.
                    raw_text = getattr(exc, "raw_text", "") or ""
                    salvaged = _extract_json_object(raw_text)
                    report = None
                    if salvaged is not None:
                        salvaged["item_number"] = item["number"]
                        salvaged["item_kind"] = item["kind"]
                        salvaged["title"] = item["title"]
                        try:
                            report = TriageReport.model_validate(salvaged)
                        except Exception:
                            report = None
                    if report is not None:
                        reports.append(report)
                        _dump(run_dir / "reports" / f"{item['kind']}-{number}.json", report.model_dump())
                        classify_log.append({"number": number, "ok": True, "salvaged": True})
                    else:
                        classify_log.append({"number": number, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        summary["stages"]["classify"] = classify_log
        if relay_state is not None:
            summary["stages"]["classify_relay_requests"] = (
                relay_state.count - (summary["relay_requests_before"] or 0) - summary["stages"].get("scan", {}).get("relay_requests", 0)
            )
        summary["reports"] = [r.model_dump() for r in reports]

        # --- stage 3: record in memory -------------------------------------
        if reports:
            ops_agent = Agent(
                runtime=runtime,
                instructions=OPS_INSTRUCTIONS,
                tools=["memory.write", triage_tools.propose_github_write],
                model=cfg.model,
                session_id=session_id,
            )
            today = time.strftime("%Y-%m-%d", time.gmtime())
            record_prompt = (
                f"Record these triage reports for {cfg.owner}/{cfg.repo} in memory, "
                f"one memory.write per report, using today's date {today}:\n"
                + json.dumps([r.model_dump() for r in reports], indent=2)
            )
            relay_mark = relay_state.count if relay_state else 0
            try:
                record_result = ops_agent.run(record_prompt, timeout_seconds=900)
                _dump(run_dir / "record_result.json", _result_payload(record_result))
                summary["stages"]["record"] = {"ok": True, "run_id": record_result.run_id}
            except Exception as exc:
                summary["stages"]["record"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if relay_state is not None:
                summary["stages"]["record"]["relay_requests"] = relay_state.count - relay_mark

            # --- stage 4: propose one gated write --------------------------
            if cfg.propose_label:
                top = sorted(reports, key=lambda r: PRIORITY_ORDER[r.priority])[0]
                label = top.suggested_labels[0] if top.suggested_labels else "bug"
                propose_prompt = (
                    f"Now propose exactly one GitHub write: call propose_github_write with "
                    f"item_number={top.item_number}, action=\"add_label\", label=\"{label}\". "
                    "Do not call any other tool. After the tool result, state in one sentence what happened."
                )
                try:
                    held = ops_agent.run(propose_prompt, timeout_seconds=900)
                    _dump(run_dir / "approval_held.json", _result_payload(held))
                    held_kind = (held.metadata or {}).get("respond_kind")
                    summary["stages"]["propose"] = {
                        "item": top.item_number,
                        "label": label,
                        "respond_kind": held_kind,
                        "thread_id": held.thread_id,
                    }
                    if approve_write and held_kind == "policy_confirmation_prompt" and held.thread_id:
                        resumed = ops_agent.run("yes", thread_id=held.thread_id, timeout_seconds=900)
                        _dump(run_dir / "approval_resumed.json", _result_payload(resumed))
                        issue = github_api.get_issue(cfg.owner, cfg.repo, top.item_number)
                        landed = [lbl["name"] for lbl in issue.get("labels", [])]
                        summary["stages"]["propose"]["resumed_text"] = resumed.text
                        summary["stages"]["propose"]["labels_after"] = landed
                        summary["stages"]["propose"]["label_landed"] = label in landed
                except Exception as exc:
                    summary["stages"]["propose"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            runtime.close()
        except Exception:
            pass
        if relay_server is not None:
            relay_server.shutdown()

    summary["relay_requests_after"] = relay_state.count if relay_state else None
    if relay_state is not None:
        summary["relay_requests_delta"] = relay_state.count - (summary["relay_requests_before"] or 0)
    summary["seconds"] = round(time.time() - started, 1)
    _dump(run_dir / "summary.json", summary)
    (run_dir / "reports.md").write_text(_render_reports_md(cfg, summary, reports), encoding="utf-8")
    return summary


def _render_reports_md(cfg: ProjectConfig, summary: dict, reports: list[TriageReport]) -> str:
    lines = [
        f"# RepoSitter run: {summary['run_name']}",
        "",
        f"- Target: {cfg.owner}/{cfg.repo}",
        f"- Provider: {cfg.provider}",
        f"- Model: {cfg.model}",
        f"- Started: {summary['started_at']}",
        f"- Fetched open items: {summary.get('fetched_count')}",
        f"- Already triaged (skipped): {summary.get('already_triaged_numbers')}",
        f"- New items triaged: {[r.item_number for r in reports]}",
        "",
    ]
    for r in reports:
        lines += [
            f"## #{r.item_number} ({r.item_kind}) {r.title}",
            "",
            f"- Category: {r.category}",
            f"- Priority: {r.priority}",
            f"- Summary: {r.summary}",
            f"- Suggested labels: {', '.join(r.suggested_labels)}",
            f"- Suggested next action: {r.suggested_next_action}",
            "",
        ]
    if not reports:
        lines.append("No new items needed triage in this run.")
    return "\n".join(lines) + "\n"
