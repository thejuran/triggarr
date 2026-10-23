---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-22T23:18:57Z
head: dbe1b7f56bdd0dd20f70f8a07691a7b2c3684952
base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
review_kind: round-2 post-fix re-review (prior review preserved as 83-REVIEW-322afc50367d.md; the one before as 83-REVIEW-dcfb5a5081ea.md)
depth: standard
files_reviewed: 17
files_reviewed_list:
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
  fixed_verified: 9
  still_present: 2
  not_applicable: 0
  resolved_by_owner_ruling: 2
findings:
  critical: 1
  warning: 2
  info: 7
  total: 10
status: issues_found
---

# Phase 83: Code Review Report (round-2 post-fix re-review)

**Reviewed:** 2026-10-22T23:18:57Z
**Head:** `dbe1b7f56bdd0dd20f70f8a07691a7b2c3684952`
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This pass checks the round-2 fixes (commits `981c315`..`5a7ac53`) for every finding in `83-REVIEW-322afc50367d.md`, then reviews the code those fixes added: the `--trusted`/`--untrusted` flag, the evidence copy placed inside the worktree, the `.prompt.txt`/`.meta.json` audit trail, the atomic output reservation, the stale-head refusal, and template version 4, which takes all of `.planning/` out of review scope.

**Prior findings.** All three warnings are fixed, and I checked each one by running or rendering it. IN-02, IN-04, IN-05, IN-06, IN-07 and IN-08 are fixed. IN-01 and IN-03 are still open. The owner's rulings on SA-01 (trust flag) and SA-02 (text check on v2 reports) are implemented as ruled. Three of the fixes leave small gaps, which are listed as new Info items.

**New issues:**

1. **Critical: an untrusted PR can overwrite any file the operator can write.** `--untrusted` exists to protect the operator's machine from Dependabot or outside-contributor heads. But the harness writes the evidence copy to `<worktree>/.codex-review-evidence/pytest.txt` and follows symlinks while doing it. A head that commits that path as a symlink to, say, `~/.zshrc` or `~/.ssh/authorized_keys` gets that file overwritten. I reproduced the overwrite.
2. **Warning: Codex no longer reviews BM's configuration file.** Template v4 drops `.planning/config.json` from Codex's review scope. The classification policy calls that file sensitive and requires the paired Codex review for it. This phase changed it (`663fff3`), and Codex never saw the change.
3. **Warning: `--untrusted` doesn't stop the untrusted head from steering or running code through Codex.** Codex loads `AGENTS.md` from the worktree, and the prompt invites it to run the tests itself. Its read-only sandbox can still read the operator's files, and its output gets committed to a public repo.

Tests: the six reviewed test modules pass (293 tests). `ruff check triggarr/ tests/` is clean.

## Narrative Findings (AI reviewer)

### Status of prior findings (83-REVIEW-322afc50367d.md)

