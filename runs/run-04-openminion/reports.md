# RepoSitter run: run-04-openminion

- Target: openminion/openminion
- Provider: gemini
- Model: gemini-3.6-flash
- Started: 2026-11-17T00:55:12Z
- Fetched open items: 25
- Already triaged (skipped): []
- New items triaged: [780, 779]

## #780 (issue) plugins: enabled external plugins never activate on the one-shot CLI run path (hooks silently skipped, no error)

- Category: bug
- Priority: high
- Summary: External plugins configured and enabled fail to activate during one-shot CLI execution, resulting in hooks being silently skipped. Direct calls to the plugin registry work as expected, but the `openminion run` CLI path bypasses plugin initialization. This prevents expected plugin hooks from executing without raising any warnings or errors.
- Suggested labels: bug, area:cli, area:plugins
- Suggested next action: Investigate CLI runner initialization logic to ensure plugin registry configuration is properly loaded and activated before processing commands.

## #779 (issue) self_improvement: max_applied_notes and min_token_overlap are accepted, persisted and never enforced

- Category: bug
- Priority: medium
- Summary: Two configuration settings in runtime.self_improvement (max_applied_notes and min_token_overlap) are parsed and persisted but never enforced by runtime consumers. Operators setting these values experience silent no-op behavior while a hardcoded context limit remains active. Enforcing these parameters in note ranking and context retrieval will resolve the inconsistency.
- Suggested labels: bug, area:config
- Suggested next action: Verify if a contributor PR is actively addressing this issue, and update context retrieval and ranking logic to enforce max_applied_notes and min_token_overlap.

