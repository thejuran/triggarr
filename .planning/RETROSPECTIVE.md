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

## Milestone: v2.3 — Multi-Instance & Tag Filtering

**Shipped:** 2026-03-14
**Phases:** 12 | **Plans:** 15

### What Was Built
- Multi-instance support: named Radarr/Sonarr instances with independent config, state, scheduling
- Per-instance tag-based search filtering (missing and cutoff queues)
- Auto-migration from v2.2 flat config to v2.3 nested TOML format
- Instance management UI (add/edit/remove/enable/disable) with tag autocomplete
- Dashboard enhancements: health summary card, tag warning badges, instance stats filter
- GitHub release update notification in nav bar
- Dismissible migration banner for upgrade awareness
- Deep review fixes: XSS, CSRF, version parsing, input validation hardening
- 466 tests (up from 302), 15,079 LOC (up from 8,964)

### What Worked
- Milestone audit after initial phases (33-39) caught 7 requirement gaps early — led to phases 40-44
- Deep review as final phase caught 8 real issues before release
- TDD approach in most plans caught regressions immediately
- Context discussion workflow (discuss-phase) captured user decisions that guided planning accurately
- Gap-closure phases (40-44) cleanly addressed audit findings without scope creep

### What Was Inefficient
- Phases 37-39 were executed as GSD slices outside the planning system, requiring gap-closure phases to finish incomplete work
- Some plans had to be revised due to planner not reading existing code patterns carefully enough
- The _update_info module-level mutable dict pattern (scheduler → routes) inverts the layer dependency — deferred to next milestone

### Patterns Established
- Milestone audit → gap-closure phases as a formal quality gate
- Deep review findings → dedicated bug-fix phase with exact patches
- Instance filter dropdown with `hx-include` for htmx poll persistence
- `HX-Request` header check as CSRF mitigation for htmx DELETE endpoints

### Key Lessons
1. Audit before completing milestone — found 7 gaps that would have shipped incomplete
2. Gap-closure phases are quick when the audit precisely identifies what's missing
3. Module-level mutable state shared between modules is a code smell — use `app.state` instead
4. Pre-release version strings need robust parsing (regex fallback, not just int())
5. Always clear derived state (tag_warnings) on early-return error paths

### Cost Observations
- Model mix: ~60% opus (execution), ~30% sonnet (verification, checking), ~10% haiku (exploration)
- Sessions: ~5 sessions across 5 days
- Notable: 12 phases in 5 days; audit-driven gap closure was efficient

---

## Milestone: v2.4 — Community Polish & Test Hardening

**Shipped:** 2026-04-09
**Phases:** 3 | **Plans:** 6

### What Was Built
- Community health files: CONTRIBUTING.md, SECURITY.md (7-mechanism model summary), MIT LICENSE
- GitHub templates: bug report + feature request YAML forms, PR template, issue config with Discussions link
- Repo metadata: 7 GitHub topics, Discussions enabled
- 45 new unhappy-path tests: connection failures, bad API responses, corrupt state/config, search edge cases
- Test count: 466 → 606 (+140 tests)

### What Worked
- Milestone audit passed clean (26/26 requirements, 4/4 flows) — no gap-closure phases needed
- Test hardening phases (46, 47) were highly parallelizable since they depended on Phase 45 but not each other
- Research phase for test hardening identified exact gaps in existing coverage, avoiding duplicate tests
- Community health files were straightforward — clear requirements, no ambiguity

### What Was Inefficient
- Phase 47 ROADMAP.md still showed `[ ]` instead of `[x]` after execution — roadmap_complete wasn't updated
- Phase 46 VALIDATION.md not updated to nyquist_compliant after execution
- Summary one-liner extraction failed for all 6 summaries — gsd-tools summary-extract didn't parse these SUMMARY formats

### Patterns Established
- Test-only milestones are efficient — no source code changes means no risk of regressions
- Community health files as a dedicated phase with requirement-per-file granularity
- Unhappy-path test organization: one plan per failure domain (connection, API, state, search)

### Key Lessons
1. Test-only milestones can ship quickly — 6 plans in one session when no source code changes are needed
2. Community health files benefit from YAML form templates over markdown templates — structured input, better UX
3. Summary one-liner extraction depends on consistent SUMMARY.md format — current format diversity breaks the tool

### Cost Observations
- Model mix: ~60% opus (execution), ~40% sonnet (planning, verification)
- Sessions: 1 session
- Notable: Entire milestone completed in a single session — test-only work is fast

---

## Milestone: v2.5 — Dashboard UI Refresh

**Shipped:** 2026-04-13
**Phases:** 6 | **Plans:** 15

### What Was Built
- Design-system foundations: focus-visible rings, reduced-motion, Geist Mono, elevation tokens
- Sticky nav with active-tab underline and pulsing update dot
- Compact health strip + hero Grab Rate card with per-app bars
- Redesigned app cards with connection pills, danger stripes, hover elevation, 3-col grid
- Terminal-style application log with TAILING indicator and expandable bottom pane
- Sticky Recent Activity rail with timeline, outcome pills, LIVE indicator

### What Worked
- AIDesigner HTML artifacts as design spec worked well for pixel-exact implementation
- 6 phases shipped in 4 days with minimal rework
- Deep code review caught 26 real issues across 3 rounds

