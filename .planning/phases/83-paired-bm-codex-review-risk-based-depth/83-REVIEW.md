---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-23T17:34:20Z
depth: standard
review_head: 49ded1e86444bc7122b7f0dda6e557312057a7a7
diff_base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
files_reviewed: 13
files_reviewed_list:
  - .claude/schemas/codex-review-findings.schema.json
  - docs/bm-review-baseline-2026-10-22.md
  - docs/buildomator-greptile-pilot.md
  - docs/codex-adversarial-review-contract.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - tests/codex_report_status.py
  - tests/codex_review_run.py
  - tests/test_app_cards.py
  - tests/test_codex_report_status.py
  - tests/test_codex_review_contract.py
  - tests/test_review_instructions.py
  - triggarr/templates/partials/cycle_grade.html
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 83: Code Review Report

**Reviewed:** 2026-10-23T17:34:20Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

This is the phase-execution review for PR #35 at pushed head `49ded1e86444bc7122b7f0dda6e557312057a7a7`. The local HEAD `04a424e` differs from the pushed head only by three planning markdown files (`83-10-SUMMARY.md`, `83-REVIEW-36eaa67c2976.md`, `83-REVIEW-EVIDENCE.md`), so every source file in scope is identical at both commits.

Checks run: the targeted suites (`test_codex_report_status`, `test_codex_review_contract`, `test_review_instructions`, `test_app_cards`, `test_codex_review_run`) pass with 306 tests, ruff is clean on the changed Python, and the BM convention check returned no findings. I spot-checked the BM line citations in `docs/bm-review-baseline-2026-10-22.md` against the installed 5.0.3 files: `quick.md:929`, `code-review-fix.md:270-275`, `execute-phase.md:1241-1249` and `code-review.md:312-321` all match.

No blockers. There are four warnings, and they all concern the review harness, the tool that decides whether a Codex review counts as "complete":
- A report that labels itself schema version 1 skips the structured completeness check. I reproduced this: a self-labelled v1 report that admits it is unfinished is accepted as "complete".
- Pytest output that is not valid UTF-8 crashes the runner and leaves an attempt with no status file.
- The checker that judges a PR's Codex review is the PR's own version of the checker.
- The committed raw Codex output exposes the operator's home path and username, even though the harness promises its public evidence never does.

The dashboard template change (`cycle_grade.html`) is correct for every row type that `outcome.py` produces today. It gets one INFO for matching on display text.

## Warnings

### WR-01: A report labelled schema version 1 skips the structured completeness check, so an unfinished review can be assessed "complete"

**File:** `tests/codex_report_status.py:81-83, 342-347`
**Issue:** `_schema_for` picks the v1 schema whenever the report itself says `"schema_version": "1"`. `assess_report` then skips `_structural_completeness`. Nothing ties the v1 path to "already recorded history". The checker accepts a v1 label on any report, including one produced today. Under v1 the only completeness signal is the narrow phrase regex (`incomplete review`, `review is/was incomplete`, `not a clean approval`).

Reproduced: a v1-labelled report with summary `"Only read two files; could not finish."` and limitation `"ran out of time before covering most files"` returns `Assessment(status='complete', reasons=())`. The same report as v2 with `review_complete: false` is correctly `incomplete`.

Today's protection is only that `codex exec --output-schema` constrains Codex to `enum ["2"]`. The checker is meant to be the gate that does not trust its input. The contract (line 67) and the module docstring both say v1 exists only so recorded history keeps its assessment.
**Fix:** Make the v1 path opt-in, so a new run can never use it:
```python
parser.add_argument("--allow-legacy-v1", action="store_true",
                    help="Re-assess an already recorded schema v1 report")
...
if report.get("schema_version") == "1" and not allow_legacy_v1:
    reasons.append("schema: schema_version 1 is only accepted when re-assessing recorded history")
```
`codex_review_run.checker_argv` never passes the flag. A test should lock in that a v1 report through the runner's checker invocation is `incomplete`.

### WR-02: Pytest output that is not valid UTF-8 crashes the runner and leaves a reserved attempt with no `.status.json`

**File:** `tests/codex_review_run.py:326-342` (also `544-549` for the checker call)
**Issue:** `_run_pytest` calls `subprocess.run(..., stdout=PIPE, stderr=STDOUT, text=True)` with the default strict decoding. If the reviewed head's test output contains bytes that are not valid UTF-8 (a test printing binary data, or a library warning in another encoding), `subprocess.run` raises `UnicodeDecodeError`. That is a `ValueError`, not an `OSError`, which I confirmed locally.

