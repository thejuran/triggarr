---
phase: 83-paired-bm-codex-review-risk-based-depth
fixed_at: 2026-10-22T20:26:50Z
review_path: .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 83: Code Review Fix Report

**Fixed at:** 2026-10-22
**Source review:** .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, CR-02, WR-01 to WR-05; IN-* and SA-* are out of scope for this pass and left to a separate executor)
- Fixed: 7
- Skipped: 0
- Rejected: 0

Mode: direct (main working tree, branch `paired-review`, as the orchestrator instructed). No worktree was created, so there was no worktree cleanup step. Nothing was pushed.

Every code fix was written test-first. The new regression tests were run on the unfixed code and failed, then passed after the fix. The failing runs are recorded under each finding below.

Final verification after all seven commits:
- `uv run pytest tests/ -x -q`: 2254 passed, 0 failed
- `uv run ruff check triggarr/ tests/`: All checks passed

CR-01, CR-02 and WR-01 change the checker's decision logic. Regression tests cover them, but they are still marked "requires human verification". In this project that verification comes from the fresh BM review and Codex pass on the new head, not from the owner reading code.

## Fixed Issues

### CR-01: Checker marks reports with wrong-typed or missing-value fields (including `findings: null`) as a complete review

**Files modified:** `tests/codex_report_status.py`, `tests/test_codex_report_status.py`
**Commit:** 3163144
**Status:** fixed: requires human verification (logic change)
**Applied fix:** Replaced the hand-written `_check_schema` with a recursive walk of `.claude/schemas/codex-review-findings.schema.json`. The walk checks:
- types, including nullable unions (a JSON boolean never counts as an integer)
- enums, including `schema_version` `["1"]`
- required fields and unexpected fields at every object level
- every array item

No new dependency was added. Codex F001 has the same root cause and is covered by the same change; its exact reproduction (every required key present, all non-SHA values null) is now a test.

The owner decision of 2026-10-22 is implemented alongside: if `summary` or any `limitations` entry contains "incomplete review", "review is/was incomplete" or "not a clean approval" (case-insensitive), the result is `incomplete` with the reason `self-declared incomplete: <field> states '<phrase>'`.

**Failing run before the fix:** `uv run pytest tests/test_codex_report_status.py -q` gave `26 failed, 30 passed`. The failures were:
- 21 wrong-type/enum cases, including `findings: null`, `findings: "none"`, `coverage: null`, `schema_version: "2"`, `summary: 5`, `line_start: true` and `commands_run[0].exit_code: true`
- the Codex F001 all-null reproduction
- 4 self-declared-incomplete cases

**After the fix:** `63 passed` (with the contract tests).

**Effect on existing evidence (for the owner):** The committed Codex report `codex/d501a68316b2-explicit-a1.last.json` says "This is an incomplete review, not a clean approval" in its limitations. The new checker assesses it as `incomplete`. Its stored `.status.json` was produced by the old checker, and under the never-edit rule it was not changed. Whoever records the d501a683 checkpoint should treat that Codex pass as incomplete. The `a7995baf187e-quick-a1` report still assesses complete.

### CR-02: A finding with a non-string `id` is counted but dropped from the qualified IDs, so it cannot be dispositioned

**Files modified:** `tests/codex_report_status.py`, `tests/test_codex_report_status.py`
**Commit:** d5d774e
**Status:** fixed: requires human verification (logic change)
**Applied fix:**
- `_finding_consistency_and_ids` no longer skips a finding silently. A missing, non-string or blank `id` now adds `finding at index N has no valid id`, which makes the report incomplete.
- Added an invariant test: every complete result has `finding_count == len(qualified_ids)`.

**Failing run before the fix:** `4 failed, 57 passed`, all in `test_finding_without_valid_id_incomplete[7|None|""|"   "]`. After CR-01, `7` and `None` were already incomplete through the schema walk but lacked the per-finding reason. `""` and `"   "` were still accepted as complete, which was a live gap the schema walk could not catch.

**After the fix:** `61 passed`.

### WR-01: Contradictory `verdict` and `findings` are accepted as complete

**Files modified:** `tests/codex_report_status.py`, `tests/test_codex_report_status.py`
**Commit:** 7c2a3da
**Status:** fixed: requires human verification (logic change)
**Applied fix:** If `verdict` is `no-findings` but findings are listed, or `verdict` is `findings` but the list is empty, the report is incomplete with a plain-language reason.

**Failing run before the fix:** `2 failed, 61 passed` (`test_no_findings_verdict_with_findings_incomplete`, `test_findings_verdict_without_findings_incomplete`). **After the fix:** `63 passed`.

