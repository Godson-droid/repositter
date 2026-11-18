#!/usr/bin/env python3
"""Create and seed the scratch repo used for the approval-gate proof.

Creates Godson-droid/repositter-scratch (via the custom.github connector
helper), creates the rubric label vocabulary, and seeds three issues: a
crash bug report, a feature request, and a docs question. Idempotent: if
the repo already has open issues, it seeds nothing.
"""

from __future__ import annotations

import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from repositter import github_api  # noqa: E402

OWNER = "Godson-droid"
REPO = "repositter-scratch"
HELPER = Path.home() / "workspace/custom-connectors/custom.github/bin/github.py"

LABELS = {
    "bug": "d73a4a",
    "enhancement": "a2eeef",
    "question": "d876e3",
    "documentation": "0075ca",
    "needs info": "fbca04",
    "good first issue": "7057ff",
    "help wanted": "008672",
    "duplicate": "cfd3d7",
    "wontfix": "ffffff",
}

ISSUES = [
    (
        "Crash on empty config file",
        "RepoSitter dies with a traceback when the config file exists but is "
        "empty.\n\nSteps to reproduce:\n1. Create an empty `repositter.toml`.\n"
        "2. Run `python run.py --run-name test`.\n\nExpected: a clear error "
        "saying the config is empty.\nActual: `tomllib.TOMLDecodeError` "
        "traceback with no guidance.",
    ),
    (
        "Add a --dry-run flag that prints the plan without calling the model",
        "It would help debugging to see which items would be triaged, and in "
        "what order, without spending model requests. A `--dry-run` flag "
        "could fetch items, compare against memory, and print the plan, "
        "then exit before any model call.",
    ),
    (
        "README does not say where run artifacts are written",
        "I ran the demo and could not find the output reports afterwards. "
        "The README explains setup and how to run, but never says that "
        "artifacts land in `runs/<run-name>/` or what files to expect there. "
        "Could the docs add a short section on the artifact layout?",
    ),
]


def main() -> int:
    status, _ = github_api._request("GET", f"/repos/{OWNER}/{REPO}")
    if status == 404:
        out = subprocess.run(
            [sys.executable, str(HELPER), "create-repo", REPO,
             "Scratch repo for RepoSitter approval-gate tests (Cortensor Hackathon #5)"],
            capture_output=True, text=True, timeout=120,
        )
        print("create-repo:", out.stdout.strip() or out.stderr.strip())
    else:
        print(f"repo exists (status {status})")
    for name, color in LABELS.items():
        code = github_api.create_label(OWNER, REPO, name, color)
        print(f"label {name}: {code}")
    existing = github_api.list_open_items(OWNER, REPO, limit=25)
    if existing:
        print(f"already seeded: {len(existing)} open items, skipping issue creation")
    else:
        for title, body in ISSUES:
            created = github_api.create_issue(OWNER, REPO, title, body)
            print(f"issue #{created['number']}: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
