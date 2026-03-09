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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 8 | 18 | Initial build, all phases sequential |
| v1.1 | 4 | 5 | Same-day ship, lightweight phases |
| v1.2 | 4 | 8 | Deep review convention established |
| v2.0 | 8 | 18 | Decimal phases for inserted work, formal deep review phases |

### Cumulative Quality

| Milestone | Tests | LOC (Python) | Zero-Dep Additions |
|-----------|-------|-------------|-------------------|
| v1.0 | 115 | ~3,672 | 0 |
| v1.1 | 145 | ~4,100 | 0 |
| v1.2 | 174 | ~5,225 | 0 |
| v2.0 | 220+ | ~8,010 | 0 (entire milestone) |

### Top Lessons (Verified Across Milestones)

1. Deep code review as a formal phase catches real bugs — validated in v1.2 (7 fixes) and v2.0 (20 fixes)
2. Zero-dependency policy keeps the stack simple and Docker images small
3. Fix test breakage immediately — deferred test debt compounds across phases
