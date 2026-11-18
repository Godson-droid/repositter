#!/usr/bin/env python3
"""Finish the day 2 leftovers (2026-11-17), reusing the pipeline's stages.

Two subcommands, both through the loopback relay on the route chosen
with --provider/--model (default: the project config's route, Groq
since 2026-11-17; the record subcommand was first used on Gemini):

  record    Record triage reports that an earlier run classified but
            could not record (run-04's record stage died on HTTP 429),
            then verify the records are findable via memory.search.
            Usage: python scripts/finish_day2.py record \
                     --run-name run-05-record \
                     --from-summary runs/run-04-openminion/summary.json

  classify  Classify specific open items of the target repo through the
            normal delegated classifier (stage 2) and record successful
            reports in memory (stage 3). The propose stage is NOT run:
            the approval gate stays held and no GitHub write is proposed
            or executed on the target repo.
            Usage: python scripts/finish_day2.py classify \
                     --run-name run-06-openminion --numbers 769,768

Artifacts land in runs/<run-name>/ in the same shapes run.py produces.
Exit code 3 means a stage failed with a provider rate limit; the caller
must stop all further provider work at that point.
"""

from __future__ import annotations

import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from openminion import Agent, subagent  # noqa: E402
from openminion.api.runtime import APIRuntime  # noqa: E402

from repositter import github_api, tools as triage_tools  # noqa: E402
from repositter.relay import start_relay  # noqa: E402
from repositter.schemas import TriageReport  # noqa: E402
from repositter.triage import (  # noqa: E402
    CLASSIFIER_INSTRUCTIONS,
    OPS_INSTRUCTIONS,
    RUBRIC_PATH,
    ProjectConfig,
    _dump,
    _extract_json_object,
    _render_reports_md,
    _result_payload,
)

LOG_PATH = PROJECT_DIR / "runs" / "relay.log"
MODEL = ProjectConfig.model
DEFAULT_PROVIDER = ProjectConfig.provider


def _log_offset() -> int:
    try:
        return LOG_PATH.stat().st_size
    except FileNotFoundError:
        return 0


def _log_delta(offset: int) -> dict:
    """Count relay requests (and 429s) appended since `offset` bytes."""
    counts: dict = {"requests": 0, "http_429": 0, "http_200": 0}
    try:
        with LOG_PATH.open("rb") as fh:
            fh.seek(offset)
            raw = fh.read().decode("utf-8", "replace")
    except FileNotFoundError:
        return counts
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        counts["requests"] += 1
        if entry.get("status") == 429:
            counts["http_429"] += 1
        elif entry.get("status") == 200:
            counts["http_200"] += 1
    return counts