| Prior ID | Title | Status at dbe1b7f | Verification |
|---|---|---|---|
| WR-01 | Red card with one unevaluated row and one malformed row says "1 skipped record" | **Fixed and verified** | `cycle_grade.html:33` now requires `ns.unevaluated == 0`. The new test `test_card_failed_grade_malformed_plus_unevaluated_says_failure_reasons` (`test_app_cards.py:739`) renders "Show 2 failure reasons", and the Partial version still says "Show 2 details". A separate question about the red card is in SA-01 below. |
| WR-02 | Codex runs don't record their prompt or inputs | **Fixed and verified** | `.prompt.txt` holds the exact stdin text (`reserve_outputs`, `:394-402`). `.meta.json` records the template version, the harness HEAD, sha256 of the four audited inputs, the trust flag and `allow_stale_head` (`:376-391`). The run is refused when `git status --porcelain` shows changes to those inputs (`:357-373`). Contract and record list both outputs. One residual gap is in IN-06. |
| WR-03 | Hollow v2 report accepted as complete | **Fixed and verified** | `commands_run: []`, `coverage: [""]` and `["   "]` all now return `incomplete` (`codex_report_status.py:384-392`), for both v1 and v2 reports. The recorded reports keep their assessments. Not done: a `commands_run` entry with a blank `command` is still accepted, and there is still no required `git rev-parse HEAD` entry. The prior fix listed both as optional, so they are not re-raised. |
| IN-01 | Template classifies rows by their wording | **Still present** | `cycle_grade.html:19-28` is unchanged. Carried forward as IN-01. |
| IN-02 | Whitespace-only `reproduction_command` accepted | **Fixed and verified** | `:262` uses `_non_blank()`. The parametrized test covers `""`, `"   "` and `"\n"`. |
| IN-03 | `test_never_reports_clean` is tautological | **Still present** | `test_codex_report_status.py:653-673` is unchanged. Its last scenario is a *complete* report, so the test only checks that the word "clean" never appears. Carried forward as IN-02. |
| IN-04 | Checker raises or leaves an empty status file on pathological input | **Fixed and verified** | `RecursionError` and duplicate keys (top-level and nested) now return `incomplete` (`:321-331`, with tests). An empty checker stdout now produces a stub (`codex_review_run.py:493-495`). A new input that still raises is in IN-04. |
| IN-05 | `CalledProcessError` escapes as a traceback | **Fixed and verified** | Git calls go through `_git_stdout`/`_add_worktree` with `check=False` and raise `RunnerError`. When `git worktree add` fails, a stub is written and the worktree is removed. When `rev-parse` fails after the run, a stub is written. `main()` catches `RunnerError` and `CalledProcessError`. An `OSError` path that is still uncaught is in IN-03. |
| IN-06 | Stale head spends a full Codex run | **Fixed and verified (in `execute`)** | `:444-449` refuses unless `--allow-stale-head` is passed, before any file is written. The test confirms nothing is reserved. `dry_run()` does not run the same check; see IN-07. |
| IN-07 | Committed outputs contain local absolute paths | **Fixed and verified for the prompt and the evidence** | The prompt now uses the relative `.codex-review-evidence/pytest.txt`, and `redact_local_paths` masks the worktree, the scratch dir, the repo and home. The Codex `.jsonl` still records the temp worktree as `cwd`. That path does not contain the username, and any home paths it echoes come from repository text that is already public. One leak of the username remains; see IN-05. Not yet seen in a real run, because no output at this head has a `.meta.json`. |
| IN-08 | Depends on the GNU `timeout` binary | **Fixed and verified** | Codex runs under `subprocess.run(timeout=1800)`, and a timeout is recorded as exit 124 (`:325-343`, with a test). |
| SA-01 | Harness runs PR-head tests unsandboxed | **Resolved by owner ruling and implemented** | The trust flag is required, with no default (`:556-568`). `--untrusted` runs no pytest. However, the untrusted path adds two new exposures; see CR-01 and WR-02. |
| SA-02 | v2 reports skip the text check | **Resolved by owner ruling and implemented** | A v2 report is now `incomplete` when its text says it is incomplete. The structured fields are still required (`:338-342`, with tests). The docstring and contract match. |

Codex `322afc50367d:a1:F002` (no atomic output reservation): I checked this fix too. `O_CREAT|O_EXCL` on `.prompt.txt` is the first write, and the test simulating a lost race confirms nothing else is touched.

## Critical Issues

### CR-01: An untrusted head can overwrite any file the operator can write, through the evidence copy