### What Was Inefficient
- Summary one-liner extraction still failing due to format inconsistency across summaries

### Patterns Established
- AIDesigner HTML artifacts as hard design spec for UI phases
- Vanilla JS for interactive components (no framework dependency)
- Conditional stat tiles (only show when respective app is enabled)

### Key Lessons
1. AIDesigner + GSD workflow: generate HTML artifacts first, use as binding spec for implementation
2. Vanilla JS interactive components avoid framework dependency for a server-rendered htmx app
3. Deep review across 3 rounds catches progressively deeper issues

### Cost Observations
- Model mix: ~50% opus (planning, review), ~50% sonnet (execution)
- Sessions: ~3 sessions across 4 days

---

## Milestone: v2.6 — Built-In Authentication

**Shipped:** 2026-04-15
**Phases:** 6 | **Plans:** 16

### What Was Built
- Deny-all auth middleware with Forms/Basic/External/Disabled modes
- First-run setup flow with credential creation and auto-generated API key
- Forms login with signed session cookies (30-day expiry) and ?next= redirect
- Settings security section with password change, auth mode switching, API key management
- 109 auth-specific tests (805 total) covering all middleware paths and edge cases
- Security hardening: login rate limiter, CSP headers, SSRF IPv6 hardening, log sanitization

### What Worked
- TDD approach in every phase caught integration bugs early (e.g., itsdangerous 2.x mock target)
- Shield security scan as input to Phase 59 provided structured, actionable findings
- Code review → fix cycles (multiple rounds in Phase 59) drove quality up significantly
- Design spec upfront (`built-in-auth-design.md`) prevented scope creep across 6 phases
- bcrypt + itsdangerous: lightweight deps that handle auth correctly without over-engineering

### What Was Inefficient
- SUMMARY.md requirements_completed frontmatter was only populated in 1 of 16 summaries — audit had to rely on VERIFICATION.md cross-reference
- Phase 59 was added mid-milestone after Shield scan — correct decision, but broke the original 54-58 scope
- Visual verification (UI-01/UI-02/UI-03) couldn't be automated — 3 requirements left as human_needed
- Nyquist VALIDATION.md files for phases 54-56 were generated during planning but never updated during execution

### Patterns Established
- Shield security scan → dedicated hardening phase as a quality gate before milestone close
- In-memory rate limiter with LRU eviction for single-user homelab tools
- API key as boolean in template context (never raw key) to prevent accidental exposure
- `_sync_auth_state` pattern: centralized auth state refresh called from all config-mutating endpoints

### Key Lessons
1. Shield scan before milestone close finds real vulnerabilities — Phase 59's 11 findings were all actionable
2. In-memory rate limiters need eviction caps — unbounded dicts are a DoS vector
3. Always populate SUMMARY.md requirements_completed — audit 3-source cross-reference breaks without it
4. Visual verification requirements should be flagged early as human-only — automated verification can't assess pixel fidelity
5. Security-hardening phases are efficient when findings are structured (SHIELD-001 through SHIELD-011 format)

### Cost Observations
- Model mix: ~40% opus (planning, verification, audit), ~60% sonnet (execution, code review)
- Sessions: ~4 sessions across 2 days
- Notable: 16 plans in 2 days; TDD approach kept rework minimal despite complex auth logic

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
| v2.3 | 12 | 15 | Milestone audit + gap-closure pattern, deep review as final phase |
| v2.4 | 3 | 6 | Test-only milestone, community health files, single-session ship |
| v2.5 | 6 | 15 | AIDesigner HTML artifacts as design spec, vanilla JS components |
| v2.6 | 6 | 16 | Shield scan → hardening phase, TDD auth, in-memory rate limiter |

### Cumulative Quality

| Milestone | Tests | LOC (Python) | Zero-Dep Additions |
|-----------|-------|-------------|-------------------|
| v1.0 | 115 | ~3,672 | 0 |
| v1.1 | 145 | ~4,100 | 0 |
| v1.2 | 174 | ~5,225 | 0 |
| v2.0 | 220+ | ~8,010 | 0 (entire milestone) |
| v2.1 | 270 | ~8,322 | 0 |
| v2.2 | 302 | ~8,964 | 0 |
| v2.3 | 466 | ~15,079 | 0 (pydantic-settings added for config, already in deps) |
| v2.4 | 606 | ~15,979 | 0 |
| v2.5 | 668 | ~17,361 | 0 |
| v2.6 | 805 | ~20,225 | 2 (bcrypt, itsdangerous — necessary for auth) |

### Top Lessons (Verified Across Milestones)

1. Deep code review as a formal phase catches real bugs — validated in v1.2 (7 fixes), v2.0 (20 fixes), v2.2 (5 fixes), v2.5 (26 fixes)
2. Zero-dependency policy keeps the stack simple and Docker images small — v2.6 added 2 deps (bcrypt, itsdangerous) only because auth requires real crypto
3. Fix test breakage immediately — deferred test debt compounds across phases
4. Always populate requirements-completed in SUMMARY frontmatter — audit depends on it (v2.2, v2.6)
5. Pure functions are easy to test and verify — keep pipeline steps pure (v2.2)
6. Shield security scan before milestone close finds real vulnerabilities — v2.6 hardening phase addressed all 11 findings
7. AIDesigner HTML artifacts as binding spec for UI phases prevents design drift (v2.5, v2.6)
