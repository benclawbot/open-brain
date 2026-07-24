"""
End-to-end test suite for the Open Brain 1.0.0 API.

Hits every category of route documented in the OpenAPI schema:
- Health and root
- Memory CRUD (POST, GET, list, search, stats, trends, weekly report)
- Continuity: identities/resolve, sessions/open, sessions/close, events
- Context: v1/context, v1/context/feedback, cache stats and cleanup
- Review workflows: lifecycle, consolidation, pruning proposals
- Maintenance: v1/maintenance/run, v1/compaction/run
- Imports: providers list, hermes markdown, provider run lifecycle (seal/rollback)
- Auth enforcement (no key / bad key / open health endpoint)

This is an integration test, not a unit test. It is skipped automatically
when the api is not reachable, so it is safe to keep in the repository
and run alongside the unit suite in CI.

Configuration via environment variables (with sensible local defaults):
  OPENBRAIN_E2E_URL    Default: http://127.0.0.1:8765
  OPENBRAIN_E2E_KEY    Required.  Read from ~/.config/openbrain/.env if not set.
  OPENBRAIN_E2E_HERMDOC  Default: e2e_hermes.md (used for the hermes markdown import)

Run from the repo root:
    pytest tests/e2e/test_api.py -v -s
or standalone:
    python tests/e2e/test_api.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# Skip the whole module under pytest when the api isn't reachable.
import pytest

DEFAULT_URL = "http://127.0.0.1:8765"
DEFAULT_HERMDOC_NAME = "e2e_hermes.md"


def _read_global_key() -> str | None:
    """Best-effort read of OPENBRAIN_API_KEY from the per-user config file."""
    cfg = pathlib.Path.home() / ".config" / "openbrain" / ".env"
    if not cfg.exists():
        return None
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENBRAIN_API_KEY="):
            return line.split("=", 1)[1].strip() or None
    return None


def _resolve_url() -> str:
    return os.environ.get("OPENBRAIN_E2E_URL", DEFAULT_URL).rstrip("/")


def _resolve_key() -> str | None:
    return os.environ.get("OPENBRAIN_E2E_KEY") or _read_global_key()


def _resolve_hermdoc() -> str:
    return os.environ.get("OPENBRAIN_E2E_HERMDOC", DEFAULT_HERMDOC_NAME)


def _api_reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


URL = _resolve_url()
KEY = _resolve_key()
IN_PYTEST = bool(os.environ.get("PYTEST_CURRENT_TEST"))

# Skip the whole module under pytest when the api isn't reachable. When run
# as a standalone script, print a clear message and exit non-zero instead.
if not KEY or not _api_reachable(URL):
    msg = (
        f"Open Brain api not reachable at {URL} or OPENBRAIN_API_KEY not set.\n"
        f"Bring up the stack with `bash scripts/quickstart.sh`, then rerun."
    )
    if IN_PYTEST:
        pytestmark = pytest.mark.skip(reason=msg)
    else:
        print(msg, file=sys.stderr)
        sys.exit(2)


# Shared state for the run
class State:
    identity_id: str | None = None
    session_id: str | None = None
    created_memory_id: str | None = None
    packet_id: str | None = None
    hermes_container_path: str | None = None
    import_run_id: str | None = None
    passed: int = 0
    failed: int = 0


S = State()
HDR = {"X-API-Key": KEY or "", "Content-Type": "application/json"}


def req(method: str, path: str, body: dict | None = None, expect: tuple | None = None):
    """Make a request. Returns (status, raw). Records pass/fail in S."""
    data = json.dumps(body).encode() if body is not None else None
    rq = urllib.request.Request(
        f"{URL}{path}",
        data=data,
        headers=HDR,
        method=method,
    )
    try:
        with urllib.request.urlopen(rq, timeout=60) as r:
            status, raw = r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read().decode("utf-8", errors="replace")

    short = raw[:200].replace("\n", " ")
    ok = expect is None or status in expect
    if ok:
        S.passed += 1
    else:
        S.failed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {method:6s} {path} -> {status} | {short}")
    return status, raw


def test_health_and_root():
    print("\n=== 1. Health and root ===")
    for path in ["/", "/health", "/health/live", "/health/ready"]:
        s, _ = req("GET", path, expect=(200,))
        assert s == 200, f"GET {path} returned {s}"
    s, raw = req("GET", "/openapi.json", expect=(200,))
    assert s == 200 and "paths" in json.loads(raw), "OpenAPI schema missing 'paths'"


def test_memory_crud():
    print("\n=== 2. Memory CRUD ===")
    # The content is intentionally distinctive (a unique "knockwurst" reference
    # and a unique timestamp) so this memory's embedding is distinguishable
    # from historical near-duplicates the api may already hold.
    s, raw = req("POST", "/memories", {
        "content": (
            "E2E test beacon written on 2099-12-31 23:59:59 from Mars colony. "
            "Unique marker: knockwurst-omega-9001. "
            "The lead PostgreSQL migration architect is now working on the "
            "Acme-OpenBrain integration in Paris. "
            "Contact ben@acme.example, https://acme.example, phone 555-123-4567. "
            "#hiring @ben #postgres #paris #e2e-beacon"
        ),
        "tags": ["test", "hiring", "e2e"],
        "source": "e2e_test",
    }, expect=(200,))
    body = json.loads(raw)
    S.created_memory_id = body.get("id")
    assert s == 200 and S.created_memory_id, f"POST /memories failed: {raw[:200]}"

    s, raw = req("GET", "/memories?limit=10", expect=(200,))
    listing = json.loads(raw)
    assert s == 200 and isinstance(listing, list), f"GET /memories failed: {raw[:200]}"

    s, raw = req("GET", f"/memories/{S.created_memory_id}", expect=(200,))
    got = json.loads(raw)
    ent = got.get("entities", {})
    assert s == 200 and ent.get("people") and ent.get("locations"), (
        f"GET /memories/{{id}} NER not populated: people={ent.get('people')}, "
        f"locations={ent.get('locations')}"
    )

    s, raw = req("POST", "/memories/search", {
        # The query is intentionally distinctive ("knockwurst-omega-9001 Mars
        # colony") so this test's just-created memory is the top hit rather
        # than any historical near-duplicate.
        "query": "knockwurst-omega-9001 Mars colony e2e beacon",
        "limit": 10,
    }, expect=(200,))
    hits = json.loads(raw)
    hit_ids = [h["id"] for h in hits]
    assert s == 200 and S.created_memory_id in hit_ids, (
        f"semantic search did not return the just-created memory; got {len(hits)} hits"
    )

    s, raw = req("POST", "/memories/search", {
        "query": "hiring", "sources": ["e2e_test"], "limit": 5,
    }, expect=(200,))
    assert s == 200 and len(json.loads(raw)) >= 1, "source-filtered search returned 0 hits"

    s, raw = req("POST", "/memories/search", {
        "query": "hiring", "tags": ["e2e"], "limit": 5,
    }, expect=(200,))
    assert s == 200 and len(json.loads(raw)) >= 1, "tag-filtered search returned 0 hits"

    s, _ = req("GET", "/memories/00000000-0000-0000-0000-000000000000", expect=(404,))
    assert s == 404, "expected 404 for unknown id"

    s, _ = req("GET", "/memories/not-a-uuid", expect=(400, 422))
    assert s in (400, 422), "expected 400/422 for malformed uuid"


def test_analytics():
    print("\n=== 3. Analytics ===")
    s, raw = req("GET", "/stats", expect=(200,))
    stats = json.loads(raw)
    assert s == 200 and "total" in stats and stats.get("total", 0) >= 1
    s, _ = req("GET", "/trends", expect=(200,))
    assert s == 200
    s, _ = req("GET", "/report/weekly?days=7", expect=(200,))
    assert s == 200


def test_continuity():
    print("\n=== 4. Continuity ===")
    s, raw = req("POST", "/v1/identities/resolve", {
        "kind": "user",
        "canonical_key": "e2e-test-user-openbrain",
        "display_name": "E2E Test User",
    }, expect=(200, 201))
    identity = json.loads(raw)
    S.identity_id = identity.get("id") or identity.get("identity_id")
    assert s in (200, 201) and S.identity_id, f"identity resolve failed: {raw[:200]}"

    s, raw = req("POST", "/v1/sessions/open", {
        "external_session_id": f"e2e-test-session-{int(time.time()*1000)}",
        "source_system": "e2e_test",
        "platform": "openbrain-e2e",
        "user": {"kind": "user", "canonical_key": "e2e-test-user-openbrain"},
        "agent": {"kind": "agent", "canonical_key": "e2e-test-agent"},
        "workspace": {"kind": "workspace", "canonical_key": "open-brain-e2e"},
    }, expect=(200, 201))
    sess = json.loads(raw)
    S.session_id = sess.get("id") or sess.get("session_id")
    assert s in (200, 201) and S.session_id, f"session open failed: {raw[:200]}"

    for et, role, content in [
        ("user.message", "user", "E2E test asks: what should I name the new service?"),
        ("tool.observation", "tool", "Looked up the project index; saw open-brain already has a quickstart script."),
        ("assistant.message", "assistant", "Named the service 'open-brain-memory'."),
    ]:
        s, _ = req("POST", "/v1/events", {
            "event_type": et,
            "idempotency_key": f"e2e-{et.replace('.','')}-{int(time.time()*1000)}",
            "source_system": "e2e_test",
            "scope": {"user_identity_id": S.identity_id, "session_id": S.session_id},
            "payload": {"role": role, "content": content},
        }, expect=(200, 201))
        assert s in (200, 201), f"event {et} failed"

    s, _ = req("POST", f"/v1/sessions/{S.session_id}/close", {
        "summary": "E2E test session — verified identity resolution, event recording, and continuity.",
    }, expect=(200, 201, 204))
    assert s in (200, 201, 204), f"session close failed"


def test_context():
    print("\n=== 5. Context ===")
    s, raw = req("POST", "/v1/context", {
        "user_identity_id": S.identity_id,
        "max_items": 10,
        "token_budget": 800,
        "include_history": False,
    }, expect=(200,))
    ctx = json.loads(raw)
    S.packet_id = ctx.get("packet_id") or ctx.get("id")
    assert s == 200 and S.packet_id is not None, f"context request failed: {raw[:200]}"

    s, _ = req("GET", "/v1/context/cache/stats", expect=(200,))
    assert s == 200
    s, _ = req("POST", "/v1/context/cache/cleanup", {}, expect=(200, 204))
    assert s in (200, 204)

    # Feedback only valid if the packet actually contained items.
    items = ctx.get("items") or ctx.get("memories") or []
    if not items:
        print("  [SKIP] POST /v1/context/feedback (packet has 0 items)")
        return
    item_id = items[0].get("id") or items[0].get("memory_id")
    s, _ = req("POST", "/v1/context/feedback", {
        "packet_id": S.packet_id,
        "items": [{"context_item_id": item_id, "disposition": "used", "note": "relevant to the question"}],
    }, expect=(200, 201, 204))
    assert s in (200, 201, 204)


def test_review_workflows():
    print("\n=== 6. Review workflows ===")
    for path in [
        "/v1/lifecycle/proposals",
        "/v1/consolidation/proposals",
        "/v1/pruning/proposals",
    ]:
        s, _ = req("GET", path, expect=(200,))
        assert s == 200
    for path in [
        "/v1/lifecycle/proposals/generate",
        "/v1/consolidation/proposals/generate",
        "/v1/pruning/proposals/generate",
    ]:
        s, _ = req("POST", path, {}, expect=(200, 201))
        assert s in (200, 201)
    s, _ = req(
        "POST",
        "/v1/pruning/tombstones/00000000-0000-0000-0000-000000000000/restore",
        {"actor": "e2e_test"},
        expect=(200, 404),
    )
    assert s in (200, 404)


def test_maintenance():
    print("\n=== 7. Maintenance ===")
    s, _ = req("POST", "/v1/maintenance/run", {}, expect=(200, 201))
    assert s in (200, 201)
    s, _ = req("POST", "/v1/compaction/run", {
        "scope_type": "user",
        "scope_id": S.identity_id,
        "dry_run": True,
    }, expect=(200, 201))
    assert s in (200, 201)


def _copy_markdown_to_container(container_md: str) -> None:
    """The api reads paths from inside its container, not the host."""
    host_md = pathlib.Path(tempfile.gettempdir()) / _resolve_hermdoc()
    host_md.write_text(
        "# E2E test\n\nThis is a memory imported via the hermes markdown path.\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["docker", "cp", str(host_md), f"openbrain-api:{container_md}"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise FileNotFoundError(
            f"docker cp failed (rc={result.returncode}): {result.stderr.strip()}"
        )


def test_imports():
    print("\n=== 8. Imports ===")
    s, raw = req("GET", "/v1/imports/providers", expect=(200,))
    providers = json.loads(raw)
    assert s == 200
    assert isinstance(providers, list) and len(providers) >= 1, "no import providers listed"

    # Hermes markdown import — needs a file inside the api container.
    container_md = "/tmp/" + _resolve_hermdoc()
    try:
        _copy_markdown_to_container(container_md)
        s, _ = req("POST", "/v1/imports/hermes/markdown", {
            "path": container_md,
            "source": "hermes.user_memory",
            "dry_run": True,
        }, expect=(200, 201, 202))
        assert s in (200, 201, 202), "hermes markdown import failed"
    except FileNotFoundError:
        # docker CLI not available — skip this subtest gracefully
        print("  [SKIP] POST /v1/imports/hermes/markdown (docker CLI not available)")

    s, raw = req("POST", "/v1/imports/providers", {
        "provider": "mem0",
        "records": [{"content": "e2e record from mem0", "source": "mem0"}],
        "source_instance": "e2e-mem0",
        "dry_run": False,
    }, expect=(200, 201, 202))
    imp = json.loads(raw)
    S.import_run_id = imp.get("id") or imp.get("run_id")
    assert s in (200, 201, 202) and S.import_run_id, f"provider import failed: {raw[:200]}"

    if S.import_run_id:
        s, _ = req("POST", f"/v1/imports/{S.import_run_id}/seal",
                   {"actor": "e2e_test", "expected_records": 1}, expect=(200, 201, 204))
        assert s in (200, 201, 204)
        s, _ = req("POST", f"/v1/imports/{S.import_run_id}/rollback",
                   {"actor": "e2e_test", "reason": "e2e teardown"}, expect=(200, 201, 204))
        assert s in (200, 201, 204)


def test_auth():
    print("\n=== 9. Auth ===")
    # No key -> 401
    rq = urllib.request.Request(f"{URL}/stats")
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            s = r.status
    except urllib.error.HTTPError as e:
        s = e.code
    assert s == 401, f"expected 401 for no key, got {s}"

    # Bad key -> 401
    rq = urllib.request.Request(f"{URL}/stats", headers={"X-API-Key": "obviously-fake-key"})
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            s = r.status
    except urllib.error.HTTPError as e:
        s = e.code
    assert s == 401, f"expected 401 for bad key, got {s}"

    # /health stays unauthenticated
    rq = urllib.request.Request(f"{URL}/health")
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            s = r.status
    except urllib.error.HTTPError as e:
        s = e.code
    assert s == 200, f"expected 200 for /health without key, got {s}"


def test_summary():
    """Final tally, always last."""
    print(f"\n=== Summary ===\n  {S.passed} passed, {S.failed} failed")


# ---------------------------------------------------------------------------
# Standalone runner: ``python tests/e2e/test_api.py``. The pytest test
# functions above are the canonical entry point; this block just chains
# them so a developer can run the suite without installing pytest.
#
# The default rate limit in this stack is 120 req/60s. The suite makes
# about 40 requests in <10 seconds, so back-to-back runs will trip the
# limit unless each function is followed by a short sleep. The
# SLOW_DELAY default of 3 seconds is enough to keep two consecutive
# runs under the budget. Pass ``--slow 0`` to disable, or ``--slow 5``
# for a more conservative pace.
#
# CLI flags:
#   --slow    Sleep SLOW_DELAY seconds between test functions. Useful when
#             running the suite multiple times in succession against a
#             stack with strict per-IP rate limits (the default 120 req/60s
#             is easy to hit on a fast machine; the suite makes ~40
#             requests in <10s, so 3s between functions is enough to stay
#             under the limit). Pass a number to override the delay:
#             ``--slow 5`` sleeps 5 seconds between functions. Default: 3.0.
#   --url URL Override the api base url.
#   --key KEY Override the api key.
# ---------------------------------------------------------------------------
SLOW_DELAY = 0.0


def _parse_argv() -> None:
    global URL, KEY, HDR, SLOW_DELAY
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--slow":
            # numeric argument optional; default to 3s if just the flag
            try:
                SLOW_DELAY = float(args[i + 1]) if i + 1 < len(args) and not args[i + 1].startswith("--") else 3.0
                i += 1
            except ValueError:
                SLOW_DELAY = 3.0
        elif a == "--url" and i + 1 < len(args):
            URL = args[i + 1].rstrip("/")
            HDR = {"X-API-Key": KEY or "", "Content-Type": "application/json"}
            i += 1
        elif a == "--key" and i + 1 < len(args):
            KEY = args[i + 1]
            HDR = {"X-API-Key": KEY, "Content-Type": "application/json"}
            i += 1
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            sys.exit(2)
        i += 1


if __name__ == "__main__":
    _parse_argv()
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and name != "test_summary" and callable(fn):
            try:
                fn()
            except AssertionError as e:
                failures += 1
                print(f"  [FAIL] {name}: {e}")
            except Exception as e:
                failures += 1
                print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            if SLOW_DELAY > 0:
                time.sleep(SLOW_DELAY)
    # Also count step-level failures recorded by req() (the test functions
    # print FAIL but don't always raise). The summary prints both.
    test_summary()
    failures += S.failed
    sys.exit(0 if failures == 0 else 1)
