# RepoSitter run: run-06-openminion

- Target: openminion/openminion
- Provider: groq
- Model: openai/gpt-oss-120b
- Started: 2026-11-17T11:29:06Z
- Fetched open items: 100
- Already triaged (skipped): []
- New items triaged: [769]

## #769 (issue) [0.1.22] Runtime bootstrap fails on Windows (WinError 206) because browser-playwright artifact dirs are created under the CWD even when no browser tool is used

- Category: bug
- Priority: high
- Summary: The runtime bootstrap fails on Windows when the current working directory path exceeds the MAX_PATH limit, because Playwright artifact directories are placed under the workspace root instead of the short OPENMINION_HOME path. This occurs even when no browser tools are enabled, causing the agent setup to abort with a WinError 206. The issue blocks Windows users from running openminion in deep project directories.
- Suggested labels: bug, area:tools, platform:windows, priority:high
- Suggested next action: Assign to the tools maintainer to adjust the Playwright artifact root handling to respect OPENMINION_HOME or allow explicit configuration, and add a test for long path scenarios on Windows.

