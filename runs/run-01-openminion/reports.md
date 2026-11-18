# RepoSitter run: run-01-openminion

- Target: openminion/openminion
- Model: cohere/north-mini-code:free
- Started: 2026-11-16T00:54:05Z
- Fetched open items: 25
- Already triaged (skipped): [759]
- New items triaged: [770]

## #770 (issue) [0.1.22] Agent.run(timeout_seconds=...) cannot extend the 300 s brain turn budget, and the budget stop is returned as a normal reply

- Category: bug
- Priority: critical
- Summary: The Agent.run() timeout parameter is ignored - the turn stops at 300 seconds regardless of the timeout value passed, and returns a misleading stop message instead of raising a proper timeout error. This prevents users from extending the brain turn budget beyond the 300s default limit.

When using output_type=SomeModel, the issue surfaces as an invalid JSON AgentOutputValidationError instead of a clear timeout exception, masking the actual problem.
- Suggested labels: bug, timeout, rate-limit, performance
- Suggested next action: Investigate the root cause in runtime.brain_turn_timeout_seconds handling and ensure Agent.run respects the timeout_seconds parameter passed by users

