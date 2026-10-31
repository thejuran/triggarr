---
phase: 86-pilot-reference-record
reviewed: 2026-10-30T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - tests/test_malformed_records_client_path.py
  - tests/test_refresh_counts.py
  - triggarr/search/engine.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 86: Code Review Report

**Reviewed:** 2026-10-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found
**Commit:** 1062097a7676fddcdde3caf500f96ba1ea04d65c (diff base d5a4467)

## Summary

The change makes Refresh counts (`refresh_radarr_counts`, `refresh_sonarr_counts`,
`refresh_lidarr_counts`) fetch with `allow_non_object_records=True` and screen
records per item with `_screen_queue`, the same way the scheduled cycles do. A
malformed record is now skipped and logged, and the instance stays connected. The
old behavior marked the whole instance disconnected.

I compared each refresh chain stage by stage with its scheduled-cycle chain
(`engine.py:1083-1137`, `1367-1432`, `1699-1750`). The screening order, the
`missing_monitored` adjustments, the Sonarr `filter_monitored` -> date-screen
ordering and the Lidarr tag gating all match. I traced the shapes that previously
reached the `except (AttributeError, KeyError, TypeError)` backstop: non-object
records, non-dict `series`/`artist`, non-list tags, timezone-less dates, and
non-int IDs. Each one is now caught by `_malformed_reason` before the filter that
would raise. The route (`routes.py:1166`) discards the helper's return value, so
the tuple-contract issue below does not affect users today. ruff is clean, and the
90 tests in the two changed test files pass.

There are no blockers. The main defect is a false contract: the new comments and
docstrings promise that the returned cutoff slot is screened and that "a malformed
record never flows out of this helper". I showed by running the code that this is
not true. The secondary concern is maintainability: there are now six refresh
chains that copy the six cycle chains by hand, and they have already drifted once
in this PR (86-03 WR-01).

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Returned cutoff slot is documented as screened, but malformed, unmonitored and out-of-scope records still come back

**File:** `triggarr/search/engine.py:1975-1979, 2015` (Radarr), `2131-2134, 2183` (Sonarr), `2299-2302, 2339` (Lidarr); docstrings at `1895-1896`, `2055-2056`, `2222-2223`
**Issue:** Each helper now returns `cutoff_screened`. That list has been through only
the first `_screen_queue` stage, which has no `key_fields`, `nested_key`, `tags_at`
or `date_fields`, so it removes only non-object records. The comment says "cutoff_screened is also what the tuple returns, so a malformed record never
flows out of this helper". That is false. I ran this probe:

```
radarr cutoff=[{"id":"x","monitored":True,"tags":5},{"id":3,"monitored":False}], cutoff_tag set
  -> r[1] == [{'id': 'x', 'monitored': True, 'tags': 5}, {'id': 3, 'monitored': False}]
sonarr cutoff=[{... "seriesId":"s", "series":"bad"}]
  -> r[1] == [{... 'seriesId': 's', 'series': 'bad'}], cutoff_searchable == 0
```

So the slot holds records with a non-int `id`, non-list `tags`, a non-dict `series`,
plus unmonitored and out-of-tag-scope records. This is inconsistent in two ways. The
missing slot (slot 0) is fully filtered, and the Sonarr cutoff count is computed
from `cutoff_seasons`, not from what is returned. No production code reads the
tuple today, because the route discards it. But the docstring now tells a future
caller that the slot is safe to dispatch from or count. A caller who trusts it
would either count the wrong number of records or hit the same
`AttributeError`/`TypeError` this PR set out to remove. No test pins slot 1, so
nothing would catch this.
**Fix:** Pick one contract and make the code, docstring and a test agree with it.
Option (a) is preferred: return the fully filtered cutoff list, which matches what
slot 0 does for missing.

```python
# Radarr / Lidarr
return (filtered_missing, filtered_cutoff if not scope.cutoff_unresolved else [], scope.cutoff_tag_id)
# Sonarr: return the screened, filtered episodes (or cutoff_seasons, mirroring missing_seasons)
```

Option (b): keep `cutoff_screened`, but reword the comments and docstrings to say
"non-object records removed only; not monitored/tag/ID screened". Either way, add a
test that asserts `result[1]` for a mixed malformed/unmonitored cutoff input.

### WR-02: Refresh filter chains copy the cycle chains by hand and have already drifted once

