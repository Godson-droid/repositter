#!/usr/bin/env python3
"""RepoSitter entrypoint.

Usage:
  python run.py --run-name run-01-openminion
  python run.py --target Godson-droid/repositter-scratch --run-name run-03-scratch --approve-write

Environment note: this sandbox exports NO_PROXY entries with bracketed
IPv6 addresses that break httpx proxy parsing inside OpenMinion, so the
proxy bypass list is normalized to a clean value before anything imports
the SDK. Outbound traffic still goes through the proxy variables; only
the bypass list is cleaned, and localhost must be on it so the agent can
reach the loopback relay.
"""

from __future__ import annotations

import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tomllib  # noqa: E402
from pathlib import Path  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from repositter.triage import ProjectConfig, run_triage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one RepoSitter triage pass")
    parser.add_argument("--target", help="owner/repo (default from repositter.toml)")
    parser.add_argument("--run-name", required=True, help="artifact directory name under runs/")
    parser.add_argument("--max-items", type=int, help="cap on newly triaged items")
    parser.add_argument("--provider", help="relay provider route: groq (primary), gemini or openrouter")
    parser.add_argument("--model", help="model id override")
    parser.add_argument("--no-propose", action="store_true", help="skip the approval-gate stage")
    parser.add_argument("--no-skill", action="store_true", help="skip loading the rubric skill in the scan stage")
    parser.add_argument(
        "--approve-write",
        action="store_true",
        help="answer yes on the held approval thread so the proposed write executes",
    )
    args = parser.parse_args()

    with (PROJECT_DIR / "repositter.toml").open("rb") as fh:
        raw = tomllib.load(fh)
    cfg = ProjectConfig(
        owner=raw["target"]["owner"],
        repo=raw["target"]["repo"],
        provider=raw.get("model", {}).get("provider", ProjectConfig.provider),
        model=raw.get("model", {}).get("primary", ProjectConfig.model),
        max_items=int(raw.get("limits", {}).get("max_items_per_run", 3)),
        relay_port=int(raw.get("relay", {}).get("port", 8377)),
        propose_label=bool(raw.get("limits", {}).get("propose_label", True)),
    )
    if args.target:
        cfg.owner, cfg.repo = args.target.split("/", 1)
    if args.max_items is not None:
        cfg.max_items = args.max_items
    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model = args.model
    if args.no_propose:
        cfg.propose_label = False
    if args.no_skill:
        cfg.load_skill = False

    summary = run_triage(
        cfg,
        project_dir=PROJECT_DIR,
        run_name=args.run_name,
        approve_write=args.approve_write,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
