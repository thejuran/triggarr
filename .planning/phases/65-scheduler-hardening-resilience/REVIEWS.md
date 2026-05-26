# Phase 65 — External Reviews

## Codex Adversarial Review (2026-05-25)

**Target:** `.planning/phases/65-scheduler-hardening-resilience/65-{01..04}-PLAN.md` (content review)
**Reviewer:** Codex (via `/codex:adversarial-review`)
**Verdict:** needs-attention

**Summary:** The plans miss the real failure paths they claim to harden, and one plan cannot pass its own verification as written.

---

### Findings

#### [HIGH] SAFETY-03 counter misses real *arr outage failures
**Location:** `65-02-PLAN.md:379-393`

The planned counter increments only when `make_search_job` catches a narrow-tuple exception. That is not the path real top-level *arr outages usually take: current `run_radarr_cycle`, `run_sonarr_cycle`, and `run_lidarr_cycle` catch `httpx.HTTPError`/`pydantic.ValidationError`, mark the instance disconnected, and return state instead of raising. The proposed tests mock `run_radarr_cycle` itself to raise, so they validate a synthetic path.

**Impact:** Under a sustained Radarr/Sonarr/Lidarr outage, the scheduler can treat the cycle as successful, save state, reset the counter to 0, and never escalate to ERROR.

**Recommendation:** Redesign the counter around an explicit cycle outcome, or raise a typed top-level `CycleAborted` from engine cycles. Add tests that trigger failures inside the real engine/client calls, not by patching the whole cycle function to raise.

---

#### [HIGH] Persistence failures are treated like transient search failures
**Location:** `65-02-PLAN.md:368-393`

The same narrow tuple catches `OSError` around both `cycle_fn(...)` and `save_state(...)`. In the current scheduler, state is mutated before `save_state` runs; if disk-full, permission, or filesystem errors happen during persistence, the plan logs through the warning/error threshold counter and returns.

**Impact:** Can leave in-memory state and durable state diverged, with duplicate or lost work after restart. This is a durability failure, not an expected external-service blip.

**Recommendation:** Split cycle execution from persistence. Handle `save_state` failures separately, log at ERROR immediately, avoid resetting success counters, and either propagate to APScheduler or enter an explicit degraded state.

---

#### [HIGH] The 60s shutdown drain conflicts with the recommended Docker deployment
**Location:** `65-03-PLAN.md:44-57`

The plan extends shutdown lock drain to 60s and claims a real `docker stop` will show the holder warning. The repo recommends Docker Compose, but `docker-compose.yml` defines no `stop_grace_period`; Docker's default stop window can kill the process before this 60s timeout fires.

**Impact:** In the recommended Docker deployment, a stuck cycle may produce no holder warning and may skip client/database cleanup entirely.

**Recommendation:** Align the drain design with deployment reality: add/document `stop_grace_period` greater than the drain timeout, make the timeout configurable by deployment, or emit holder identity immediately on shutdown before waiting.

---

#### [MEDIUM] TEST-04 proves MockTransport behavior, not production close behavior
**Location:** `65-04-PLAN.md:123-144`

Both in-flight close tests use `httpx.MockTransport`, which bypasses the real async connection pool and socket teardown used by production `ArrClient`. The tests can pass while a real TCP request behaves differently during `AsyncClient.aclose()`. The variant also accepts RuntimeError, cancellation, HTTP errors, or clean completion, so it only proves the mock path does not hang.

**Impact:** Test passes do not provide confidence that production close behavior is actually safe.

**Recommendation:** Keep MockTransport as a unit test if useful, but satisfy TEST-04 with a local asyncio TCP/HTTP server or ASGI transport path that exercises the production `AsyncHTTPTransport` close behavior under an in-flight request.

---

#### [MEDIUM] 65-01 cannot pass ruff with the planned unused import
**Location:** `65-01-PLAN.md:240-246`

Task 2 tells the implementer to add `import time` in 65-01 solely because 65-03 will use it later. No 65-01 code uses `time`, but the same task requires `uv run ruff check triggarr/search/scheduler.py tests/test_scheduler.py`. With ruff F401 enabled, this plan fails its own verification before 65-03 lands.

**Impact:** 65-01 fails its own acceptance gate; phases are not independently executable as written.

**Recommendation:** Move the `time` import and its acceptance assertion into 65-03, or land the lock-holder code in the same task that introduces the import.

---

### Next Steps

- Rework SAFETY-03 around real engine outcomes and separate persistence failures from transient cycle failures.
- Revise RES-01 to match Docker stop-grace behavior before claiming graceful shutdown coverage.
- Replace the TEST-04 proof with a real transport/socket close test.
- Fix 65-01 import sequencing so each plan can pass independently.
