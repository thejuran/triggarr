---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T20:39:52Z
reviewed_head: b272d82fd7679350cebadda1fff8ced30f87147e
diff_base: 5592e4e
iteration: 10
depth: standard
files_reviewed: 7
files_reviewed_list:
  - tests/test_codex_report_status.py
  - tests/test_codex_review_run.py
  - tests/fixtures/codex-recorded/322afc50367d-postfix-a1.last.json
  - tests/fixtures/codex-recorded/322afc50367d-postfix-a2.last.json
  - tests/fixtures/codex-recorded/a7995baf187e-quick-a1.last.json
  - tests/fixtures/codex-recorded/d501a68316b2-explicit-a1.last.json
  - tests/fixtures/codex-recorded/d501a68316b2-explicit-a2.last.json
findings:
  critical: 0
  warning: 1
  info: 7
  total: 8
status: issues_found
---

# Phase 85: Code Review Report (iteration 10, post-merge archive-safe fixtures)

**Reviewed:** 2026-10-28T20:39:52Z (head `b272d82fd7679350cebadda1fff8ced30f87147e`, diff base `5592e4e`)
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found (1 warning, info items; no blocker)

## Summary

Scope: `git diff 5592e4e..b272d82 -- tests/`, which is commit b272d82. The later commit on `archive-safe-fixtures` (1eb1a67) changes `.planning/` only and is out of scope.

Verification on this tree:
- `uv run pytest tests/test_codex_report_status.py tests/test_codex_review_run.py -q`: 280 passed. The placeholder folder is gone after a single run.
- `uv run ruff check` on both test files: clean.
- `gsd-tools verify conventions --check` on both test files: no findings.
- `cmp` of each of the five fixtures against `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/`: byte-identical.

**Fixture copies (test_codex_report_status.py): sound.** `_assess_recorded` takes the head and base from the report itself, so the tests do not depend on the folder name. I re-ran the assessment on each copy. `322afc50367d-postfix-a1` is still `incomplete` for the recorded reasons (it declares itself incomplete in its summary and limitations, and lists files it did not fully read). The two v2 `complete` reports return no reasons. The v1 pair still needs the legacy path. Each recorded-history test still checks real recorded output, not a synthetic copy. No other test in `tests/` or `.github/scripts/` reads a real phase folder. The remaining `.planning/phases/8x-x/...` strings are synthetic pathspec samples.

**Placeholder phase folder (test_codex_review_run.py): works for one run at a time, but writes into the real checkout (WR-01).** No test writes output files into `REPO_ROOT / PHASE_DIR`. Every test that calls `main()` against the real `REPO_ROOT` is a dry run or exits on an argument error (lines 398, 418, 606, 666, 710). The two dry-run tests compare before and after for every output suffix. Every test that writes output first moves `runner.REPO_ROOT` to `tmp_path`. The subprocess harness at line 2329 does the same. Before this commit, the dry-run tests checked `.planning/phases/83-.../codex/` for `aaaaaaaaaaaa-*` files. Now they check an empty folder, which is an equal or stronger guarantee.

xdist is not installed or configured (`pyproject.toml` has no `-n`), so a single CI run cannot race itself. Two pytest runs in the same checkout can, though. I started three runs of this module at once, three times: one of nine runs failed, and the placeholder folder was left behind afterwards. See WR-01. I removed the empty leftover folder after the probe; `git status` is clean.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: The per-test placeholder folder in the real checkout races between pytest runs and can be left behind permanently

