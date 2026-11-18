#!/usr/bin/env python3
"""One small live probe of the configured free model through the relay.

Run 1: a forced custom tool call (checks native tool calling).
Run 2: a delegated classifier subagent returning a typed TriageReport
(checks structured output). Each run is a handful of provider requests;
the relay log delta is printed so the cost is explicit.
"""

from __future__ import annotations

import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from openminion import Agent, subagent, tool  # noqa: E402
from openminion.api.runtime import APIRuntime  # noqa: E402

from repositter.relay import start_relay  # noqa: E402
from repositter.schemas import TriageReport  # noqa: E402
from repositter.triage import ProjectConfig  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else ProjectConfig.model
PROVIDER = ProjectConfig.provider


@tool(min_scope="READ_ONLY", idempotent=True)
def probe_lookup(code: str) -> str:
    """Return the status word for a probe code."""

    return f"probe {code}: ok"


def main() -> int:
    server, state = start_relay(8377, PROJECT_DIR / "runs" / "relay.log", provider=PROVIDER)
    time.sleep(0.3)
    runtime = APIRuntime.from_config_path(
        str(PROJECT_DIR / ".openminion" / "agents.json"), logging_mode="interactive"
    )
    try:
        before = state.count
        with Agent(
            runtime=runtime,
            instructions="Use probe_lookup and answer in one sentence.",
            tools=[probe_lookup],
            forced_tools=["probe_lookup"],
            model=MODEL,
            session_id="repositter-probe",
        ) as agent:
            result = agent.run("Check probe ZX-1", timeout_seconds=600)
        print("PROBE1 text:", result.text)
        print("PROBE1 run_id:", result.run_id, "state:", result.run_state)
        print("PROBE1 stats:", result.stats)
        mid = state.count
        print(f"PROBE1 relay requests: {mid - before}")

        parent = Agent(runtime=runtime, name="probe-parent", session_id="repositter-probe")
        classifier = subagent(
            parent,
            name="classifier",
            instructions=(
                "Classify exactly one GitHub issue using this rubric: category is one of "
                "bug, feature, question, docs, other; priority is one of critical, high, "
                "medium, low; labels only from: bug, enhancement, question, documentation, "
                "needs info, good first issue, help wanted, duplicate, wontfix. "
                "Answer with the TriageReport JSON only."
            ),
            output_type=TriageReport,
            model=MODEL,
            timeout_seconds=600,
        )
        sample = (
            "Classify this issue from openminion/openminion.\n"
            "Number: 752\nTitle: cli: bare `openminion replay` crashes with AttributeError\n"
            "Author: unknown\nCreated: 2026-11-14\nCurrent labels: []\nComments: 0\n"
            "Body: Running `openminion replay` with no arguments crashes with an "
            "AttributeError instead of printing usage."
        )
        result2 = classifier.run(sample)
        print("PROBE2 output:", result2.output.model_dump_json(indent=2))
        print("PROBE2 run_id:", result2.run_id)
        print(f"PROBE2 relay requests: {state.count - mid}")
    finally:
        runtime.close()
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
