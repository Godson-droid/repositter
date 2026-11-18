#!/usr/bin/env python3
"""Run only RepoSitter's scan stage (fetch + skill + memory comparison).

Useful as a cheap diagnostic: it shows which items the agent considers
already triaged (from persistent memory) versus new, without spending
model requests on classification. It still costs a few model requests
(the scan is an agent run), so use it sparingly on the free tier.

Usage: python scripts/scan_probe.py [--target owner/repo]
Writes runs/probe-scan/scan.json and prints the relay request delta.
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

from openminion import Agent  # noqa: E402
from openminion.api.runtime import APIRuntime  # noqa: E402

from repositter import tools as triage_tools  # noqa: E402
from repositter.relay import start_relay  # noqa: E402
from repositter.schemas import ScanReport  # noqa: E402
from repositter.triage import SCAN_INSTRUCTIONS, ProjectConfig, _extract_json_object  # noqa: E402

MODEL = ProjectConfig.model
PROVIDER = ProjectConfig.provider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="openminion/openminion")
    args = parser.parse_args()
    owner, repo = args.target.split("/", 1)

    out_dir = PROJECT_DIR / "runs" / "probe-scan"
    out_dir.mkdir(parents=True, exist_ok=True)
    triage_tools.configure(owner, repo)

    server, state = start_relay(8377, PROJECT_DIR / "runs" / "relay.log", provider=PROVIDER)
    time.sleep(0.3)
    runtime = APIRuntime.from_config_path(
        str(PROJECT_DIR / ".openminion" / "agents.json"), logging_mode="interactive"
    )
    try:
        agent = Agent(
            runtime=runtime,
            instructions=SCAN_INSTRUCTIONS.format(repo=f"{owner}/{repo}"),
            tools=[triage_tools.fetch_open_items, "memory.search", "skill.get"],
            forced_tools=["fetch_open_items"],
            output_type=ScanReport,
            model=MODEL,
            session_id=f"repositter-{owner}-{repo}-probe-scan",
        )
        before = state.count
        scan: ScanReport | None = None
        try:
            result = agent.run(
                f"Run a triage scan of {owner}/{repo} now. Follow the protocol in your instructions.",
                timeout_seconds=900,
            )
            scan = result.output
            print("scan ok, run_id:", result.run_id)
        except Exception as exc:
            raw_text = getattr(exc, "raw_text", "") or ""
            salvaged = _extract_json_object(raw_text)
            if salvaged is not None:
                try:
                    scan = ScanReport.model_validate(salvaged)
                    print("scan ok via salvage")
                except Exception:
                    scan = None
            if scan is None:
                print("scan FAILED:", type(exc).__name__, exc)
                (out_dir / "scan_error.json").write_text(
                    json.dumps({"error": traceback.format_exc()}, indent=2), encoding="utf-8"
                )
        print(f"relay requests used: {state.count - before}")
        if scan is not None:
            (out_dir / "scan.json").write_text(
                json.dumps(scan.model_dump(), indent=2), encoding="utf-8"
            )
            print(json.dumps(scan.model_dump(), indent=2))
        fetched = triage_tools.last_fetch()
        print(f"fetched items: {len(fetched)}")
    finally:
        runtime.close()
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