**File:** `tests/test_codex_review_run.py:46-59`
**Issue:** The autouse fixture is function-scoped. It creates and deletes `<repo>/.planning/phases/00-codex-runner-test-fixture` around each of the module's 153 tests, and `created = not path.exists()` decides who owns the cleanup. If two pytest runs share one checkout (for example, an agent running the full suite in the background while another runs a targeted test, or two terminals), the following happens:
1. Run A sees no folder and owns it. Run B sees A's folder (`created = False`). A's teardown removes the folder while B is between `path.mkdir`'s internal steps, or while B's test is inside `main()`. I reproduced this: `ERROR at setup of test_contract_documents_untrusted_sources`, `FileExistsError` raised from `path.mkdir(parents=True, exist_ok=True)` (pathlib's `mkdir` failed, then its follow-up `is_dir()` saw the folder already removed). If the removal lands during `main()`, the result is a spurious `phase-dir does not exist` exit 2.
2. The last run to finish may be one that saw `created = False`. It then leaves the folder in place. I reproduced this too. After that, every later run also sees `created = False`, so nothing removes it again. The same happens after a hard kill (`SIGKILL`, a second Ctrl-C) between setup and teardown. The folder is empty, so `git status` does not show it. But BM/GSD phase tooling and the Roadmaps page scan `.planning/phases/`, and they would see a stray "phase 00".
3. In a read-only checkout, every test in the module now errors at setup. Before this change, this module needed no writes to the repo.

The effect is flaky test failures and leftover state, not wrong results in CI. That is why this is a WARNING, not a BLOCKER.
**Fix:** Stop writing into the real checkout. Point the runner's output root at `tmp_path` for every test, and create the placeholder there:
```python
@pytest.fixture(autouse=True)
def _placeholder_phase_dir(tmp_path, monkeypatch):
    """main() requires --phase-dir to exist; give every test its own repo root so
    no test touches the real checkout's .planning/phases/."""
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / PHASE_DIR).mkdir(parents=True)
```
Then:
- Remove the now-redundant `monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)` / `(tmp_path / PHASE_DIR).mkdir(...)` pairs. If they are kept, change them to `mkdir(parents=True, exist_ok=True)`, because the existing `mkdir(parents=True)` calls would otherwise raise `FileExistsError`.
- Change line 242 to compare against `runner.REPO_ROOT`, not the imported constant.
- Keep reading `docs/` and `tests/codex_report_status.py` through the imported `REPO_ROOT` constant (lines 190, 313, 1270, 1406), which the patch does not change.
- Check `_assert_signal_kills_active_process_group` (line 2015, `cwd=runner.REPO_ROOT`). Under the patch it would run in `tmp_path`, so pin it to the imported `REPO_ROOT` if it needs the repo on its import path.

A smaller alternative is to keep the real-repo folder but make the fixture `scope="module"`, name the folder per process (for example `00-codex-runner-test-fixture-{os.getpid()}`), and always remove it when it is empty. That narrows the race but still writes into the checkout.

## Info

### IN-06: Teardown uses `rmtree(..., ignore_errors=True)`, which would quietly delete anything a test wrongly wrote there

**File:** `tests/test_codex_review_run.py:58-59`
**Issue:** Before this commit, a regression that wrote real runner output into the phase folder showed up as untracked files under phase 83's `codex/` folder. Now the fixture deletes the whole tree without checking, and ignores errors. The two dry-run tests still check before and after explicitly, so today's coverage holds. But the folder no longer acts as a passive guard for other `main()` tests, and a failed removal is never reported. The cleanup also removes only the leaf folder. If `.planning/phases/` was missing (for example, after a full archive), it creates `.planning/phases/` and leaves it behind.
**Fix:** This is resolved by the WR-01 fix (use `tmp_path`, so pytest handles cleanup). If the real-repo folder stays, use `path.rmdir()` so a non-empty folder fails loudly, and do not ignore errors.

### IN-07: `import shutil` is inside the fixture body

**File:** `tests/test_codex_review_run.py:51`
**Issue:** This is minor. The module imports at the top elsewhere, and other tests in this file use function-local imports (`import json as _json`, `import os`) by local habit. It is harmless, and the WR-01 fix removes it.
**Fix:** Drop it with the WR-01 fix, or move it to the module imports.

### IN-05 (carried from iteration 9): The pins file header points to evidence in a phase folder that will be archived, and nothing checks its "checked" date

**File:** `.github/tool-pins.env:1-5` (not in this round's scope)
**Issue:** Recorded as in iteration 9. Not re-raised.

### IN-03 (carried from iteration 8): The drain-timeout fallback decodes as UTF-8 and ignores the caller's `encoding`, `errors` and newline handling

**File:** `tests/codex_review_run.py:211-222` (not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-04 (carried from iteration 8): The new end-to-end test assumes the child prints within one second

**File:** `tests/test_codex_review_run.py:2079-2111` (line numbers before b272d82; about +18 after it; not in this round's scope)
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

### SA-08 (carried from iteration 9): resolved by b272d82

**Where:** `tests/test_codex_report_status.py:483-486`, `tests/test_codex_review_run.py:41-59`
**Status:** Both suites no longer read phase 83's folder. The fixture copies are byte-identical, and the orchestrator ran the suites with phases 82-85 moved away. The placeholder approach has its own problem, recorded as WR-01. No ruling is needed for SA-08 itself.

### SA-10: The fixture copies and the phase-83 originals can drift apart

**Where:** `tests/fixtures/codex-recorded/*.last.json`, `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/`
**Why excluded:** The duplication is intentional, and the originals are records that should never change. Nothing checks that the two sets match while both exist. That check would break once the originals are archived, which defeats the purpose.
**Effect if left as is:** None in practice. If someone edited one copy, the "recorded history" tests could grade text that no longer matches the original record. The comment at lines 483-485 states the origin.
**Needs:** No ruling needed unless the owner wants a SHA-256 manifest of the five files kept next to the fixtures as a tamper check that survives archiving.

### SA-09 (carried from iteration 9): `.github/tool-pins.env` is not on the sensitive-path list

Unchanged from `85-REVIEW.iter9.md`.

### SA-07 (carried from iteration 8): When stderr is not captured, `exc.stderr` gets a made-up drain marker

Unchanged from `85-REVIEW.iter8.md`.

### SA-01 to SA-06 (carried from iteration 7)

Unchanged from `85-REVIEW.iter7.md`: SA-01 (acceptance runs on the gate it introduces), SA-02 (register schema cutover strands open PRs), SA-03 (Dependabot `uv` has no cooldown), SA-04 (a runner-changing PR can certify its own base cross-grade; owner-recorded follow-up), SA-05 (reusable workflows and local actions are not inspected; owner-recorded follow-up), SA-06 (digit splitting creates initial-like false positives; inside the accepted residual). This commit does not touch any of them.

---

_Reviewed: 2026-10-28T20:39:52Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
