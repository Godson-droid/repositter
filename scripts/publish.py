#!/usr/bin/env python3
"""Publish RepoSitter to GitHub: main branch + gh-pages dashboard.

Uses repositter.github_api (credential via the custom.github surrogate).
Pushes the project tree to `main` (excluding .venv, .openminion,
web/node_modules, __pycache__) and web/dist to an orphan `gh-pages`
branch, then enables GitHub Pages from gh-pages. Idempotent: re-running
updates both branches from the current tree.

Usage: python3 scripts/publish.py [--dry-run]
"""

from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from repositter import github_api  # noqa: E402

OWNER = "Godson-droid"
REPO = "repositter"

EXCLUDE_DIRS = {".venv", ".openminion", "node_modules", "__pycache__", ".git"}
EXCLUDE_SUFFIXES = (".pyc",)


def collect(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(EXCLUDE_SUFFIXES):
                continue
            p = Path(dirpath) / fn
            files.append((p.relative_to(root).as_posix(), p))
    return files


def _call_with_retry(method: str, path: str, body: dict | None = None,
                     attempts: int = 3):
    """One GitHub API call with retries on transient 5xx responses."""
    last: tuple[int, object] = (0, None)
    for attempt in range(attempts):
        status, payload = github_api._request(method, path, body)
        last = (status, payload)
        if status < 500:
            return status, payload
        time.sleep(2 * (attempt + 1))
    return last


def push_branch(branch: str, root: Path, message: str, parents: list[str]) -> str:
    files = collect(root)
    items = []
    for rel, p in files:
        data = base64.b64encode(p.read_bytes()).decode()
        status, blob = _call_with_retry(
            "POST", f"/repos/{OWNER}/{REPO}/git/blobs",
            {"content": data, "encoding": "base64"})
        if status not in (200, 201):
            raise RuntimeError(f"blob {rel} failed: {status} {blob}")
        items.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    status, tree = github_api._request(
        "POST", f"/repos/{OWNER}/{REPO}/git/trees", {"tree": items})
    if status not in (200, 201):
        raise RuntimeError(f"tree {branch} failed: {status} {tree}")
    status, commit = github_api._request(
        "POST", f"/repos/{OWNER}/{REPO}/git/commits",
        {"message": message, "tree": tree["sha"], "parents": parents})
    if status not in (200, 201):
        raise RuntimeError(f"commit {branch} failed: {status} {commit}")
    status, ref = github_api._request(
        "GET", f"/repos/{OWNER}/{REPO}/git/refs/heads/{branch}")
    if status == 200:
        status, ref = github_api._request(
            "PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/{branch}",
            {"sha": commit["sha"], "force": False})
        if status not in (200, 201):
            raise RuntimeError(f"update {branch} failed: {status} {ref}")
    elif status == 404:
        status, ref = github_api._request(
            "POST", f"/repos/{OWNER}/{REPO}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        if status not in (200, 201):
            raise RuntimeError(f"create {branch} failed: {status} {ref}")
    else:
        raise RuntimeError(f"ref check {branch} failed: {status} {ref}")
    print(f"{branch}: {len(files)} files, commit {commit['sha']}")
    return commit["sha"]


def main() -> int:
    dry = "--dry-run" in sys.argv
    main_files = collect(PROJECT_DIR)
    pages_files = collect(PROJECT_DIR / "web" / "dist")
    print(f"main: {len(main_files)} files, gh-pages: {len(pages_files)} files")
    if dry:
        return 0
    # main branch: parent is the current head if it exists; a brand-new
    # repo rejects blob creation until seeded with one Contents-API commit
    status, ref = github_api._request(
        "GET", f"/repos/{OWNER}/{REPO}/git/refs/heads/main")
    if status == 200:
        parents = [ref["object"]["sha"]]
    else:
        seed = base64.b64encode(
            (PROJECT_DIR / "README.md").read_bytes()).decode()
        status, seeded = github_api._request(
            "PUT", f"/repos/{OWNER}/{REPO}/contents/README.md",
            {"message": "Initial commit", "content": seed, "branch": "main"})
        if status not in (200, 201):
            raise RuntimeError(f"seed README failed: {status} {seeded}")
        parents = [seeded["commit"]["sha"]]
        print("seeded empty repo with README.md")
    push_branch(
        "main", PROJECT_DIR,
        "RepoSitter: Cortensor Hackathon #5 entry, triage agent on OpenMinion 0.1.21 (approval-gate proof run-09)",
        parents)
    status, gh_ref = github_api._request(
        "GET", f"/repos/{OWNER}/{REPO}/git/refs/heads/gh-pages")
    gh_parents = [gh_ref["object"]["sha"]] if status == 200 else []
    push_branch(
        "gh-pages", PROJECT_DIR / "web" / "dist",
        "Dashboard build (web/dist)",
        gh_parents)
    status, pages = github_api._request(
        "GET", f"/repos/{OWNER}/{REPO}/pages")
    if status == 200:
        print("pages already enabled:", pages.get("html_url"), pages.get("status"))
    else:
        status, pages = github_api._request(
            "POST", f"/repos/{OWNER}/{REPO}/pages",
            {"source": {"branch": "gh-pages", "path": "/"}})
        if status not in (200, 201):
            raise RuntimeError(f"enable pages failed: {status} {pages}")
        print("pages enabled:", pages.get("html_url"), pages.get("status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
