"""Typed outputs for RepoSitter, validated by the OpenMinion runtime."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TriageReport(BaseModel):
    """One classified issue or pull request."""

    item_number: int = Field(description="The GitHub issue or PR number")
    item_kind: Literal["issue", "pull_request"]
    title: str
    category: Literal["bug", "feature", "question", "docs", "other"] = Field(
        description="bug = broken behaviour, feature = new capability request, "
        "question = asking how something works, docs = documentation problem, "
        "other = anything else"
    )
    priority: Literal["critical", "high", "medium", "low"]
    summary: str = Field(description="Two or three sentences: what it is, why it matters, any blocker")
    suggested_labels: list[str] = Field(
        description="Labels from the rubric vocabulary only: bug, enhancement, "
        "question, documentation, needs info, good first issue, help wanted, "
        "duplicate, wontfix"
    )
    suggested_next_action: str = Field(description="One concrete next step for a maintainer")


class ScanReport(BaseModel):
    """Result of comparing freshly fetched items against agent memory."""

    fetched_count: int = Field(description="How many open items the fetch returned")
    new_item_numbers: list[int] = Field(description="Fetched items with no triage record in memory")
    already_triaged_numbers: list[int] = Field(
        description="Fetched items that already have a triage record in memory"
    )
    notes: str = Field(description="One or two sentences on what the scan found")
