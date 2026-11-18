"""Custom OpenMinion tools for RepoSitter.

`fetch_open_items` is read-only. `propose_github_write` is declared
dangerous, which puts it behind the runtime action policy: with the
project policy (default require_confirm) the run pauses for a human
decision before this function is ever invoked.
"""

from __future__ import annotations

import json

from openminion import tool

from . import github_api

_STATE: dict = {"owner": "", "repo": "", "items": []}


def configure(owner: str, repo: str) -> None:
    _STATE["owner"] = owner
    _STATE["repo"] = repo


def last_fetch() -> list[dict]:
    """Items from the most recent fetch, with full body excerpts."""
    return list(_STATE["items"])


@tool(min_scope="READ_ONLY", idempotent=True)
def fetch_open_items(limit: int = 25) -> str:
    """Fetch the open issues and pull requests of the configured GitHub repo.

    Returns a compact JSON list with number, kind (issue or pull_request),
    title, current labels, author, creation date and comment count for each
    open item, newest first.
    """
    items = github_api.list_open_items(_STATE["owner"], _STATE["repo"], limit=limit)
    _STATE["items"] = items
    compact = [
        {
            "number": it["number"],
            "kind": it["kind"],
            "title": it["title"][:100],
            "labels": it["labels"],
            "author": it["author"],
            "created_at": it["created_at"],
            "comments": it["comments"],
        }
        for it in items
    ]
    return json.dumps({"repo": f"{_STATE['owner']}/{_STATE['repo']}", "count": len(compact), "items": compact})


@tool(dangerous=True)
def propose_github_write(item_number: int, action: str, label: str = "", comment: str = "") -> str:
    """Apply one write to the configured GitHub repo. DANGEROUS: human approval required.

    action "add_label" applies `label` to the issue or PR `item_number`.
    action "post_comment" posts `comment` on the issue or PR `item_number`.
    Only call this when a human is expected to approve the exact write.
    """
    owner, repo = _STATE["owner"], _STATE["repo"]
    if action == "add_label":
        if not label:
            return "error: add_label needs a label"
        github_api.add_labels(owner, repo, item_number, [label])
        return f"applied label '{label}' to {owner}/{repo}#{item_number}"
    if action == "post_comment":
        if not comment:
            return "error: post_comment needs a comment"
        created = github_api.add_comment(owner, repo, item_number, comment)
        return f"posted comment on {owner}/{repo}#{item_number}: {created.get('html_url', '')}"
    return f"error: unknown action {action!r}"
