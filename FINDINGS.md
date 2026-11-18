# Findings: building blocks tested, friction, and bugs

Project: RepoSitter (GitHub issue/PR triage agent), Cortensor Hackathon #5.
SDK: `openminion` 0.1.21 from PyPI (Python 3.12.3). Model for all live
runs through 2026-11-16: `cohere/north-mini-code:free` via OpenRouter's
free tier, reached through a loopback relay (see the README for why).
On 2026-11-16 the primary route was switched to Google Gemini
(`gemini-3.6-flash`, free tier) through the same relay, with OpenRouter
kept as the fallback route (F15). On 2026-11-17 the primary route was
switched again, to Groq (`openai/gpt-oss-120b`, free tier) through the
same relay (F17). Dates: 2026-11-15
(build and shakedown runs). Every claim below was reproduced or observed
first-hand during this project; request counts come from the relay log
(`runs/relay.log`), which records every forwarded model request.

## Building blocks tested

| Block | How RepoSitter uses it | Result | Evidence |
| --- | --- | --- | --- |
| Agent execution | `Agent` facade with instructions, tools, `forced_tools`, typed `output_type`, per-run sessions | Works. Runs return run IDs, state, stats and metadata. | `runs/run-00-shakedown/scan_result.json`, `record_result.json` |
| Real model | OpenRouter free model `cohere/north-mini-code:free` through a loopback relay that attaches the credential | Works. Native tool calls are reliable; 1.4 to 5.6 s per request. | `runs/relay.log` (all HTTP 200) |
| Custom tools | `@tool` functions `fetch_open_items` (READ_ONLY, idempotent) and `propose_github_write` (dangerous) | Works. Risk class is derived from the decorator flags as documented. | `repositter/tools.py` |
| Built-in tools | `skill.get`, `memory.search`, `memory.write` | Work, with the lifecycle and policy caveats in F2 and F6. | Run artifacts below |
| Skills | Ingested `skills/triage-rubric/SKILL.md`, admitted it, loaded it in the scan stage with `skill.get` | Works only after the full ingest, verify, admit path (F2). The rubric also travels in the classifier's instructions so classification is consistent. | Skill listed as `verified`, active version `5684b201...` |
| Memory | `memory.write` fact records per triaged item; `memory.search` in the next run's scan | Works across runs and processes. A later scan correctly reported item #759 as already triaged from an earlier run's record. | `runs/probe-scan/scan.json` (`already_triaged_numbers: [759]`) |
| Delegation | Bounded classifier created with `subagent(parent, ...)`, typed `TriageReport` output | Works. Chosen over a `Handoff` because the orchestrator needs the typed report object itself, not a relayed summary. The task-family scheduler tools (`task.*`) did not fit this workflow and were not used; that is stated plainly rather than forced. | `runs/run-00-shakedown/reports/issue-759.json` |
| Sessions | Fresh session id per run (`repositter-<owner>-<repo>-<run>`); cross-run state lives in memory, not session context | Works as intended; run 2 style scans see only memory, not the earlier conversation. | `scripts/scan_probe.py` uses its own session and still sees run 0's memory |
| Permissions / policy | Action policy: `memory.write` auto-approved by rule; `propose_github_write` (dangerous) keeps `default_action: require_confirm` and pauses the run for approval | Policy derivation from tool specs works exactly as the source describes. The held-approval and resume artifacts are produced by the propose stage (see "Pending" below). | `.openminion/agents.json` action_policy; `repositter/triage.py` stage 4 |
| Diagnostics | `openminion doctor`, run IDs, telemetry DB, `result.stats`, relay request log | Doctor is genuinely useful (config, storage, provider checks). Telemetry omits message content by design, which limits debugging of provider-response issues (F4). | `runs/diagnostics/doctor.txt` |
| Echo provider | All development and debugging before any live call | Works and saved the free-tier budget; recommended pattern for SDK development. | Phase tooling |

## Findings

### F1. Bracketed IPv6 entries in NO_PROXY break every provider call with a misleading error

- Repro: in this sandbox the environment ships
  `NO_PROXY=localhost,127.0.0.1,[::1],[fd8b:...]`. Start any agent run
  against a real provider.
- Expected: the provider call goes through the proxy, or bypasses it for
  loopback only.
- Actual: every call fails with `Invalid port: ':1]'` from httpx, which
  points at a port parsing problem in the user's own config, not at the
  environment variable. Removing the bracketed entries (or setting
  `NO_PROXY=localhost,127.0.0.1`) fixes it. Curl is unaffected, which
  makes the failure look SDK-specific when it is not.
- Note: environment-specific, but the error message sends you to the
  wrong layer. A clearer httpx/SDK error would save real debugging time.

### F2. Skill lifecycle: an ingested skill is invisible until admitted, and the errors do not say so

Reproduced end to end with `openminion skill` CLI against a project home:

1. `skill ingest --file SKILL.md --name triage-rubric --scope project
   --trust trusted_local` returns ok with a skill id and version hash,
   plus the warning `admission.pending`.
2. `skill list` then prints "No skills found". `skill show`,
   `skill validate` and `skill debug` for the same id all return
   `NOT_FOUND` ("Skill not found"), the same error as for a skill that
   does not exist at all.
3. The reason is only visible in the source
   (`tools/skill/plugin.py::_model_visible_package`): a skill is
   model-visible only when its scope is `global` (or agent-owned) AND
   the requested version is the admitted active version. Project scope
   is stored "as a label only" per the CLI's own JSON output, which the
   ingest success message does not surface as a warning.
