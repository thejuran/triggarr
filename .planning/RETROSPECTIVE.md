# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v2.0 — Closed-Loop Tracking

**Shipped:** 2026-03-09
**Phases:** 8 | **Plans:** 18

### What Was Built
- Closed-loop download tracking pipeline (history polling, correlation, outcome state machine)
- Dashboard stats cards with effectiveness rates, lifetime counters, time-to-grab metric
- Production hardening suite (rate limiting, health check, graceful shutdown, CSRF)
- Deep code review with 20 security and quality fixes
- Full project rename from Fetcharr to Triggarr

### What Worked
- Phase dependency graph allowed parallel execution of Phase 18 and 19
- Deep review as dedicated phases (20.1, 20.2) caught real bugs before shipping
- Decimal phase numbering (20.1, 20.2) cleanly inserted review work without renumbering
- Zero new PyPI dependencies for the entire milestone — existing stack + stdlib sufficient
- Verification reports caught ruff violations and edge cases that tests alone missed

### What Was Inefficient
- Some phases (19, 20) had plans created on-the-fly without formal PLAN.md files, making verification harder to trace
- test_search.py test failures from Phase 20.1 sanitization change were deferred across 3 subsequent phases instead of being fixed immediately
- Rename phase (22) required touching 55+ files — could have been done earlier to avoid accumulating "fetcharr" references

### Patterns Established
- Deep code review as a dedicated phase pair (security + quality) before shipping
- Double-checked locking pattern for rate limiting in async contexts
- frozenset allowlists for dynamic SQL column references
- Type-based exception sanitization (_sanitize_exc) to avoid information leakage

### Key Lessons
1. Fix test failures immediately when behavior changes — deferring creates compounding context cost across phases
2. Project renames are easier when done early (fewer files to update) or as a dedicated final phase with no other work mixed in
3. Deep review as a formal phase catches real bugs — the 20 fixes weren't cosmetic

### Cost Observations
- Model mix: ~70% sonnet (execution), ~30% opus (planning, verification, audit)
- Notable: 18 plans across 8 phases in 12 days; deep review phases were the slowest due to investigation time

---

## Milestone: v2.1 — Harden & Fix

**Shipped:** 2026-03-09
**Phases:** 2 | **Plans:** 2

### What Was Built
- Configurable config directory via TRIGGARR_CONFIG_DIR env var
- ROOT_PATH support for reverse proxy deployments
- Config path validation (reject relative/traversal paths)
- Temp file cleanup on os.replace failure

### What Worked
- Small, focused milestone (2 phases) shipped quickly
- Each fix was self-contained with targeted tests

### What Was Inefficient
- Nothing notable — milestone was appropriately scoped

### Patterns Established
- `get_config_dir()` function for testable env var reading
- `request.url_for` everywhere for root_path consistency

### Key Lessons
1. Deployment hardening works best as a focused milestone after initial shipping reveals real-world issues
2. Small milestones (2-3 phases) are efficient for targeted fixes

### Cost Observations
- Model mix: ~80% sonnet, ~20% opus
- Notable: 2 plans in 1 day — minimal overhead

---

## Milestone: v2.2 — Skip Unreleased Media

**Shipped:** 2026-03-09
**Phases:** 4 | **Plans:** 5

### What Was Built
- `skip_unreleased` config field with filter_unreleased_movies() pure function
- Settings UI checkbox with conditional engine pipeline wiring
- Dashboard eligible/total display with amber skip badge
- Code review fixes: badge math, template wrapping, print→loguru, Callable annotation

### What Worked
- TDD approach (RED/GREEN commits) produced clean, testable code from the start
- Phase dependency chain (25→26→27→28) ensured each layer was solid before building on it
- Code review as a dedicated Phase 28 caught the badge math bug before shipping
- Nyquist validation filled retroactively — all 4 phases had tests already, just needed VALIDATION.md updates

### What Was Inefficient
- Phase 27 SUMMARY.md didn't record requirements-completed frontmatter (DASH-01, DASH-02) — caught during audit
- Phase 28 was added mid-milestone for code review findings — could have been caught by running /deep-review earlier

### Patterns Established
- `missing_monitored` intermediate count for accurate badge math (monitored vs raw total)
- Conditional pipeline filter gated by config field: `if settings.general.flag: list = filter(list)`
- Boolean checkbox pattern: `form.get('field') == 'on'` for HTML checkboxes

### Key Lessons
1. Always populate requirements-completed in SUMMARY frontmatter — audit cross-reference depends on it
2. Running deep review mid-milestone (not just at the end) catches bugs earlier and scopes fix phases tighter
3. Pure functions (filter_unreleased_movies) are easy to test and verify — keep pipeline steps pure

### Cost Observations
- Model mix: ~75% sonnet (execution, validation), ~25% opus (audit, completion)
- Notable: 5 plans in 1 day; the entire feature was self-contained and well-defined

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 8 | 18 | Initial build, all phases sequential |
| v1.1 | 4 | 5 | Same-day ship, lightweight phases |
| v1.2 | 4 | 8 | Deep review convention established |
| v2.0 | 8 | 18 | Decimal phases for inserted work, formal deep review phases |
| v2.1 | 2 | 2 | Small focused milestone for deployment fixes |
| v2.2 | 4 | 5 | TDD approach, code review as dedicated phase |

### Cumulative Quality

| Milestone | Tests | LOC (Python) | Zero-Dep Additions |
|-----------|-------|-------------|-------------------|
| v1.0 | 115 | ~3,672 | 0 |
| v1.1 | 145 | ~4,100 | 0 |
| v1.2 | 174 | ~5,225 | 0 |
| v2.0 | 220+ | ~8,010 | 0 (entire milestone) |
| v2.1 | 270 | ~8,322 | 0 |
| v2.2 | 302 | ~8,964 | 0 |

### Top Lessons (Verified Across Milestones)

1. Deep code review as a formal phase catches real bugs — validated in v1.2 (7 fixes), v2.0 (20 fixes), and v2.2 (5 fixes)
2. Zero-dependency policy keeps the stack simple and Docker images small
3. Fix test breakage immediately — deferred test debt compounds across phases
4. Always populate requirements-completed in SUMMARY frontmatter — audit depends on it (v2.2)
5. Pure functions are easy to test and verify — keep pipeline steps pure (v2.2)
