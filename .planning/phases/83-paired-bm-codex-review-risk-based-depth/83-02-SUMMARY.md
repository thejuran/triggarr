---
phase: 83-paired-bm-codex-review-risk-based-depth
plan: "02"
subsystem: review-workflow
tags: [codex, codex-cli, json-schema, adversarial-review, repository-instructions]

# Dependency graph
requires: []
provides:
  - Fixed, versioned Codex adversarial review contract (docs/codex-adversarial-review-contract.md): single prompt template, read-only exact-commit invocation, raw-output storage, failure/retry rule
  - Strict output schema (.claude/schemas/codex-review-findings.schema.json) covering every REVIEW-04 field
  - Drift-guard test (tests/test_codex_review_contract.py) pinning the contract's placeholder set and the schema's strict shape
affects: [83-03 (codex_report_status.py checker), 83-05, 83-06 (CLAUDE.md review-pairing instruction), 83-REVIEW-EVIDENCE.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single fixed prompt template with exactly four {{PLACEHOLDER}} slots, piped verbatim to `codex exec --sandbox read-only --output-schema`"
    - "Strict JSON Schema (draft 2020-12): every object node lists every property in `required` and sets `additionalProperties: false`; optional values expressed as nullable type arrays, never via omission from `required`"

key-files:
  created:
    - docs/codex-adversarial-review-contract.md
    - .claude/schemas/codex-review-findings.schema.json
    - tests/test_codex_review_contract.py
  modified: []

key-decisions:
  - "The fixed prompt lives as one unedited fenced block with exactly {{PR_URL}}, {{HEAD_SHA}}, {{BASE_SHA}}, {{SCOPE}} — no other placeholder, no added framing (D-07)"
  - "codex exec is invoked against a detached git worktree pinned to the exact head SHA, never the live working tree, so the inspected commit cannot drift mid-review"
  - "The installed codex plugin's /codex:adversarial-review command is explicitly not used for this contract: it wraps prompts in its own template and its default schema lacks the REVIEW-04 fields (stable id, reproduced/hypothesis, coverage/exclusions/commands_run/limitations) — raw `codex exec` plus a custom schema was used instead, per RESEARCH.md Pitfall 4"

patterns-established:
  - "Pattern: fixed-template + custom --output-schema is the only sanctioned Codex invocation shape for this repository; no other Codex command or template substitutes for it"
  - "Pattern: raw output storage directory shape OUT=.planning/phases/<phase-dir>/codex/<head12>-<label>-a<attempt> with .jsonl/.last.json/.status.json, gitleaks-scanned before `git add -f`"

requirements-completed: [REVIEW-02, REVIEW-04]

# Metrics
duration: ~10min
completed: 2026-10-22
---

# Phase 83 Plan 02: Codex Adversarial Review Contract Summary

**Fixed, versioned Codex prompt template + read-only exact-commit invocation procedure, plus a strict JSON Schema enforcing every REVIEW-04 finding field, guarded by a 7-test drift suite.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-10-22T14:3x (session start, not separately timestamped)
- **Completed:** 2026-10-22T14:40:15-04:00 (final task commit)
- **Tasks:** 2
- **Files modified:** 3 (all new)

## Accomplishments

- Wrote `docs/codex-adversarial-review-contract.md`: the single fixed prompt (version 1), its boundary rules (Codex is read-only, never edits/commits/pushes/approves), a six-step invocation procedure using a detached worktree pinned to the exact head SHA, a raw-output storage convention, and the one-retry-then-incomplete failure rule.
- Wrote `.claude/schemas/codex-review-findings.schema.json`: a strict (OpenAI structured-output compatible) JSON Schema with exactly the 12 top-level REVIEW-04 fields and 14 finding fields from the plan's `<interfaces>` block, nullable fields expressed as type arrays, no `pattern`/`minLength` keywords.
- Wrote `tests/test_codex_review_contract.py` first (RED — confirmed it failed only because the schema file didn't exist yet), then the schema (GREEN — all 7 tests pass).

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the fixed contract and invocation procedure** - `bf83283` (docs)
2. **Task 2: Write the strict output schema and its drift-guard test** - `0c5a4cf` (test — schema + test committed together per the plan's TDD instruction)

**Plan metadata:** (this commit, docs: complete plan)

_Note: Task 2 followed the RED→GREEN TDD cycle (test written and confirmed failing before the schema existed); no separate refactor commit was needed._

## Files Created/Modified

- `docs/codex-adversarial-review-contract.md` - Fixed prompt template (version 1), boundary, invocation, raw-output storage, failure rule
- `.claude/schemas/codex-review-findings.schema.json` - Strict output schema for `codex exec --output-schema`, covering every REVIEW-04 field
- `tests/test_codex_review_contract.py` - Drift guard: 7 tests pinning the schema's strict shape and the contract's placeholder/read-only/schema-path invariants

## Decisions Made

- None beyond what the plan specified — the contract text, schema shape, and test behaviors were written exactly per the plan's `<action>` and `<behavior>` blocks, adapted from `docs/bm-greptile-codex-blueprint.md` §"Codex adversarial review contract" (lines 125-141) and the structural style of `docs/owner-cli-acceptance.md`.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' acceptance criteria were verified by running the exact commands listed in the plan (grep checks, `uv run pytest tests/test_codex_review_contract.py -q`, the schema `required`-fields print, the `pattern`/`minLength` grep, and the full `uv run pytest tests/ -x -q`).

## Issues Encountered

None. The RED phase failed for the expected reason (`FileNotFoundError` on the not-yet-created schema file), confirming the test was exercising real behavior rather than passing vacuously.

## User Setup Required

None - no external service configuration required. This plan creates documentation and a schema file only; no BM setting, `.planning/config.json` key, or application code was touched.

## Next Phase Readiness

- Plan 03 (the `codex_report_status.py` checker referenced by this contract's Invocation step 6) can now be written against a stable, tested schema and field-name set.
- The raw-output storage convention (`OUT=.planning/phases/<phase-dir>/codex/<head12>-<label>-a<attempt>`) and the failure/retry rule are specified and ready for the first real `codex exec` invocation in a later plan.
- No blockers. `.planning/config.json` was not modified by this plan (confirmed via `git diff` against the session-start commit).

---
*Phase: 83-paired-bm-codex-review-risk-based-depth*
*Completed: 2026-10-22*

## Self-Check: PASSED

All created files confirmed present on disk; both task commit hashes (`bf83283`, `0c5a4cf`) confirmed present in git history.