`execute` only catches `RunnerError` and `OSError` (lines 508-516), and `main` does not catch it either. The result:
- `.prompt.txt` and `.meta.json` are already written, so the attempt number is used up.
- No `.status.json` stub is written. This contradicts the contract's promise (Invocation step 4.5) that any failure after the reservation leaves an `incomplete` stub.
- The operator gets a Python traceback.

The same gap applies to an `OSError` from the `.meta.json` write at line 494, which runs before the `try`.
**Fix:** Decode tolerantly, and stub every non-`RunnerError` failure after the reservation:
```python
proc = command_runner(pytest_argv(), ..., text=True, errors="replace", timeout=PYTEST_TIMEOUT_SECONDS)
...
except RunnerError as exc:
    _write_status_stub(run, f"harness failed before codex finished: {exc}"); raise
except Exception as exc:  # reservation exists: never leave it without a status
    reason = f"harness failed before codex finished: {type(exc).__name__}"
    _write_status_stub(run, reason)
    raise RunnerError(reason) from exc
```
Move the `.meta.json` write inside the same guarded block. Use `errors="replace"` on the checker call too. Add a runner test with a fake command runner whose stdout raises `UnicodeDecodeError`.

### WR-03: The checker that judges a PR's Codex review is the PR's own version of the checker

**File:** `tests/codex_review_run.py:480-486, 534-546`; `tests/codex_report_status.py` (whole module)
**Issue:** By default `execute` refuses unless the harness checkout's HEAD equals `--head`. So the contract, schema, checker and runner that produce and judge the Codex result are always the reviewed head's own copies. `audit_inputs` only proves those files are committed. It does not prove they are the trusted (base) versions.

A PR that weakens `codex_report_status.py` (for example, one that drops a reason or widens the v1 path in WR-01) is judged "complete" by the weakened checker. The evidence record does not say so. This PR is itself such a change: it rewrites the checker, the runner and the prompt that judge it.

The owner has said they cannot judge code by reading it. So the checker's `complete` verdict is effectively what goes on the acceptance checklist, and CLAUDE.md says "Do not weaken CI, suppress findings ... to make a task appear complete".
**Fix:** Pick one (in order of preference):
1. When `git diff --name-only base..head -- <AUDITED_INPUTS>` is non-empty, also run the checker from the base commit (`git show {base}:tests/codex_report_status.py` into the scratch dir) and record both verdicts in `.status.json` / `.meta.json`. Treat a disagreement as `incomplete`.
2. At minimum, record `"audited_inputs_changed_in_diff": [...]` in `.meta.json`, and require the checkpoint record's Codex row to state "assessed by a harness this PR modifies".

### WR-04: Committed raw Codex output exposes the operator's home path and username, contrary to the harness's own publication guarantee

**File:** `tests/codex_review_run.py:262-297, 360-370`; `docs/codex-adversarial-review-contract.md:80-89`
**Issue:** `redact_local_paths` says "The evidence is committed to a public repository, so the temp worktree, the temp dir, the system temp dir, the main checkout and the home directory never appear in it". That redaction only covers `.pytest.txt`. The `.jsonl` event stream is committed unedited (D-11).

The `.jsonl` files already committed under `.planning/phases/83-.../codex/` (for example `36eaa67c2976-final-a1.jsonl` and `49ded1e86444-phase-a1.jsonl`) contain `failed to parse hooks config /Users/julianamacbook/.codex/hooks.json: unknown field SessionStart ...`. That line exposes the operator's username, home path and local Codex hook configuration. The files also contain `/private/var/folders/xq/.../T/codex-review-*/wt/...` temp paths.

The two pre-commit checks in the contract (gitleaks, 32-hex scan) do not detect either. The content is low-sensitivity (no credential). But the published evidence breaks a privacy guarantee stated in the code. Future Codex startup messages could carry more (config paths, profile names).
**Fix:** Do not edit the raw stream, which keeps D-11. Instead:
- Run Codex with an isolated `CODEX_HOME` (a scratch copy holding only the auth and config files Codex needs), so the operator's hooks and home paths never reach the stream.
- Add a third pre-commit check to the contract that blocks the commit when the codex directory contains `$HOME`, `getpass.getuser()` or `tempfile.gettempdir()`. The check should list file names only, like the hex scan.
- Correct the `redact_local_paths` docstring so it claims redaction only for the harness-written files.

Whether to purge the already-committed lines from history is an owner decision (see SA-02).

## Info

### IN-01: The template classifies detail rows by matching their display text, not a row kind

**File:** `triggarr/templates/partials/cycle_grade.html:18-28`
**Issue:** The label logic infers row type from wording: `startswith('Missing queue not evaluated: ')`, `endswith('— malformed data') or endswith('skipped')`, and `split(' ')[0] | int(0)` for the record count. This is correct for every row `triggarr/search/outcome.py:256-335` builds today. Failure and fetch rows end in `)`, and the eligible row is counted as `other`.

