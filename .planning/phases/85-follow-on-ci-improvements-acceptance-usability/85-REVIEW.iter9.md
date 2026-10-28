---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T20:12:00Z
reviewed_head: 3b3713b7eebe288c702a2c0d4fb4e50398e013c3
diff_base: 030931395f558a7dde7170fd2244902e9335b6e4
iteration: 9
depth: standard
files_reviewed: 3
files_reviewed_list:
  - .github/scripts/ci-job-consistency.test.cjs
  - .github/tool-pins.env
  - tests/test_ci_followon_wiring.py
findings:
  critical: 0
  warning: 0
  info: 5
  total: 5
status: issues_found
---

# Phase 85: Code Review Report (iteration 9, post-merge CI-trap fixes)

**Reviewed:** 2026-10-28T20:12:00Z (head `3b3713b7eebe288c702a2c0d4fb4e50398e013c3`, diff base `030931395f558a7dde7170fd2244902e9335b6e4`)
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found (info only; no new blocker or warning)

## Summary

Scope: `git diff 0309313..3b3713b -- .github/ tests/`, which is commits b0e1ee4 and 3b3713b. The other commits on `ci-traps` (8c58da6, d2ca91b, ece43ab, 42a6529, db57caa, 5213f02) change `.planning/` only and are out of scope.

Verification on this tree:
- `node --test .github/scripts/ci-job-consistency.test.cjs`: 87 passed
- `uv run pytest tests/test_ci_followon_wiring.py -q`: 18 passed
- `uv run ruff check tests/`: clean
- `gsd-tools verify conventions --check` on all three files: no findings

**b0e1ee4 (regex anchors): fixed, and both negative tests still catch what they should.**
- `mutate()` still asserts that `from` is in the text and that the text changed. `findAnchor()` returns the literal matched text, so `from` is built from real file content and the `includes` check passes only if the step is really there. If the anchor regex stops matching (for example a pin moves to a bare tag), `findAnchor` fails loudly. It cannot quietly do nothing.
- I simulated a Dependabot bump. I replaced both pinned SHAs with dummy 40-hex values and changed the checkout comment to `# v6.1.0`, then ran the same anchor and mutation logic. The anchors matched, the mutated text differed from the original, and `findSkipConditions` reported exactly the expected reasons: `required job "acceptance" sets continue-on-error`, and `required job "docker" step if: not on the reviewed allowlist: "Check PR title"`. The unmutated real files return `[]` (tests at lines 237 and 244). So each assertion depends on the mutation.
- The mutations hit the right steps. `review-acceptance.yml` has one `actions/checkout` step, at line 26 inside job `acceptance`, followed directly by `with:`. In `ci.yml`, the `Set up Docker Buildx` step name appears only once, inside job `docker` (line 122-123). The inserted step goes right after it, so it stays inside `docker`.
- `String.prototype.replace` with a string pattern reads `$&`, `$1` and similar in the replacement string as special codes. Neither anchor nor either inserted step contains a `$`, so this cannot happen here.

**3b3713b (pins file): fixed, and the values match.**
- The four values in `.github/tool-pins.env` are identical to `ci.yml` (`TRIVY_VERSION` 0.76.1 / `TRIVY_SHA256` c7cbe313…39d9c0 at lines 395-396; `ACTIONLINT_VERSION` 1.7.12 / `ACTIONLINT_SHA256` 8aca8db9…49a3d8 at lines 214-215). They are also identical to the evidence key=value lines in `85-TOOL-PINS-AND-BASELINE.md` lines 8-11.
- The file is no longer read at import time: `_tool_pin` reads it inside the call. Nothing else in the repo still reads `85-TOOL-PINS-AND-BASELINE.md`, so moving the phase-85 directory cannot break collection or these tests.
- The regex `^{name}=(\S+)$` with MULTILINE cannot match the `#` comment lines. A CRLF-saved file would fail loudly rather than return a value that includes `\r`.
- Editing only one of `ci.yml` or `tool-pins.env` still fails the test, so a pin bump must change both. Because it changes `ci.yml`, the PR is still classed as sensitive, as the file header says.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Info

### IN-05: The pins file header points to evidence in a phase folder that will be archived, and nothing checks its "checked" date

