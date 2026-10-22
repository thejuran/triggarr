---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-22T20:56:03Z
head: 322afc50367d4cf7e2610eb6f8852bb8c9302457
base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
review_kind: post-fix re-review (prior review preserved as 83-REVIEW-dcfb5a5081ea.md)
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
  fixed_verified: 11
  still_present: 3
  not_applicable: 0
findings:
  critical: 0
  warning: 3
  info: 8
  total: 11
status: issues_found
---

# Phase 83: Code Review Report (post-fix re-review)

**Reviewed:** 2026-10-22T20:56:03Z
**Head:** `322afc50367d4cf7e2610eb6f8852bb8c9302457`
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This re-review covers the fixes for the prior review at `dcfb5a5081ea`, plus the code added since then: the Codex runner (`tests/codex_review_run.py`), report schema v2 with the `review_complete`/`incomplete_reasons` fields, contract template v3, and the two files that were in scope but missed last time (`CLAUDE.md`, `docs/owner-cli-acceptance.md`; prior SA-02).

**Prior findings.** Both critical findings and all five warnings are fixed, and I re-checked each one by running it, not by reading the fix report. Each wrong-type case from the prior table now returns `incomplete` with a clear reason: `findings: null`/`"none"`, `coverage: null`/`"all"`, an unknown `schema_version`, `summary: 5`, `id: 7`, a blank id, `line_start: true`, `exit_code: true`, and a verdict that contradicts the findings. A non-UTF-8 or directory report path now prints a JSON `incomplete` result and exits 1. `--attempt 0` is rejected. The v1 schema that the checker derives at runtime matches the v1 schema committed at `402ba42^` exactly. Re-checking the two recorded reports gives `a7995baf187e-quick-a1` complete and `d501a68316b2-explicit-a1` incomplete (it calls itself incomplete), as the fix report says. Three Info items are still open (IN-01, IN-03, and part of IN-05).

**New issues.** No critical issues. Three warnings:

1. **The SA-01 fix caused a regression on red cards.** A Failed card with one unevaluated row and one malformed row now says "Show 1 skipped record" but lists 2 rows. Before the fix it said "Show 2 details", and the owner's ruling says red cards should say "failure reason". I confirmed this by rendering the card.
2. **Codex runs don't record their own inputs.** The runner never saves the exact prompt it sent to Codex, and it doesn't record which contract or template version it used. It also reads the contract, schema and checker from the working tree as they are on disk, including uncommitted edits. So the evidence can't show that the fixed template was used, which is the point of D-07.
3. **A hollow report can still count as complete.** With schema v2, the checker accepts a report with `commands_run: []` and `coverage: [""]` as complete. Such a report shows no sign that Codex ran anything. Codex now marks its own report as complete, and these are the only cheap checks that could catch a run that didn't really happen.

Tests: the 244 tests in the six reviewed test modules pass. `ruff check triggarr/ tests/` is clean. The conventions tool found nothing.

## Narrative Findings (AI reviewer)

### Status of prior findings (83-REVIEW-dcfb5a5081ea.md)