4. Re-ingesting the same file with `--scope global` fails with
   `SKILL_SCOPE_OWNER_CONFLICT` until the first skill is removed.
5. `skill admit` with the ingest hash then fails
   `SKILL_ADMISSION_VALIDATION_FAILED` with blocker
   `status.requires_verification`; it only succeeds once
   `--verification-check`, `--verification-result passed` and
   `--verification-evidence-ref` are supplied, plus
   `--expected-active-version-hash none` for a first admission.
6. The version hash changes when only the scope changes
   (`d39f44de...` for project scope, `5684b201...` for global), so the
   hash printed by a failed first ingest cannot be reused.

- Expected: ingest output (or `skill list`) would show the skill as
  pending admission, and NOT_FOUND errors would distinguish "missing"
  from "exists but not admitted / not visible in this scope".
- Actual: a successfully ingested skill is indistinguishable from a
  missing one until you read the plugin source. The full path
  (ingest as global, remove on conflict, admit with verification
  evidence) does work, and is documented in the README.
- Minor: ingest also emits six `parse.warning:h2_flattened_into_parent`
  warnings for a plain `##`-sectioned SKILL.md; harmless, but it reads
  like the file format is wrong when it is not.

### F3. Chunked-streaming responses through a proxy relay make the provider layer report EMPTY_PROVIDER_RESPONSE

- Repro: point the OpenAI-compatible provider at a loopback relay that
  forwards the upstream response as HTTP chunked transfer encoding
  (headers, then body chunks, then the terminal chunk). Run any agent.
- Expected: the run proceeds; the upstream responses are valid
  OpenAI-shaped JSON with native tool calls (verified by replaying the
  same request shape non-streaming, which returns a correct
  `tool_calls` payload).
- Actual: every agent run fails with
  `ProviderError: EMPTY_PROVIDER_RESPONSE: Provider returned no usable
  entry response after configured retries`, even though the relay log
  shows HTTP 200 for every request (5 attempts, then the run aborts).
  The identical pipeline through a relay that buffers each response and
  returns it with a `Content-Length` succeeds immediately.
- Evidence: `runs/run-01-failed-chunked-relay/` (summary and scan
  error), `runs/relay.log`.
- Honest limit: we did not isolate which exact framing interaction
  (chunk boundaries, flush timing, header set) the adapter's streaming
  parser trips on; telemetry omits response content by design, which
  made this harder to pin down than it should be (see F4). The
  workaround is in production in `repositter/relay.py`.

### F4. Telemetry omits the content needed to debug provider-response failures

- `llm.response` telemetry events carry `usage: {}` and
  `_telemetry_policy: {"sensitive_content": "omitted"}`. For F3 there
  was no way to see what the adapter received or why normalization
  judged it empty; diagnosis required building a separate capture
  relay outside the SDK.
- Expected: a debug mode that records at least the response shape
  (finish reason, presence of tool calls, byte counts) without bodies.
- Actual: only the final error string survives.

### F5. Typed outputs are fragile with small free models; the runtime's JSON recovery is narrower than it looks

- The classifier subagent returned `openminion: {\n"category": ...}`
  (a prose prefix before the JSON object). `Agent.run` raised
  `AgentOutputValidationError`, even though the facade's `_coerce_output`
  contains a balanced-brace JSON extraction fallback; the model's JSON
  was also missing fields the prompt had not enumerated explicitly.
- Mitigations that worked: enumerate every required field in the
  instructions with types, demand "ONLY one JSON object", and add an
  orchestrator-side salvage that extracts the first balanced JSON
  object from `error.raw_text`, re-stamps identity fields (number,
  kind, title) from the fetch (facts the orchestrator owns), and
  validates again. Salvages are flagged in the run's classify log.
- Cost note: validation failures are retried inside the run before the
  exception surfaces, so a malformed-output problem silently burns
  several billable (or quota-counted) requests. Our first probe pair
  cost 14 requests for two tiny runs.

### F6. memory.write requires confirmation by default; the fix is declarative but undiscoverable from the tool docs

- `memory.write` is WRITE_SAFE with `idempotent=False`, so the policy
  engine classifies it as a write with unknown reversibility and the
  default action policy (`require_confirm`) pauses the run for a human
  OK. An autonomous agent that must ask permission to remember anything
  cannot complete a batch run.
- Fix: an action-policy rule
  `{"match": {"tool_name": "memory.write"}, "mode": "auto"}` in
  `agents.json`. This works cleanly and is the right design (policy is
  data, not code), but nothing in the tool's own help suggests it; we
  found the rule format by reading
  `base/config/parser/action.py` and the policy module source.

### F7. memory.write rewrites the record key without saying so

- Instructed key: `triaged:openminion/openminion#759`. Stored key:
  `fact:triaged_openminion_openminion_759` (type prefix added, `:` and
  `/` and `#` slugified away).
- Consequence: any matching logic keyed on the exact requested key
  format breaks. RepoSitter's scan therefore matches on record content
  (which we now make name the full `owner/repo` explicitly) rather than
  on the key. Worth documenting on the tool: key normalization is
  reasonable, silent normalization is a trap.

### F8. One agent run costs far more model requests than its visible tool calls

Measured with the relay log and a one-off capture of request bodies:

- A scan stage (4 tool calls: skill.get, fetch, memory.search, plus
  the final answer) costs about 12 model requests.
- A full 1-item run (scan, classify, record) cost 22 requests.
- The extra calls are runtime-internal helpers, identified from their
  system prompts: a skill-selection helper (1 per run), a
  freshness-routing classifier (1 per run), a clarify helper, repeated
  batch guards, and, under the default `tool_call_strategy: "hybrid"`,
  a separate "tool-calling contract" call per tool invocation (9 in
  one run). Switching the provider to `tool_call_strategy: "native"`
  removes the contract calls; the per-run helpers remain.