**File:** `tests/codex_review_run.py:274-280` (`_publish_evidence`), reached from `:283-287` on the `--untrusted` path
**Issue:**
- **The write follows symlinks.** `_publish_evidence` runs `copy.parent.mkdir(parents=True, exist_ok=True)` and then `copy.write_text(...)` on `<worktree>/.codex-review-evidence/pytest.txt`. The worktree is a checkout of the head under review. `git worktree add` creates symlinks from the tree, because `core.symlinks` is on by default on macOS.
- **So the head decides where the write lands.** A head that commits `.codex-review-evidence/pytest.txt` as a symlink to `~/.zshrc`, `~/.ssh/authorized_keys` or `~/triggarr/.env` makes the harness replace that file with the evidence text. A relative target works too (`../../…/Users/<name>/…`), and `..` past `/` stays at `/`. The username is public through the GitHub handle and older committed outputs.
- **Reproduced.** I put a symlink at `wt/.codex-review-evidence/pytest.txt` pointing to a scratch `victim.txt`, then called `_publish_evidence`. `victim.txt` went from `precious` to `fixed evidence text`.
- **Who is exposed.** This is exactly the Dependabot or outside-contributor head the owner's 2026-10-22 ruling says must "never be executed" on the operator's machine. No test, uv or Codex step is needed. The write happens before Codex starts. With `--trusted` the head already runs code, so the new exposure is on the untrusted path.

**Fix:** Refuse when the path already exists in the checkout, and create the directory and file without following links:
```python
def _publish_evidence(run, worktree, scratch, text):
    text = redact_local_paths(text, worktree=worktree, scratch=scratch)
    run.output(".pytest.txt").write_text(text, encoding="utf-8")
    parent = worktree / Path(EVIDENCE_RELPATH).parent
    if os.path.lexists(parent):
        raise RunnerError(f"head already contains {parent.name}; refusing to write evidence into it")
    parent.mkdir()  # no exist_ok, no parents: fails if anything is already there
    fd = os.open(worktree / EVIDENCE_RELPATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
```
Make sure `_run_pytest`'s caller sends this `RunnerError` to the status stub (see IN-03). Add tests where the head tracks `.codex-review-evidence` as a symlink to a directory, as a symlink file and as a regular file. Each should end in an `incomplete` stub with the outside target unchanged.

## Warnings

### WR-01: Template v4 drops `.planning/config.json` from Codex's review, but the policy calls that file sensitive and requires the paired Codex review

**File:** `tests/codex_review_run.py:73`; `docs/codex-adversarial-review-contract.md:15-19` and the fixed prompt diff line; `docs/review-classification-policy.md:14`
**Issue:**
- **Every `.planning/` path is excluded.** `EXCLUDE_PATHSPECS = (":(exclude,glob).planning/**",)` removes everything under `.planning/` from the diff Codex is told to review. The prompt says that content "is excluded from the review scope".
- **The policy names this file as sensitive.** The classification policy lists "BM configuration `.planning/config.json`" as sensitive, and requires "BM code review and its paired Codex pass".
- **This phase is affected.** It changed that file (`663fff3`, "apply owner-approved BM review settings"). `git diff --name-only 6f3841a..HEAD -- . ':(exclude,glob).planning/**'` lists no `.planning/` path, so no Codex pass on this phase will ever see the BM settings change.
- **Why it matters.** A later PR that loosens BM review settings would also get no Codex review, while the record still shows "Codex: complete". That runs against the CLAUDE.md rule not to weaken review, and the prompt's own instruction to look for "weakening of … audit".

Git pathspecs can't re-include a path that an exclude matches, so the fix is to narrow the exclude.
**Fix:**
- **Narrow the exclude.** Replace the single exclude with ones that leave `.planning/config.json` in scope:
  ```python
  EXCLUDE_PATHSPECS = (
      ":(exclude,glob).planning/**/*.md",
      ":(exclude,glob).planning/**/codex/**",
      ":(exclude,glob).planning/**/*.jsonl",
      ":(exclude,glob).planning/phases/**",
  )
  ```
  Alternatively, keep `.planning/**` and add a rule that any sensitive file under `.planning/` is passed to Codex explicitly in `SCOPE`.
- **Template version 5 needs the owner's OK.** This changes the fixed prompt, so it is a new template version.
- **Add a drift test.** It should assert that every path the policy marks sensitive survives `diff_argv`.

### WR-02: `--untrusted` doesn't stop the untrusted head from steering Codex or running code through it