**File:** `.github/tool-pins.env:1-5`
**Issue:** The header names `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-TOOL-PINS-AND-BASELINE.md` as the evidence and says "checked 2026-10-27". The commit's own purpose is that the phase folder will be archived, and once it is, this pointer leads nowhere. Also, a later pin bump only has to change the two value lines to pass the test. The header (date and evidence pointer) can stay stale, and the file would still call values "verified" that nobody re-checked. The test only proves that `ci.yml` and the file agree. It cannot prove that anyone verified the values. The test docstring states this correctly, but the header implies more. There is no runtime effect.
**Fix:** Change the header to point at something that survives archiving, and say what a bump must record. For example: `# Evidence for each bump: the PR that changes these lines must link the release page and checksum source. Original verification: Phase 85 plan 85-12 (archived with milestone v2.13).` Alternatively, add a `TOOL_PINS_CHECKED=YYYY-MM-DD` key and have the pin-bump checklist require updating it.

### IN-03 (carried from iteration 8): The drain-timeout fallback decodes as UTF-8 and ignores the caller's `encoding`, `errors` and newline handling

**File:** `tests/codex_review_run.py:211-222` (not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-04 (carried from iteration 8): The new end-to-end test assumes the child prints within one second

**File:** `tests/test_codex_review_run.py:2079-2111` (not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-01 (carried from iteration 7, owner left out of scope): The Node detector's quoted-key support misses YAML escape spellings

**File:** `.github/scripts/ci-job-consistency.cjs:589-596` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

### IN-02 (carried from iteration 7, owner left out of scope): Run-splitting logic is duplicated

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 133-137` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

## Accepted residuals (carried, not counted)

### Iteration-7 WR-01: Run-together reviewer names typed in one case (`claudecode`, `bmreviewer`, `gsdagent`, `codexreviewrun`) still pass

**File:** `.github/scripts/codex-fallback.cjs:113-137`
**Status:** The owner accepted this as a residual after iteration 7. Recorded here for continuity. Not re-raised, and not counted in `findings`.

## Set aside (needs ruling)

### SA-08: The same archive trap exists for phase 83's recorded Codex evidence

**Where:** `tests/test_codex_report_status.py:483-494`, `tests/test_codex_review_run.py:41`
**Why excluded:** These files are outside this round's file scope. Commit 5213f02 already records the trap in `.planning/backlog/MAINTENANCE.md:114`. `_CODEX_DIR` is only a path at import time, and the file is read inside `_assess_recorded`. So archiving phase 83 makes those tests fail at run time, not at collection, and the failure is loud.
**Effect if left as is:** Archiving milestone v2.13 before the fixtures move turns `test` red on main. Every PR, including Dependabot's, would then fail until someone fixes it. This is the same kind of harm b0e1ee4 just fixed.
**Needs:** Owner ruling on timing. My recommendation is to move the fixtures to `tests/fixtures/` before the milestone archive step, as the backlog item says.

### SA-09: `.github/tool-pins.env` is not on the sensitive-path list

**Where:** `docs/review-classification-policy.md:14` (lists `.github/workflows/**` and `.github/scripts/**`, not the other files under `.github/`)
**Why excluded:** Today a real pin change has to touch `ci.yml`, so the PR is classed as sensitive anyway, and an edit to the pins file alone fails CI. No gap exists today.
**Effect if left as is:** None, as long as the cross-check test exists. If that test were ever removed or weakened, a pins-file-only PR could be classed as ordinary.
**Needs:** No ruling needed unless the owner wants the policy to name `.github/tool-pins.env` (and `.github/os-scan-exceptions.json`, `.github/dependabot.yml`) explicitly.

### SA-07 (carried from iteration 8): When stderr is not captured, `exc.stderr` gets a made-up drain marker

Unchanged from `85-REVIEW.iter8.md`.

### SA-01 to SA-06 (carried from iteration 7)

Unchanged from `85-REVIEW.iter7.md`: SA-01 (acceptance runs on the gate it introduces), SA-02 (register schema cutover strands open PRs), SA-03 (Dependabot `uv` has no cooldown), SA-04 (a runner-changing PR can certify its own base cross-grade; owner-recorded follow-up), SA-05 (reusable workflows and local actions are not inspected; owner-recorded follow-up), SA-06 (digit splitting creates initial-like false positives; inside the accepted residual). These commits do not touch any of them.

---

_Reviewed: 2026-10-28T20:12:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
