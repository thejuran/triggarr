---
phase: 261022-l7h-fix-card-reasons-label-for-skip-only-row
reviewed: 2026-10-22T19:41:14Z
depth: quick
files_reviewed: 2
files_reviewed_list:
  - tests/test_app_cards.py
  - triggarr/templates/partials/cycle_grade.html
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 261022-l7h: Code Review Report

**Reviewed:** 2026-10-22T19:41:14Z
**Depth:** quick (pattern scan plus targeted trace of the new classification logic against its data source in `triggarr/search/outcome.py`, since the template change is a conditional-logic fix, not a cosmetic one)
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the two changed files for commits `98c2dc6..e0e72ba`: a new classification block in `cycle_grade.html` that decides whether the `<details>` summary reads "failure reason(s)", "skipped record(s)", or "detail(s)", plus eight new regression tests in `tests/test_app_cards.py`.

Pattern scan (secrets, `eval`/`innerHTML`, debug artifacts, empty catches, commented-out code) found nothing. `ruff check tests/test_app_cards.py` is clean and `uv run pytest tests/test_app_cards.py -q` passes 84/84. I traced the new Jinja `{% if/elif/else %}` branches against the exact strings `triggarr/search/outcome.py::cycle_view()` produces (dash character, label text, truncation) to confirm no trivial text-match bug exists — none found; the branching correctly reproduces the four documented scenarios (skip-only, unevaluated-only, mixed malformed+unevaluated, any-real-failure-wins) and the new "eligible-not-searched" regression. The function-level result is correct and well covered by tests.

The two findings below are about *how* the fix was implemented, not about the user-visible outcome for the scenarios tested: the template classifies rows by sniffing substrings of translated display text rather than consuming a structural tag, and the "skipped record" count display trusts an aggregate field that isn't cross-validated against the per-queue rows that triggered the branch. Both are latent robustness/maintainability gaps, not reproducible defects in the behavior that was shipped.

## Warnings

### WR-01: Row classification is done by sniffing display text instead of a structural tag

**File:** `triggarr/templates/partials/cycle_grade.html:18-28`
**Issue:** The new `ns.unevaluated` / `ns.malformed` / `ns.other` counters classify each `app.last_cycle.reasons` entry by `startswith`/`endswith` matching against its already-formatted, human-readable `text` — e.g. `r.text.startswith('Missing queue not evaluated: ')`, `r.text.endswith('— malformed data')`. But `triggarr/search/outcome.py::cycle_view()` already knows the category of every row at the moment it builds that same `reasons` list (the unevaluated-queue loop at line ~280, the malformed-by-queue loop at line ~296-307, and the legacy-aggregate fallback at line ~309-314 are each a distinct, already-known case). The template re-derives that same classification from the rendered string, which:
- duplicates business logic that already exists server-side, now living in two places that must be kept byte-for-byte in sync (including the exact em-dash `—`, U+2014, used in the malformed-row wording);
- is a silent-desync risk: if a future change to the wording in `outcome.py` (e.g. renaming `"upgrade-queue"` or changing `"— malformed data"` phrasing) isn't mirrored in the template, rows fall into the `other` bucket by default, and the card silently reverts to "Show N failure reason(s)" for what are actually skip/unevaluated rows — i.e., the exact bug this patch fixes, reintroduced by an unrelated future wording change with no error, no test failure outside this specific test file, and no comment in either file flagging the coupling;
- is fragile under truncation: `_truncate()` in `outcome.py` hard-cuts any reason text at 120 chars. A sufficiently long upstream value (e.g., an *arr error message embedded in a `failure_reasons` entry) could be truncated such that the resulting text no longer ends in the expected closing `)`; this is a narrow/low-likelihood path today given current message lengths, but there is nothing preventing a future reason string from being truncated into accidentally matching/not-matching one of these suffix checks.