- Impact: on OpenRouter's free tier (50 requests/day, failed requests
  count) the SDK's real cost per workflow is roughly 3 to 5 times the
  naive estimate. Anyone budgeting a free-tier agent needs the relay
  style request log; the provider's own usage counter is eventually
  consistent and lagged our relay count by several requests at times.
- Suggestion: expose a per-run request budget and a breakdown of
  internal versus agent-visible calls in `result.stats`.

### F9. memctl, the documented memory operator surface, fails out of the box

- `memctl forget --memory <id>` and `memctl search <q>` both abort
  with `FileNotFoundError: config file not found:
  <home>/memory.yaml`. The runtime itself never creates a `memory.yaml`
  (the agent writes memory happily without one), so the operator CLI
  is unusable in exactly the layout the runtime produces.
- Expected: memctl would fall back to the same defaults the runtime
  uses, or the runtime would write the config it expects.
- Workaround used: none needed for the workflow (records are managed
  through the agent), but deleting a single record through a supported
  path was not possible during development.

### F10. Default timeouts are hostile to slow models

- Defaults found in scoping: 90 s chat turn cap
  (`chat_turn_timeout_seconds`) and a 60 s per-request preset for
  Ollama. Free-tier hosted models regularly exceed these under load.
  RepoSitter raises the turn caps to 600/900 s and the provider timeout
  to 300 s in config. First-time users will hit this as unexplained
  `TurnTimeoutError`s.

### F11. Config is anchored to the working directory and stores absolute paths

- `openminion setup`/`config init` write `.openminion/agents.json`
  under the current directory's home, and the generated config embeds
  an absolute storage path. Moving a project means regenerating config;
  checking the generated file into a repo leaks machine paths. This
  repo therefore gitignores `.openminion/` and ships
  `config/agents.example.json` with only the values that matter.
- Related: a long-lived `openminion.daemon` process holds state across
  invocations; after changing config or environment, stale daemons can
  keep serving the old setup. We had to kill one during development.

### F12. The classifier drifts outside the rubric's label vocabulary

- Run 0's report for issue #759 suggested labels `feature, rate-limit,
  retry, provider, performance`. The rubric's vocabulary is `bug,
  enhancement, question, documentation, needs info, good first issue,
  help wanted, duplicate, wontfix`; the correct head label was
  `enhancement`. Category and priority were right, and the summary was
  accurate.
- This is a model-quality observation, not an SDK defect. It is why
  RepoSitter treats reports as drafts for a human and never auto
  applies labels outside the approval gate. A schema-level enum on
  `suggested_labels` would catch it, at the cost of more validation
  retries (F5); we chose to log the drift instead.

### F13. A repeated-tool-batch guard can interrupt legitimate multi-record writes

- During the record stage the runtime injected "You have repeated an
  identical successful tool batch. Do not..." when the model re-issued
  a `memory.write`. Writing several similar records in one stage is
  the normal shape of this workflow; the guard's threshold is worth
  knowing about before designing batch writes. The stage still
  completed and the record landed (record id returned and later found
  by search).

### F14. Smaller observations

- Docs pin openminion 0.1.20; PyPI serves 0.1.21. We pinned and tested
  0.1.21 and say so in `requirements.txt`.
- The built-in `github.*` tools require a `GITHUB_TOKEN` environment
  variable. RepoSitter instead uses its own read tools plus a
  credential surrogate for writes, so no token sits in the agent's
  environment; worth copying for other builders.
- Unauthenticated GitHub reads share the egress IP's 60 requests/hour
  budget (we observed 20 remaining at one point). Not an SDK issue; a
  deployment reality for agent sandboxes.
- The Cortensor hackathon documentation still describes a dedicated
  submissions repository "to be added before kickoff" and a TBD
  deadline; in practice entrants publish their own repo and submit a
  DoraHacks Buidl. The event page's own text is the stale part.

### F15. Provider economics forced a switch from OpenRouter to Gemini; the relay and config now carry both routes

- Why: F8 measured one SDK run at 3 to 5 times its visible tool calls,
  and OpenRouter's free tier allows 50 requests a day with failed
  requests counting. On day 1 that cap ended run 02 mid-flight
  (`RATE_LIMITED` in the propose stage), and 3 of 5 classifications
  failed on the F5 prose-instead-of-JSON error from the small free
  model `cohere/north-mini-code:free`. The binding constraints were
  the daily cap and typed-output reliability, not the SDK.
- Switch (2026-11-16, operator approved): the primary route is now
  Google's Gemini API free tier through its OpenAI-compatible
  endpoint (`https://generativelanguage.googleapis.com/v1beta/openai`),
  model `gemini-3.6-flash`, the model the SDK's own setup catalog
  recommends for its `gemini` preset. Gemini's free tier allows
  orders of magnitude more requests per day than 50, and a frontier
  class model is expected to end the prose-JSON failure mode. That
  expectation is stated as a hypothesis until a live run proves it
  (see the status below).
- SDK shape worth knowing: there is no `gemini` runtime adapter and
  `config init --provider` does not accept `gemini`. The preset's
  runtime adapter is `openai`, so the Gemini route lives in the
  `providers.openai` block with `provider_identity` pinned to the
  gemini translation (`service_vendor: gemini`, `model_family:
  gemini`); without the pin, a loopback `base_url` makes the identity
  resolver report vendor `unknown`. The agent profile's provider is
  therefore `openai` on the Gemini route and `openrouter` on the
  fallback route.
