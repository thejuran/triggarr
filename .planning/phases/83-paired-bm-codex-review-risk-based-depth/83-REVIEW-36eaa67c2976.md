---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-23T17:30:00Z
head: 36eaa67c29764e008cdafe5babbd55a69f70b834
base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
review_kind: final re-review after round 3 (bf4fb5f..0ffa806) and round-4 test fix 272701f; prior review preserved as 83-REVIEW-dbe1b7f56bdd.md
depth: standard
files_reviewed: 18
files_reviewed_list:
  - .planning/config.json
  - .claude/schemas/codex-review-findings.schema.json
  - CLAUDE.md
  - docs/bm-review-baseline-2026-10-22.md
  - docs/buildomator-greptile-pilot.md
  - docs/codex-adversarial-review-contract.md
  - docs/owner-cli-acceptance.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - tests/codex_report_status.py
  - tests/codex_review_run.py
  - tests/test_app_cards.py
  - tests/test_codex_report_status.py
  - tests/test_codex_review_contract.py
  - tests/test_codex_review_run.py
  - tests/test_review_checkpoint_record.py
  - tests/test_review_instructions.py
  - triggarr/templates/partials/cycle_grade.html
prior_findings:
  fixed_verified: 8
  still_present: 3
  not_applicable: 0
  resolved_by_owner_ruling: 1
findings:
  critical: 0
  warning: 0
  info: 6
  total: 6
status: issues_found
---

# Phase 83: Code Review Report (final re-review)

**Reviewed:** 2026-10-23T17:30:00Z
**Head:** `36eaa67c29764e008cdafe5babbd55a69f70b834`
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found (Info only)

## Summary

This pass checks the round-3 fixes (`f9f20c8`..`0ffa806`) and the round-4 test fix (`272701f`) against every finding in `83-REVIEW-dbe1b7f56bdd.md`, then reviews the code those fixes added.

**Prior findings.** The Critical and both Warnings are fixed, and I checked each one:

- **CR-01:** the evidence copy is now created without following links, and a head that already has anything at that path is refused.
- **WR-01:** `.planning/config.json` is back in Codex's review diff.
- **WR-02:** untrusted heads are now refused outright.

IN-03, IN-04, IN-05 and IN-06 are fixed. The owner's SA-01 ruling ("red Failed cards always say failure reason(s)") is implemented as ruled. IN-01 and IN-02 are still present. The owner classified both as non-blocking debt and excluded them from fixing. IN-07, the dry-run preview gap, is also still present: it was carried into round 3 under decision 4 and got no fix.

**New issues:** none at Critical or Warning. Three small Info items:

- The contract still says `--untrusted --dry-run` previews a run, but the runner now refuses it.
- One write between the reservation and the guarded block can still fail without leaving a status record.
- A git failure in the post-run audit is labeled "inputs changed".

**Checks run:**

- **Tests:** the six reviewed test modules pass (310 passed). `ruff check triggarr/ tests/` is clean.
- **Real-run evidence:** the round-3 Codex outputs at `f46f18ccac12` show `<tmp>/pytest-of-<user>/…` in `.pytest.txt`, with no home path. `.prompt.txt` and `.meta.json` contain no local paths. Codex reported one finding, F001, which `272701f` fixes.
- **Diff scope:** `git diff --name-only 6f3841a..HEAD` with the v5 pathspecs lists `.planning/config.json` and `83-config-before.json`, and no `.planning/**/*.md` or `codex/` file.

## Narrative Findings (AI reviewer)

### Status of prior findings (83-REVIEW-dbe1b7f56bdd.md)

