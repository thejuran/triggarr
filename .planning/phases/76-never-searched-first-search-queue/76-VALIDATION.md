---
phase: 76
slug: never-searched-first-search-queue
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 76 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `76-RESEARCH.md` § Validation Architecture (Nyquist Dimension 8).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) [VERIFIED: pyproject.toml] |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/test_search.py tests/test_state.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Lint gate** | `uv run ruff check triggarr/ tests/` (E,F,I,UP,B,SIM; line-length 120) |
| **Estimated runtime** | ~quick: a few seconds; full: tens of seconds (924-fn baseline) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_search.py tests/test_state.py -x -q` + `uv run ruff check triggarr/ tests/`
- **After every plan wave:** Run `uv run pytest tests/ -x -q` (full suite must stay green)
- **Before `/gsd:verify-work`:** Full suite green + `ruff check` clean + static guards: `! grep -rq "slice_batch" triggarr/ tests/` and `! grep -rq "_cursor" triggarr/state.py triggarr/search/engine.py`
- **Max feedback latency:** ~30 seconds

---

## Per-Requirement Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| QUEUE-01 | Searched-log persists per queue, oldest-first | unit + round-trip | `uv run pytest tests/test_state.py -k searched -x` | ❌ W0 |
| QUEUE-02 | Per-app key normalization; Sonarr composite distinguishes seasons | unit | `uv run pytest tests/test_search.py -k "prioritize and key" -x` | ❌ W0 |
| QUEUE-03 | Cursor fields removed; pre-upgrade file loads clean as everything-unsearched | unit (back-compat) | `uv run pytest tests/test_state.py -k "back_compat or legacy_cursor" -x` | ❌ W0 |
| QUEUE-04 | Never-searched-first in fetch order | unit | `uv run pytest tests/test_search.py -k "prioritize and unsearched_first" -x` | ❌ W0 |
| QUEUE-05 | Top-up oldest-searched-first | unit | `uv run pytest tests/test_search.py -k "prioritize and topup" -x` | ❌ W0 |
| QUEUE-06 | **Cold-start equivalence** (empty log == old slice_batch first cycle) | property/unit | `uv run pytest tests/test_search.py -k cold_start_equivalence -x` | ❌ W0 (LOAD-BEARING) |
| QUEUE-07 | All 6 sites use prioritize_batch; slice_batch gone | integration + static | `uv run pytest tests/test_search.py -k cycle -x` then `! grep -rq "slice_batch" triggarr/ tests/` | ❌ W0 |
| QUEUE-08 | Mark-on-attempt; failed search still logged | integration | `uv run pytest tests/test_search.py -k "mark_on_attempt" -x` | ❌ W0 |
| QUEUE-09 | Pass-complete clears log + bumps `*_pass` | unit + integration | `uv run pytest tests/test_search.py -k "pass_complete" -x` | ❌ W0 |
| QUEUE-10 | Prune-to-eligible drops departed items, preserves order | unit | `uv run pytest tests/test_search.py -k "prioritize and prune" -x` | ❌ W0 |
| QUEUE-11 | Commit only at cycle-end (single save_state) | integration | `uv run pytest tests/test_search.py -k "commit_at_cycle_end" -x` | partial (migrate assertion) |
| (invariant) | refresh-counts never reads/writes searched-log | invariant | `uv run pytest tests/test_refresh_counts.py -x` | ⚠️ exists (re-express, D-06) |
| (regression) | Existing cycle search-counts + history rows stay green | regression | `uv run pytest tests/test_search.py -x` | ✅ exists (migrate cursor asserts only) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Validation Strategy by Surface

1. **Pure `prioritize_batch` unit matrix (spec §8 — exhaustive):** cold-start; unsearched-first; top-up oldest-first; pass-completion (last unsearched ⇒ `pass_completed=True`, full log); mid-pass no-completion; prune (departed IDs dropped, survivor order kept); re-search recency (re-batched item → log tail); empty eligible ⇒ `([], [], False)`; eligible < N ⇒ all searched + pass completes; `key_fn` correctness (Sonarr S1/S2 distinct, Radarr/Lidarr int→str). Fully synchronous, no I/O, no mocks — fastest feedback loop.

2. **Cold-start behavior-equivalence (load-bearing, QUEUE-06):** dedicated test asserting `prioritize_batch(items, [], N, key_fn)[0] == slice_batch(items, 0, N)[0]` across representative inputs **while `slice_batch` still exists** (oracle comparison), PLUS a post-removal fixed-expectation variant so the guarantee survives `slice_batch`'s deletion.

3. **Per-app cycle integration (extend existing `run_*_cycle` tests):** two-cycle no-re-search-within-a-pass; new-item-jumps-the-line; mark-on-attempt (a `search_*`-raising item still in log next cycle); pass-reset bumps `*_pass` + clears log; fetch-failure ⇒ log untouched + `connected=False`; commit-at-cycle-end (state saved once, log + `*_pass` consistent). Run for all three apps.

4. **Back-compat state load (QUEUE-03):** load a pre-upgrade `state.json` with `missing_cursor`/`cutoff_cursor` and no searched-logs → loads clean, dispatch treats everything unsearched, leftover keys ignored + overwritten on next save. New test in `test_state.py`.

5. **Count-only queue-independence invariant (D-06):** re-express the 3 `test_refresh_counts.py` "cursor unchanged" tests as "searched-log unchanged after refresh-counts" for Radarr/Sonarr/Lidarr.

---

## Wave 0 Requirements

- [ ] New `prioritize_batch` unit-test suite in `tests/test_search.py` (10-case matrix per spec §8) — covers QUEUE-02/04/05/09/10 + key_fn
- [ ] Cold-start-equivalence test (oracle vs `slice_batch`, then fixed-expectation) — covers QUEUE-06
- [ ] Back-compat state-load test in `tests/test_state.py` — covers QUEUE-03
- [ ] Searched-log round-trip + default-state tests in `tests/test_state.py` — covers QUEUE-01
- [ ] Re-expressed queue-independence tests in `tests/test_refresh_counts.py` (×3 apps) — covers the invariant (D-06)
- [ ] Per-app cycle-integration extensions (mark-on-attempt, pass-reset, new-item-jumps-line, commit-at-cycle-end) — covers QUEUE-07/08/09/11
- [ ] Static guard: no `slice_batch` / no `*_cursor` survivors (grep assertion / verify-work check)

*Framework install: none needed — pytest-asyncio auto mode already configured. No new test dependencies.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live never-searched-first behavior over multiple real cycles against a deployed NAS instance | QUEUE-04/05/09 | Requires real *arr instances with a large wanted list and multiple scheduled cycles to observe pass progression | Milestone-end NAS walkthrough: trigger searches, observe logs show unsearched-first ordering, then pass-completion INFO line, then re-search of the same items next pass |

*All unit/integration behaviors have automated verification; only multi-cycle live progression is walkthrough-observed.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