- What changed: `repositter/relay.py` is provider-parameterised
  (`PROVIDERS` map: upstream base, connector credential name, allowed
  hosts) and keeps the F3 buffered-response behaviour and the
  no-bodies logging discipline for both routes; the relay log now
  records the provider per request. `repositter.toml` carries
  `[model] provider` and the pinned model; `run.py` gained
  `--provider`. OpenRouter remains fully wired as the fallback
  (provider block untouched in `.openminion/agents.json`, one flag
  plus one profile value to return to it).
- Smoke evidence (2026-11-16): a minimal SDK run (no RepoSitter
  tools, trivial prompt) against the Gemini config forwarded 15
  requests through the relay to Google, all correctly addressed
  (`POST /v1/chat/completions`, model `gemini-3.6-flash`) and all
  answered HTTP 400 by Google. The wiring is proven end to end; the
  failure is the credential, not the plumbing.
- Blocker: the stored `custom.gemini` credential is rejected by
  Google as not a valid API key (`INVALID_ARGUMENT`,
  `API_KEY_INVALID`) on the model list, on a chat completion probe
  and through the relay. Controls run the same day: the OpenRouter
  helper verified live through the identical surrogate mechanism,
  and a garbage bearer token produces Google's identical response.
  Remedy: reconnect `custom.gemini` with a valid Google AI Studio
  API key, then rerun the connector helper's `models` and `probe`
  and this smoke run before any pipeline run uses the Gemini route.

### F16. An agent run can return success at the API level while doing nothing at all