| Prior ID | Title | Status at 322afc5 | Verification |
|---|---|---|---|
| CR-01 | Wrong-typed or missing fields treated as complete | **Fixed and verified** | Recursive schema walk (`codex_report_status.py:134-176`). I reproduced every case in the prior table, and each now returns `incomplete` with a `schema:` reason. |
| CR-02 | Non-string `id` dropped from the qualified IDs | **Fixed and verified** | `:247-252`. `id` set to `7`, `None`, `""` or `"   "` gives `incomplete` with "finding at index 0 has no valid id". The invariant test is at `test_codex_report_status.py:511`. |
| WR-01 | Verdict contradicts the findings | **Fixed and verified** | `:349-355`. Both directions reproduced as `incomplete`. |
| WR-02 | CLI crash on a non-UTF-8 or directory path | **Fixed and verified** | `:424-428`. Ran the CLI on `\xff\xfe` bytes and on a directory. Both print JSON `incomplete` and exit 1. |
| WR-03 | Record said BM keeps no re-review history | **Fixed and verified** | `review-checkpoint-record.md:132`. The citation matches `bm/5.0.3/workflows/code-review-fix.md:269-275` on disk. |
| WR-04 | `sensitive` and `code` not ranked against each other | **Fixed and verified** | `review-classification-policy.md:7, 21, 42` now require both classes' reviews, recorded as `code`. |
| WR-05 | Raw Codex streams committed to a public repo | **Fixed and verified** | Prompt line 37 limits reads to the working copy. The hex-key scan is at `:76-82`. The regex matches 32-hex values and not 40-hex SHAs. |
| IN-01 | Template classifies rows by matching wording | **Still present** | Not addressed. Carried forward as IN-01 below. |
| IN-02 | Skipped-record label count not cross-checked against the rows | **Fixed and verified** | `cycle_grade.html:33` now requires `malformed_skipped == ns.malformed_total`. |
| IN-03 | `test_never_reports_clean` is tautological | **Still present (substance addressed)** | Parametrized wrong-type tests (`:241-278`) and the `finding_count == len(qualified_ids)` invariant were added. The tautological test is unchanged at `:573-593`. Carried forward as IN-03 below. |
| IN-04 | `--attempt` accepts 0 or negative values | **Fixed and verified** | `_positive_int` in both the checker (`:381-389`) and the runner (`:322-329`). Also checked in `ReviewRun.__post_init__`. |
| IN-05 | Whitespace-only text and booleans counted as integers | **Partly fixed, still present** | The booleans and `hypothesis` are fixed. A whitespace-only `reproduction_command` still passes (`:260`). Carried forward as IN-02 below. |
| IN-06 | Attempt 3 not covered by the record template | **Fixed and verified** | Contract `:86` and record `:86` now agree. Guarded by `test_review_checkpoint_record.py:32`. |
| SA-01 | Red card with only unevaluated rows says "detail" | **Resolved by owner ruling and implemented, but the fix caused a regression** | The unevaluated-only case now says "failure reason" (`cycle_grade.html:31`). The mixed case regressed. See WR-01 below. |
| SA-02 | `CLAUDE.md` and `owner-cli-acceptance.md` not in scope | **Resolved** | Both are in scope and were reviewed this pass. No defects found. One related point is in SA-01 below. |

Codex F002 (wrong `gh api` field syntax) was fixed outside this review. I checked it: `review-checkpoint-record.md:16` uses `-F body=@FILE`, which is valid `gh api` syntax, and `test_review_checkpoint_record.py:21` guards it.

## Warnings

### WR-01: SA-01 fix mislabels a Failed card that has both an unevaluated row and a malformed row

**File:** `triggarr/templates/partials/cycle_grade.html:31-34`
**Issue:** The SA-01 fix added `app.last_cycle.grade != 'failed'` to the unevaluated ("detail") branch only. On a Failed card that has an unevaluated row and a malformed row, that branch is now skipped. The next branch (`no_failure and ns.malformed > 0 and malformed_skipped == ns.malformed_total`) still matches, because it never checks for unevaluated rows. This case is common: a cycle with 0 accepted and any malformed records is graded Failed (`outcome.py:76-79`). I rendered the card at this head:

```
grade=failed, accepted=0, failed=0, malformed_by_queue={"cutoff":1}, unevaluated=[missing]
  summary: "Show 1 skipped record"
  rows:    "Missing queue not evaluated: tag 'x' not found", "1 upgrade-queue record skipped — malformed data"
grade=partial (same rows)
  summary: "Show 2 details"
```

