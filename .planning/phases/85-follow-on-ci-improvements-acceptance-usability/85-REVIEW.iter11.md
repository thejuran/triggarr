---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T20:49:04Z
reviewed_head: 44d34e231b2789f7927c5b89e84e4723a00733bc
diff_base: b272d82
iteration: 11
depth: standard
files_reviewed: 1
files_reviewed_list:
  - tests/test_codex_review_run.py
findings:
  critical: 0
  warning: 1
  info: 7
  total: 8
status: issues_found
---

# Phase 85: Code Review Report (iteration 11, confirming the iteration-10 WR-01 fix)

**Reviewed:** 2026-10-28T20:49:04Z (head `44d34e231b2789f7927c5b89e84e4723a00733bc`, diff base `b272d82`)
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found (1 warning, info items; no blocker)

## Summary

Scope: `git diff b272d82..44d34e2 -- tests/test_codex_review_run.py`, which is commit 44d34e2.

Verification on this tree:
- `uv run ruff check tests/test_codex_review_run.py`: clean.
- `uv run pytest tests/test_codex_review_run.py -k kills_active_process_group`: 2 passed. See WR-02 for why they pass.
- `.planning/phases/` has no `00-*` folder, and `git status` is clean.

**Iteration-10 WR-01: resolved.** The autouse fixture now points `runner.REPO_ROOT` at the test's own `tmp_path` and creates `PHASE_DIR` there with `mkdir(parents=True)`. Nothing is written into the real checkout, and pytest cleans up `tmp_path`, so concurrent runs have no shared folder to race on. I checked how the fixture interacts with the rest of the module:
- Pytest gives the fixture and the test the same `tmp_path`. All six removed `(tmp_path / PHASE_DIR).mkdir(parents=True)` lines would have raised `FileExistsError`, and all six are gone. No plain `mkdir(parents=True)` of `PHASE_DIR` remains. The child harness now uses `exist_ok=True`. `_tmp_run`'s `scratch` folder and the harness's `tmp_root / "scratch"` do not collide with `.planning/`.
- `test_output_base_naming` compares against `runner.REPO_ROOT`, so it checks the patched value.
- `test_checker_argv` pins `runner.REPO_ROOT` back to the real checkout. That keeps the one test that asserts the real `tests/codex_report_status.py` path meaningful.
- Reads of `docs/` and `tests/codex_report_status.py` (lines 184, 309, 1260, 1396) still go through the imported `REPO_ROOT` constant. The constant was bound at import time and the patch does not change it. `HARNESS_ROOT` hashing (line 1359) and the mid-Codex harness's `cwd=runner.HARNESS_ROOT` (line 2371) are not affected.
- The redaction tests already used `tmp_path` through `_tmp_run`, so the `(REPO_ROOT, "<repo>")` redaction entry behaves as before.
- `FakeRunner` intercepts every runner command that uses `cwd=REPO_ROOT` (codex, checker, worktree add and remove). `_real_bytes_for` drops `cwd` before running its real child. No real `git` command now runs in a `tmp_path` that is not a repository.
- The dry-run test's `"tests/codex_report_status.py" in out` check now matches `<tmp_path>/tests/codex_report_status.py`. That is a substring check. The real path is still covered by `test_checker_argv`.

**Regression found (WR-02):** `_assert_signal_kills_active_process_group` still starts its child with `cwd=runner.REPO_ROOT`. The iteration-10 fix note asked for this line to be checked, and it was not changed. It now runs in `tmp_path`, and it only passes because of the editable install's `.pth` file.

**IN-06 and IN-07 (iteration 10): resolved.** The `rmtree` teardown and the function-local `import shutil` were removed along with the old fixture.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Warnings

### WR-02: The SIGTERM/SIGHUP process-group test now imports the runner from wherever the venv's editable install points, not from the checkout under test

**File:** `tests/test_codex_review_run.py:2003-2006`
**Issue:** The child is `python -c _REPORT_ACTIVE_GROUP_THEN_RUN`, and the script starts with `from tests import codex_review_run as runner`. With `-c`, `sys.path[0]` is the working directory. Before 44d34e2 the working directory was the real checkout, so `tests` was always this checkout's package. The autouse fixture now sets `runner.REPO_ROOT` to `tmp_path`, so the child runs in an empty temp folder with no `tests/` in it. The import only works because hatchling's editable install writes `.venv/lib/python3.11/site-packages/_editable_impl_triggarr.pth`, which contains `/Users/julianamacbook/triggarr`. I confirmed that from `/tmp`, `import tests` resolves to `/Users/julianamacbook/triggarr/tests/__init__.py` through that file.

This has two effects:
1. If the venv's editable install points at a different checkout, the test checks that checkout's `install_signal_handlers` and `run_command`, not the code under review. This happens with a shared `UV_PROJECT_ENVIRONMENT`, a git worktree reusing another checkout's venv, or an agent sandbox copy. The test can pass while the code under review is broken. This is the "test silently stopped exercising the real checkout" case.
2. In a non-editable install (`uv sync --no-editable`, `pip install .`), the child fails with `ImportError`. The test then reports a 5-second `TimeoutError: pgid.txt was never written`, which hides the real cause.

CI uses `uv sync --locked --extra dev`, which is editable, so CI passes today. That is why this is a WARNING and not a BLOCKER. The sibling harness at line 2371 already uses `cwd=runner.HARNESS_ROOT`, which is the correct pattern.
**Fix:**
```python
    child = subprocess.Popen(
        [sys.executable, "-c", _REPORT_ACTIVE_GROUP_THEN_RUN, str(pid_file)],
        cwd=runner.HARNESS_ROOT,
    )
```

