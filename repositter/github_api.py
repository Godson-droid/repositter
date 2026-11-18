"""Minimal GitHub REST client for RepoSitter.

Reads are public data. Authentication, when available, comes from the
registered custom.github connection through the Muse dynamic-credential
surrogate, so the token never appears in this process as a readable value.
Fallbacks, in order: GITHUB_TOKEN from the environment (for users running
outside Muse), then unauthenticated requests (public data only, low
rate limits). Writes go through the same path and are only ever invoked by
the approval-gated tool or by the scratch-repo setup script.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
try:  # the surrogate mechanism exists inside Muse; outside it, fall back
    from dynamic_credentials import add_surrogate_to_request
except Exception:  # pragma: no cover
    add_surrogate_to_request = None  # type: ignore[assignment]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object) -> None:
        raise RuntimeError("redirect refused, verify the endpoint")


_OPENER = urllib.request.build_opener(_NoRedirect())


def _request(method: str, path: str, body: dict | None = None, auth: bool = True) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "repositter")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if auth and add_surrogate_to_request is not None:
        try:
            add_surrogate_to_request(request, "custom.github", allowed_hosts=["api.github.com"])
        except Exception:
            token = os.environ.get("GITHUB_TOKEN", "")
            if token:
                request.add_header("Authorization", f"Bearer {token}")
    elif auth:
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
    try:
        with _OPENER.open(request, timeout=60) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload: object = json.loads(raw) if raw else None
        except Exception:
            payload = {"raw": raw[:400].decode("utf-8", "replace")}
        return exc.code, payload


def get_repo(owner: str, repo: str) -> dict:
    status, payload = _request("GET", f"/repos/{owner}/{repo}")
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"get_repo {owner}/{repo} failed: {status} {payload}")
    return payload


def list_open_items(owner: str, repo: str, limit: int = 25) -> list[dict]:
    """Open issues and PRs, newest first, normalized for triage."""
    status, payload = _request(
        "GET", f"/repos/{owner}/{repo}/issues?state=open&per_page=100&sort=created&direction=desc"
    )
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(f"list_open_items {owner}/{repo} failed: {status} {payload}")
    items: list[dict] = []
    for raw in payload[:limit]:
        body = (raw.get("body") or "").strip()
        items.append(
            {
                "number": raw["number"],
                "kind": "pull_request" if "pull_request" in raw else "issue",
                "title": raw["title"],
                "body_excerpt": body[:1200],
                "labels": [label["name"] for label in raw.get("labels", [])],
                "author": (raw.get("user") or {}).get("login", ""),
                "created_at": raw.get("created_at", ""),
                "comments": raw.get("comments", 0),
                "url": raw.get("html_url", ""),
            }
        )
    return items


# --- writes (approval-gated tool and scratch setup only) ---


def create_issue(owner: str, repo: str, title: str, body: str) -> dict:
    status, payload = _request("POST", f"/repos/{owner}/{repo}/issues", {"title": title, "body": body})
    if status not in (200, 201) or not isinstance(payload, dict):
        raise RuntimeError(f"create_issue failed: {status} {payload}")
    return payload


def create_label(owner: str, repo: str, name: str, color: str = "ededed") -> int:
    status, _ = _request("POST", f"/repos/{owner}/{repo}/labels", {"name": name, "color": color})
    return status  # 201 created, 422 already exists


def add_labels(owner: str, repo: str, number: int, labels: list[str]) -> dict:
    status, payload = _request("POST", f"/repos/{owner}/{repo}/issues/{number}/labels", {"labels": labels})
    if status not in (200, 201):
        raise RuntimeError(f"add_labels failed: {status} {payload}")
    return payload  # type: ignore[return-value]


def add_comment(owner: str, repo: str, number: int, body: str) -> dict:
    status, payload = _request("POST", f"/repos/{owner}/{repo}/issues/{number}/comments", {"body": body})
    if status not in (200, 201) or not isinstance(payload, dict):
        raise RuntimeError(f"add_comment failed: {status} {payload}")
    return payload


def get_issue(owner: str, repo: str, number: int) -> dict:
    status, payload = _request("GET", f"/repos/{owner}/{repo}/issues/{number}")
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"get_issue failed: {status} {payload}")
    return payload