The red card says "1 skipped record", but the list has 2 rows. The row it leaves out, "Missing queue not evaluated", is the real cause of the failure. Before the SA-01 fix this card said "Show 2 details". The owner's ruling says red cards should say "failure reason". The current label matches neither. `test_card_details_label_malformed_plus_unevaluated` (`test_app_cards.py:719`) covers only the Partial grade, so the suite misses this.
**Fix:** Allow the skipped-record branch only when there are no unevaluated rows, and add a Failed-grade version of the mixed test that expects "Show 2 failure reasons":
```jinja
{% elif no_failure and ns.unevaluated == 0 and ns.malformed > 0 and app.last_cycle.malformed_skipped > 0 and app.last_cycle.malformed_skipped == ns.malformed_total %}
```

### WR-02: Codex runs do not record the exact prompt or which harness and template produced them

**File:** `tests/codex_review_run.py:42-43, 103-110, 253-292`
**Issue:**
- **The prompt is not saved.** The runner renders the prompt and sends it to Codex on stdin, but never writes it to disk. The Codex `--json` event stream doesn't include the user prompt either. I checked the in-progress `d501a68316b2-explicit-a2.jsonl`: it starts with `thread.started` and then shows hook-parse errors and agent items. So the stored outputs (`.jsonl`, `.last.json`, `.status.json`, `.pytest.txt`) cannot show what Codex was told. D-07 ("Claude adds no risk notes … or framing of its own") can't be checked from them.
- **Inputs are read from disk as-is.** `CONTRACT_PATH`, `SCHEMA_PATH` and the checker are read from the main checkout as they are on disk, including uncommitted edits. The output doesn't record the commit or the template version that was used.
- **Example.** The current `d501a68316b2-explicit-a2` retry uses the v3 template and the v2 schema. Attempt `a1` on the same head used the earlier template and the v1 schema. Only `schema_version` in `.last.json` hints at the change, and the template version isn't recorded anywhere.

This is an evidence-integrity gap in tooling whose only job is evidence. The docstring calls it a "Reproducible runner", but given only its outputs, the run can't be reproduced.
**Fix:**
- Write the rendered prompt to `<OUT>.prompt.txt`, before Codex starts, and add it to `OUTPUT_SUFFIXES`, the contract's "Raw output storage" list and the record's "Raw output paths" row.
- Put a provenance header in `.pytest.txt`, or a small `<OUT>.run.json`. It should hold `git rev-parse HEAD` of the harness checkout, the template version line, and the sha256 of the contract, schema and checker.
- Refuse to run, or at least warn, when `git status --porcelain -- docs/codex-adversarial-review-contract.md .claude/schemas tests/codex_report_status.py tests/codex_review_run.py` is non-empty.

### WR-03: A v2 report showing no sign that Codex did any work is accepted as complete

**File:** `tests/codex_report_status.py:357-359` (no check on `commands_run`); schema `codex-review-findings.schema.json:46-76`
**Issue:**
- **No other cross-check.** With schema v2, the checker now relies on Codex's own `review_complete: true`, with no free-text check as a backstop. That makes the cross-checks the checker *can* do the only defense against a hollow or fabricated report.
- **Both gaps reproduced.** The valid fixture with `commands_run: []` returns `complete`. So does `coverage: [""]` or `["   "]`, because `:358` only rejects an empty list.
- **Why it matters.** The fixed prompt requires "First run git rev-parse HEAD and report it as inspected_head_sha" and "every command actually run". A report with no commands means the inspected SHA was never checked and the diff was never read. Yet it would show in the owner checklist as "Codex: complete, No findings". That is the false-clean outcome D-09 forbids.
- **Likelihood.** `--output-schema` makes a fully empty report unlikely, but the schema can't enforce `minItems` here. This checker is the backstop for exactly this case.

