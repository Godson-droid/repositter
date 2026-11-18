"""Loopback relay that lets OpenMinion use a registered Muse connector
credential without the key ever entering the agent process.

OpenMinion is configured with base_url http://127.0.0.1:<port>/v1 and a
dummy placeholder api_key. Every request it sends lands here; the relay
forwards it to the provider's OpenAI-compatible endpoint and attaches
the real credential through the Muse dynamic-credential surrogate
(the same mechanism as the connector helpers in
~/workspace/custom-connectors/custom.openrouter/bin/openrouter.py and
~/workspace/custom-connectors/custom.gemini/bin/gemini.py). The relay
process only ever holds the surrogate token, never the key.

Three providers are wired:

- ``groq`` (primary since 2026-11-17): forwards to Groq's
  OpenAI-compatible endpoint at https://api.groq.com/openai/v1/... and
  attaches the ``custom.groq`` credential.
- ``gemini``: forwards to Google's OpenAI-compatible endpoint
  at https://generativelanguage.googleapis.com/v1beta/openai/... and
  attaches the ``custom.gemini`` credential.
- ``openrouter`` (fallback): forwards to https://openrouter.ai/api/v1/...
  and attaches the ``custom.openrouter`` credential.

Each forwarded request is counted and logged (provider, method, path,
model, status, seconds) to a JSONL file so the request budget is
auditable. Request and response bodies are never logged.

The ``groq`` route is additionally paced (see ``GroqPacer`` and
FINDINGS.md F18): Groq's free tier caps ``openai/gpt-oss-120b`` at
8,000 tokens per minute, charged at admission as prompt tokens plus
the requested completion allowance, and the SDK's internal helper
calls arrive in bursts that spend that budget in seconds. The relay
therefore meters groq requests through a token bucket, enforces a
minimum interval between them, and absorbs HTTP 429s with bounded
backoff honouring ``Retry-After``, so the SDK sees slow successes
instead of failures. The other routes are forwarded exactly as
before.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

# provider name -> (upstream base for /v1/* paths, connector credential
# name, allowed hosts for the surrogate mechanism)
PROVIDERS: dict[str, tuple[str, str, list[str]]] = {
    "groq": (
        "https://api.groq.com/openai/v1",
        "custom.groq",
        ["api.groq.com"],
    ),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "custom.gemini",
        ["generativelanguage.googleapis.com"],
    ),
    "openrouter": (
        "https://openrouter.ai/api/v1",
        "custom.openrouter",
        ["openrouter.ai"],
    ),
}

DEFAULT_PROVIDER = "groq"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object) -> None:
        raise RuntimeError("redirect refused, verify the endpoint")


_OPENER = urllib.request.build_opener(_NoRedirect())


class RelayState:
    def __init__(self, log_path: Path, provider: str = DEFAULT_PROVIDER) -> None:
        self.log_path = log_path
        self.provider = provider
        self.count = 0
        self.lock = threading.Lock()
        # Pacing exists only on the groq route (F18); the other routes
        # keep the exact behaviour they had before.
        self.pacer: GroqPacer | None = GroqPacer() if provider == "groq" else None

    def record(self, entry: dict) -> None:
        with self.lock:
            self.count += 1
            entry = {"n": self.count, "provider": self.provider, **entry}
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")


class GroqPacer:
    """Token-bucket pacing for the groq route (FINDINGS.md F18).

    Limits measured live on this account on 2026-11-17 from response
    headers: ``x-ratelimit-limit-tokens: 8000`` (tokens per minute for
    ``openai/gpt-oss-120b``) and ``x-ratelimit-limit-requests: 1000``
    (per day). A diagnostic completion (78 prompt + 64 requested
    completion tokens) dropped ``x-ratelimit-remaining-tokens`` by
    exactly 142, so Groq charges a request against the minute window
    at admission as prompt tokens plus the requested completion
    allowance. The bucket is therefore charged an estimate of that
    sum before each send and re-synced to the remaining-tokens header
    after every response, so estimation error corrects itself.

    The bucket runs at 90% of the measured limit for margin. A
    minimum start interval of 2.2 s also keeps the route inside the
    stated 30 requests/minute free-tier cap. HTTP 429 responses are
    retried inside the relay with bounded backoff that honours the
    ``Retry-After`` header (falling back to the reset-tokens header,
    then to exponential backoff), capped per request so the SDK's own
    timeout is not consumed by waiting.
    """

    LIMIT_TOKENS_PER_MINUTE = 8000
    BUDGET_FRACTION = 0.9
    MIN_INTERVAL_SECONDS = 2.2
    DEFAULT_COMPLETION_RESERVE = 1024
    MAX_429_RETRIES = 6
    MAX_RETRY_WAIT_SECONDS = 240.0

    def __init__(self) -> None:
        self.capacity = self.LIMIT_TOKENS_PER_MINUTE * self.BUDGET_FRACTION
        self.refill_per_second = self.capacity / 60.0
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self.last_start = 0.0
        self.lock = threading.Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
            self.last_refill = now

    @staticmethod
    def estimate_charge(body: bytes) -> int:
        """Approximate Groq's admission charge for one request body."""
        prompt_estimate = max(1, len(body) // 4)
        completion = GroqPacer.DEFAULT_COMPLETION_RESERVE
        try:
            payload = json.loads(body)
            for key in ("max_completion_tokens", "max_tokens"):
                value = payload.get(key)
                if isinstance(value, int) and value > 0:
                    completion = value
                    break
        except Exception:
            pass
        return prompt_estimate + completion

    def acquire(self, charge: int) -> float:
        """Block until sending is inside the budget; return seconds waited."""
        started = time.monotonic()
        with self.lock:
            while True:
                now = time.monotonic()
                self._refill(now)
                interval_wait = self.last_start + self.MIN_INTERVAL_SECONDS - now
                if self.tokens >= charge and interval_wait <= 0:
                    break
                if self.tokens >= self.capacity and interval_wait <= 0:
                    break  # charge exceeds the whole budget; send with a full bucket
                wait = max(interval_wait, (charge - self.tokens) / self.refill_per_second, 0.05)
                time.sleep(min(wait, 5.0))
            self.tokens = max(0.0, self.tokens - charge)
            self.last_start = time.monotonic()
        return time.monotonic() - started

    def observe(self, headers: object) -> dict:
        """Re-sync the bucket from a response's rate-limit headers.

        Returns the limit values seen (numbers only, safe to log).
        """
        seen: dict = {}
        try:
            remaining = headers.get("x-ratelimit-remaining-tokens")  # type: ignore[attr-defined]
            limit = headers.get("x-ratelimit-limit-tokens")  # type: ignore[attr-defined]
        except Exception:
            return seen
        if limit is not None:
            seen["rl_limit_tokens"] = int(limit)
        if remaining is not None:
            seen["rl_remaining_tokens"] = int(remaining)
            with self.lock:
                self._refill(time.monotonic())
                self.tokens = min(self.tokens, float(remaining))
        return seen

    def retry_delay(self, headers: object, attempt: int) -> float:
        """Seconds to wait before retrying after an HTTP 429."""
        delay: float | None = None
        try:
            retry_after = headers.get("Retry-After")  # type: ignore[attr-defined]
            if retry_after:
                delay = float(retry_after)
            else:
                reset = headers.get("x-ratelimit-reset-tokens")  # type: ignore[attr-defined]
                if reset:
                    delay = _parse_duration_seconds(str(reset))
        except Exception:
            delay = None
        if delay is None:
            delay = min(5.0 * (2**attempt), 60.0)
        return delay + 0.5


def _model_of(body: bytes) -> str:
    try:
        return str(json.loads(body).get("model", ""))
    except Exception:
        return ""


def _parse_duration_seconds(text: str) -> float | None:
    """Parse Groq duration strings like '1.065s', '7m12s', '2m30.5s'."""
    total = 0.0
    matched = False
    for value, unit in re.findall(r"([0-9]+(?:\.[0-9]+)?)([hms])", text):
        matched = True
        total += float(value) * {"h": 3600.0, "m": 60.0, "s": 1.0}[unit]
    return total if matched else None


def make_handler(state: RelayState) -> type[BaseHTTPRequestHandler]:
    upstream_base, credential_name, allowed_hosts = PROVIDERS[state.provider]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args: object) -> None:  # silence stderr log
            pass

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _forward(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            if self.path == "/health":
                self._send(200, "application/json", b'{"ok": true}')
                return
            if not self.path.startswith("/v1/"):
                self._send(404, "application/json", b'{"error": "relay only forwards /v1/*"}')
                return
            url = upstream_base + self.path[len("/v1"):]
            pacer = state.pacer
            charge = pacer.estimate_charge(body) if pacer is not None else 0
            retry_wait_spent = 0.0
            attempt = 0
            while True:
                started = time.time()
                paced_wait = pacer.acquire(charge) if pacer is not None else 0.0
                request = urllib.request.Request(url, data=body if method == "POST" else None, method=method)
                request.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
                # Groq sits behind Cloudflare, which refuses the default
                # Python-urllib signature with HTTP 403 "error code: 1010"
                # (a signature refusal, not a bad key; see the custom.groq
                # connector doc). Send the same browser user agent the
                # connector helpers send. Harmless for the other upstreams.
                request.add_header(
                    "User-Agent",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                )
                try:
                    add_surrogate_to_request(request, credential_name, allowed_hosts=allowed_hosts)
                except Exception as exc:  # credential mechanism unavailable
                    self._send(502, "application/json", json.dumps({"error": f"surrogate failed: {exc}"}).encode())
                    state.record({"ts": time.time(), "method": method, "path": self.path,
                                  "model": _model_of(body), "status": 502, "seconds": round(time.time() - started, 2)})
                    return
                status = 0
                response_headers = None
                try:
                    with _OPENER.open(request, timeout=600) as response:
                        status = response.status
                        response_headers = response.headers
                        content_type = response.headers.get("Content-Type", "application/json")
                        # Buffered, not streamed: with chunked pass-through the
                        # OpenMinion provider layer reported EMPTY_PROVIDER_RESPONSE
                        # for agent runs, while the identical requests succeeded
                        # when returned complete with a Content-Length (see
                        # FINDINGS.md F3). Agent turns consume whole responses
                        # anyway, so buffering costs nothing here.
                        payload = response.read()
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    response_headers = exc.headers
                    payload = exc.read()
                    content_type = exc.headers.get("Content-Type", "application/json")
                except Exception as exc:  # upstream timeout / connection failure
                    status = 502
                    payload = json.dumps({"error": f"relay upstream failure: {exc}"}).encode()
                    content_type = "application/json"
                entry = {"ts": time.time(), "method": method, "path": self.path,
                         "model": _model_of(body), "status": status,
                         "seconds": round(time.time() - started, 2)}
                if pacer is not None:
                    entry["attempt"] = attempt
                    entry["paced_wait_s"] = round(paced_wait, 2)
                    if response_headers is not None:
                        entry.update(pacer.observe(response_headers))
                state.record(entry)
                if (
                    pacer is not None
                    and status == 429
                    and attempt < GroqPacer.MAX_429_RETRIES
                    and response_headers is not None
                ):
                    delay = pacer.retry_delay(response_headers, attempt)
                    if retry_wait_spent + delay > GroqPacer.MAX_RETRY_WAIT_SECONDS:
                        self._send(status, content_type, payload)
                        return
                    retry_wait_spent += delay
                    attempt += 1
                    time.sleep(delay)
                    continue
                self._send(status, content_type, payload)
                return

        def do_GET(self) -> None:  # noqa: N802
            self._forward("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._forward("POST")

    return Handler


def start_relay(
    port: int, log_path: Path, provider: str = DEFAULT_PROVIDER
) -> tuple[ThreadingHTTPServer, RelayState]:
    """Start the relay on 127.0.0.1 in a daemon thread and return it."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown relay provider: {provider!r} (known: {sorted(PROVIDERS)})")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    state = RelayState(log_path, provider)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True, name=f"{provider}-relay")
    thread.start()
    return server, state
