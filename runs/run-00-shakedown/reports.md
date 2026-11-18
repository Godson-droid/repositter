# RepoSitter run: debug-scan

- Target: openminion/openminion
- Model: cohere/north-mini-code:free
- Started: 2026-11-15T11:57:07Z
- Fetched open items: 25
- Already triaged (skipped): []
- New items triaged: [759]

## #759 (issue) llm: add a provider cooldown registry and honour Retry-After instead of a constant retry backoff

- Category: feature
- Priority: high
- Summary: The issue proposes adding a provider cooldown registry and honoring the Retry-After header to improve rate limiting. Currently the retry mechanism uses a constant exponential backoff and ignores the Retry-After values sent by providers, leading to repeated attempts during rate limit windows. This feature will track per‑provider cooldown periods and respect provider‑specified retry delays.
- Suggested labels: feature, rate-limit, retry, provider, performance
- Suggested next action: Design and implement a provider cooldown registry that stores the time a provider hit a rate limit, and modify the retry loop to use the captured Retry-After value (or the registry) instead of the fixed backoff.