**Fix:**
```python
commands = report.get("commands_run")
if isinstance(commands, list) and not commands:
    reasons.append("no commands run: the report gives no evidence the diff was inspected")
if isinstance(coverage, list) and not any(_non_blank(c) for c in coverage):
    reasons.append("no coverage stated")
```
Also consider requiring a `commands_run` entry whose command contains `git rev-parse HEAD` with `exit_code == 0`. Add tests for `commands_run: []` and `coverage: [""]` that expect `incomplete`. These checks are also safe for the recorded v1 reports, since both have non-empty `commands_run`. Re-run the two recorded-report tests to confirm.

## Info

### IN-01 (carried from prior IN-01): Template classifies reason rows by matching the wording `outcome.py` produces

**File:** `triggarr/templates/partials/cycle_grade.html:19-28`
**Issue:** Unchanged since the prior review. WR-01 shows how fragile this branching is: each new label condition has to account for every row category by hand.
**Fix:** Have `cycle_view` emit a `kind` per row (`failure`/`unevaluated`/`malformed`), or a precomputed `detail_label`, and branch on that.

### IN-02 (carried from prior IN-05, partly fixed): A whitespace-only `reproduction_command` passes on a reproduced finding

**File:** `tests/codex_report_status.py:260`
**Issue:** `hypothesis` now uses `_non_blank()`, but `reproduction_command` still uses `not finding.get(...)`. Setting `reproduced: true, reproduction_command: "   "` returns `complete` (reproduced). A finding can then be labelled "reproduced" in the disposition table with no command to re-run.
**Fix:** `if reproduced is True and not _non_blank(finding.get("reproduction_command")):`, plus a test.

### IN-03 (carried from prior IN-03): `test_never_reports_clean` is still tautological

**File:** `tests/test_codex_report_status.py:573-593`
**Issue:** It checks only that the word "clean" never appears, and no code path could produce it. The real guard is now the parametrized wrong-type tests, so this test only adds runtime.
**Fix:** Delete it, or turn it into an assertion that every listed scenario returns `status == "incomplete"`.

### IN-04: The checker can still raise, or leave an empty status file, on pathological input

**File:** `tests/codex_report_status.py:303-307`; `tests/codex_review_run.py:289`
**Issue:**
- **Deep nesting crashes the checker.** `json.loads` on deeply nested input (`"["*100000 + "]"*100000`) raises `RecursionError`, which `except json.JSONDecodeError` doesn't catch. The docstring says the checker "never raises on malformed input", so this breaks that promise. I reproduced it.
- **Duplicate keys resolve silently.** A report with duplicate keys (`"review_complete": false … "review_complete": true`) silently takes the last value and returns `complete`.
- **A crash leaves an empty status file.** When the checker subprocess crashes, the runner writes an empty `.status.json`. That file then blocks re-running the same attempt, and it records no reason.

All three are contrived for schema-constrained Codex output.
**Fix:**
- Catch `(json.JSONDecodeError, RecursionError)`.
- Use `json.loads(text, object_pairs_hook=...)` to reject duplicate keys, with the reason "unparseable: duplicate key".
- In the runner, when `checker.stdout` is empty, write a JSON stub: `{"status":"incomplete","reasons":["checker produced no output (exit N)"]}`.

### IN-05: `execute()` lets `CalledProcessError` from `git worktree add` / `git rev-parse` escape as a traceback

**File:** `tests/codex_review_run.py:268, 280-282, 356-360`
**Issue:** Both calls use `check=True`, but `main()` catches only `FileExistsError`. If the head isn't present locally, or a stale worktree is registered, the operator gets a traceback and no status record. If `rev-parse` fails after Codex has finished, `.jsonl` and `.last.json` exist but `.status.json` is never written, so that attempt can only be assessed by hand.
**Fix:** Catch `subprocess.CalledProcessError` in `main()`, and print one plain-language error. If Codex outputs already exist, write a `.status.json` stub with the reason.

### IN-06: A retry on a head that is no longer current spends a full Codex run before reporting "stale"

