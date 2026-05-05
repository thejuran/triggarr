---
estimated_steps: 5
estimated_files: 5
skills_used:
  - write-docs
  - verify-before-complete
---

# T01: Write requirement-scope coverage artifact

Create the milestone-scope requirement coverage artifact that retires the false premise that M001/S06 must re-prove every historically validated project requirement.

Expected executor skills/frontmatter: `write-docs`, `verify-before-complete`.

Steps:
1. Read the listed inputs and write `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md` for a cold-reader milestone validator/release verifier.
2. Include a table with columns for requirement/capability, M001 relationship, evidence, and validation treatment.
3. State that `.gsd/REQUIREMENTS.md` has no Active requirements, and classify project-wide validated/deferred/out-of-scope requirements as historical/prior coverage unless M001 changed them.
4. Include direct INST-04 migration proof if INST-04 is mentioned: `triggarr/config.py` `detect_and_migrate_v22(...)`, `tests/test_config.py` migration tests, and the focused migration command that T04 will rerun fresh.
5. Do not mutate requirement statuses or invent new requirement IDs.

Must-haves:
- The artifact names the reader and post-read action: a milestone validator/release verifier deciding whether validation can pass, needs attention, or needs remediation.
- It separates M001 acceptance themes from project-wide historical requirements.
- It preserves prior validated documentation/evidence coverage rather than reopening unrelated work.

Failure Modes (Q5):
- Dependency: historical requirements/artifacts. On conflicting evidence, cite the conflict and prefer current tracked tests plus decisions over stale summaries; do not silently choose the more convenient claim.
- Dependency: command evidence. If fresh command evidence is not yet available, mark it as pending T04 rather than fabricating a passing result.

Negative Tests (Q7):
- Search the artifact for accidental status mutation language such as `new Active requirement`, `status changed`, or `revalidated all requirements`.
- Confirm it does not contain secret-looking placeholders or generated credentials.

Verification:
- `test -s .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`
- `rg -n "Active requirements|INST-04|detect_and_migrate_v22|validation treatment|milestone validator" .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`

## Inputs

- `.gsd/REQUIREMENTS.md`
- `.gsd/milestones/M001/M001-VALIDATION.md`
- `triggarr/config.py`
- `tests/test_config.py`

## Expected Output

- `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`

## Verification

test -s .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md && rg -n "Active requirements|INST-04|detect_and_migrate_v22|validation treatment|milestone validator" .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md

## Observability Impact

Adds a durable validation inspection surface for requirement-scope decisions, making future validation failures localizable to a named S06 artifact instead of scattered historical requirement rows.