**File:** `triggarr/search/engine.py:1951-1991` vs `1083-1137`; `2110-2155` vs `1367-1432`; `2279-2314` vs `1699-1750`
**Issue:** Each of the six queue chains (3 apps x missing/cutoff) now exists twice:
once in `run_*_cycle` and once in `refresh_*_counts`. The copies match stage for
stage, including the counting arithmetic (`missing_monitored -= len(x) - len(screened)`).
Correctness depends on keeping 12 hand-written blocks in step. This PR already
shows the risk. The first version of the Sonarr refresh chain left out
`filter_monitored` before the `airDateUtc` screen. That logged unmonitored
timezone-less episodes as malformed, and it needed a follow-up fix (86-03 WR-01, the
`test_refresh_sonarr_counts_unmonitored_tzless_airdate_not_logged_as_malformed`
test). The next screening rule added to the cycle, such as a new `date_fields` or
`key_fields` entry, has to be copied into the refresh helpers too. If it is not,
the dashboard counts will quietly disagree with what the cycle searches.
**Fix:** Move each per-queue chain into one pure function per app/queue that both
callers use. Each function returns the filtered list plus any monitored/eligible
counts and takes the tally as a parameter, for example:
`_radarr_missing_chain(items, scope, settings, tally) -> tuple[list[dict], int]`. The
cycle and the refresh then differ only in what they do with the result (dispatch vs
cache counts). If this is deferred, add a parity test that runs the same fixture
through both the cycle and the refresh for each app and asserts identical
`missing_eligible` / `missing_monitored` / `*_searchable` values.

## Info

### IN-01: Radarr/Lidarr refresh computes `filtered_cutoff` and then discards it

**File:** `triggarr/search/engine.py:1975-1991`, `2299-2314`
**Issue:** `filtered_cutoff` is assigned in the Radarr and Lidarr refresh helpers
but is never read, committed to `ist` or returned. That was true before this PR.
Now the dead chain has a side effect: its `tags_at` and `key_fields`
`_screen_queue` stages write WARNING log lines on every Refresh click for records
whose result is thrown away. The same skip is already logged by the scheduled
cycle.
**Fix:** If WR-01 option (a) is taken, `filtered_cutoff` becomes the returned value
and the dead code goes away. Otherwise, remove the unused stages or add a comment
saying they are kept only to log parity with the cycle.

### IN-02: The non-object-record client-path test does not check the cutoff side

**File:** `tests/test_malformed_records_client_path.py:278-299`
**Issue:** The fixture puts `None` in both queues (`"cutoff": [None, _GOOD[app]]`),
but the test checks only `connected`, `unreachable_since` and `missing_eligible`.
A cutoff-side fault would still be caught through `result is not None`. However, a
regression that counted or returned the `None` cutoff record would pass, because
the Sonarr `cutoff_searchable` and the tuple's cutoff slot are not checked.
**Fix:** Add `assert ist.get("cutoff_searchable") == 1` for Sonarr, and an assertion
on `result[1]` that matches whichever contract WR-01 settles on.

### IN-03: Docstring wording: "an other-unexpected-fault"

**File:** `triggarr/search/engine.py:1896`, `2056`, `2223`
**Issue:** "None on fetch failure or an other-unexpected-fault" reads like a
leftover from an edit, and the hyphenated phrase is not defined anywhere.
**Fix:** "None on a fetch failure or any other unexpected fault in the filter chain
(the backstop `except`)."

## Set aside (needs ruling)

### SA-01: Malformed-record skips on Refresh counts are visible only in System Logs

**Where:** `triggarr/search/engine.py:1932-1935`, `2092-2095`, `2259-2262` (throwaway `screen_tally`)
**Why excluded:** The code comments say this is a recorded product decision (D-02/D-02a:
"no new dashboard warning"). Whether the card should say anything is a product
choice, not a code defect.
**Effect if left as is:** After a Refresh, the card's eligible counts can be lower
than its raw counts (`missing_count` still includes non-object records), and the
card gives no reason. A user who wants to know why has to open System Logs. Before
this change, the card showed "disconnected", which was louder but wrong.
**Needs:** A ruling from the owner. Accept, which matches D-02a as recorded, or defer
a card hint to a later milestone.

---

_Reviewed: 2026-10-30T00:00:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