The risk is maintenance. Any future row whose text ends in "skipped", or a rewording of the unevaluated or malformed rows in `outcome.py`, silently changes which label a red or amber card shows. `outcome.py` already knows each row's kind.
**Fix:** Have `outcome.py` emit `{"text": ..., "count": ..., "kind": "fetch|failure|unevaluated|malformed|eligible"}` plus a precomputed `malformed_rows_total`. Then branch on `r.kind` in the template.

### IN-02: The checker never compares the report's `pr_url` / `scope` with what was requested

**File:** `tests/codex_report_status.py:288-407`
**Issue:** The head and base SHAs are compared with the expected values, but `pr_url` and `scope` are only type-checked. A report copied from another PR at the same head and base (for example a local-checkpoint run reused as PR evidence) is assessed `complete` without any note.
**Fix:** Pass `--expected-pr-url` / `--expected-scope` from `checker_argv`, and add a `wrong request:` reason when they differ.

### IN-03: The fixed prompt still describes untrusted heads running Codex with no tests

**File:** `docs/codex-adversarial-review-contract.md:36`; `tests/codex_review_run.py:350`
**Issue:** The prompt says the harness "either ran ... pytest ... or, for an untrusted source such as a Dependabot or outside-contributor PR, ran no tests". The runner refuses untrusted heads outright (`execute` line 473, `main` line 647), and the evidence header hardcodes `source: trusted (--trusted)`. The untrusted branch of that sentence can never happen. It is stale prompt text that tells Codex about a mode which does not exist.
**Fix:** Drop the untrusted clause in the next template version (version 6), or keep it only once Phase 85 re-enables untrusted runs.

### IN-04: `diff_argv` is only used by tests, and the CLAUDE.md guard tests only check substrings

**File:** `tests/codex_review_run.py:194-195`; `tests/test_review_instructions.py:53-58`
**Issue:**
- `diff_argv` is never called by the runner. Codex gets the diff command from the prompt text, and `test_codex_review_contract.py:207` keeps its own quoted copy of the pathspecs. So the "runner uses the same list" claim in the contract (line 25) is enforced by two separate constant lists, not by shared code.
- `test_claude_md_codex_pairing_paths` passes if "phase execution" etc. appear anywhere in CLAUDE.md, not necessarily in the Codex pairing instruction.

**Fix:**
- Derive the prompt's pathspec string from `EXCLUDE_PATHSPECS` in a test (`shlex.join`-style quoting). Or remove `diff_argv` and state that the constant is test-only.
- Scope the CLAUDE.md assertion to the pairing section's text.

## Set aside (needs ruling)

### SA-01: `--trusted` is self-declared and never checked

**Where:** `tests/codex_review_run.py:116-119, 473-474, 616-628`
**Why excluded:** The owner decided on 2026-10-22 that trust is an operator flag, and Phase 85 is scheduled to harden the harness. Changing that is out of scope for this phase.
**Effect if left as is:** The harness runs the head's full test suite unsandboxed on the operator's machine. Nothing checks the flag against the head's author or origin. Dependabot branches also live in this repository's origin (`dependabot/*`), so "this repository's own branches" does not separate them. If one is mislabelled `--trusted`, third-party code runs locally.
**Needs:** Ruling on whether a cheap guard should land now: refuse when `git log -1 --format=%ae HEAD` is a bot address, or when the head is reachable only from `origin/dependabot/*`. The alternative is to defer to Phase 85.

### SA-02: Already-committed `.jsonl` files contain the operator's home path

**Where:** `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/*.jsonl` (not modified; the review was told not to touch this directory)
**Why excluded:** D-11 requires the raw output to stay unedited, and the directory is outside this review's write scope.
**Effect if left as is:** The username `julianamacbook`, the `~/.codex/hooks.json` path and macOS temp paths become public when PR #35 merges. There is no credential.
**Needs:** Owner ruling: accept as is, or regenerate the evidence under an isolated `CODEX_HOME` before merge (see WR-04).

### SA-03: Planning markdown that is executable agent instructions is outside the Codex diff

**Where:** `docs/codex-adversarial-review-contract.md:17-25`; `docs/review-classification-policy.md:13-14`
**Why excluded:** The owner approved the `.planning/**/*.md` exclusion in round 3 (template version 5).
**Effect if left as is:** `*-PLAN.md` files are instructions that BM executor agents follow. Under the policy's own content-based rule ("agent instructions ... even when they live in Markdown") they are arguably sensitive. Yet the paired Codex pass never sees them as scope.
**Needs:** Ruling on whether PLAN.md files stay ordinary-docs. If they do, record that explicitly in the policy.

---

_Reviewed: 2026-10-23T17:34:20Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