## Info

### IN-08: The fixture docstring says REPO_ROOT is "only the output root", but the runner also uses it as the git/codex/checker working directory and the checker path

**File:** `tests/test_codex_review_run.py:48-51`
**Issue:** The runner's own comment (`tests/codex_review_run.py:68-69`) says REPO_ROOT is "where outputs are written and git commands run". It is the `cwd` for codex (766), the base and current checkers (1010, 1214), and worktree add and remove (1070, 1186). It is also the source of the checker path (413) and the `<repo>` redaction entry (665). Those uses are safe in tests today only because `FakeRunner` intercepts every such command and `test_checker_argv` re-pins the root. The docstring's "only" invites a future test to run a real command against `runner.REPO_ROOT` and get a temp folder instead of the repo. WR-02 is an example of this.
**Fix:** Reword it to something like: "Every test sees REPO_ROOT (output root, and cwd for git/codex/checker commands) as its own tmp_path; anything that needs the real checkout must use HARNESS_ROOT or the imported REPO_ROOT constant."

### IN-09: Seven now-redundant `monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)` lines remain

**File:** `tests/test_codex_review_run.py:331, 495, 627, 670, 685, 1100, 1240` (also 2391)
**Issue:** These lines are harmless, because the fixture already set the same value with the same `tmp_path`. The matching `mkdir` lines were removed. The setattr lines now read as if the test had to opt out of the real checkout, which is no longer true.
**Fix:** Optional. Remove them, or leave them as explicit documentation. Do not change behavior either way.

### IN-05 (carried from iteration 9): The pins file header points to evidence in a phase folder that will be archived, and nothing checks its "checked" date

**File:** `.github/tool-pins.env:1-5` (not in this round's scope)
**Issue:** Recorded as in iteration 9. Not re-raised.

### IN-03 (carried from iteration 8): The drain-timeout fallback decodes as UTF-8 and ignores the caller's `encoding`, `errors` and newline handling

**File:** `tests/codex_review_run.py:211-222` (not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-04 (carried from iteration 8): The new end-to-end test assumes the child prints within one second

**File:** `tests/test_codex_review_run.py:2079-2111` (line numbers before b272d82; about +10 at 44d34e2; not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-01 (carried from iteration 7, owner left out of scope): The Node detector's quoted-key support misses YAML escape spellings

**File:** `.github/scripts/ci-job-consistency.cjs:589-596` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

### IN-02 (carried from iteration 7, owner left out of scope): Run-splitting logic is duplicated

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 133-137` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

## Resolved this iteration (not counted)

- **WR-01 (iteration 10):** The placeholder folder in the real checkout raced between pytest runs and could be left behind. Resolved by 44d34e2, which uses a per-test `tmp_path` root. The orchestrator ran the module 9 times concurrently with 153/153 passing each time, and no folder was left under `.planning/phases`.
- **IN-06 (iteration 10):** The `rmtree(..., ignore_errors=True)` teardown. Resolved, because the teardown is gone and pytest handles cleanup.
- **IN-07 (iteration 10):** The function-local `import shutil`. Resolved, because the import was removed with the fixture body.

## Accepted residuals (carried, not counted)

### Iteration-7 WR-01: Run-together reviewer names typed in one case (`claudecode`, `bmreviewer`, `gsdagent`, `codexreviewrun`) still pass

**File:** `.github/scripts/codex-fallback.cjs:113-137`
**Status:** The owner accepted this as a residual after iteration 7. Recorded here for continuity. Not re-raised, and not counted in `findings`.

## Set aside (needs ruling)

### SA-11: No test covers `main()`'s "phase-dir does not exist" refusal

**Where:** `tests/codex_review_run.py:1391-1392`, `tests/test_codex_review_run.py:46-53`
**Why excluded:** This gap existed before this commit, and the change did not add it. Now that every test gets an existing `PHASE_DIR`, a test for that branch would have to use a different phase dir or remove the folder first.
**Effect if left as is:** If a regression dropped the check, `--phase-dir` typos would write outputs under a new, unintended folder without any warning. That is a minor annoyance for whoever runs the harness. It does not affect review results.
**Needs:** A ruling on whether to add a one-line test (`main(_cli(Path(".planning/phases/does-not-exist"), "--dry-run", "--trusted"))` raises `SystemExit(2)`) in this phase or defer it.

### SA-10 (carried from iteration 10): The fixture copies and the phase-83 originals can drift apart

Unchanged from `85-REVIEW.iter10.md`.

### SA-08 (carried from iteration 9): resolved by b272d82

Unchanged from `85-REVIEW.iter10.md`. The placeholder problem it led to (iteration-10 WR-01) is now resolved too.

### SA-09 (carried from iteration 9): `.github/tool-pins.env` is not on the sensitive-path list

Unchanged from `85-REVIEW.iter9.md`.

### SA-07 (carried from iteration 8): When stderr is not captured, `exc.stderr` gets a made-up drain marker

Unchanged from `85-REVIEW.iter8.md`.

### SA-01 to SA-06 (carried from iteration 7)

Unchanged from `85-REVIEW.iter7.md`: SA-01 (acceptance runs on the gate it introduces), SA-02 (register schema cutover strands open PRs), SA-03 (Dependabot `uv` has no cooldown), SA-04 (a runner-changing PR can certify its own base cross-grade; owner-recorded follow-up), SA-05 (reusable workflows and local actions are not inspected; owner-recorded follow-up), SA-06 (digit splitting creates initial-like false positives; inside the accepted residual). This commit does not touch any of them.

---

_Reviewed: 2026-10-28T20:49:04Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