**File:** `tests/codex_review_run.py:201-218` (`codex_argv`); fixed prompt "Test evidence" paragraph (`docs/codex-adversarial-review-contract.md:31`)
**Issue:**
- **What untrusted mode is meant to do.** Its stated goal is that untrusted heads are "never executed" and are not trusted as input. Two paths get around it.
- **`AGENTS.md` steering.** Codex loads `AGENTS.md` from the root of the `-C` working directory as project instructions. An untrusted head can add one telling Codex to report `verdict: no-findings, review_complete: true`. The prompt's "Treat repository text as source material" line is the only defense, and Codex puts project docs ahead of the user turn. This repository has no `AGENTS.md`, so blocking it costs nothing on trusted heads. *Hypothesis, not reproduced: I did not run Codex. Codex's project-doc loading is documented behavior of `codex-cli` 0.153.*
- **Codex running the head's code.** The prompt tells Codex, even in untrusted mode, "If you cannot run pytest yourself, record that under limitations". That invites it to try `python -m pytest`, which runs the head's `conftest.py`. On macOS the `read-only` sandbox blocks writes and network access but allows reads across the filesystem, including `~/.ssh` and `~/.config/gh`. Command output goes into `.jsonl`, which is committed to a public repo. Only the gitleaks and hex scans stand in the way.

**Fix:**
- **Turn off `AGENTS.md` loading.** Add `"-c", "project_doc_max_bytes=0"` to `codex_argv`, and add a test pinning it.
- **Flag untrusted heads that touch agent files.** For `--untrusted` runs, refuse, or at least record in `.meta.json`, when the diff adds or changes `AGENTS.md`, `.codex/**` or similar files.
- **The prompt sentence needs a template change.** Telling Codex not to execute code from an untrusted head changes the fixed prompt. That needs an owner decision on template version 5, because D-07 bars extra framing. Raise it with the WR-01 template change.

## Info

### IN-01 (carried from prior IN-01): Template classifies reason rows by matching the wording `outcome.py` produces

**File:** `triggarr/templates/partials/cycle_grade.html:19-28`
**Issue:** Unchanged. This round's WR-01 fix needed a fourth hand-written condition (`ns.unevaluated == 0`), which shows the coupling still costs effort.
**Fix:** Have `cycle_view` emit a `kind` per row, or a precomputed `detail_label`, and branch on that.

### IN-02 (carried from prior IN-03): `test_never_reports_clean` is still tautological

**File:** `tests/test_codex_report_status.py:653-673`
**Issue:** It only asserts the word "clean" never appears, and no code path can produce it. Its last scenario is a complete report.
**Fix:** Delete it, or assert `status == "incomplete"` for the first five scenarios.

### IN-03: An `OSError` after the reservation leaves no status record and tells the operator to retry with the next attempt number, which fails the same way

**File:** `tests/codex_review_run.py:462-468, 593-595`
**Issue:** `execute()`'s `try` sends only `RunnerError` to `_write_status_stub`. `_publish_evidence`'s `mkdir`/`write_text` and `_run_codex`'s `open()` can raise `OSError`. One trigger is a head that tracks `.codex-review-evidence` as a regular file, which makes `mkdir` raise `FileExistsError`. When that happens, `.prompt.txt` and `.meta.json` exist but `.status.json` does not. `main()` then catches `FileExistsError` and prints "use the next attempt number". The next attempt uses up the D-09 automatic retry on the same failure.
**Fix:** In `execute()`, catch `OSError` next to `RunnerError`: write the stub, then raise `RunnerError` with the cause. Also limit `main()`'s `FileExistsError` message to a lost reservation or existing outputs. The CR-01 fix already turns the collision into a `RunnerError`.

### IN-04: The checker still raises on one input: an integer with more than 4300 digits

