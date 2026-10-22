# Phase 83 Plan 07 — Quick-task item proposal

Purpose: demonstrate the quick-task review path (REVIEW-02, REVIEW-05) on a
small, real, owner-authorized maintenance item (D-16). This document proposes
the item; nothing below has been run yet and no source file has been edited.

Reproductions were read-only: a scratch script
(`repro_card_label.py`, run from the session scratchpad, not committed)
drove the real route and template exactly as the app does, and a one-line
scratch check exercised `tempfile.mkstemp`. `git status --porcelain
triggarr/ tests/` is empty — only this planning file changed.

## Candidates

| Candidate | Source | Demonstrated defect? | Evidence | Size | Classification of the change |
|---|---|---|---|---|---|
| Card reasons label (`triggarr/templates/partials/cycle_grade.html:19`) | MAINTENANCE.md "Card reasons label" (found in the Phase 80 walkthrough, 2026-10-18) | **Yes** | See "Card reasons label — reproduction" below: a Partial cycle with 0 failed, whose only row is a malformed-record skip, renders "Show 1 failure reason" / "1 missing-queue record skipped — malformed data" | Small — one template line's wording; row text and grade colors unchanged | code (template + a new regression test in `tests/test_app_cards.py`) |
| Former 999.8 chmod cleanup (`triggarr/config.py::generate_default_config`, lines 437-504) | D-16's own example; MAINTENANCE.md "Atomic writes (former 999.8)" change-time rule | **No** | See "Former 999.8 — reproduction" below: `tempfile.mkstemp` already creates the temp file at mode `0o600`, confirmed locally, before `os.replace` makes it live | Small — would remove one redundant `os.chmod` call | code (one function in `triggarr/config.py`), but as a cleanup with no demonstrated defect |

### Card reasons label — reproduction

Built the real FastAPI app with the actual `triggarr.web.routes` router (same
code path the app uses, no edits to it) and a `last_cycle` record shaped like
MAINTENANCE.md's example: `grade="partial"`, `accepted=1`, `failed=0`,
`malformed_skipped=1`, `malformed_by_queue={"missing": 1}`. Fetched
`/partials/app-card/radarr/Default` and captured the rendered HTML
(`uv run python repro_card_label.py`, status 200):

```html
<div class="text-[12px] mb-2 flex items-center gap-1.5 text-amber-400">
  <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
  Partial · 1 accepted, 0 failed · <span title="2026-10-22 10:00:00 UTC">9h ago</span>
</div>

<details data-cycle-detail class="mb-2 text-[11px] text-triggarr-muted">
  <summary class="cursor-pointer select-none">Show 1 failure reason</summary>
  <ul class="mt-1 ml-4 list-disc">
    <li>1 missing-queue record skipped — malformed data</li>
  </ul>
</details>
```

The grade line itself is honest ("0 failed"), but the expandable summary
still says "Show 1 failure reason" even though the one row listed is a
malformed-record skip, not a failure. This reproduces MAINTENANCE.md's
report exactly and traces to `triggarr/templates/partials/cycle_grade.html`
line 19, which always renders the word "failure reason(s)" whenever
`app.last_cycle.has_detail` is true — `has_detail` (`triggarr/search/
outcome.py` line 337) is true whenever the grade is partial/failed (or a
queue went unevaluated) and there is at least one row, regardless of
whether that row is an actual failure, an unevaluated-queue note, or a
malformed-record skip.

### Former 999.8 — reproduction

```
$ uv run python -c "
import tempfile, os, stat
with tempfile.TemporaryDirectory() as d:
    fd, path = tempfile.mkstemp(dir=d, suffix='.tmp')
    mode = stat.S_IMODE(os.fstat(fd).st_mode)
    print('mkstemp mode:', oct(mode))
    os.close(fd)
"
mkstemp mode: 0o600
```

`tempfile.mkstemp` already creates the file at mode `0o600` before anything
is written to it, and `generate_default_config` writes through that same fd
and only calls `os.replace` afterward — the file is 0600 for its entire life
on disk, including at the moment `os.replace` makes it visible under its
final name. The later `os.chmod(config_path, 0o600)` on line 504 is
therefore redundant: there is no window where the file exists world- or
group-readable. This matches MAINTENANCE.md's change-time rule ("Fix
demonstrated defects with focused tests; no mandatory consolidation") and
the archived backlog language that "omitting a later chmod does not by
itself demonstrate world-readable output." Removing it would be a
no-behavior-change cleanup, not a defect fix.

## Recommendation

**Card reasons label wording** is the recommended item. It is a real,
user-visible, small, reproduced defect with a defined fix (reword the
summary text so a skip-only or unevaluated-only row set is never called a
"failure reason"; keep the row text itself and the grade colors unchanged),
and it is naturally test-first: write the failing regression test against
the reproduction above, then change only the label wording.

Former 999.8 is offered only as a no-behavior-change cleanup, not as the
recommended item, because the reproduction above found no demonstrated
defect: `mkstemp` already creates the file at `0o600`, so there is no
permission window the `os.chmod` call closes. MAINTENANCE.md's own
change-time rule allows consolidating this kind of copy only alongside a
demonstrated defect or a change to that writer — it discourages
consolidation on its own, which is exactly this candidate's situation.

## Exact /bm:quick invocation

```
/bm:quick --full "Fix the dashboard card's expandable detail label: when a Partial or Failed cycle's only detail rows are skip-only (malformed-record skip or unevaluated-queue) rows and there are zero actual failures, the summary text must not say 'failure reason(s)'. Write the failing regression test first (in tests/test_app_cards.py, using the Phase 80-style skip-only Partial cycle fixture), then change only the label wording in triggarr/templates/partials/cycle_grade.html so skip-only rows are never called failures. Keep the existing row text (e.g. '1 missing-queue record skipped — malformed data') and the existing grade colors (success/partial/failed) unchanged."
```

The `--full` flag is the exact flag the installed BM needs: per
`docs/bm-review-baseline-2026-10-22.md` ("Installed behavior re-check",
item (a), quick-task row), `workflows/quick.md` Step 6.25 skips the
automatic code-review step entirely unless `$FULL_MODE` is true, and
`$FULL_MODE` is set only by `--full` (or by `--discuss --research
--validate` together, which does not apply to a task this size). Without
`--full`, BM's review would not run at all for this quick task.

## Owner decision

(empty — to be filled in Task 2)
