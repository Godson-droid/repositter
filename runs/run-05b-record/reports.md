# RepoSitter run: run-05b-record

- Target: openminion/openminion
- Provider: gemini
- Model: gemini-3.6-flash
- Started: 2026-11-17T04:49:52Z
- Fetched open items: None
- Already triaged (skipped): None
- New items triaged: [779]

## #779 (issue) self_improvement: max_applied_notes and min_token_overlap are accepted, persisted and never enforced

- Category: bug
- Priority: medium
- Summary: Two configuration settings in runtime.self_improvement (max_applied_notes and min_token_overlap) are parsed and persisted but never enforced by runtime consumers. Operators setting these values experience silent no-op behavior while a hardcoded context limit remains active. Enforcing these parameters in note ranking and context retrieval will resolve the inconsistency.
- Suggested labels: bug, area:config
- Suggested next action: Verify if a contributor PR is actively addressing this issue, and update context retrieval and ranking logic to enforce max_applied_notes and min_token_overlap.

