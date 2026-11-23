# RepoSitter

A GitHub issue and pull request triage agent built on the OpenMinion 0.1
Python SDK, written for Cortensor Hackathon #5.

RepoSitter watches a configured GitHub repository. On each run it fetches
the open issues and PRs, skips anything it has already triaged in an
earlier run (using the SDK's persistent memory), classifies each new item
through a delegated subagent, and saves a typed triage report: category,
priority, a short summary, suggested labels, and a suggested next action.
Any write back to GitHub (applying a label, posting a comment) is gated
behind the SDK's permissions flow and only executes after an explicit
human approval on the paused run thread.

## How a run works

1. **Scan** (agent run, typed `ScanReport` output). The agent loads the
   triage rubric skill with `skill.get`, calls the custom
   `fetch_open_items` tool for the target repo's open issues and PRs,
   then searches persistent memory for items triaged in earlier runs and
   reports which items are new and which are already done.
2. **Classify** (delegated subagent). Each new item goes to a bounded
   classifier subagent created with the SDK's `subagent()` API. The
   subagent carries the rubric in its instructions and returns a typed
   `TriageReport` (Pydantic-validated). Reports are saved as JSON
   artifacts plus a readable `reports.md`.
3. **Record** (agent run). An operations agent writes one memory record
   per report (`memory.write`, fact records keyed
   `triaged:<owner>/<repo>#<number>`), so the next run skips those items.
   Memory writes are set to auto-approve in the action policy; GitHub
   writes are not.
4. **Propose** (approval gate). The same operations agent is asked to
   apply the top report's first suggested label via the custom
   `propose_github_write` tool, which is declared `dangerous=True`. The
   policy engine pauses the run for confirmation. Without approval
   nothing is written; with `--approve-write` the run resumes on the
   same thread with "yes" and the label is applied and verified by an
   API read-back. In the example runs this stage only ever targets a
   scratch repo owned by the author, never a third-party repo.

Every run writes its artifacts to `runs/<run-name>/`: `summary.json`
(stage outcomes and the relay request count), `scan.json`,
`scan_result.json`, `reports/*.json`, `reports.md`,
`record_result.json`, and `approval_held.json` / `approval_resumed.json`
when the propose stage runs.

## Headline findings

1. One run costs far more model requests than its visible tool calls, about twelve requests for a four tool call scan stage.
2. A run can return success while doing nothing at all, so stages are judged by tool call counts and read backs, never by the absence of an error.
3. The Groq free tier token per minute limit is spent in seconds by the SDK helper call bursts; a token bucket pacer in the relay fixed it.
4. The memctl CLI could not run in the standard layout; filed as issue 805, maintainer confirmed, fix delivered as pull request 815.
5. Typed outputs are fragile with small free models; an orchestrator side salvage extracts the first balanced JSON object.
6. An ingested skill is invisible until admitted, and nothing in the product says so.

## Setup

Requirements: Python 3.11+, a Groq API key (the free tier is enough;
the agent uses one pinned model), and network access to
`api.github.com` and `api.groq.com`. Gemini and OpenRouter free
accounts are the earlier routes, kept wired in the relay (see step 1).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # openminion==0.1.21
```

1. **Configure OpenMinion.** The live config lives in
   `.openminion/agents.json` (gitignored; it contains absolute paths for
   your machine). Generate it and apply the values from
   `config/agents.example.json`:

   ```bash
   OPENMINION_HOME=$PWD .venv/bin/openminion config init --provider openrouter
   ```

   The primary route is Groq. OpenMinion ships a native `groq`
   adapter (an OpenAI-compatible provider), so the Groq route lives in
   the `providers.groq` block: `base_url http://127.0.0.1:8377/v1`
   (the loopback relay below), `model openai/gpt-oss-120b`,
   `tool_call_strategy native`, generous turn timeouts, the agent
   profile's provider set to `groq`, and an action-policy rule that
   auto-approves `memory.write` while everything else keeps the
   default `require_confirm`. The earlier routes stay wired in the
   relay: Gemini lives in the `providers.openai` block (its setup
   preset runs on the OpenAI adapter, with `provider_identity` pinned
   to the Gemini translation; profile provider `openai`, run with
   `--provider gemini`), and the OpenRouter fallback keeps the
   `providers.openrouter` block (`model cohere/north-mini-code:free`;
   profile provider `openrouter`, run with `--provider openrouter`).

2. **Give the relay a credential.** OpenMinion never sees a real API
   key. `repositter/relay.py` listens on 127.0.0.1:8377, forwards each
   request to the active provider's endpoint
   (`https://api.groq.com/openai/v1/...` for Groq,
   `https://generativelanguage.googleapis.com/v1beta/openai/...` for
   Gemini, `https://openrouter.ai/api/v1/...` for OpenRouter), and
   attaches the matching key held in the author's Muse connection
   store through the dynamic-credential surrogate mechanism (the relay
   process only ever holds the surrogate). The relay also sends a
   browser user agent: Groq's Cloudflare front door refuses the
   default Python client signature with HTTP 403 (`error code: 1010`),
   which is a signature refusal, not a bad key (FINDINGS.md F17). To
   run RepoSitter with your own key instead, point `base_url` at the
   provider's endpoint and set `api_key_env`/`api_key` in the config
   the normal OpenMinion way; the relay is only needed for the
   credential-store setup. Either way, exactly one model is pinned per
   route and no paid fallback exists.

3. **Admit the rubric skill.** Skills are not usable straight after
   ingestion; the version must be admitted (see FINDINGS.md for the full
   story):

   ```bash
   OPENMINION_HOME=$PWD .venv/bin/openminion skill ingest \
     --file skills/triage-rubric/SKILL.md --name triage-rubric \
     --scope global --trust trusted_local
   OPENMINION_HOME=$PWD .venv/bin/openminion skill admit \
     --skill-id triage_rubric --version-hash <hash from ingest> \
     --expected-active-version-hash none --target-status verified \
     --verification-check manual-content-review \
     --verification-result passed \
     --verification-evidence-ref skills/triage-rubric/SKILL.md \
     --reason "operator reviewed the rubric"
   ```

4. **Pick a target.** Edit `repositter.toml` (`[target] owner/repo`), or
   pass `--target` per run. Public repos need no GitHub credential for
   reads; if `GITHUB_TOKEN` is set it is used, otherwise reads are
   unauthenticated (60 requests/hour per IP).

## Running

```bash
.venv/bin/python run.py --run-name run-01 --max-items 3
```

Options: `--target owner/repo`, `--max-items N`, `--model <id>`,
`--no-propose` (skip the approval-gate stage), `--no-skill`,
`--approve-write` (approve the held GitHub write so it executes; only
ever use this against a repo you own).

Useful diagnostics:

```bash
.venv/bin/python scripts/scan_probe.py     # scan stage only: what is new vs already triaged
OPENMINION_HOME=$PWD .venv/bin/openminion doctor   # config/storage/provider health
.venv/bin/python scripts/setup_scratch.py  # create + seed the author's scratch repo for gate tests
```

## Example runs (in `runs/`)

- `run-00-shakedown/` — the development shakedown run (executed under
  the name `debug-scan` before the run naming settled). One real item
  from `openminion/openminion` (#759) classified end to end and recorded
  in memory.
- `probe-scan/` — a scan-only probe run against the fixed relay. It
  fetched 25 open items and correctly reported #759 as already triaged
  from the shakedown run's memory record, proving cross-run memory
  before the full example runs were made.
- `run-01-failed-chunked-relay/` — a failed run kept on purpose: every
  provider call returned HTTP 200, yet the agent died with
  `EMPTY_PROVIDER_RESPONSE`. Root cause and fix are in FINDINGS.md.
- Full example runs (fresh triage, a second run that skips everything,
  and the approval-gate proof) are added under `runs/` as they are made;
  see FINDINGS.md for the current status of each. Day 1 runs, made
  2026-11-16 after the 00:00 UTC reset: `run-01-openminion/` (issue
  #770 triaged and recorded; the proposed `bug` label held at the
  approval gate, `approval_held.json`) and `run-02-openminion/` (PR
  #771 triaged and recorded on retry; #769 and #768 classification
  failed; propose stage hit the free-tier daily cap, so no approval
  artifact there). Day 2 runs, made 2026-11-17 on the Gemini route
  (`gemini-3.6-flash`, probe passed after the credential was
  reconnected): `run-04-openminion/` classified issues #780 and #779
  cleanly on the stronger model with no prose instead of JSON failure,
  but its scan and record stages both failed on Gemini rate limiting
  (46 of 60 relay requests answered HTTP 429) and the proposed `bug`
  label for #780 held at the approval gate; `run-03-scratch/` then
  failed in its scan stage on the same rate limit (13 of 14 requests
  answered 429) and never reached the approval proof, so the scratch
  label and its read back are still to come. A finish pass later on
  2026-11-17 (Gemini probe passing cleanly at its start) completed the
  memory records: `run-05-record/` tried to record both reports and
  wrote nothing (the ops agent returned a refusal with zero tool calls
  while reporting success; FINDINGS.md F16), and `run-05b-record/` then
  recorded issue #779 with its origin noted in the record content and
  verified it by search read back; issue #780's record turned out to
  have been written by run 04's record stage before that stage failed,
  and was likewise verified by search. That pass then stopped on the
  rate limit (29 of run 05b's 35 relay requests answered 429), so the
  classification retries for #769 and #768 and the scratch approval
  proof are still to come. A further pass on 2026-11-17 switched the
  primary route to Groq (`openai/gpt-oss-120b`, free tier; the
  connector helper's JSON probe passed before the pass). The pipeline
  probe through the real configuration first hit Cloudflare's 1010
  signature refusal because the relay sent no browser user agent
  (fixed in the relay), then received real completions from Groq but
  hit the free tier's tokens-per-minute limit 13 requests in and
  stopped per the pass's stop rule, so the #769 retry and the scratch
  approval proof were not attempted on Groq either. Issue #768 has
  since been closed upstream, so its retry is moot. A throttling pass
  the same day added the relay token-bucket pacer (FINDINGS.md F18):
  the probe then ran 14 requests with zero HTTP 429, but still did
  not complete a classification (the model never made its forced tool
  call, and the classifier reply carried the F5 prose prefix). A
  finish pass later that day ran the leftovers through the classify
  path's F5 salvage: `run-06-openminion/` classified issue #769
  (bug/high, labels `bug, area:tools, platform:windows,
  priority:high`, the first three matching the maintainer's own
  labels) and its memory record reads back verbatim from the store;
  whether the salvage fired is undetermined, because a runtime
  restart killed the driver before its logs were written. The scratch
  proof in that pass then stopped on Groq's daily token budget
  (200,000 tokens for `gpt-oss-120b`; F19). The proof landed on
  2026-11-18 after the 00:00 UTC reset: `run-09-scratch/` (32 relay
  requests, zero HTTP 429) classified scratch issue #3 (docs/low),
  held the proposed `documentation` label at the approval gate,
  applied it on resume with `--approve-write`, and the label was read
  back from the GitHub API on the issue (`documentation`, updated
  2026-11-18T00:29:17Z). The record stage in run 09 hit the F16
  refusal again (0 tool calls, no memory record for #3; FINDINGS.md
  F20), so a future scratch scan will see #3 as new. Published
  2026-11-18: the project repo is
  https://github.com/Godson-droid/repositter and the dashboard is
  https://godson-droid.github.io/repositter/ (both verified by public
  read back; see FINDINGS.md).

## Building blocks exercised

Agent execution with typed outputs, a real hosted model (Groq free
tier as the primary route since 2026-11-17, Gemini free tier before
that, OpenRouter free tier before that and kept as the fallback),
custom `@tool` functions, the built-in skill tools with an
ingested and admitted skill, persistent memory (`memory.search` /
`memory.write`), bounded subagent delegation for classification,
sessions (fresh session per run; memory, not session context, carries
state between runs), the permissions/policy engine (auto-approved
memory writes, confirmation-gated dangerous GitHub writes, thread
resume), and diagnostics (`openminion doctor`, run IDs, telemetry).
Details and evidence are in FINDINGS.md.

## Honest limitations

- The free model sometimes wraps its JSON in prose; the orchestrator
  salvages the first balanced JSON object and re-stamps the identity
  fields (number, kind, title) from the fetch, which it owns. Salvaged
  reports are marked in the run's classify log.
- The classifier occasionally suggests labels outside the rubric
  vocabulary (run 0 suggested `rate-limit`, `retry`, `provider`). The
  reports are artifacts for a human maintainer, not auto-applied.
- One agent run costs far more model requests than its visible tool
  calls (runtime-internal helper calls). On OpenRouter's
  50-requests/day free tier that made RepoSitter a batch tool you run
  a few times a day, not a daemon, which is why the primary route
  moved off OpenRouter, first to Gemini and then to Groq; each free
  tier limits differently (daily count, per-key rate, tokens per
  minute), and the SDK's burst pattern is what has to fit
  (FINDINGS.md F8, F15 and F17).
  The relay logs every request so the budget is auditable either way.

## Files

- `run.py` — entrypoint and CLI.
- `repositter/triage.py` — the four-stage orchestrator.
- `repositter/tools.py` — custom tools (`fetch_open_items`,
  `propose_github_write`).
- `repositter/github_api.py` — small GitHub REST client.
- `repositter/relay.py` — loopback provider relay (credential seam;
  Groq primary; Gemini and OpenRouter also wired).
- `repositter/schemas.py` — `TriageReport` / `ScanReport` models.
- `skills/triage-rubric/SKILL.md` — the triage rubric skill.
- `FINDINGS.md` — building blocks tested and every friction point or
  bug found, with reproductions. `DEMO.md` — the demo recording
  runbook.
