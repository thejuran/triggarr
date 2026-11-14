---
phase: 86-pilot-reference-record
plan: 03
subsystem: review-workflow
tags: [pilot, pilot-02, vibe-check, bm-review, codex, d-09, comparison]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-01 pre-registered method and D-15 bar; 86-02 Refresh-counts H1 03182462100e9f71defc9408245410d2b99110a5"
provides:
  - "PILOT-02 same-head comparison at H1: vibe-check vs BM + paired Codex, every finding judged by proof (D-09)"
  - "H1 review-checkpoint record in 86-REVIEW-EVIDENCE.md (classification, RISK-01, BM, Codex complete, dispositions)"
  - "Owner tally approval, quoted verbatim"
  - "The confirmed defect and its proving test, for the 86-04 batched revision"
affects: [86-04, 86-07, 86-08]

key-files:
  created:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md
    - .planning/phases/86-pilot-reference-record/86-REVIEW-refresh-03182462100e.md
    - .planning/phases/86-pilot-reference-record/vibe-check/03182462100e-refresh-comparison.md
    - .planning/phases/86-pilot-reference-record/vibe-check/03182462100e-refresh-comparison.json
    - .planning/phases/86-pilot-reference-record/codex/03182462100e-pilot-refresh-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}
  modified:
    - .planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md
    - .planning/phases/86-pilot-reference-record/86-02-SUMMARY.md

key-decisions:
  - "Vibe-check ran in range mode (d5a4467..H1). The stock no-argument invocation reviews uncommitted changes only, and H1 is committed. Range mode is also stateless, so no fix loop could run during the comparison."
  - "BM's workflow docs commit was skipped instead of committed onto the pilot branch and then undone. The result is the same (H1 stays the tip, the report stays untracked) without a reset entry in the pilot branch reflog, which the trusted Codex check reads."
  - "BM diff_base was passed as the merge-base d5a4467: the workflow's grep for '86' in commit messages resolved to an unrelated 2026-03 commit."
  - "Test-gap findings whose gap-filling test passes are labeled unproven, not false positive. The gap is real; a passing test shows only that the specific case behaves correctly (owner-directed wording, 2026-10-30)."
  - "BM WR-02 is labeled unproven: the comment/return mismatch reproduces (P2 fails), but the only caller discards the list, so no consequence can be demonstrated."

requirements-completed: [PILOT-02]

duration: ~45 min
completed: 2026-10-30
---

# Phase 86 Plan 03: PILOT-02 same-head comparison on the Refresh-counts PR

**Vibe-check, BM and the paired Codex pass reviewed the same frozen head H1. Both sides found the one confirmed defect, and neither side found a defect the other missed. The owner approved the tally.**

## Results

- Order held: vibe-check (00:36:29Z–00:42:38Z), then BM (00:42:59Z–00:45:20Z), then Codex (00:45:25Z–00:48:04Z, attempt 1 complete, 0 findings). The Codex prompt contains no vibe-check text. The pilot branch tip stayed at H1 `03182462100e9f71defc9408245410d2b99110a5` throughout, and nothing was committed to it.
- Tally (D-09):

  | Reviewer | Confirmed | False positive | Unproven | Unique confirmed |
  |---|---|---|---|---|
  | vibe-check | 1 | 0 | 4 | 0 |
  | BM | 1 | 0 | 4 | 0 |
  | Codex | 0 | 0 | 0 | 0 |
- Owner tally decision (2026-10-30): "Approve tally for H1 0318246. Continue with 86-04. Correct the passing-test wording to avoid claiming broader correctness than the tests establish. This approves only the comparison tally; retirement remains a separate decision using the full pilot evidence, including PR #36’s two later-fixed misses."

## Confirmed defect to fix in 86-04

**Sonarr Refresh counts logs malformed-date skips for unmonitored episodes** (BM WR-01 = vibe-check arch-001 + bugs-001 + imp-001), at `triggarr/search/engine.py`:
- missing chain, 2111-2115;
- cutoff chain, 2137-2141.

`run_sonarr_cycle` calls `filter_monitored` before the `airDateUtc` date screen, and the refresh chains don't. So an unmonitored episode with a timezone-less air date gets logged as "Skipped 1 … malformed date data" on refresh only. The counts are unaffected.

Fix: insert `filter_monitored(...)` between the bare `_screen_queue` and the `date_fields=("airDateUtc",)` screen in both Sonarr refresh chains, matching `run_sonarr_cycle`.

Proving test (fails at H1 on both queues; add it to `tests/test_refresh_counts.py` in the batched revision):

```python
@pytest.mark.parametrize("queue", ["missing", "cutoff"])
async def test_refresh_sonarr_counts_unmonitored_tzless_airdate_not_logged_as_malformed(queue):
    bad = _make_sonarr_episode(series_id=5, episode_id=5, monitored=False)
    bad["airDateUtc"] = "2026-01-01T00:00:00"  # no timezone
    good = _make_sonarr_episode(series_id=6, episode_id=6)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[bad, good] if queue == "missing" else [good])
    client.get_wanted_cutoff = AsyncMock(return_value=[bad] if queue == "cutoff" else [])
    client.get_library_count = AsyncMock(return_value=2)
    state = _make_test_state()
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await refresh_sonarr_counts(client, state, "Default", _instance_config(), make_settings())
    finally:
        logger.remove(handler_id)
    assert result is not None
    assert state["sonarr"]["Default"]["connected"] is True
    assert "malformed date" not in sink.getvalue()
```

## Not fixed in 86-04 (no confirmed defect)

The unproven findings stay as nonblocking debt (dispositions in `86-REVIEW-EVIDENCE.md`):
- BM WR-02 (the comment overstates what the returned cutoff list guarantees);
- BM IN-01, IN-02, IN-03;
- vibe-check cov-001 to cov-004.

The owner may still choose to fold the cheap ones into the batched revision. The plan's scope is confirmed defects only.

## Deviations

- The 86-02 SUMMARY wrote H1 as `**H1: \`sha\`**`, which the plan's `grep 'H1: [0-9a-f]{40}'` could not match. Fixed in `f26b7a7` (docs only).
- The deviations in the vibe-check range mode, the skipped BM docs commit and the BM diff_base are listed under key-decisions above.

## Commits

- `f26b7a7` docs(86-02): write H1 as a plain 'H1: <sha>' line
- `037ee7d` docs(86-03): record PILOT-02 same-head comparison on the Refresh-counts PR
- `9f7350f` docs(state): Phase 86 executing; paused at 86-03 owner tally checkpoint
- `13e0909` docs(86-03): record owner tally decision
