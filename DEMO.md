# Demo runbook: RepoSitter in 1 to 5 minutes

Goal: one continuous screen recording that shows the problem, the agent
running on the OpenMinion SDK, memory working across runs, and the
approval gate holding a GitHub write. Target length about 3 minutes.

## Before recording

1. Terminal in `~/workspace/cortensor/repositter`, font large enough to
   read on video (16pt+), dark theme.
2. Make sure the one-time setup is done (README): venv with
   `openminion==0.1.21`, `.openminion/agents.json` generated, rubric
   skill admitted (`openminion skill list` shows `triage_rubric`
   verified).
3. Have these tabs open in a browser:
   - https://github.com/openminion/openminion/issues (the target repo)
   - https://github.com/Godson-droid/repositter-scratch/issues (the
     scratch repo used for the gate proof)
4. Check the free-tier headroom: the demo's live run costs roughly 25
   to 30 model requests. If the day's budget is short, record segments
   1, 2 and 4 against the committed artifacts in `runs/` and only the
   scratch segment live.
5. Kill any stale daemon so the recording starts clean:
   `pkill -f openminion.daemon` (ignore "no process" errors).

## Shot list

### 0:00 to 0:25 — The problem (talking head or terminal text)

Say: "Maintainers drown in untriaged issues. RepoSitter is a triage
agent on the OpenMinion SDK. It reads a repo's open issues and PRs,
skips the ones it already triaged in earlier runs, classifies the new
ones, and never writes to GitHub without a human saying yes."

Show the target repo's issues tab (25 open items) for a few seconds.

### 0:25 to 0:45 — The project shape

```bash
ls
sed -n 1,30p repositter.toml
```

Point out: target repo and the single pinned free model are config
values. Then:

```bash
OPENMINION_HOME=$PWD .venv/bin/openminion skill list
OPENMINION_HOME=$PWD .venv/bin/openminion doctor | head -8
```

Expected: skill `triage_rubric | triage-rubric | verified`; doctor
shows config, storage and provider OK. Say: "The triage rubric is an
OpenMinion skill. It had to be ingested and admitted before the agent
could load it; that story is in FINDINGS."

### 0:45 to 1:45 — Run 1 live

```bash
.venv/bin/python run.py --run-name demo-01 --max-items 2
```

While it runs, narrate the four stages as the console prints them:
scan (skill, fetch, memory search), classify (delegated subagent),
record (memory writes), propose (the write is prepared). When it
finishes:

```bash
cat runs/demo-01/reports.md
```

Expected: two typed reports with category, priority, summary,
suggested labels and next action. Then show the gate artifact:

```bash
cat runs/demo-01/approval_held.json
```

Say: "The agent wanted to apply this label. The policy engine paused
the run. Nothing was written to GitHub."

### 1:45 to 2:20 — Run 2: memory skips everything

```bash
.venv/bin/python scripts/scan_probe.py
```

Expected output: `already_triaged_numbers` now includes the items from
run 1 (and #759 from the shakedown run). Say: "Same repo, new session.
The only reason it skips these is persistent memory. That is the whole
point of a sitter: it remembers what it already looked at."

### 2:20 to 3:00 — The approval gate, executed on a scratch repo

```bash
.venv/bin/python run.py --target Godson-droid/repositter-scratch \
  --run-name demo-scratch --max-items 1 --approve-write
```

Narrate: "Same gate, but this time I approve. Watch the run pause,
resume on the same thread, and the write execute." Then cut to the
scratch repo's issues tab and refresh: the label is on the issue.
Back in the terminal:

```bash
cat runs/demo-scratch/approval_resumed.json
```

### 3:00 to 3:20 — Close

```bash
grep -c chat/completions runs/relay.log
```

Say: "Every model request is counted in the relay log, because on a
free tier the budget is real: one run costs far more requests than its
visible tool calls, thanks to runtime-internal helper calls. All of
that, plus fourteen findings with reproductions, is in FINDINGS.md."

## If a live run misbehaves on camera

- `EMPTY_PROVIDER_RESPONSE`: a stale relay or daemon is running.
  Kill python processes on port 8377 and any `openminion.daemon`,
  then rerun.
- Scan validation error in the summary: the salvage path usually
  recovers the JSON; the artifacts still land in `runs/<name>/`.
  Narrate it honestly; it is finding F5 in FINDINGS.md.
- Rate limited by OpenRouter: switch to the committed artifacts
  (`runs/run-00-shakedown/`, `runs/probe-scan/`) and record segments
  against those.
