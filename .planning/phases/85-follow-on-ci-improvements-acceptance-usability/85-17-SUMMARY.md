---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "17"
subsystem: docs
tags: [codex-review, acceptance, review-checkpoint-record, documentation-guard-tests]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-05)
    provides: the schema-2 keyed register (registerKey, upsertSlice/verifyWrite/migrateSchema1, review-register.cjs CLI) this plan documents
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-09)
    provides: coverage-provenance.cjs (buildProvenance/buildLocalProvenance/checkEvidence, write/write-local/check CLI) this plan's coverage-evidence procedure documents
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-10)
    provides: the no-Python-distributions release shape (D-14) this plan's pilot-doc edit records
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-13)
    provides: the verified-origin trust boundary (verify_trust, TRUSTED_AUTHORS, local reflog check) and untrusted-refused/.base-status.json contract this plan documents
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-14)
    provides: codex-fallback.cjs (FALLBACK_FIELDS/OWNER_DECISIONS/validateFallback) and acceptance-readiness.cjs (readiness/renderChecklist/codexStatusFor/headTrustFor) this plan's docs cite by field name and CLI flag
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-16)
    provides: the review-machinery drift guard (tests/test_review_machinery_lists.py) this plan's checklist edits must not violate
provides:
  - "docs/codex-adversarial-review-contract.md: '### Owner-approved fallback' section naming every codex-fallback.cjs field/decision; a verified-origin --trusted mode description; the interim untrusted-head rule verbatim (D-07 amendment); the pre-grading redaction stage replacing the stale 'full, unedited' claim"
  - "docs/review-checkpoint-record.md: a '| Fallback |' Codex-table row, '.base-status.json' in Raw output paths, a consistent vibe-check-as-fallback sentence, the interim-rule Rules bullet, a new '## Coverage evidence for vibe-check' section, and two new Owner acceptance checklist lines (Codex fallback, Readiness check)"
  - "docs/owner-cli-acceptance.md: steps 1 and 5 both run acceptance-readiness.cjs and state the no-compare-and-swap serialization rule"
  - "docs/buildomator-greptile-pilot.md: schema-2 by_pr_head/global_open Register shape with the writer and one-time migrate command; no-Python-distributions release wording linking the OS-scan policy; the routine-workflow approval step now requires the paired Codex review"
  - "tests/test_acceptance_docs.py (new): 16 guard tests pinning every D-16/D-19/D-20/CIMAINT-06 wording requirement above, reading codex-fallback.cjs's own FALLBACK_FIELDS/OWNER_DECISIONS via subprocess rather than duplicating them by hand"
affects: [85-18, 85-19]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guard tests read the validator's own exported field list via a `node -e` subprocess call instead of hand-copying field names into the test, so the doc-vs-code contract can't silently drift when the validator's schema changes"

key-files:
  created:
    - tests/test_acceptance_docs.py
  modified:
    - docs/codex-adversarial-review-contract.md
    - docs/review-checkpoint-record.md
    - docs/buildomator-greptile-pilot.md
    - docs/owner-cli-acceptance.md
    - tests/test_review_checkpoint_record.py
    - tests/test_codex_review_run.py

key-decisions:
  - "The 'wait'/'retry later' substring check for test_no_doc_overclaims_untrusted_review excludes bare 'egress' from a plain-substring ban because 'regressions' contains it as a false positive (r-EGRESS-ions); used a word-boundary regex for that one term instead of dropping the check"
  - "Added the Owner acceptance checklist's 'Codex fallback' line as part of this plan rather than deferring it, even though it was specified in Task 1's action text — the first GREEN pass on Task 1 missed it; caught before commit by re-reading the task's full action text against the diff"
  - "The two pre-existing pinned assertions in tests/test_codex_review_run.py ('Codex: PENDING — untrusted source' literal) were updated to check the new interim-rule vocabulary (untrusted-refused, Phase 85.1, CI still runs) instead of the superseded wording — see Deviations"

requirements-completed: [ACCEPT-01, ACCEPT-02, CIMAINT-03, CIMAINT-06]

# Metrics
duration: 29min
completed: 2026-10-27
---

# Phase 85 Plan 17: Acceptance and Review Docs for the D-16/D-19/D-20 Mechanisms Summary

