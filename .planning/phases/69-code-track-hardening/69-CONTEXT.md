# Phase 69: Code-track hardening - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the curated known code-track items and **every Phase-68 FOLD-IN finding**, then prove the
fixes. Scope is fixed by the gate artifact: the four `P68-FI-NNN` rows in
`.planning/phases/68-code-track-hostile-reader-discovery/68-FINDINGS.md` → `## Fold-In Summary`,
mapped to CHARD-01..04:

- **CHARD-01** ← P68-FI-004: `.orchestrator.json` git-ignore + repo-hygiene audit-and-close.
- **CHARD-02** ← P68-FI-003: SAFETY-03 manual/scheduled failure-counter unification; remove the
  `# TODO(SAFETY-03)` at `scheduler.py:~325`.
- **CHARD-03**: a test covering manual-search failure increment/reset (proves CHARD-02); no existing
  scheduler failure-counter test deleted or skipped.
- **CHARD-04**: every fold-in finding fixed (P68-FI-001 broken `.gitleaksignore`, P68-FI-002
  `starlette` CVE) ; every parked finding already recorded with rationale in the findings artifact.

This phase **writes source fixes**. It does NOT re-run the hostile discovery pass (that was Phase 68)
and does NOT fold in the pre-parked config-knob UI debt (DEBT-03/06/07/08, UI-01..03 — spec D-5).
Presentation/docs work is Phase 70/71, out of scope here.
</domain>

<decisions>
## Implementation Decisions