| Prior ID | Title | Status at 36eaa67 | Verification |
|---|---|---|---|
| CR-01 | An untrusted head can overwrite operator files through the evidence copy | **Fixed and verified** | `_write_evidence_copy` (`tests/codex_review_run.py:300-319`) refuses when `os.path.lexists(<wt>/.codex-review-evidence)`. It then creates the directory with a plain `mkdir()` and the file with `O_WRONLY\|O_CREAT\|O_EXCL\|O_NOFOLLOW`. An `OSError` there becomes a `RunnerError` and is written to the stub. `test_evidence_copy_refuses_pre_existing_paths` covers four cases: a symlinked directory, a symlinked file, a dangling symlink and a regular file. In each one the outside sentinel is unchanged, the stub is `incomplete`, Codex does not run, and the worktree and scratch directory are removed. `test_evidence_copy_is_created_exclusively_without_following_links` pins the flags. A second layer of protection: untrusted heads no longer get a worktree at all (`execute()` `:473-474`, `main()` `:647-649`). |
| WR-01 | Template v4 dropped `.planning/config.json` from Codex's review | **Fixed and verified** | `EXCLUDE_PATHSPECS` (`:80-84`) is narrowed to `**/codex/**`, `**/*.jsonl` and `**/*.md`. The fixed prompt (template v5) and the contract scope section match it. A drift test reads the policy's sensitive row and asserts that every listed path survives `diff_argv` (`test_codex_review_run.py:150-175`). I confirmed with `git diff --name-only` that `.planning/config.json` is in scope and that `STATE.md`, `ROADMAP.md` and the `83-*.md` files are not. |
| WR-02 | `--untrusted` didn't stop the head from steering Codex through `AGENTS.md` or running code through Codex | **Fixed and verified (attack surface removed)** | Owner decision: Codex is not run for untrusted heads until Phase 85. `main()` returns 2 before any command runs. `execute()` also raises `RunnerError(UNTRUSTED_REFUSAL)` first, as a second layer. `_forbid_everything` tests confirm no subprocess runs and no temp dir is created. The checkpoint record gains `Codex: PENDING — untrusted source`. `project_doc_max_bytes=0` was not added. With only trusted heads reviewed, that is acceptable for now, and it belongs to the Phase 85 hardening. |
| IN-01 | Template classifies reason rows by their wording | **Still present** (owner: non-blocking debt, excluded) | `cycle_grade.html:19-28` is unchanged. Carried forward as IN-01. |
| IN-02 | `test_never_reports_clean` is tautological | **Still present** (owner: non-blocking debt, excluded) | `test_codex_report_status.py` is unchanged. Carried forward as IN-02. |
| IN-03 | An `OSError` after the reservation leaves no status record | **Fixed and verified** | `execute()` now catches `OSError` next to `RunnerError`, writes a stub and re-raises as `RunnerError` (`:511-516`). `mkdtemp` failure is also stubbed (`:496-501`). `main()` prints "use the next attempt number" only for a real `FileExistsError` (existing outputs or a lost reservation). A covering test exists (`test_oserror_after_reservation_writes_status_stub`). A one-line remainder is in new IN-05. |
| IN-04 | Checker raises on an integer longer than 4300 digits | **Fixed and verified** | `except ValueError` comes after the two subclass handlers (`codex_report_status.py:332-336`) and returns `incomplete`. A test exists. |
| IN-05 | pytest temp paths publish the username | **Fixed and verified** | `redact_local_paths` adds `tempfile.gettempdir()` (both raw and resolved) → `<tmp>`, and `pytest-of-<user>` → `pytest-of-<user>`. Replacements are applied longest first, so scratch is replaced before tmp, and the repo before home. The real round-3 `.pytest.txt` shows `<tmp>/pytest-of-<user>/pytest-512/…`, with no home path. |
| IN-06 | Checker hashes recorded at launch, checker run after Codex finishes | **Fixed and verified** | `audit_inputs()` is repeated just before the checker and compared with `meta["inputs"]`. On a mismatch or a dirty input, a stub is written and the run returns 1 (`:534-542`). A test exists. A labeling nit is in new IN-06. |
| IN-07 | `--dry-run` doesn't warn about a stale head or dirty inputs | **Still present** | `dry_run()` (`:562-590`) still only prints the `git status` command with "must be empty". It does not compare `--head` with HEAD. It was carried into round 3 under decision 4 but not fixed. The effect is still low, because the real run refuses cleanly. Carried forward as IN-03. |
| SA-01 | Red Failed skip-only card says "skipped records" | **Resolved by owner ruling and implemented** | The skipped-record branch now also requires `app.last_cycle.grade != 'failed'` (`cycle_grade.html:33`). The D-01 test was rewritten to expect "Show 1 failure reason" with the row text unchanged. A new parametrized test covers per-queue rows and the legacy aggregate row. The Partial and Success skipped-record tests still pass. |