**Rewrote the Codex contract, checkpoint record, pilot doc and owner-acceptance procedure to describe exactly what Plans 85-05/85-09/85-10/85-13/85-14/85-16 already built — the owner-approved fallback, the verified-origin trusted mode, the interim untrusted-head rule, the keyed-register serialization rule, the acceptance-readiness check, and the coverage-evidence procedure — each guarded by new tests.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-10-27T14:02:00Z (approx, worktree base correction)
- **Completed:** 2026-10-27T14:31:03Z
- **Tasks:** 2 completed (each ran RED then GREEN)
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- `docs/codex-adversarial-review-contract.md` gained a `### Owner-approved fallback` section naming every one of `codex-fallback.cjs`'s `FALLBACK_FIELDS` and `OWNER_DECISIONS` (read live via subprocess in the guard test, never hand-copied), replaced the stale "harness is hardened in Phase 85" wording with the verbatim D-07-amendment interim rule, described the verified-origin `--trusted` mode (`TRUSTED_AUTHORS`, local commit reflog, `origin/main` ancestor requirement, fail-closed), and replaced the "full, unedited" raw-output claim with the actual pre-grading redaction stage plus a historical-evidence exception.
- `docs/review-checkpoint-record.md` gained a `| Fallback |` row and `.base-status.json` in the Codex table, a vibe-check sentence that no longer contradicts the contract's fallback definition, the same interim-rule wording in its Rules section, a new `## Coverage evidence for vibe-check` section (CI-artifact vs. exact-head local coverage, both gated by `coverage-provenance.cjs check`), and two new Owner acceptance checklist lines (`Codex fallback`, `Readiness check`).
- `docs/owner-cli-acceptance.md` steps 1 and 5 now both invoke `acceptance-readiness.cjs` and state that final acceptance updates are serialized because repository variables have no compare-and-swap.
- `docs/buildomator-greptile-pilot.md`'s Register shape moved from schema 1 to the real schema-2 `by_pr_head`/`global_open` shapes with the writer and one-time `migrate` command; its release-promotion wording dropped the retired Python-distribution claim and now links the OS-package scan policy; its routine-workflow approval step now requires the paired Codex review (complete, or an accepted fallback) before approval.
- New `tests/test_acceptance_docs.py` (16 tests) and 3 new tests in `tests/test_review_checkpoint_record.py` guard every D-16/D-19/D-20/CIMAINT-06 wording requirement; all listed verify commands plus the full repository suite (2564 tests) pass.

## Task Commits

Both tasks followed RED -> GREEN:

1. **Task 1: D-16 fallback definition, wait/retry-later rule, vibe-check consistency, interim untrusted-head rule, pilot Codex precondition**
   - `b9446cb` test(85-17): add failing D-16 fallback and wording guards
   - `faa4387` docs(85-17): define the owner-approved Codex fallback, the verified-origin trusted mode, the interim untrusted-head rule and the redaction stage (D-16, D-07)
2. **Task 2: D-19/D-20 acceptance procedure, register docs, coverage-evidence procedure, release and scan wording**
   - `2496e81` test(85-17): add failing acceptance procedure and register doc guards
   - `e72e971` docs(85-17): document keyed registers, serialized acceptance updates, readiness and coverage evidence (D-19, D-20, CIMAINT-06)

_Both tasks are `tdd="true"`; each ran a failing `test(...)` commit before its `docs(...)` GREEN commit. No `refactor(...)` commit was needed for either._

## Files Created/Modified