- Repro (2026-11-17, finish-day2 pass): the record stage was run as a
  standalone ops-agent run whose prompt was the pipeline's standard
  record prompt plus an appended "additional instruction" paragraph
  (asking for an origin note inside each memory record's content).
- Actual: the run returned normally after 278 s and 4 LLM calls with
  `tool_calls_count: 0` and the final text "I could not safely update
  the task conditions. Please restate the current task and its required
  conditions." (`brain_status: waiting_user`). No exception, no error
  artifact; a caller that only checks for exceptions records the stage
  as successful while nothing was written.
- Retrying the same record with the extra instruction woven into the
  prompt's main sentence instead of appended after the report JSON
  worked first try (1 `memory.write`, record verified by search).
- Lesson for SDK users: a stage's success signal has to include its
  tool-call count or a read-back of the effect, never just the absence
  of an exception. RepoSitter's finish-day2 driver was caught by its
  own verification stage here; the run-05 summary in `runs/` documents
  the correction.

### F17. The Groq route works, but Groq's free-tier tokens-per-minute limit collides with the SDK's request bursts

- Wiring (2026-11-17, operator directed after the Gemini per-key 429
  wall in the day 2 update below): the relay gained a `groq` route
  (upstream `https://api.groq.com/openai/v1`, `custom.groq`
  credential), and because the SDK ships a native `groq` adapter (an
  OpenAI-compatible provider subclass), the route lives in the
  `providers.groq` block of `.openminion/agents.json` with `base_url`
  pointed at the relay, model `openai/gpt-oss-120b`,
  `tool_call_strategy: native`, timeout 300 s, and the agent profile's
  provider set to `groq`. No `provider_identity` pin is needed on this
  route (contrast F15). `repositter.toml`, the `ProjectConfig`
  defaults and `scripts/finish_day2.py` (new `--provider`/`--model`
  flags, plus a memory read-back verification stage on its classify
  path, per F16) were updated to match.
- Cloudflare gotcha: the first pipeline probe died with
  `AUTH_ERROR ... groq auth failed: HTTP 403` on every request, while
  the connector helper worked fine. Reproduced directly: the same
  request with urllib's default user agent returns HTTP 403 with body
  `error code: 1010` (Cloudflare refusing the client signature, as the
  `custom.groq` connector doc warns), and with the browser user agent
  the helper sends it returns 200. The relay forwarded no user agent;
  it now sends the same browser user agent as the helpers. The 403 is
  a signature refusal, not a credential problem; do not rotate the key
  over it.
- The wall: with the user agent fixed, the pipeline probe
  (`scripts/model_probe.py`: a forced tool call, then a delegated
  classifier returning a typed `TriageReport`) got real completions
  through the full SDK + relay path (2 HTTP 200 among the first 7
  requests) but then hit Groq's free-tier rate limit and died with
  `RATE_LIMITED` (the provider error names a tokens-per-minute limit
  for `openai/gpt-oss-120b`). Of the probe's 13 relay requests: 3
  HTTP 400, 2 HTTP 200, 8 HTTP 429. Per this pass's stop rule, no
  further provider work was attempted, so the probe never completed
  and steps 2 and 3 below were not run on Groq.
- Reading: the SDK fires its internal helper calls (F8) in bursts of
  several requests within seconds, each carrying the full system
  prompt and tool schemas. A per-minute token budget sized for chat
  use is spent by a handful of those bursts, where Gemini's limit
  behaved as a request-rate wall and OpenRouter's as a daily count.
  Any future Groq attempt needs pacing the SDK itself does not offer
  (throttling at the relay is the obvious seam: it already sees every
  request), or a paid tier. This is a provider-economics constraint,
  not an SDK defect and not a model-quality result: the two 200s show
  the model answering through the pipeline, but no classification was
  completed, so gpt-oss-120b's typed-output reliability for this
  pipeline is still unproven either way.
- Unexplained: the 3 HTTP 400 responses that preceded the first 200
  in the same probe. The relay does not log bodies (by design), so
  what Groq rejected is unknown. Recorded as an observation, not a
  conclusion.

### F18. Relay-side pacing makes the Groq route survivable: a token bucket sized from Groq's own limit headers, plus bounded 429 absorption

- Limit evidence (measured live on this account, 2026-11-17): a
  one-off diagnostic completion through the connector surrogate
  returned `x-ratelimit-limit-tokens: 8000` (the tokens-per-minute
  cap for `openai/gpt-oss-120b` on the free tier) and
  `x-ratelimit-limit-requests: 1000` (per day). The diagnostic used
  78 prompt tokens with a 64-token completion allowance, and
  `x-ratelimit-remaining-tokens` fell by exactly 142, so Groq charges
  a request against the minute window at admission as prompt tokens
  plus the requested completion allowance. That is the number the
  F17 bursts were blowing: two SDK helper calls carrying a few
  thousand prompt tokens each spend most of the 8,000 in seconds.
- Implementation (`repositter/relay.py`, `GroqPacer`, groq route
  only; the gemini and openrouter routes are byte-for-byte the old
  behaviour): before each send the relay estimates the admission
  charge as request-body bytes / 4 plus the body's
  `max_completion_tokens`/`max_tokens` (default reserve 1,024 when
  the SDK sets neither) and meters it through a token bucket of
  capacity 7,200 (90% of the measured 8,000) refilling at 120
  tokens/second. A 2.2 s minimum interval between request starts
  also keeps the route inside the stated 30 requests/minute cap.
  After every response the bucket re-syncs down to the
  `x-ratelimit-remaining-tokens` header when one is present, so
  estimation error corrects itself instead of accumulating.
- 429 handling: a 429 is retried inside the relay instead of being
  handed to the SDK. The wait honours `Retry-After`, falls back to
  the `x-ratelimit-reset-tokens` duration, then to exponential
  backoff (5 s doubling, capped at 60 s), plus a 0.5 s buffer;
  bounded at 6 retries and 240 s of total wait per request so the
  SDK's own 300 s provider timeout is not consumed by waiting. If
  the bound is hit the final 429 is returned to the SDK unchanged.
- Logging discipline kept: the relay log gains only numbers (attempt
  index, seconds paced, the rate-limit header values
  `rl_limit_tokens` / `rl_remaining_tokens`). Bodies, prompts and
  credential material are still never logged.
- Offline verification: the pacer's arithmetic was unit-checked
  before any live run (charge estimation, a second 4,000-token
  charge waiting exactly (4000 − 3200) / 120 = 6.67 s against the
  refilling bucket, header re-sync clamping, and the retry-delay
  precedence Retry-After > reset-tokens > backoff).
- Live verification (2026-11-17, `scripts/model_probe.py` through
  the real pipeline config): the pacing eliminated the rate limit
  entirely. The probe's 14 relay requests drew 7 HTTP 200 and
  7 HTTP 400 and **zero HTTP 429** (the unpaced probe in F17 drew 8
  in 13), with 258 s of total paced waiting and the
  remaining-tokens header staying in the 4,100 to 6,500 range
  throughout. No 429 retry was ever needed. The token-limit problem
  is solved; what the probe then exposed is a model-output problem,
  below.
- The probe still did not complete, for two separate non-limit
  reasons. Probe 1 (forced tool call) finished its run with
  `tool_calls: 0`: the model never called the forced tool, and the
  final text was a freshness-guard style refusal ("Missing
  live-data evidence for a freshness-sensitive answer"), not an
  answer to the probe task. Probe 2 (the delegated classifier) died
  with `AgentOutputValidationError`: the model returned
  `openminion: {` followed by otherwise well-formed TriageReport
  JSON, which is the F5 prose-prefix failure verbatim, from
  gpt-oss-120b this time. The plain connector probe
  (`custom.groq` helper) had returned clean JSON for the same kind
  of prompt, so the prefix appears when the model answers through
  the SDK's agent scaffolding, not through a bare completion.
  `model_probe.py` has no salvage path by design (it is the strict
  test); the production classify path in `scripts/finish_day2.py`
  does carry the F5 salvage, but per this pass's gate the leftovers
  were not run on a failed probe.
- The 7 HTTP 400s remain unexplained, as in F17: the relay logs no
  bodies by design, so what Groq rejects in those requests is still
  unknown. They did not block the 200s and are recorded as an
  observation, not a conclusion.

### F19. Groq's binding limit for this workload is tokens per day; a memory read-back by search is a ranked sample, not a census

Three observations from the 2026-11-17 finish pass on the paced
Groq route, each evidenced first-hand:

- **The daily token budget is the real wall.** After the F18 pacer
  eliminated the per-minute limit, the day's runs still died on
  HTTP 429, this time with `x-ratelimit-remaining-tokens` reading
  the full 8,000: the per-minute window was untouched, because the
  budget being spent was a different one. `run-08-scratch`'s scan
  stage error named it directly, in Groq's own text: "Rate limit
  reached for model `openai/gpt-oss-120b` ... on tokens per day
  (TPD): Limit 200,000". Admission charges prompt tokens plus the
  requested completion allowance against that daily budget, so
  near the end of the budget a minimal request (5-word prompt,
  16-token allowance; diagnostic at 12:24Z, HTTP 200,
  `x-ratelimit-remaining-requests` 940) is still admitted while
  SDK-sized requests are refused. Arithmetic: the day's four
  provider passes plus this one total roughly 170 relay requests,
  most carrying the full system prompt, rubric and tool schemas
  (F8); 200,000 tokens is a few hours of that traffic. The remedy
  is the 00:00 UTC reset, not pacing: pacing shapes the minute,
  it cannot stretch the day.
- **At least some of the F17/F18 HTTP 400s are the model inventing
  tools.** A scan-probe run in this pass failed with Groq's own
  message surfaced by the provider layer: "Tool call validation
  failed: attempted to call tool 'exec' which was not in
  request.tools". gpt-oss-120b, answering through the SDK's agent
  scaffolding, sometimes emits a call to a tool that was never
  offered, and Groq rejects the whole request with HTTP 400. The
  relay still logs no bodies, so the share of the earlier 400s
  with this cause is unknown; the mechanism is now proven to
  exist and to occur in practice.
- **A single `memory.search` is not a read-back of the store.**
  Run 06's record for issue #769 is present in
  `.openminion/memory/memory.db` (`fact:triaged_openminion_
  openminion_769`, written 11:34:29Z, content matching the report
  verbatim) and in the FTS index, yet the finish-day2 verify
  stage's agent, searching "triaged openminion/openminion",
  reported it absent from its results. The recall layer returns a
  ranked set capped at 5 items and 500 tokens
  (`PrecisionRecallOptions` defaults in the SDK's recall module);
  five near-identical triage records compete for that budget, so
  any one search can omit a record that exists. F16's lesson
  extends: verify a write by reading the store (or by a search
  narrow enough to be a census), never by one broad search, and
  never by the writing run's own success signal.

### F20. The F16 silent no-op recurred on Groq, and the run summary itself now carries the false ok

- Repro (2026-11-18, `run-09-scratch`, Groq route): the record
  stage's ops agent returned the verbatim F16 refusal ("I could
  not safely update the task conditions. Please restate the current
  task and its required conditions.") with `tool_calls_count: 0`
  and `brain_status: waiting_user`, after 3 LLM calls and 6 relay
  requests. No memory record for scratch issue #3 exists in the
  store (verified by direct store read: the only `fact:triaged*`
  keys are 759, 769, 779 and 780).
- What is new versus F16: the refusal recurred on run.py's
  standard record prompt (report JSON, no appended instruction
  paragraph), so it is not confined to the appended-paragraph shape
  that F16 blamed. And the run's own `summary.json` records the
  record stage as `"ok": true` with the run id: `triage.py` sets ok
  unconditionally whenever the stage raises no exception (line
  307). A caller that trusts the summary records the stage as
  successful while nothing was written, which is the exact trap F16
  describes, now demonstrated inside the project's own summary
  artifact rather than only in a caller.
- The same run's classify stage returned clean typed JSON for issue
  #3 with no salvage marker in the run artifacts, and the propose
  stage executed normally, so the refusal is specific to the
  record-stage agent run, not a route-wide failure. Consequence: a
  future scan of the scratch repo will see issue #3 as new again
  (no record), while the label read-back still proves the approval
  path end to end. The summary's `record.ok` needs the F16 check
  (tool-call count or store read-back) before it can be trusted;
  that fix is recorded here, not made in this run.

## Pending at the time of writing

- **DONE 2026-11-18 (run-09-scratch, Groq route).** The
  approval-gate evidence now exists: `runs/run-09-scratch/
  approval_held.json` (propose held at the policy gate) and
  `approval_resumed.json` (resumed with approval;
  `propose_github_write` executed, tool result "applied label
  'documentation' to Godson-droid/repositter-scratch#3"), and the
  label was read back from the GitHub API on issue #3
  (`documentation`, updated 2026-11-18T00:29:17Z). See the final
  Groq-sequence update at the end of this section.
- **Update 2026-11-16 (day 1 runs, after the 00:00 UTC reset).**
  `run-01-openminion` (32 requests): scan found #771 and #770 new,
  #759 already triaged from memory; #770 classified (bug, critical)
  and recorded; #771 classification failed with the F5 prose-JSON
  validation error. The propose stage **held at the policy gate**:
  `runs/run-01-openminion/approval_held.json` shows
  `policy_confirmation_prompt`, brain `waiting_user`, 0 tool calls;
  GitHub timeline confirms the `bug` label on #770 was applied by
  maintainer `wireindevice` at 23:25:47Z, before the run started, so
  RepoSitter wrote nothing. `run-02-openminion` (43 relay attempts,
  cap hit mid-run): scan correctly reported #770 as already triaged;
  #771 classified on retry (PR, bug, critical) and recorded; #769 and
  #768 classification failed with the same F5 validation error; the
  propose stage then failed with `RATE_LIMITED`
  (free-models-per-day), so run 02 has **no** approval artifact.
  Day counter ended at 56 used / 50 limit / 0 remaining (attempts
  past the cap count in the provider's tally). Still open for day 2:
  a held/resumed approval pair (needs a fresh day's budget), and
  classification retries for #769 and #768. Note the run-02 lesson:
  run 01's `--max-items 2` left older items untriaged, so run 02 did
  not see "everything already triaged" as planned; and 3 of 5
  classifications across the two runs failed on the F5 prose-JSON
  error, which is now the dominant failure mode, not an occasional
  one.
- **Update 2026-11-16 (provider switch, F15).** RepoSitter's primary
  route is now Gemini (`gemini-3.6-flash`) with OpenRouter as the
  fallback; wiring and config are complete and a minimal SDK smoke
  run reached Google through the relay. The stored Gemini credential
  is being rejected by Google as an invalid API key, so the day 2
  runs must not start on the Gemini route until the credential is
  reconnected and the helper `models`/`probe` checks plus the smoke
  run pass. If that is not resolved in time, day 2 can still run on
  the OpenRouter fallback within one day's 50-request budget.
- **Update 2026-11-17 (day 2 runs: the Gemini rate limit is now the binding constraint).**
  The F15 credential blocker is cleared: the stored Gemini credential
  was reconnected and `gemini.py probe` passed (model
  `gemini-3.6-flash`, valid JSON triage reply) before any run started,
  so day 2 ran on the Gemini route. `run-04-openminion` (60 relay
  requests: 14 HTTP 200, 46 HTTP 429): the scan stage failed on
  `RATE_LIMITED` but the orchestrator salvaged the fetched item list,
  and the two newest items #780 and #779 were both classified cleanly
  (bug/high and bug/medium), with no F5 prose instead of JSON failure,
  so the F15 hypothesis that a stronger model ends that failure mode
  held on this run. The record stage then failed on the same 429, so
  no memory records were written for #780 or #779 and a later run
  will see them as new again. The propose stage held at the gate:
  `runs/run-04-openminion/approval_held.json` shows
  `policy_confirmation_prompt`, brain `waiting_user`, 0 tool calls.
  GitHub timeline confirms the labels on #780 and #779 were all
  applied by maintainer `wireindevice` on 2026-11-16, before the run,
  so RepoSitter wrote nothing; the maintainer labels agree with the
  classifier's head label `bug` on both items and with `area:config`
  on #779. Issues #769 and #768 are still unclassified: the scan
  picked the two newest items, not the oldest untriaged ones.
  `run-03-scratch` then failed in its scan stage after 14 relay
  requests (1 HTTP 200, 13 HTTP 429) in 26 seconds, fetched 0 items,
  and never reached classify, record or propose, so the held/resumed
  approval pair is still unproven and there is no label read back.
  The pattern across both runs is a few successful requests then a
  wall of 429s, which reads as a per key rate limit on the Gemini
  free tier rather than a daily quota: successes kept arriving
  through run 04, and a 6 minute idle gap did not clear it for
  run 03. Per the job's stop rule the package was not published: no
  public repo, no dashboard publish. The OpenRouter fallback budget
  is untouched today (0 used / 50 limit, checked after run 03
  failed), but the job's fallback trigger was a probe failure with an
  API key error, which did not happen, so using it next is Godson's
  call. Still open: the approval proof on the scratch repo, memory
  records for #780 and #779, and classification retries for #769 and
  #768.
- **Update 2026-11-17 (finish-day2 pass: memory records completed; pass
  then stopped on the rate limit).** The pass opened with the Gemini
  probe passing cleanly (`gemini.py probe`, valid JSON, no 429). Step 1
  is now done, with a correction to the day 2 account above: run 04's
  record stage evidently wrote the #780 record before it failed (a
  `memory.search` in this pass found it verbatim, in run 04's standard
  content format), and died on the #779 write, so only #779 was actually
  missing. `run-05-record` first tried to write both records and wrote
  nothing at all: the ops agent returned the F16 refusal with 0 tool
  calls while reporting success to the caller. `run-05b-record` then
  recorded #779 alone (1 `memory.write`), with the origin note the
  project required inside the record content ("classified in
  run-04-openminion; recorded in run-05b-record"), and a verification
  search read the stored record back verbatim (stored key
  `fact:triaged_openminion_openminion_779`, the F7 slugification). Both
  #780 and #779 are now in persistent memory, so a future scan will skip
  them as already triaged. The cost was high for two records: by the end
  of run 05b, 29 of its 35 relay requests had been answered HTTP 429,
  the stages completing only through SDK retries as individual requests
  leaked through the per key limit. Per the pass's stop rule, steps 2
  (classification retries for #769 and #768), 3 (the scratch approval
  proof) and 5 (publication) were therefore NOT attempted in this pass.
  Still open: the approval proof on the scratch repo and classification
  retries for #769 and #768. The OpenRouter fallback budget remains
  untouched (0 of 50); using it remains Godson's call. Nothing was
  published: no public repo, no dashboard publish.
- **Update 2026-11-17 (Groq pass: provider switched; probe stopped on
  Groq's tokens-per-minute limit).** The operator directed a switch to
  Groq (`openai/gpt-oss-120b`, free tier) after the Gemini wall; the
  wiring is complete (F17) and the connector helper had already
  verified the model live (clean JSON probe) before this pass. The
  pipeline probe through the actual RepoSitter configuration first
  failed on Cloudflare's 1010 signature refusal (relay user agent;
  fixed in the relay), then reached Groq and received real completions
  but hit the free-tier tokens-per-minute 429 wall 13 requests in and
  was stopped per the pass's stop rule; no fallback to Gemini or
  OpenRouter was made. Groq requests spent in this pass: 19 in total
  (1 connector `models` read, 2 direct diagnosis calls, 16 through
  the relay). Separately, the pre-flight repo check found that
  openminion/openminion **#768 is now closed upstream** (state read
  from the GitHub API on 2026-11-17), so its classification retry is
  moot: there is nothing open to classify, and no classification was
  fabricated for it. #769 is still open. The scratch repo still has
  its 3 seeded issues open and unlabelled. Because the probe (step 1)
  did not complete, steps 2 (#769 retry with memory record and
  read-back) and 3 (the scratch approval proof) were NOT attempted,
  and per the publication gate nothing was published (verified after
  the stop: `Godson-droid/repositter` returns 404 and the GitHub
  Pages URL returns 404). Still open: the #769 classification retry,
  the approval proof on the scratch repo, and publication, all now
  gated on a provider route whose limits fit the SDK's request
  pattern (see F17 for the relay-throttling idea).
- **Update 2026-11-17 (throttling pass: the limit wall is gone; the
  probe now fails on model output, F18).** The relay's groq route
  gained the F18 token-bucket pacing, sized from Groq's own headers
  (8,000 tokens/minute, charged at admission as prompt plus
  requested completion). The pipeline probe then ran 14 requests
  with zero HTTP 429 (258 s of paced waiting) but did not complete:
  probe 1 never made its forced tool call (0 tool calls, a
  freshness-guard style answer), and probe 2's classifier reply
  carried the F5 `openminion: {` prose prefix and failed typed
  validation. Per the pass's gate, steps 2 (#769) and 3 (scratch
  approval proof) were NOT attempted and nothing was published
  (verified after the stop: `Godson-droid/repositter` and the
  GitHub Pages URL still return 404). Groq requests spent in this
  pass: 15 (1 diagnostic header read, 14 through the relay);
  34 in total today. The blocker has changed shape: it is no
  longer any provider's limits, it is gpt-oss-120b's typed-output
  behaviour through the SDK scaffolding (the F5 failure the small
  OpenRouter model showed, which Gemini's frontier model did not).
  Still open: the #769 classification retry, the approval proof on
  the scratch repo, and publication, now gated on a route whose
  model returns clean typed output through the pipeline (the
  finish-day2 classify path's F5 salvage is one candidate remedy;
  using it is the operator's call, as is any model change on the
  groq route).
- **Update 2026-11-17 (finish pass on the paced Groq route: step 1
  done; the scratch proof stopped on the daily token budget,
  F19).** The operator directed running the leftovers through
  finish_day2.py's classify path, whose F5 salvage the strict
  probe lacks. `run-06-openminion` classified issue #769 through
  that path on Groq: report bug/high, suggested labels
  `bug, area:tools, platform:windows, priority:high` (the first
  three agree with the maintainer's own labels on the issue). The
  driver process was then killed by a Muse runtime restart
  after the report artifact was written and the record stage's
  `memory.write` had landed (record
  `fact:triaged_openminion_openminion_769`, 11:34:29Z, content
  matching the report) but before it wrote its own stage
  artifacts; whether the F5 salvage fired is undetermined,
  because the classify log died with the process and telemetry
  records no typed-output validation failure for the classifier
  in the window. A recovery pass verified the record by reading
  the memory store directly; the verify stage's own agent search
  did not surface the record, which is the F19 read-back caveat,
  not a missing record. Issue #768's retry remains moot (closed
  upstream). The scratch approval proof was attempted twice.
  `run-07-scratch` (full pipeline, `--approve-write`) completed
  its scan and classified scratch issues #3 (docs/low) and #2,
  then entered an unbroken HTTP 429 stream on the third item and
  was terminated by the operator after 52 relay requests;
  nothing was recorded, proposed or applied. `run-08-scratch`
  (`--max-items 1`) died in its scan stage after 13 relay
  requests with `RATE_LIMITED`, its error naming Groq's tokens
  per day limit (200,000) as the binding constraint (F19). All
  three scratch issues were read back unlabelled afterwards, and
  per the pass's gate nothing was published (verified after the
  stop: `Godson-droid/repositter` returns 404 and the GitHub
  Pages URL returns 404). Groq requests in this pass: 102
  (15 classify driver, 8 recovery verify, 13 scan probe, 52
  run 07, 13 run 08, 1 diagnostic); 136 in total today by the
  relay log's accounting (Groq's own counter, which counts
  admitted requests only, read 940 of 1,000 remaining at 12:24Z).
  Still open: the scratch approval proof and publication, now
  gated on the daily token reset (00:00 UTC) rather than on any
  wiring, pacing or salvage question; and the README's example
  runs section, which is updated with run 06 once publication
  lands.
- **Update 2026-11-18 (run-09-scratch on the reset Groq budget:
  the approval proof is done; publication follows in this run).**
  The first launch attempt was killed by a Muse runtime restart 5
  relay requests in (scan stage, no writes); the rerun went clean.
  `run-09-scratch` (32 relay requests: 18 HTTP 200, 14 HTTP 400,
  **zero HTTP 429**; 800 s): the scan found the scratch repo's 3
  issues new; classify returned issue #3 (docs/low, labels
  `documentation`, `enhancement`) as clean typed JSON with no
  salvage marker; the propose stage held at the gate and, resumed
  with `--approve-write`, applied label `documentation` to issue
  #3, read back from the GitHub API the same morning (`labels:
  ['documentation']`, updated 2026-11-18T00:29:17Z). The approval
  path is now proven end to end on Groq, closing the Groq
  sequence: F17's per-minute wall (solved by the F18 pacer), F19's
  daily token wall (cleared by the 00:00 UTC reset), and the F5
  typed-output failure (no occurrence in run 09's classify stage;
  the F5 salvage question from run 06 remains undetermined). Two
  caveats travel with the proof: the record stage hit the F16
  refusal again (0 tool calls, no memory record for #3; see F20),
  so a future scratch scan will see #3 as new; and the 14 HTTP
  400s are the known invented-tool rejections (F19) that cost
  requests without blocking the run. Groq use today: 37 relay
  requests (5 in the killed attempt, 32 in run 09) plus 1 models
  read; the day's token budget is barely touched by comparison
  with 2026-11-17's 136. Publication of the repo
  `Godson-droid/repositter` and the dashboard at
  https://godson-droid.github.io/repositter/ is the next step of
  this run; the verified-live status is recorded here once both
  read back publicly. Still open after this run: the F20
  summary-ok fix, a record-stage retry for scratch #3, and the
  DoraHacks Buidl submission and demo video, which are not part of
  this run.