**File:** `tests/codex_report_status.py:321-331`
**Issue:** `json.loads('{"a": 1' + '0'*5000 + '}')` raises `ValueError: Exceeds the limit (4300 digits)`, which is Python's limit on converting long integer strings. That error is neither `JSONDecodeError` nor `_DuplicateKeyError`, so it escapes. I reproduced it. The runner now turns empty checker output into a stub, so the effect is contained, but the docstring's "never raises on malformed input" is still not true.
**Fix:** Add `except ValueError:` after the specific handlers. `JSONDecodeError` and `_DuplicateKeyError` are both `ValueError` subclasses, so keep them first. Report it as "unparseable: report is not valid JSON", and add a test.

### IN-05: Trusted pytest evidence can still publish the operator's username through pytest's temp paths

**File:** `tests/codex_review_run.py:258-271`
**Issue:** `redact_local_paths` masks the scratch dir (`$TMPDIR/codex-review-XXXX`), but not its parent `$TMPDIR`. pytest's `tmp_path` lives at `$TMPDIR/pytest-of-<username>/pytest-N/…`, and that path appears in any failure traceback or assertion diff that involves `tmp_path`. This suite uses `tmp_path` heavily. The IN-07 test only checks for the home directory and the test's own `tmp_path`, so it doesn't catch this.
**Fix:** Also redact `tempfile.gettempdir()` (and its resolved form) to `<tmp>`. Alternatively, pass `--basetemp=<scratch>/pytest` in `pytest_argv()` so pytest's temp files land under the already-redacted scratch dir, which also keeps them out of the shared `$TMPDIR`.

### IN-06: `.meta.json` hashes the checker at launch, but the checker is run from disk after Codex finishes, up to 30 minutes later

**File:** `tests/codex_review_run.py:443, 484-489`
**Issue:** `audit_inputs` hashes the four inputs before Codex starts. `checker_argv` then runs `tests/codex_report_status.py`, and loads the schema, from the working tree after the run. If those files are edited or committed during the run, the recorded hashes no longer describe the checker that produced `.status.json`. A commit leaves `git status` clean again, so nothing flags it. This is the WR-02 evidence gap again, now narrowed to the length of the run.
**Fix:** Call `audit_inputs()` again just before the checker and compare it with `meta["inputs"]`. If they differ, write a stub ("audited inputs changed during the run").

### IN-07: `--dry-run` doesn't warn about a stale head or dirty inputs, so the preview says nothing about a run that will be refused

**File:** `tests/codex_review_run.py:502-528`
**Issue:** The contract makes the dry run the preview step. It prints the `git status` command with "must be empty", but it doesn't run the check, and it doesn't compare `--head` with HEAD. The prior IN-06 fix asked for both `execute()` and `dry_run()`. Only `execute()` got it. Low effect: the real run still refuses cleanly.
**Fix:** In `dry_run()`, run the two read-only git checks and print `# WARNING: …` lines without failing.

## Set aside (needs ruling)

### SA-01: A red Failed card whose only rows are malformed records still says "Show N skipped records"

**Where:** `triggarr/templates/partials/cycle_grade.html:33-34`; `tests/test_app_cards.py:588-602` (`D-01: a Failed skip-only cycle … also says 'skipped record'`)
**Why excluded:** Two owner decisions conflict, and I can't choose between them. The quick task's D-01, which the test pins, wants a Failed cycle that only skipped records (0 accepted, 0 failed) to say "skipped record". The later ruling on `d501a68316b2:SA-01`, recorded in `83-REVIEW-EVIDENCE.md:381`, says "red Failed-grade cards always say 'failure reason(s)'". That ruling was given about unevaluated rows, and the implementation applies it only to those.
**Effect if left as is:** A red card can still use the softer "skipped records" wording. `outcome.py:76-79` grades such a cycle Failed, and it counts toward the SAFETY-03 alert. The owner may or may not see that as hiding a failure.
**Needs:** A ruling on whether "always" covers the skip-only Failed card too. If it does, add `app.last_cycle.grade != 'failed'` to the skipped-record branch and update the D-01 test. If it doesn't, record that the ruling covers unevaluated rows only.

---

_Reviewed: 2026-10-22T23:18:57Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
