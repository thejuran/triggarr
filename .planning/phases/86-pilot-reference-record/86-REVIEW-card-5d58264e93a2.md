---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T04:45:39Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - tests/test_outcome.py
  - triggarr/search/outcome.py
  - triggarr/templates/partials/cycle_grade.html
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 86: Code Review Report

**Reviewed:** 2026-11-14T04:45:39Z (started 2026-11-14T04:43:50Z)
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found
**Head reviewed:** `5d58264e93a21b100d01e80503b9a7d064253d36` (branch `pilot-card-reason-kind`, merge of main `aeead4b601d7a26b927656bf1a07ab8c66fde58f`)
**Scope:** `git diff aeead4b601d7a26b927656bf1a07ab8c66fde58f...HEAD` (commits `1fb66b9`, `46c3919`), reviewed as it stands at the merge head.

## Summary

The change adds a structured `kind` to every reason row built by `cycle_view` (plus a numeric
`skip_count` on malformed rows) and switches the dashboard card partial from matching display
text to reading those fields.

No blocker was found. What was checked, and how:

- **Behaviour against the previous template.** Both versions of `cycle_grade.html` (the one at
  `aeead4b` and the one at this head) were rendered against 10,752 generated records covering every
  grade, fetch failure, failure reasons, unevaluated queues, per-queue and legacy malformed
  counts, tampered values and eligible maps. The new template was rendered with strict undefined
  handling and raised no error on any of them. Output differed on 2,016 records, and every one of
  those involves a failure reason whose 120-character truncated text happens to end in
  "skipped". The old text match counted that row as a malformed-record row; the new `kind` check
  counts it as a failure. That is the intended correction, not a regression. All other records
  render identically.
- **Interaction with main's `triggarr/search/engine.py`.** Main's changes there are in the
  count-refresh functions, which use a throwaway `CycleTally` that is never turned into a
  persisted record. The search-cycle paths that feed `last_cycle` (`record_malformed`,
  `mark_unevaluated` with "malformed data (...)", `record_eligible`, `record_fetch_failure`,
  `_finalize_cycle`) still produce exactly the record shape `cycle_view` reads. A cycle that both
  skips malformed records and marks the same queue unevaluated renders without error and with the
  "details" label.
- **Other consumers.** `cycle_view` has one caller (`triggarr/web/routes.py:402`) and the partial
  is included only from `partials/app_card.html`. No other code builds reason rows by hand, so no
  consumer can hand the template a row without `kind`.
- **Tests and lint.** `uv run pytest tests/test_outcome.py tests/test_app_cards.py tests/test_scheduler.py`
  passed (206 tests). `ruff check` and `ruff format --check` are clean on the two Python files.
- **Security.** Reason text still goes through Jinja autoescape; `kind` and `skip_count` are
  values set by `cycle_view`, never taken from the persisted record, so tampered state cannot
  steer the grouping. No secrets, logging or SecretStr handling is touched.

**Limitation -- convention check not run.** The combined command that included the
`gsd-tools.cjs verify conventions` call was refused by a pre-tool hook
(`holdout_guard.py`: "this tool call reaches the sealed holdout folder (v2.12 barrier)"). It was
not retried. The rule packs cover JS/TS files only and all three files in scope are Python or a
Jinja template, so the packs would have skipped; no CONVENTION-tier findings are reported, and
that tier should be read as "not run" rather than "clean".

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: No test fails if the card template goes back to matching display text

**Classification:** WARNING
**File:** `triggarr/templates/partials/cycle_grade.html:20-24` (tests: `tests/test_outcome.py:707-753`, `tests/test_app_cards.py` unchanged)
**Issue:** The purpose of this change is that the card groups and counts rows by `kind` and
`skip_count` instead of by wording. The new test only checks that `cycle_view` attaches those
fields. Nothing renders the card with a record where the two approaches disagree, and
`tests/test_app_cards.py` was not touched. The differential run above shows the old and new
templates produce identical output for every record the existing card tests use, so the old
text-matching template would pass the whole suite at this head. The one behaviour this change
actually alters on the card -- a failure reason whose truncated text ends in "skipped" no longer
being counted as a skipped record -- is unpinned, and a later edit could silently reintroduce
text matching.
**Fix:** Add one card-level test in `tests/test_app_cards.py` using a record where wording and
kind diverge, for example:

```python
def test_card_failure_reason_ending_in_skipped_is_not_a_skipped_record(client, test_app):
    """Phase 86 D-03: the card classifies rows by kind, not by how the text ends."""
    reason = "x" * 80 + "skipped" + "yyyy"  # card text truncates to end in "skipped"
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="partial",
        accepted=1,
        failed=0,
        malformed_skipped=1,
        malformed_by_queue={"missing": 1},
        failure_reasons=[{"reason": reason, "count": 1}],
    )
    html = client.get("/").text
    assert "Show 2 failure reasons" in html
    assert "skipped record" not in html.split("data-cycle-detail")[1].split("</summary>")[0]
```

(Adjust the fixture helper arguments and the route to match the neighbouring tests.)

## Info

### IN-01: `skip_count` is read with no fallback, where the old code had one

**Classification:** WARNING-adjacent robustness note, graded Info because it is unreachable today
**File:** `triggarr/templates/partials/cycle_grade.html:24`
**Issue:** `ns.malformed_total + r.skip_count` assumes every `malformed` row carries
`skip_count`. Both construction sites in `cycle_view` (`triggarr/search/outcome.py:316`, `:324`)
set it, so this holds now. The Jinja environment uses the default undefined type
(`triggarr/web/routes.py:76`), so a future malformed row added without `skip_count` would raise
on the addition and turn the whole dashboard request into a server error, rather than degrading
to a wrong label as the previous `| int(0)` did.
**Fix:** Either `r.skip_count | default(0)` in the template, or keep the template as is and rely
on the existing test assertion that every malformed row has an integer `skip_count`
(`tests/test_outcome.py:733-735`) -- in which case say so in a template comment.

### IN-02: Reason kinds are bare string literals repeated in three places

**File:** `triggarr/search/outcome.py:267,283,300,316,324,345`; `triggarr/templates/partials/cycle_grade.html:20,22`; `tests/test_outcome.py:707`
**Issue:** The grades in this module have named constants (`GRADE_SUCCESS` and so on); the new
kinds do not. The allowed set exists only in the test file. A misspelled kind in the template
(`'unevaluted'`) raises nothing -- the row quietly falls into the "other" bucket and the card
shows the "failure reason" label.
**Fix:** Define `REASON_KIND_*` constants (or a `REASON_KINDS` frozenset) in `outcome.py`, use
them at the six append sites, and have the test import the set instead of redeclaring it.

### IN-03: The "all kinds covered" assertion is partly hard-coded

**File:** `tests/test_outcome.py:748-749`
**Issue:** `all_kinds_seen = kinds_seen | {"malformed"} | {...}` adds the literal `"malformed"`
instead of the kinds actually observed on the legacy-aggregate view, so that line would still
pass if the legacy row carried a different kind. The legacy row's kind is asserted separately at
line 740, so coverage is not lost; the union line simply does not prove what its docstring says
("exercises all six append sites").
**Fix:** `all_kinds_seen = kinds_seen | {r["kind"] for r in view_legacy["reasons"]} | {r["kind"] for r in view_eligible["reasons"]}`.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-11-14T04:45:39Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
