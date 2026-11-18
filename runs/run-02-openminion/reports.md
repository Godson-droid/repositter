# RepoSitter run: run-02-openminion

- Target: openminion/openminion
- Model: cohere/north-mini-code:free
- Started: 2026-11-16T00:58:05Z
- Fetched open items: 25
- Already triaged (skipped): [770]
- New items triaged: [771]

## #771 (pull_request) fix(storage): treat literal empty storage.path like omitted path (Refs #766)

- Category: bug
- Priority: critical
- Summary: The PR fixes a bug where setting storage.path to an empty string in agents.json caused the database path to resolve incorrectly, leading to sqlite3.OperationalError. It treats empty strings like None while preserving whitespace filenames and existing path handling, and adds regression tests and config bootstrap. An Unreleased note is also added to document the fix.
- Suggested labels: bug, storage
- Suggested next action: Run CI for the storage module and merge once tests pass.

