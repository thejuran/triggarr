# Phase 67: Observability & CSRF Test Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 67-observability-csrf-test-coverage
**Areas discussed:** RES-02 granularity, RES-02 write site, RES-03 cache invalidation, TEST-01 depth

---

## RES-02 — "Last successful search" granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Per-instance success ts | New `last_success` ISO ts on per-(app,instance) AppState, written on connected→True, rendered per card, stale at >2× that instance's interval. | ✓ |
| Per-app-type aggregate | One "last successful" per app type (max across instances), surfaced once per type in the stats/health strip. | |
| Both: per-instance + rollup | Per-instance on cards AND an app-type rollup in the health strip. | |

**User's choice:** Per-instance success timestamp (Recommended).
**Notes:** Each dashboard card already IS an app-type instance, so per-instance satisfies ROADMAP's "per app type" while being strictly more informative in multi-instance setups. Per-app-type rollup noted as a deferred idea.

---

## RES-02 — Where the timestamp gets written

| Option | Description | Selected |
|--------|-------------|----------|
| In engine, beside last_run | Set `ist["last_success"]` at the same success point as `connected=True` / `last_run` in each cycle fn. Single source of truth; manual search_now updates it too. | ✓ |
| In scheduler _evaluate_cycle_outcome | Write in scheduler's success branch. But manual search_now bypasses that helper (existing TODO), so manual successes wouldn't update it. | |

**User's choice:** In engine, beside last_run (Recommended).
**Notes:** Manual `search_now` calls the cycle fn directly and bypasses `_evaluate_cycle_outcome`, so writing in the engine is the only site that covers both scheduled and manual successes. `last_run` = last attempt; `last_success` = last connected-True cycle.

---

## RES-03 — Tag cache invalidation scope on config save

| Option | Description | Selected |
|--------|-------------|----------|
| Per-instance key, targeted invalidation | Cache keyed (app,instance); on save, invalidate only instances whose url/api_key/tags changed. | ✓ |
| Per-instance key, blanket invalidation on any save | Same cache, but any settings POST clears the whole tag cache. Simpler, more refetch churn. | |

**User's choice:** Per-instance key, targeted invalidation (Recommended).
**Notes:** Matches ROADMAP "invalidate the cache for that instance." Acceptable fallback if the changed-instance diff is awkward in the save handler: invalidate all entries present in the new config (still per-instance keyed). 1h TTL using `time.monotonic()` (not wall-clock).

---

## TEST-01 — OriginCheckMiddleware test depth

| Option | Description | Selected |
|--------|-------------|----------|
| Add the named gaps + document behavior | Add the 5 ROADMAP scenarios; pin current netloc-vs-host behavior with comments; do NOT change middleware in a test-only requirement. | ✓ |
| Tests + harden middleware if gaps found | Same tests, but fix the middleware if scheme/port reveals a real bypass. | |

**User's choice:** Add the named gaps + document behavior (Recommended).
**Notes:** Verified 2026-05-31 by simulating the middleware's `urlparse(origin).netloc != host` logic:
- Scheme mismatch (`https://testserver` vs host `testserver`) → **ALLOW** (scheme ignored; only netloc compared). NOT a bypass in the single-origin threat model — test pins ALLOW with an explanatory comment.
- Cross-origin (`evil.com`) → REJECT. Suffix spoof (`testserver.evil.com`) → REJECT. Port mismatch (`:8080` vs none) → REJECT.
Conclusion: no real vuln, so test-only scope holds; middleware unchanged. Hardening-to-compare-scheme noted as a deferred idea (revisit only if multi-origin support lands).

---

## Claude's Discretion

- Threading mechanism for the tag cache into engine cycle fns (resolver callable vs cache handle vs app.state passthrough) — planner picks least-coupling option.
- Exact amber stale-flag markup on the card (must reuse existing `bg-amber-500/15 text-amber-400` tokens).
- Whether the changed-instance diff for invalidation lives inline in the save handler or in a small helper.

## Deferred Ideas

- Per-app-type rollup of last-successful-search (in addition to per-card).
- Scheduler job dashboard (OBS-01, already a deferred STATE.md item).
- Hardening OriginCheck to compare scheme (no vuln today; revisit if multi-origin support is added).
- Negative/failure caching of `get_tags()` results (explicitly avoided — only successful fetches cached).