**Fix:** Add a `"kind"` field (`"failure" | "unevaluated" | "malformed" | "other"`) to each dict appended in `cycle_view()`'s `reasons` list, where the call site already knows the category, and branch the template on `r.kind` instead of `r.text`:
```python
# triggarr/search/outcome.py, e.g. in the unevaluated loop:
reasons.append({"text": _truncate(f"{label} queue not evaluated: {reason}"), "count": 1, "kind": "unevaluated"})
# in the malformed-by-queue loop:
reasons.append({"text": _truncate(text), "count": 1, "kind": "malformed"})
# failure_reasons / fetch_failed / eligible-backstop rows:
reasons.append({..., "kind": "failure"})
```
```jinja
{% for r in app.last_cycle.reasons %}
  {% if r.kind == 'unevaluated' %}{% set ns.unevaluated = ns.unevaluated + 1 %}
  {% elif r.kind == 'malformed' %}{% set ns.malformed = ns.malformed + 1 %}
  {% else %}{% set ns.other = ns.other + 1 %}
  {% endif %}
{% endfor %}
```
This removes the duplicated wording dependency entirely and makes future wording changes in `outcome.py` safe by construction.

### WR-02: "Skipped record" count trusts `malformed_skipped` without cross-checking the rows that triggered the branch

**File:** `triggarr/templates/partials/cycle_grade.html:32-33`
**Issue:** The branch `{% elif no_failure and ns.malformed > 0 and app.last_cycle.malformed_skipped > 0 %}` displays `app.last_cycle.malformed_skipped` (a separately-persisted integer) as the "N skipped records" count, guarded only by `ns.malformed > 0` (derived from text-sniffing the rows) and `malformed_skipped > 0` (read independently from the record). `malformed_skipped` and `malformed_by_queue` are two independent keys in `LastCycleRecord` (`triggarr/state.py:49,52`); under normal write-side operation `CycleTally.to_dict()` always derives `malformed_skipped = sum(malformed_by_queue.values())` (`triggarr/search/outcome.py:176`), so they stay consistent in practice. But `cycle_view()` — the read-side function, which is explicitly hardened elsewhere in the same function against a tampered/corrupted `state.json` (`_as_count`, `isinstance` checks on every field, docstring: "a malformed persisted record renders as 'Not run yet', never crashes") — reads the two fields independently with no cross-validation between them. If a persisted record ever has `malformed_by_queue` entries (so `ns.malformed > 0`, i.e. one or more malformed rows exist in `reasons`) but `malformed_skipped == 0` (e.g. hand-edited state, a future write-path bug, or disk corruption), this guard fails and the code falls through to the `else` branch, mislabeling pure skip rows as "Show N failure reason(s)" — i.e., it silently regresses to exactly the bug this quick task fixes, just via a different trigger than the one tested.
**Fix:** Either (a) have `cycle_view()` derive the skip-count the template needs directly from the rows it already built (e.g. expose `malformed_row_count` or sum the per-row counts under the new `"kind": "malformed"` tag from WR-01) instead of relying on a second, independently-sourced field, or (b) clamp/reconcile `malformed_skipped` against `malformed_by_queue` inside `cycle_view()` the same way other fields there are already defensively coerced, e.g.:
```python
# in cycle_view(), after building malformed_by_queue rows:
if malformed_rows_appended > 0:
    malformed_skipped = max(malformed_skipped, sum(_as_count(raw_malformed_by_queue.get(q)) for q in QUEUES))
```
so the count the template trusts can never be less than the rows actually rendered.

## Info

### IN-01: Redundant `fetch_failed` conjunct in `no_failure`

**File:** `triggarr/templates/partials/cycle_grade.html:28`
**Issue:** `no_failure` is `app.last_cycle.failed == 0 and not app.last_cycle.fetch_failed and ns.other == 0`. The fetch-failed row's text (`"Couldn't reach {app_label} ({fetch_error})"`) already falls into the `ns.other` bucket (it matches none of the `unevaluated`/`malformed` suffix/prefix checks), so `not app.last_cycle.fetch_failed` is currently always implied by `ns.other == 0` whenever a fetch-failed row exists in `reasons`. This isn't a bug — it's a harmless belt-and-suspenders check — but two different signals (a boolean flag vs. a text-derived bucket) are being used to express the same condition, which is confusing to a future maintainer deciding which one is authoritative. Resolving WR-01 (structural `kind` tagging) naturally resolves this too, since `fetch_failed` would just become another `kind: "failure"` row and the explicit flag check could be dropped.
**Fix:** No action needed standalone; subsumed by the WR-01 fix.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-10-22T19:41:14Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: quick_