def _rate_limited(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "RATE_LIMITED" in text or "429" in text or "rate limit" in text.lower()


def _open_runtime(relay_port: int = 8377, provider: str = DEFAULT_PROVIDER):
    server, state = start_relay(relay_port, LOG_PATH, provider=provider)
    time.sleep(0.3)
    runtime = APIRuntime.from_config_path(
        str(PROJECT_DIR / ".openminion" / "agents.json"), logging_mode="interactive"
    )
    return server, state, runtime


def _record_stage(runtime, session_id: str, owner: str, repo: str,
                  reports: list[TriageReport], model: str = MODEL,
                  extra_instruction: str = "") -> dict:
    """Mirror of triage.py stage 3: one memory.write per report."""
    ops_agent = Agent(
        runtime=runtime,
        instructions=OPS_INSTRUCTIONS,
        tools=["memory.write"],
        model=model,
        session_id=session_id,
    )
    today = time.strftime("%Y-%m-%d", time.gmtime())
    prompt = (
        f"Record these triage reports for {owner}/{repo} in memory, "
        f"one memory.write per report, using today's date {today}."
    )
    if extra_instruction:
        prompt += " " + extra_instruction
    prompt += "\n" + json.dumps([r.model_dump() for r in reports], indent=2)
    result = ops_agent.run(prompt, timeout_seconds=900)
    return _result_payload(result)


def _verify_stage(runtime, session_id: str, owner: str, repo: str,
                  numbers: list[int], model: str = MODEL) -> dict:
    """Read memory back and report which items' records are really there.

    Per FINDINGS F16, a record stage is only believed once its effect is
    read back. A record's content line reads "... issue #780 'title' ..."
    (number, space, quote); a bare "#780" would also match a verify
    agent saying the item is missing, so match the content shape.
    """
    verify_agent = Agent(
        runtime=runtime,
        instructions=(
            "You verify persistent memory records. Use memory.search and "
            "report exactly what you find, verbatim where possible."
        ),
        tools=["memory.search"],
        model=model,
        session_id=session_id,
    )
    verify_prompt = (
        f'Call memory.search with the query "triaged {owner}/{repo}". '
        "Then report, verbatim, every record you find that concerns "
        + " or ".join(f"{owner}/{repo} item #{n}" for n in numbers)
        + ". If a record for one of those items is missing, say so explicitly."
    )
    vres = verify_agent.run(verify_prompt, timeout_seconds=900)
    vpayload = _result_payload(vres)
    text = vpayload.get("text") or ""
    return {
        "payload": vpayload,
        "stage": {
            "ok": True,
            "run_id": vpayload.get("run_id"),
            **{f"found_{n}": (f"#{n} '" in text) for n in numbers},
        },
    }


def cmd_record(args: argparse.Namespace) -> int:
    run_dir = PROJECT_DIR / "runs" / args.run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    source = json.loads((PROJECT_DIR / args.from_summary).read_text(encoding="utf-8"))
    reports = [TriageReport.model_validate(r) for r in source["reports"]]
    owner, repo = source["target"].split("/", 1)
    triage_tools.configure(owner, repo)
    summary: dict = {
        "run_name": args.run_name,
        "target": source["target"],
        "provider": args.provider,
        "model": args.model,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": (
            f"Record stage only: write memory records for the reports "
            f"classified in {source['run_name']}, whose own record stage "
            f"failed on the Gemini rate limit (HTTP 429)."
        ),
        "stages": {},
        "reports": [r.model_dump() for r in reports],
    }
    offset = _log_offset()
    server, state, runtime = _open_runtime(provider=args.provider)
    session_id = f"repositter-{owner}-{repo}-{args.run_name}"
    stop = False
    try:
        origin_note = (
            "These reports were classified in "
            f"{source['run_name']} and are only being recorded now because "
            "that run's record stage failed on a provider rate limit, so end "
            "each record's content with: "
            f"(classified in {source['run_name']}; recorded in {args.run_name})"
        )
        try:
            payload = _record_stage(runtime, session_id, owner, repo, reports,
                                    model=args.model, extra_instruction=origin_note)
            _dump(run_dir / "record_result.json", payload)
            summary["stages"]["record"] = {"ok": True, "run_id": payload.get("run_id")}
        except Exception as exc:
            summary["stages"]["record"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            _dump(run_dir / "record_error.json", {"error": traceback.format_exc()})
            stop = _rate_limited(exc)
        summary["stages"]["record"]["relay"] = _log_delta(offset)

        if summary["stages"]["record"]["ok"]:
            numbers = [r.item_number for r in reports]
            try:
                verified = _verify_stage(runtime, session_id, owner, repo, numbers, model=args.model)
                _dump(run_dir / "memory_verify.json", verified["payload"])
                summary["stages"]["memory_verify"] = verified["stage"]
            except Exception as exc:
                summary["stages"]["memory_verify"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                stop = stop or _rate_limited(exc)
            summary["stages"]["memory_verify"]["relay"] = _log_delta(offset)
    finally:
        try:
            runtime.close()
        except Exception:
            pass
        server.shutdown()
    summary["relay_total"] = _log_delta(offset)
    _dump(run_dir / "summary.json", summary)
    cfg = ProjectConfig(owner=owner, repo=repo)
    (run_dir / "reports.md").write_text(_render_reports_md(cfg, summary, reports), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return 3 if stop else 0


def cmd_classify(args: argparse.Namespace) -> int:
    owner, repo = args.target.split("/", 1)
    numbers = [int(n) for n in args.numbers.split(",") if n.strip()]
    run_dir = PROJECT_DIR / "runs" / args.run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    triage_tools.configure(owner, repo)
    summary: dict = {
        "run_name": args.run_name,
        "target": args.target,
        "provider": args.provider,
        "model": args.model,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": (
            f"Classification retries for {owner}/{repo} items {numbers} "
            "(failed on day 1 with the F5 prose-instead-of-JSON error), run "
            "through the normal classify and record stages. The propose "
            "stage is not run: the approval gate stays held and no GitHub "
            "write is proposed or executed on this repo."
        ),
        "stages": {"propose": {"skipped": True, "reason": "approval gate held; no write proposed or executed"}},
        "reports": [],
    }
    items = github_api.list_open_items(owner, repo, limit=100)
    by_number = {it["number"]: it for it in items}
    missing = [n for n in numbers if n not in by_number]
    if missing:
        summary["stages"]["fetch"] = {"ok": False, "error": f"items not open/found: {missing}", "fetched_count": len(items)}
        _dump(run_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, default=str))
        return 0
    summary["stages"]["fetch"] = {"ok": True, "fetched_count": len(items)}
    offset = _log_offset()
    server, state, runtime = _open_runtime(provider=args.provider)
    session_id = f"repositter-{owner}-{repo}-{args.run_name}"
    stop = False
    reports: list[TriageReport] = []
    try:
        rubric = RUBRIC_PATH.read_text(encoding="utf-8")
        parent = Agent(runtime=runtime, name="repositter-parent", session_id=session_id)
        classifier = subagent(
            parent,
            name="classifier",
            instructions=CLASSIFIER_INSTRUCTIONS.format(rubric=rubric),
            output_type=TriageReport,
            model=args.model,
            timeout_seconds=600,
        )
        classify_log: list[dict] = []
        for number in numbers:
            item = by_number[number]
            prompt = (
                f"Classify this {item['kind']} from {owner}/{repo}.\n"
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
                    if _rate_limited(exc):
                        stop = True
                        break
        summary["stages"]["classify"] = classify_log
        summary["reports"] = [r.model_dump() for r in reports]

        if reports and not stop:
            try:
                payload = _record_stage(runtime, session_id, owner, repo, reports, model=args.model)
                _dump(run_dir / "record_result.json", payload)
                summary["stages"]["record"] = {
                    "ok": True,
                    "run_id": payload.get("run_id"),
                    # F16: keep the tool-call evidence next to the claim;
                    # the memory read-back below is the deciding check.
                    "stats": payload.get("stats"),
                }
            except Exception as exc:
                summary["stages"]["record"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                _dump(run_dir / "record_error.json", {"error": traceback.format_exc()})
                stop = _rate_limited(exc)

        if reports and not stop and summary["stages"].get("record", {}).get("ok"):
            numbers = [r.item_number for r in reports]
            try:
                verified = _verify_stage(runtime, session_id, owner, repo, numbers, model=args.model)
                _dump(run_dir / "memory_verify.json", verified["payload"])
                summary["stages"]["memory_verify"] = verified["stage"]
            except Exception as exc:
                summary["stages"]["memory_verify"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                stop = stop or _rate_limited(exc)
    finally:
        try:
            runtime.close()
        except Exception:
            pass
        server.shutdown()
    summary["relay_total"] = _log_delta(offset)
    _dump(run_dir / "summary.json", summary)
    cfg = ProjectConfig(owner=owner, repo=repo)
    summary.setdefault("fetched_count", len(items))
    summary.setdefault("already_triaged_numbers", [])
    (run_dir / "reports.md").write_text(_render_reports_md(cfg, summary, reports), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return 3 if stop else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_rec = sub.add_parser("record")
    p_rec.add_argument("--run-name", required=True)
    p_rec.add_argument("--from-summary", required=True)
    p_rec.add_argument("--provider", default=DEFAULT_PROVIDER)
    p_rec.add_argument("--model", default=MODEL)
    p_rec.set_defaults(fn=cmd_record)
    p_cls = sub.add_parser("classify")
    p_cls.add_argument("--run-name", required=True)
    p_cls.add_argument("--target", default="openminion/openminion")
    p_cls.add_argument("--numbers", required=True)
    p_cls.add_argument("--provider", default=DEFAULT_PROVIDER)
    p_cls.add_argument("--model", default=MODEL)
    p_cls.set_defaults(fn=cmd_classify)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