- `docs/codex-adversarial-review-contract.md` - Owner-approved fallback section; verified-origin trusted-mode description; interim untrusted-head rule (verbatim, twice — Invocation and in the new section's cross-reference); pre-grading redaction stage in Raw output storage; Failure rule's fallback cross-reference and wait/retry-later-blocks-acceptance sentence
- `docs/review-checkpoint-record.md` - Codex table Fallback row and `.base-status.json`; consistent vibe-check sentence; interim-rule Rules bullet plus wait/retry-later sentence; new Coverage-evidence-for-vibe-check section; Owner acceptance checklist's Codex-fallback and Readiness-check lines
- `docs/buildomator-greptile-pilot.md` - release-promotion wording (no distributions, OS-scan link); CI-upload wording (no distributions); schema-2 Register shape with writer/migrate commands and the serialization rule; Routine BM workflow step 4's Codex precondition
- `docs/owner-cli-acceptance.md` - step 1 and step 5 both run `acceptance-readiness.cjs`; step 1 states the serialization rule
- `tests/test_acceptance_docs.py` (created) - 16 tests: owner-approved-fallback definition (schema-read via subprocess), wait/retry-later-blocks-acceptance, vibe-check consistency, no stale harness-hardening wording, interim untrusted-head rule (verbatim + required terms), no untrusted-review overclaim, verified-origin trusted mode, redaction-stage wording, pilot Codex precondition, readiness-check presence in both acceptance steps, serialization-rule sentence, schema-2 register shape, no-distributions wording, OS-scan link, coverage-evidence section, checklist readiness-command presence
- `tests/test_review_checkpoint_record.py` - 3 new tests: Fallback-row presence, new-raw-output-paths presence (and Phase-85.1-only-outputs absence), wait/retry-later-blocks-acceptance sentence
- `tests/test_codex_review_run.py` - updated two pre-existing pinned assertions that checked the now-superseded `"Codex: PENDING — untrusted source"` literal, to check the interim-rule vocabulary instead (see Deviations)

## Decisions Made

See `key-decisions` in the frontmatter above. In summary: the "egress" ban in `test_no_doc_overclaims_untrusted_review` uses a word-boundary regex (not a plain substring) because "regressions" — already present in the unrelated, pre-existing prompt text — contains "egress" as a false positive; the Owner acceptance checklist's "Codex fallback" line (specified in Task 1's own action text) was added during Task 1's GREEN pass after being initially missed, caught by re-reading the task text against the diff before committing; and the two literal-string assertions in `tests/test_codex_review_run.py` that pinned the stale "Codex: PENDING — untrusted source" wording were updated in place rather than left broken, since this plan intentionally supersedes that framing with the interim-rule vocabulary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two pre-existing pinned assertions in `tests/test_codex_review_run.py` broke on the intended wording change**
- **Found during:** Task 1, running the full repository suite after the GREEN doc edits (per the parallel-executor instruction to run `uv run pytest tests/ -x -q` before finishing, not just plan-owned tests)
- **Issue:** `test_contract_documents_untrusted_sources` and `test_record_documents_untrusted_pending` (added in Plan 85-13, not in this plan's `<files>` list) asserted the literal substring `"Codex: PENDING — untrusted source"` in both docs, plus `"Phase 85"` and `"CI results"` in the contract. This plan's Task 1 action text explicitly requires removing the stale "harness is hardened in Phase 85" framing and replacing it with the interim-rule vocabulary (`untrusted-refused`, `Phase 85.1`, `CI still runs`) — the old literal string no longer appears anywhere, by design, once that rewrite lands.
- **Fix:** Updated both assertions to check for the new interim-rule vocabulary (`"untrusted-refused"`, `"Phase 85.1"`, `"CI still runs"`) instead of the superseded literal, preserving each test's original intent (the contract/record document untrusted-source handling) rather than its exact wording.
- **Cost if wrong:** If this reading were wrong, the fix is a one-line test-wording revert; no runtime behavior is affected either way — these are documentation drift guards, not functional code.
- **Files modified:** `tests/test_codex_review_run.py`
- **Verification:** `uv run pytest tests/test_codex_review_run.py -q` → 141 passed, both before (confirmed failing against the new docs) and after (passing) the fix; full repository suite (2564 tests) passes with the fix applied.
- **Committed in:** `faa4387`

---

**Total deviations:** 1 auto-fixed (Rule 1, discovered by the plan's own full-suite verification step)
**Impact on plan:** Necessary to keep the full suite green after this plan's intentional, D-16-mandated wording change; no scope creep — the touched file already existed and the specific assertions were the exact ones this plan's wording change made stale.

## Issues Encountered

- The first draft of `test_no_doc_overclaims_untrusted_review` banned the bare substring "egress", which false-matched the pre-existing, unrelated word "regressions" in both docs' prompt/evidence text (`r-EGRESS-ions`). Fixed by switching that one term to a word-boundary regex; the other banned multi-word phrases stayed as plain substrings since none of them had the same false-positive risk.
- My own first pass on `test_pilot_approval_precondition_includes_codex` matched the wrong "4." list item — the pilot doc has two separate numbered lists ("Connect Greptile" and "Routine BM workflow"), both with a step 4. Fixed by scoping the search to the text after the `### Routine BM workflow` heading.

## User Setup Required

None - no external service configuration required. This plan is documentation and guard tests only; it touches no workflow file, no CI job, and no live repository variable.

## Verification Evidence

- `uv run pytest tests/test_review_checkpoint_record.py tests/test_acceptance_docs.py tests/test_review_instructions.py tests/test_codex_review_contract.py tests/test_review_machinery_lists.py tests/test_codex_review_run.py -q` → 203 passed (Task 1's listed command plus `tests/test_codex_review_run.py`, added after discovering the Rule-1 fix was needed there)
- `uv run pytest tests/test_acceptance_docs.py tests/test_review_checkpoint_record.py tests/test_review_instructions.py tests/test_review_machinery_lists.py tests/test_docs_accuracy.py -q` → 51 passed (Task 2's exact listed command)
- Full repository suite: `uv run pytest tests/ -x -q` → **2564 passed**, 38 pre-existing warnings (starlette/httpx deprecation, unrelated to this plan), observed directly, not inferred
- `uv run ruff check triggarr/ tests/` → clean
- `actionlint` → exit 0 (sanity check only; this plan touches no workflow file)
- All grep-based acceptance criteria for both tasks verified directly (see individual `grep -c`/`grep -ci` commands run during execution); all returned the exact counts the plan specifies

## Known Stubs

None. This plan touches only markdown documentation and Python test files; no UI, no data-flow code, no placeholder values.

## Threat Flags

None — this plan's edits are exactly the mitigations the plan's own `<threat_model>` names (T-85-52, T-85-52a, T-85-52b, T-85-53, T-85-54, T-85-55), all addressed by the doc wording and guard tests above. No new network endpoint, auth path, file-access pattern, or schema change was introduced.

## Next Phase Readiness

- All `must_haves` artifacts and `key_links` from the plan frontmatter are present and grep-verified: `docs/review-checkpoint-record.md` contains `| Fallback |`; `docs/codex-adversarial-review-contract.md` contains `owner-approved fallback`; `tests/test_acceptance_docs.py` contains `def test_`; `docs/owner-cli-acceptance.md` names `acceptance-readiness\.cjs` in both cited steps; `docs/buildomator-greptile-pilot.md`'s Register shape names `by_pr_head`.
- The docs now describe exactly what Plans 85-05 (keyed register), 85-09 (coverage provenance), 85-10 (no-distributions release), 85-13 (trust boundary), 85-14 (readiness/fallback validator) and 85-16 (drift guard) already built — no remaining doc-vs-code drift for the D-16/D-19/D-20/CIMAINT-06 carry-forward items this phase absorbed.
- No blockers for downstream plans. Plans 85-18/85-19 (if they touch acceptance or pilot checklist wording again) should be aware the Owner acceptance checklist now has 7 status lines (BM, Codex, Codex fallback, Greptile, Vibe-check, CI, Readiness check), not 5.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: docs/codex-adversarial-review-contract.md
- FOUND: docs/review-checkpoint-record.md
- FOUND: docs/buildomator-greptile-pilot.md
- FOUND: docs/owner-cli-acceptance.md
- FOUND: tests/test_review_checkpoint_record.py
- FOUND: tests/test_acceptance_docs.py
- FOUND: tests/test_codex_review_run.py
- FOUND commit: b9446cb (test(85-17): add failing D-16 fallback and wording guards)
- FOUND commit: faa4387 (docs(85-17): define the owner-approved Codex fallback, the verified-origin trusted mode, the interim untrusted-head rule and the redaction stage (D-16, D-07))
- FOUND commit: 2496e81 (test(85-17): add failing acceptance procedure and register doc guards)
- FOUND commit: e72e971 (docs(85-17): document keyed registers, serialized acceptance updates, readiness and coverage evidence (D-19, D-20, CIMAINT-06))