### SAFETY-03 failure-counter unification (CHARD-02 / P68-FI-003)
- **D-01:** Extract a **shared `_run_one_cycle(app, app_name, instance_name)` helper** that both the
  scheduled `job()` closure in `make_search_job` and the manual `search_now` route call. Both paths
  must share: failure-counter increment/reset semantics (`app.state.search_failures` via the existing
  `_record_failure`/reset helpers, driven by the engine's `connected` flag) **and** holding
  `app.state.search_lock` for the full cycle + state-save. This is the spec's explicitly preferred
  shape (design spec §3.1 + the SAFETY-03 risk-mitigation row: "extract a shared helper used by both
  paths"). Preferred over routing `search_now` through `make_search_job` because the manual path
  should NOT inherit the APScheduler-job wrapper semantics (job_id provenance, scheduler logging) —
  only the cycle+counter+lock core.
- **D-02:** Remove the `TODO(SAFETY-03)` comment at `scheduler.py:~325` and the bypass note at
  `:342` once the manual path is unified. `grep -rn "TODO(SAFETY-03)" triggarr/` must return nothing.
- **D-03:** Preserve all existing scheduled-path behavior exactly — the scheduled `job()` outcome is
  still derived from `connected`, OSError/persistence still in their dedicated try/except blocks
  (SAFETY-03 Codex findings 1 & 2). The refactor is a **mechanical extraction**, not a redesign of
  the counter logic.

### CHARD-03 covering test
- **D-04:** Add a test (e.g. `test_search_now_failure_counter_increment` + a reset assertion) to
  `tests/test_scheduler.py` proving a failing manual `search_now` **increments**
  `app.state.search_failures[job_id]` and a subsequent success **resets** it — identical to the
  scheduled path. **No existing scheduler failure-counter test may be deleted or skipped**
  (CHARD-03 hard bar). Run both old and new: `uv run pytest tests/test_scheduler.py -x`.

### starlette CVE remediation (CHARD-04 / P68-FI-002)
- **D-05:** Fix `starlette@0.52.1 → PYSEC-2026-161` by **raising the `fastapi` pin** to a release whose
  resolved `starlette` is ≥1.0.1 (single transitive owner, cleanest). **Fallback:** add a direct
  `starlette>=1.0.1` constraint in `pyproject.toml` only if no acceptable fastapi release resolves
  starlette ≥1.0.1. Then `uv lock` and re-audit.
- **D-06:** The starlette 0.x→1.x major is a **breakage-risk gate**: confirm no API breakage by
  running the **full** test suite (965+ tests) green and ruff clean after the bump, not just the
  audit. If the major introduces breakage, surface it during planning/execution rather than pinning
  around it silently.

### .gitleaksignore repair (CHARD-04 / P68-FI-001)
- **D-07:** Convert `.gitleaksignore` to **gitleaks-8.x fingerprint entries**
  (`commitSHA:filepath:rule:line`) for the 4 test-fixture dummy-key locations, keeping the allowlist
  in the **existing `.gitleaksignore` file** rather than introducing a new `gitleaks.toml` (minimize
  new config surface; the file already exists and is honored-by-default). Goal: `gitleaks git .`
  emits **no** "Invalid .gitleaksignore entry" warnings and reports `leaks found: 0` (or only the
  intended allowlisted fingerprints).
- **D-08:** Generate the fingerprints from a real gitleaks run (don't hand-fabricate SHAs) so they
  match what 8.30.x actually computes. Tuning `generic-api-key` to stop matching planning-doc prose
  is **optional/nice-to-have**, not required — the hard requirement is "no Invalid-entry warnings +
  the 4 test fixtures suppressed."

### CHARD-01 repo-hygiene audit-and-close (P68-FI-004)
- **D-09:** Add `.orchestrator.json` (the confirmed gap) to `.gitignore`. Sibling orchestrator
  runtime artifacts, if any, get the same treatment.
- **D-10:** "Audit-and-close, not a fixed checklist" = actively sweep, then close whatever is open:
  (a) `git status --porcelain` for any untracked-but-not-ignored runtime/tooling artifact;
  (b) `git ls-files` for accidentally-tracked editor/tooling cruft (e.g. `.DS_Store` already ignored
  & untracked — confirm none tracked). Record the audit result so CHARD-01's "no untracked transient
  or accidentally-tracked artifact remains" is demonstrably true, not assumed.

### Claude's Discretion
- Exact name/location of the extracted helper and its internal structure (as long as D-01's shared
  semantics hold).
- Exact test method names and fixtures (as long as D-04's increment+reset assertions exist and no
  existing test is removed/skipped).
- The specific fastapi version chosen (as long as resolved starlette ≥1.0.1 and the suite is green).
- Order in which the 4 findings are fixed (they are largely independent; SAFETY-03 is the only one
  touching application code).
</decisions>

<specifics>
## Specific Ideas

- The fix scope is **exactly** the 4-row `## Fold-In Summary` table in `68-FINDINGS.md` — that table
  is the CHARD-04 checklist, one-to-one, no additions. Each row already carries a concrete
  remediation **and** a verify command; planning should reuse those verify commands as the phase's
  acceptance checks rather than inventing new ones.
- SAFETY-03 is the only finding that changes runtime application behavior; the other three are
  repo-hygiene / tooling / dependency changes. Treat SAFETY-03 as the phase's primary correctness
  risk and the place the turingmind deep-review + the NAS walkthrough (manual + scheduled search live)
  will scrutinize most.
- Security framing the code track must keep intact (and that Phase 71 will later state as a selling
  point): CSP nonces, session rotation on password change, `apikey=`-in-URL rejection, Basic-auth
  control-char validation. Don't regress any of these while hardening.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Fix scope (the gate — read first)
- `.planning/phases/68-code-track-hostile-reader-discovery/68-FINDINGS.md` — **authoritative fix
  checklist.** The `## Fold-In Summary` table (4 rows P68-FI-001..004) IS CHARD-04. Each source
  section (gitleaks working-tree, dependency audit, entry-point skim, cross-check) carries the full
  remediation + verify command + evidence for its finding.

### Milestone design (authoritative scope)
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — §3.1 (code track: curated known
  items + fix bars), D-3 (launch-visible bound), D-4 (curated subset = repo-hygiene audit +
  SAFETY-03), D-5 (parked config-knob debt — must NOT be folded in), §"Per-phase verification"
  (SAFETY-03 phase bar: TODO resolved + covering test + existing tests stay green).
- `.planning/REQUIREMENTS.md` — CHARD-01..04 requirement text + success criteria; the parked v2 items
  (DEBT-03/06/07/08, UI-01..03) explicitly out of fold-in scope.

### Codebase concerns + conventions
- `.planning/codebase/CONCERNS.md` — v2.8 audit; documents SAFETY-03 with file:line pointers and the
  "Safe modification" note (hold `search_lock` for the full cycle+state-save).
- `.planning/codebase/CONVENTIONS.md` — error-handling convention (no bare `except`; `httpx.HTTPError`
  + `pydantic.ValidationError`), SecretStr discipline — the refactor must stay convention-compliant.

### Existing scan / tooling config
- `.gitleaksignore` — the 4 test-fixture allowlist entries to convert to 8.x fingerprints (P68-FI-001).
- `pyproject.toml` — `fastapi` pin (bare today, line ~15) to raise for the starlette bump (P68-FI-002);
  ruff config (E/F/I/UP/B/SIM, line-length 120).
- `.gitignore` — add `.orchestrator.json` (P68-FI-004).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/search/scheduler.py` — `make_search_job` (line ~94) builds the scheduled `job()` closure
  that acquires `app.state.search_lock`, runs `cycle_fn`, derives outcome from the engine `connected`
  flag, and calls the failure-counter helpers (`_record_failure` increment at ~`:280-295`; reset on
  success). The `_run_one_cycle` extraction (D-01) is carved out of this existing closure body.
- `triggarr/web/routes.py` — manual `search_now` handler at `:875-876`
  (`@router.post("/api/search-now/{app}/{instance}")`) currently calls `cycle_fn(...)` directly,
  bypassing the counter + full-cycle lock. This is the call site to route through `_run_one_cycle`.
- `tests/test_scheduler.py` — existing scheduler failure-counter tests live here; extend (don't
  replace) for CHARD-03. Other failure-counter-touching tests: `tests/test_middleware.py`,
  `tests/test_web.py`, `tests/test_config.py`.
- Project tooling already wired: `uv` (lock/export/pip-audit), `ruff`, `pytest` (965+ tests),
  gitleaks 8.30.1 — all confirmed available in Phase 68.

### Established Patterns
- Error handling: narrow exception catches, no bare `except:`. The SAFETY-03 refactor must preserve
  the existing dedicated OSError + persistence try/except split (SAFETY-03 Codex findings 1 & 2).
- Concurrency: single-worker `asyncio.Lock` model (`app.state.search_lock`). The unified helper must
  hold the lock for the full cycle + state-save — manual searches currently do not, which is part of
  the SAFETY-03 gap.
- Atomic state writes (write-then-rename) for `app.state.triggarr_state` persistence.

### Integration Points
- `_run_one_cycle` is the new shared seam between `scheduler.py` (scheduled) and `routes.py` (manual).
- Dependency change (starlette bump) flows through `pyproject.toml` → `uv.lock` → the deployed Docker
  image; verified by `uv export | pip-audit -r` + full test suite.
- `.gitleaksignore` + `.gitignore` changes are repo-metadata only — verified by re-running the Phase
  68 verify commands, no app behavior change.

</code_context>

<deferred>
## Deferred Ideas

- Config-knob UI debt (DEBT-03 history cap, DEBT-06 drain timeout, DEBT-07 request timeout, DEBT-08
  page size) — pre-parked by spec D-5; invisible to a launch reader. MUST NOT be folded in. Tracked
  in REQUIREMENTS.md v2.
- UI-01/02/03 pixel-exact auth-page verification — out of scope (behind first-run setup, not
  launch-visible; human_needed).
- Tuning gitleaks `generic-api-key` to stop matching planning-doc prose — optional nice-to-have under
  D-08, not required to close P68-FI-001.
- Presentation/docs hardening (README/SECURITY.md/repo-metadata/changelog) — Phase 70 (discovery) +
  Phase 71 (rewrite).

</deferred>

---

*Phase: 69-code-track-hardening*
*Context gathered: 2026-06-02*