**File:** `tests/codex_review_run.py:253-288`
**Issue:** The checker compares the report head with `git rev-parse HEAD` taken *after* the run. When `--head` is already behind the checkout's HEAD at launch, the result is certain to be `stale` and `incomplete`, after up to 30 minutes of Codex time. The `d501a68316b2-explicit-a2` retry running now is in this position: its head is `d501a683` and the checkout is at `322afc50`.
**Fix:** In `execute()` and `dry_run()`, compare `run.head` with the current HEAD first. If they differ, print a warning that the result will be assessed as stale, and require an explicit `--allow-stale-head` flag to continue.

### IN-07: Committed raw outputs contain local absolute paths, including the macOS username

**File:** `tests/codex_review_run.py:136, 226`; `docs/codex-adversarial-review-contract.md:55`
**Issue:** `TEST_EVIDENCE` is the absolute path `/Users/<user>/triggarr/.planning/...`, and Codex echoes it into the committed `.jsonl`. The stream also records Codex config errors that name `~/.codex/hooks.json` by absolute path. pytest output can include the `/var/folders/...` temp worktree path. These go into a public repository. The leak is low-sensitivity (a username and directory layout), but the two secret scans won't flag it.
**Fix:** Pass a repo-relative `TEST_EVIDENCE` path. Codex runs with `-C` set to the worktree, so you can either copy the evidence file into a known relative location, or keep it absolute but document that the path is published.

### IN-08: The runner depends on GNU `timeout`, which macOS does not ship

**File:** `tests/codex_review_run.py:158-175`
**Issue:** `timeout` is present here only through Homebrew coreutils (`/opt/homebrew/bin/timeout`). On a machine without it, every attempt fails with "codex exit status unknown". That is incomplete, not a false-clean result, but both automatic attempts would be wasted without explanation.
**Fix:** Drop the external binary and use `subprocess.run(..., timeout=CODEX_TIMEOUT_SECONDS)` for Codex, as the pytest step already does, recording a timeout as exit 124. Otherwise, check `shutil.which("timeout")` up front and print a clear error.

## Set aside (needs ruling)

### SA-01: The runner executes the PR head's test suite outside any sandbox, with the operator's full environment

**Where:** `tests/codex_review_run.py:196-221`; `CLAUDE.md` ("This standing instruction authorizes only running the read-only Codex review")
**Why excluded:** This follows the owner's 2026-10-22 decision to give Codex harness-produced test evidence. The new `CLAUDE.md` wording describes the standing authorization as covering "only running the read-only Codex review". The runner also runs `uv run --extra dev pytest` on the head, without a sandbox, passing every environment variable except `VIRTUAL_ENV` (for example `GH_TOKEN` and SSH agent sockets). Its output goes into a file that gets committed publicly.
**Effect if left as is:** On the owner's own PRs this is the same as running the tests locally. On a Dependabot or outside-contributor PR, it automatically runs new dependency code, or contributor test code, on the owner's machine with the owner's credentials. That happens as a side effect of a step described as read-only.
**Needs:** A ruling on whether the standing Codex authorization should name the pytest step explicitly. Also: should it be limited to owner-authored heads, or run with a minimal environment (`PATH`, `HOME`, `UV_*`)?

### SA-02: Schema v2 does not search the report text, by design

**Where:** `tests/codex_report_status.py:209-224, 314-317`
**Why excluded:** This is an owner decision (2026-10-22). A v2 report with `review_complete: true` whose summary says "This is an incomplete review" is assessed `complete`, and `test_v2_does_not_text_match_completeness` pins that behavior.
**Effect if left as is:** If Codex gets the structured flag wrong while saying the review is incomplete in its prose, the run counts as complete. The owner sees the prose only by reading `.last.json`.
**Needs:** Confirmation that this is accepted. One option is to surface the summary and limitations verbatim in the owner checklist, which the record template already does for limitations.

---

_Reviewed: 2026-10-22T20:56:03Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
