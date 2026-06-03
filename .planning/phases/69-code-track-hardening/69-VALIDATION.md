---
phase: 69
slug: code-track-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 69 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `69-RESEARCH.md` → ## Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (≥9.0.3) + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_scheduler.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~quick: a few seconds · full: 965+ tests |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_scheduler.py -x -q` (SAFETY-03 tasks) or the relevant targeted subset.
- **After every plan wave:** `uv run pytest tests/ -x -q` + `uv run ruff check triggarr/ tests/`.
- **Before `/gsd:verify-work`:** Full suite green, ruff clean, `gitleaks git .` → `leaks found: 0` with no "Invalid entry" warnings, pip-audit → `CLEAN`, `grep -rn "TODO(SAFETY-03)" triggarr/` → nothing.
- **Max feedback latency:** seconds (quick) to ~1 min (full suite).

---

## Per-Task Verification Map

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| CHARD-02 | `search_now` failure increments `app.state.search_failures[job_id]` | unit | `uv run pytest tests/test_scheduler.py -k "search_now and failure" -x` | ❌ Wave 0 | ⬜ pending |
| CHARD-02 | `search_now` success resets the counter | unit | `uv run pytest tests/test_scheduler.py -k "search_now" -x` | ❌ Wave 0 | ⬜ pending |
| CHARD-02 | `TODO(SAFETY-03)` removed from scheduler | source | `grep -rn "TODO(SAFETY-03)" triggarr/` returns nothing | n/a | ⬜ pending |
| CHARD-03 | All 6 existing scheduler failure-counter tests still pass (none deleted/skipped) | unit | `uv run pytest tests/test_scheduler.py -x -q` | ✅ (6 tests) | ⬜ pending |
| CHARD-04 (starlette) | Full test suite green after the fastapi/starlette bump | integration | `uv run pytest tests/ -x -q` | ✅ | ⬜ pending |
| CHARD-04 (starlette) | pip-audit clean after bump | audit | `uv export --no-dev --no-emit-project --format requirements-txt > /tmp/r.txt && uv run pip-audit -r /tmp/r.txt --format json` → no vulns | ✅ (script) | ⬜ pending |
| CHARD-04 (gitleaks) | gitleaks reports 0 leaks, no "Invalid entry" warnings | tooling | `gitleaks git . --no-banner --redact 2>&1 \| grep -E "Invalid .gitleaksignore entry\|leaks found"` | ✅ (gitleaks 8.30.1) | ⬜ pending |
| CHARD-01 | `.orchestrator.json` is git-ignored; no untracked/accidentally-tracked artifact remains | tooling | `git check-ignore .orchestrator.json` returns the path AND `git status --porcelain \| grep -q "\.orchestrator\.json"` returns nothing | ✅ (git) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scheduler.py` — add `test_search_now_failure_counter_increment` and
      `test_search_now_failure_counter_resets_on_success` (CHARD-03). Pattern: build a test app with a
      MockTransport that fails, call the `search_now` route (or `_run_one_cycle` directly), assert
      `app.state.search_failures[job_id]` increments / resets. MUST NOT patch `_record_cycle_failure`
      or `_evaluate_cycle_outcome` — exercise the real counter logic end-to-end as the existing tests do.

*All other phase behaviors reuse existing infrastructure (pytest, gitleaks, pip-audit, git, ruff).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Manual + scheduled search both work live on the deployed branch build | CHARD-02 | End-to-end behavior against real *arr instances; verifies counter parity in production | Milestone-end NAS walkthrough: trigger a manual `/search-now` and observe a scheduled cycle; confirm both increment/reset the failure counter identically (escalation logging parity). |

---

## Validation Sign-Off

- [ ] All tasks have an automated verify command or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers the missing CHARD-02/03 test stubs
- [ ] No watch-mode flags
- [ ] Feedback latency < ~60s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