Codex `f46f18ccac12:a1:F001` (the `os.open` spy dropped `dir_fd`, so `shutil.rmtree` failed on a clean checkout): **fixed and verified** in `272701f`. The spy now forwards `**kwargs`. The test passes in this run.

## Info

### IN-01 (carried from dbe1b7f56bdd IN-01): Template classifies reason rows by matching the wording `outcome.py` produces

**File:** `triggarr/templates/partials/cycle_grade.html:19-28`
**Issue:** Unchanged. Round 3 added a fifth hand-written condition to the summary branch (`grade != 'failed'`). Owner classification: non-blocking debt, refactor excluded from this phase.
**Fix:** Have `cycle_view` emit a `kind` per row, or a precomputed summary label, and branch on that.

### IN-02 (carried from dbe1b7f56bdd IN-02): `test_never_reports_clean` is tautological

**File:** `tests/test_codex_report_status.py` (`test_never_reports_clean`)
**Issue:** It only asserts that the word "clean" never appears in the status or reasons, and no code path produces it. Its last scenario is a complete report. Owner classification: non-blocking debt.
**Fix:** Delete it, or assert `status == "incomplete"` for the first five scenarios.

### IN-03 (carried from dbe1b7f56bdd IN-07): `--dry-run` preview doesn't run the stale-head or dirty-input checks

**File:** `tests/codex_review_run.py:562-590`
**Issue:** The contract makes the dry run the preview step. The preview still doesn't say when the real run will be refused.
**Fix:** In `dry_run()`, run the two read-only git checks (`git status --porcelain -- <AUDITED_INPUTS>`, and `git rev-parse HEAD` compared with `--head`), and print `# WARNING: …` lines without failing.

### IN-04 (new): The contract still says `--untrusted --dry-run` previews the run, but the runner refuses it

**File:** `docs/codex-adversarial-review-contract.md:55` (Invocation step 3); `tests/codex_review_run.py:647-649`
**Issue:** Step 3 shows `--trusted|--untrusted --dry-run` and says it "renders the prompt and prints every command". Since round 3, `main()` returns 2 with `UNTRUSTED_REFUSAL` for every `--untrusted` call, before it checks `--dry-run`. Step 2 of the same contract describes the refusal correctly, so step 3 contradicts it. An operator following step 3 for a Dependabot PR gets an error where the contract promised a preview. The outcome is still the safe one.
**Fix:** In step 3, change `--trusted|--untrusted` to `--trusted`, and add "(`--untrusted` is refused, see step 2)".

### IN-05 (new): A failed `.meta.json` write still leaves a reservation with no status record

**File:** `tests/codex_review_run.py:493-494`
**Issue:** `reserve_outputs()` creates `.prompt.txt`, and then `run.output(".meta.json").write_text(...)` runs outside any `try`. If that write raises `OSError` (disk full, permissions), `.prompt.txt` exists but `.status.json` does not. That is the state IN-03 was meant to rule out. `main()` doesn't catch a bare `OSError`, so the operator also sees a traceback. This is unlikely, and the effect is limited to a confusing retry.
**Fix:** Wrap the meta write so a failure stubs and re-raises:
```python
try:
    run.output(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
except OSError as exc:
    reason = f"harness could not write provenance: {type(exc).__name__}"
    _write_status_stub(run, reason)
    raise RunnerError(reason) from exc
```

### IN-06 (new): A git failure in the post-run audit is recorded as "audited inputs changed during the run"

**File:** `tests/codex_review_run.py:534-538`
**Issue:** `audit_inputs()` raises `RunnerError` in two cases: when an input is dirty, and when `git status` itself fails (`_git_stdout`: "could not run" / "exited N"). Both are prefixed "audited inputs changed during the run: …". The status is correctly `incomplete`, but the record can claim the inputs changed when git simply failed.
**Fix:** Use a neutral prefix, such as `"could not re-audit inputs after the run: {exc}"`. Keep "changed" for the hash-mismatch branch at `:539-542`.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-10-23T17:30:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
