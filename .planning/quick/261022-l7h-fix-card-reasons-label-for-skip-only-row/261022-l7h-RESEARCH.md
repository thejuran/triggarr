# Quick Task 261022-l7h: Card reasons label for skip-only rows - Research

**Researched:** 2026-10-22
**Domain:** Jinja2 template (FastAPI + htmx dashboard card), `triggarr/search/outcome.py::cycle_view`
**Confidence:** HIGH (every claim below was checked by reading the code or running tests in this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Skip-only label wording:** When every detail row is a skip-only row (zero actual failures), the link reads "Show 1 skipped record" (singular) / "Show N skipped records" (plural). Owner selected this wording.
- **Mixed failure + skip rows:** When the list contains at least one real failure, keep today's wording "Show N failure reason(s)" unchanged. Only skip-only lists change. Owner selected the minimal change.
- Row text (e.g. "1 missing-queue record skipped — malformed data") and grade colors (success/partial/failed) stay byte-identical.
- Test first: the regression test must fail against the current template before the template changes.

### Claude's Discretion
- How skip-only rows are detected in the template (use existing row/cycle data; no new backend fields unless the template cannot tell rows apart).
- If an unevaluated-queue row cannot accurately be described as a "skipped record", flag it in the SUMMARY rather than inventing new wording.

### Deferred Ideas (OUT OF SCOPE)
- None listed.
</user_constraints>

## Summary

The label is one line, `triggarr/templates/partials/cycle_grade.html:19`. It always prints `Show {{ reason_count }} failure reason(s)` whenever `has_detail` is true. `reason_count` is `len(reasons)`. `reasons` is a flat list of `{"text", "count"}` dicts built by `cycle_view()` (`triggarr/search/outcome.py:219-351`), and the rows carry **no type field**. The only route that renders the partial is `triggarr/web/routes.py:402`. It is included twice in `app_card.html` (lines 34 and 48, for the connected and unreachable bodies), so a single template edit covers both.

The template can identify the reproduced case from cycle-level fields it already receives: `failed == 0`, `not fetch_failed`, and `malformed_skipped > 0`. Under those conditions the only rows that can appear besides malformed-skip rows are **unevaluated-queue rows**. The "eligible item not searched" row is suppressed whenever `malformed_skipped > 0` (outcome.py:318-324). Failure rows only appear when `failed > 0`, except in a tampered record. The view does not expose an unevaluated-row count, so a template-only fix needs one row-level guard that rules out unevaluated rows.

**Primary recommendation:** Template-only. Before `<details>`, compute `skip_only` with a Jinja `namespace` loop. It is true only when `failed == 0`, `not fetch_failed`, `malformed_skipped > 0`, and every row's text ends with malformed-skip wording. When `skip_only` is true, render `Show {{ malformed_skipped }} skipped record(s)`; otherwise keep the current line exactly. Use **`malformed_skipped` (record count), not `reason_count` (row count)**, as N. See Pitfall 1.

## Row types produced by `cycle_view` (in order)

| Row | Producer line | Text format | Ends with | Is it a "skipped record"? |
|---|---|---|---|---|
| Fetch failure | 258-260 | `Couldn't reach {App} ({err})` | `)` | No: failure |
| Command failure | 262-275 | `Command rejected by {App} (HTTP 500)` / `Search command to {App} failed (...)` | `)` | No: failure |
| Unevaluated queue | 277-292 | `{Missing\|Cutoff unmet} queue not evaluated: {reason}`. Reasons come from engine.py:867 (`tag 'X' not found`, `couldn't load tags`) and :1116/1146/1398/1444/1725/1759 (`malformed data (TypeError)`) | `found` / `tags` / `)` | **No.** A whole queue was not evaluated. It is not a record that was skipped. |
| Malformed per-queue | 294-307 | `1 missing-queue record skipped — malformed data` / `N upgrade-queue records skipped — malformed data` | `— malformed data` | Yes |
| Malformed legacy | 309-314 | `1 malformed record skipped` / `N malformed records skipped` | `skipped` | Yes |
| Eligible not searched | 318-335 | `N eligible item(s) not searched this cycle` (only Failed with accepted=0, failed=0, no unevaluated, **malformed_skipped == 0**) | `this cycle` | No. It never coexists with malformed rows. |

**Finding for the discretion item:** "skipped record" does **not** accurately describe unevaluated-queue rows. They report that a whole queue (for example a missing tag, or a queue-level malformed-data exception) was not searched. No records were counted or skipped. So:
- Unevaluated-only cycles (failed=0, no malformed rows) should **keep** the current "failure reason(s)" label in this task. The SUMMARY should flag them as still mislabeled, with the wording left to the owner.
- Mixed malformed + unevaluated cycles with failed=0 should also keep the current label, because "Show 2 skipped records" would misdescribe the unevaluated row. This combination is reachable: for example, the cutoff tag is missing while the missing queue has one malformed record.

The phrase "malformed-record skip or unevaluated-queue" in the task description therefore conflicts with the locked wording "skipped record(s)". The recommended fix changes only the cases where that wording is accurate.

## Recommended template change (pattern)

```jinja
{% if app.last_cycle.has_detail %}
{% set ns = namespace(skip_only=(app.last_cycle.failed == 0 and not app.last_cycle.fetch_failed and app.last_cycle.malformed_skipped > 0)) %}
{% for r in app.last_cycle.reasons %}{% if not (r.text.endswith('— malformed data') or r.text.endswith('skipped')) %}{% set ns.skip_only = false %}{% endif %}{% endfor %}
<details data-cycle-detail class="mb-2 text-[11px] text-triggarr-muted">
  {% if ns.skip_only %}
  <summary class="cursor-pointer select-none">Show {{ app.last_cycle.malformed_skipped }} skipped record{% if app.last_cycle.malformed_skipped != 1 %}s{% endif %}</summary>
  {% else %}
  <summary class="cursor-pointer select-none">Show {{ app.last_cycle.reason_count }} failure reason{% if app.last_cycle.reason_count != 1 %}s{% endif %}</summary>
  {% endif %}
  ... <ul> unchanged ...
```

- Jinja 3.1.6 is installed `[VERIFIED: uv run python -c "import jinja2"]`. `namespace()` is required because `{% set %}` inside `{% for %}` does not leak out of the loop scope `[CITED: jinja.palletsprojects.com/en/3.1.x/templates/#assignments]`. Python `str.endswith` is callable from templates (the environment is a normal `Environment` with `autoescape=True`, routes.py:78, not a sandbox).
- The `'— malformed data'` literal is an em dash (U+2014), the same character used at outcome.py:303/305. Copy it exactly.
- **Alternative if the planner rejects text matching in the template:** add one boolean, `skip_only`, to `cycle_view`'s return dict (true when `failed == 0`, `not fetch_failed`, `unevaluated_rows == 0`, and malformed rows > 0), plus a `tests/test_outcome.py` unit test. This is cleaner, but it goes beyond the owner's stated "change only the label wording in cycle_grade.html". The CONTEXT discretion clause allows it only if the template cannot tell rows apart, and with the suffix guard above it can. Recommend the template-only version and mention the alternative in the SUMMARY.

## Test fixtures and assertion style (`tests/test_app_cards.py`)

- Fixtures: `test_app` (lines 27-107, async, builds a FastAPI app with the real `router` and in-memory `triggarr_state`) and `client` (110-113, `TestClient`).
- Record builder: `_last_cycle_record(**overrides)` (463-480). The defaults are grade success, all counts 0, empty lists, and `fetch_error=None`. It has **no** `malformed_by_queue` key, so pass it explicitly.
- The Phase 80-style skip-only fixture already exists in `test_card_malformed_by_queue_row_renders` (531-543): `grade="partial", accepted=1, malformed_skipped=1, malformed_by_queue={"missing": 1}`. This matches the reproduction in 83-QUICK-PROPOSAL.md exactly.
- Style: set `test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True` and `[...]["last_cycle"] = _last_cycle_record(...)`, then `client.get("/partials/app-card/radarr/Default")`, then `assert response.status_code == 200` and plain substring `in` / `not in` checks on `response.text`. Place the new tests directly after line 543.

Suggested tests (the first one must fail on the current template):
1. `test_card_skip_only_partial_label_says_skipped_record`: uses the reproduction fixture. Asserts `"Show 1 skipped record" in text`, `"failure reason" not in text`, `"1 missing-queue record skipped — malformed data" in text`, `"Partial · 1 accepted, 0 failed" in text`, and `"text-amber-400" in text`.
2. Plural, counting records rather than rows: `malformed_skipped=3, malformed_by_queue={"missing": 2, "cutoff": 1}` gives 2 rows and asserts `"Show 3 skipped records"`.
3. Failed skip-only: `grade="failed", accepted=0, malformed_skipped=1, malformed_by_queue={"missing": 1}` asserts `"Show 1 skipped record"` and `"text-triggarr-danger"`.
4. Mixed failure + skip, label unchanged: `failed=1, failure_reasons=[{"reason":"HTTP 500","count":1}]` plus malformed asserts `"Show 2 failure reasons"`.
5. Malformed + unevaluated with failed=0, label unchanged: `unevaluated=[{"queue":"cutoff","reason":"tag 'x' not found"}]` plus malformed asserts `"failure reason" in text` and `"skipped record" not in text`. This documents the deliberate gap.
6. Optionally, the legacy aggregate only: `malformed_skipped=1` with no `malformed_by_queue` key asserts `"Show 1 skipped record"`.

## Common Pitfalls

1. **N must count records, not rows.** One per-queue row can stand for many records ("2 missing-queue records skipped"). With `{"missing": 2, "cutoff": 1}` there are 2 rows but 3 records, so "Show 2 skipped records" would be wrong. Use `malformed_skipped`. It equals `sum(malformed_by_queue.values())` by construction (outcome.py:176) and also covers the legacy row.
2. **Substring traps in assertions.** `"Show 1 skipped record"` is a substring of `"Show 1 skipped records"`. Assert the plural cases with the full plural string, and use the `"failure reason" not in` check for the singular case. The existing assertion `"Show 1 failure reason"` (line 510) has the same overlap and still passes, because that test has failed=1 and its label is unchanged.
3. **Existing assertions on the old wording:** only `tests/test_app_cards.py:510` (failed=1, unaffected). `tests/test_outcome.py:406` checks `reason_count`, which stays unchanged. No docs or README quote the label (grep in this session). The spec line `docs/superpowers/specs/2026-10-08-search-correctness-design.md:103` describes "failure reasons" in prose only, so leave it alone.
4. **Unreachable or fetch-failed card.** The partial is also rendered in the unreachable body. `fetch_failed` forces `skip_only` false, so "Couldn't reach" stays a failure reason.
5. **htmx open-panel persistence.** The script at `dashboard.html:55-82` keys on `[data-cycle-detail]`, not on the summary text. Keep the `data-cycle-detail` attribute and the `<details>` element unchanged.
6. **Jinja scoping.** A plain `{% set skip_only = false %}` inside the loop silently does nothing outside it. Use `namespace`.
7. **Do not touch `has_detail`, the `<li>` text, or the grade-color `if` chain.** The constraints require them to stay byte-identical.

## Validation Architecture

| Property | Value |
|---|---|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Quick run | `uv run pytest tests/test_app_cards.py -x -q` (baseline in this session: 74 passed) |
| Full suite | `uv run pytest tests/ -x -q` plus `uv run ruff check triggarr/ tests/` |
| Test-first gate | Run test 1 before editing the template and confirm it FAILS (current output: "Show 1 failure reason") |

No Wave 0 gaps. The fixtures and the builder already exist.

## Security Domain

Template-only change. Row text is still autoescaped (`autoescape=True`), and `test_reason_text_with_script_tag_is_escaped` (738) keeps covering that. The new label interpolates only an int (`malformed_skipped`, coerced by `_as_count`). The change introduces no new input, secret, or logging path.

## Assumptions Log

| # | Claim | Risk if wrong |
|---|---|---|
| A1 | The owner's "N" in "Show N skipped records" means the number of skipped records, not the number of rows | Low. If the owner meant rows, switch N to `reason_count`. Confirm in the SUMMARY. |

## Open Questions (RESOLVED)

RESOLVED (owner, 2026-10-22): 0-failure lists that include any unevaluated-queue row read "Show N details" (N = rows); see CONTEXT.md "Unevaluated-queue rows".


~~1. Wording for unevaluated-only and malformed+unevaluated cycles with 0 failures.~~ Superseded by the owner decision above: those cycles read "Show N details".