### WR-02: CLI crashes with a traceback (no JSON assessment) on a non-UTF-8 or directory report path

**Files modified:** `tests/codex_report_status.py`, `tests/test_codex_report_status.py`
**Commit:** ae4e282
**Applied fix:**
- `main()` now catches `OSError` and `UnicodeDecodeError` when it reads an existing report path.
- `assess_report()` takes a new keyword-only argument, `read_error`. When it is set, the CLI prints JSON with `status: incomplete` and the reason `unreadable report: <ExceptionType>`, then exits 1. The reason names only the exception type, so no file content or path is printed.
- A path that does not exist still reports `missing report`.

**Failing run before the fix:** `2 failed, 63 passed`. The non-UTF-8 test failed with `UnicodeDecodeError` and the directory test with `IsADirectoryError`; both were raw tracebacks. **After the fix:** `65 passed`.

### WR-03: The checkpoint record says BM re-review keeps no history, which contradicts the verified baseline and BM's own workflow

**Files modified:** `docs/review-checkpoint-record.md`
**Commit:** 1adb17d
**Applied fix:**
- Corrected the "Before any re-review" section. BM 5.0.3's `--fix --auto` loop copies `REVIEW.md` and `REVIEW-FIX.md` to `*.iterN.md` before each overwrite. The source is cited: `~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/code-review-fix.md`, step `auto_iteration_loop`, lines 270-275, confirmed on disk. The section also points to `docs/bm-review-baseline-2026-10-22.md`.
- The section now explains why the head-SHA snapshot is still required under D-08 and REVIEW-06: the backups are named by iteration number, not by head SHA, and BM never commits them. Line 363 of the same file confirms the commit behavior. The `cp` snapshot step is unchanged.

**Verification:** Docs only. Re-read the section, and `tests/test_review_instructions.py` passed (4 passed).

### WR-04: The classification policy does not rank `sensitive` against `code`, but the record requires a single "most consequential" class

**Files modified:** `docs/review-classification-policy.md`
**Commit:** 7a854c5
**Applied fix:** Applied the owner decision "Apply both" in three places:
- **Principle:** now says a PR with both application code and sensitive content gets every review either class requires.
- **Mixed changes:** a new paragraph says sensitive and code are not ranked against each other. Such a PR gets the full code-review path: BM with paired Codex, Greptile when it runs, CI, and routine vibe-check while the owner still requires it. It also gets the sensitive-content risk assessment (RISK-01, plus the RISK-02 vibe-check recommendation when risk is high), covering the sensitive files specifically.
- **Classification record:** the PR is recorded as `classification: code`, with both classes in `classes_present` and the sensitive files named in `rationale`. The `classification` field definition says the same.

**Verification:** Docs only. Re-read the sections, and `tests/test_review_instructions.py` passed.

### WR-05: Raw Codex event streams are committed to a public repo, with pattern-based gitleaks as the only safeguard

**Files modified:** `docs/codex-adversarial-review-contract.md`, `tests/test_codex_review_contract.py`
**Commit:** 9290303
**Applied fix:** The template is now version 2. The version line records what changed and why, and the heading now reads "Fixed prompt (version 2)". The changes:
- **(b) Prompt line:** the fixed prompt gains one line: "Read only files inside this working copy; do not read files outside it." There are still exactly four placeholders.
- **(a) Second secret check:** "Raw output storage" now requires two checks on the codex directory before `git add -f`. The first is gitleaks. The second scans for 32-character lowercase hex strings with `grep -rlE '(^|[^0-9a-f])[0-9a-f]{32}([^0-9a-f]|$)'`. The scan lists file names only, so a hit never prints the key, and full 40-character commit SHAs do not match. Any listed file blocks the commit until someone reviews it by hand. If the match is a credential, the raw files are not committed and the owner is told the key may need rotating.
- **Tests:** the drift-guard test now targets the version 2 heading and checks:
  - the version line
  - the working-copy line in the prompt
  - the hex scan, the "blocks the commit" rule, the filename-only flag and gitleaks in the storage section
  - that the contract itself contains no 32-hex value

  No secret is embedded anywhere.

**Failing run before the fix:** `uv run pytest tests/test_codex_review_contract.py -q` gave `4 failed, 7 passed`: `test_contract_placeholders` (the version 2 heading was absent), `test_contract_template_version_two`, `test_contract_prompt_confines_reads_to_working_copy` and `test_contract_requires_hex_key_scan_before_commit`. **After the fix:** `15 passed` (with `test_review_instructions.py`).

**Check on existing files:** The new scan run on the current `codex/` directory found no matches (grep exit 1), so nothing already committed is flagged.

---

_Fixed: 2026-10-22_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
