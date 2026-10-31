# Phase 86 review evidence

Per-head review checkpoint records for the Phase 86 pilot PRs. These are kept in the
phase folder until each PR exists, and use the template in
`docs/review-checkpoint-record.md` ("Template"). Once a PR is opened, each record is
posted as that PR's per-head checkpoint comment, and a durable copy stays here.

## Credential-shape hand review

none

## Refresh-counts PR

Branch `pilot-refresh-counts-skip-malformed`, cut from `origin/main` at
`d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Local checkpoint only; nothing pushed.

### Head 03182462100e9f71defc9408245410d2b99110a5 (H1, comparison head)

```markdown
<!-- review-checkpoint head=03182462100e9f71defc9408245410d2b99110a5 -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `03182462100e9f71defc9408245410d2b99110a5` (local checkpoint, no PR yet) |
| PR base SHA | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` (merge-base with origin/main) |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `03182462100e9f71defc9408245410d2b99110a5` |
| Codex inspected base (`inspected_base_sha`) | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` |

Reconciliation: All fields match; no reconciliation needed.

### Classification

{"schema":1,"head":"03182462100e9f71defc9408245410d2b99110a5","classification":"code","classes_present":["code"],"rationale":"Changes runtime behavior in triggarr/search/engine.py (refresh_radarr/sonarr/lidarr_counts now screen each record via _screen_queue and skip malformed ones instead of marking the instance disconnected) plus its tests; no agent instructions, workflows, hooks, permissions or release policy touched.","supersedes_head":null}

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr, local checkpoint (not pushed), head `03182462100e9f71defc9408245410d2b99110a5`, base `d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Whole-PR review: Refresh counts for Radarr, Sonarr and Lidarr skips one malformed record per item instead of disconnecting the instance.
- **Risk:** moderate. Possible failures if the screening is wrong:
  - valid records are dropped silently, so counts come out too low;
  - a shape fault still marks the instance disconnected;
  - a real fetch failure is swallowed as a skip, so the instance shows connected while the API is down.

  The only user-visible effect is on the dashboard counts. Refresh counts triggers no search, and no config or credential path is touched.
- **Recommended review:** BM standard depth on the full PR, plus the paired Codex pass; a vibe-check deep review as the PILOT-02 comparison subject.
- **Required evidence:** targeted regression tests showing a malformed record is skipped per item in all three apps and that fetch failures still disconnect; full suite and ruff passing at H1.
- **What this recommendation cannot establish:** behavior against live Radarr/Sonarr/Lidarr payload variants not represented in fixtures, and how the dashboard renders the resulting counts in a browser.

### Vibe-check (RISK-02)

- Risk below high: no additional vibe-check recommended.
- **Routine vibe-check status:** ran on this head as the PILOT-02 comparison subject (`/vibe-check:deep-review`, stock, range mode `d5a4467..H1`), before BM and Codex; report at `vibe-check/03182462100e-refresh-comparison.{md,json}`. Exact-head local coverage was prepared first; provenance `check` passed for H1.

Vibe-check never substitutes for a complete Codex pass, is never counted or recorded as Codex, never waives a finding and never reduces required coverage.

### BM review

| Field | Value |
|---|---|
| Path | explicit `/bm:code-review 86 --files=triggarr/search/engine.py,tests/test_refresh_counts.py,tests/test_malformed_records_client_path.py` |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow file/step: `bm/5.0.3/workflows/code-review.md:spawn_reviewer` |
| Report location | `.planning/phases/86-pilot-reference-record/86-REVIEW-refresh-03182462100e.md` |
| Status | complete (2 warning, 3 info) |

Run notes:
- Ultracode mode was inactive. The setting is `auto`, and the date is after 2026-06-22.
- The catalog matched the skill `code-reviewer`, but it was not inserted because no local checkout exists at its pin.
- `diff_base` was passed as the merge-base `d5a4467`. The workflow's own commit-message search for "86" resolved to an unrelated commit from 2026-03.
- The workflow's docs commit was skipped, so the report was never committed to the pilot branch (the plan's alternative was commit and then undo). H1 stayed the branch tip.

### Codex

| Field | Value |
|---|---|
| Status | complete (trusted mode; `.status.json` complete, 0 findings, `inspected_head` = H1) |
| Fallback | none |
| Attempts | 1 |
| Raw output paths | `codex/03182462100e-pilot-refresh-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}` |
| Review complete | `review_complete: true`, `incomplete_reasons: []` (report schema v2) |
| Coverage | Complete in-scope diff: both changed test files and all three refresh helpers; per-item screening, raw vs eligible counts, monitored/tag/date filtering, Sonarr dedup; real-client pagination validation, non-object records, invalid envelopes, HTTP failures; unresolved tag scopes, previous-count preservation, backstops; refresh route callers; security/policy impact |
| Exclusions | Planning markdown other than changed `*-PLAN.md`, planning JSONL transcripts, generated review artifacts under `.planning/`; no changed phase plans |
| Commands run | as reported in `.last.json` `commands_run` (all exit 0), including a focused 44-test run |
| Limitations | Read-only sandbox (full suite from harness evidence: 3279 passed, 1 skipped); no live services; "new real-client refresh tests assert missing eligibility and connectivity but do not explicitly assert surviving cutoff contents or Sonarr cutoff counts" |

Findings: none (verdict `no-findings`).

### Greptile

not run: not pushed

### CI

| Required check | Run ID | Result |
|---|---|---|
| all | — | not run: not pushed |

Local evidence: full suite at H1 3279 passed, 1 skipped (`codex/03182462100e-pilot-refresh-a1.pytest.txt`; also 86-02's final-head gate and this plan's coverage run); `ruff check triggarr/ tests/` clean (86-02 Task 3).

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:03182462100e:WR-01` | bm | `03182462100e9f71defc9408245410d2b99110a5` | confirmed defect (fix in 86-04) | proof test P1 fails at H1 (both Sonarr queues log "Skipped 1 … malformed date data" for an unmonitored episode) | `03182462100e9f71defc9408245410d2b99110a5` |
| `bm:03182462100e:WR-02` | bm | `03182462100e9f71defc9408245410d2b99110a5` | nonblocking_debt (mismatch reproduced by P2; no consumer, so no consequence demonstrable) | proof test P2 fails at H1; `routes.py` discards the return value | `03182462100e9f71defc9408245410d2b99110a5` |
| `bm:03182462100e:IN-01` | bm | `03182462100e9f71defc9408245410d2b99110a5` | nonblocking_debt | read at H1: Radarr/Lidarr `filtered_cutoff` is built and never read | `03182462100e9f71defc9408245410d2b99110a5` |
| `bm:03182462100e:IN-02` | bm | `03182462100e9f71defc9408245410d2b99110a5` | nonblocking_debt (gap real; gap-filling tests P4, P5, P5b pass) | proof tests pass at H1 | `03182462100e9f71defc9408245410d2b99110a5` |
| `bm:03182462100e:IN-03` | bm | `03182462100e9f71defc9408245410d2b99110a5` | nonblocking_debt | no fixture currently patches in that scope; no failure reproducible | `03182462100e9f71defc9408245410d2b99110a5` |

The vibe-check findings are labeled in `86-PILOT-RECORD.md` under "PILOT-02 comparison result". Codex reported no findings.

### Incomplete items

- Greptile and CI: not run (not pushed).
- Owner tally approval for PILOT-02 is pending (86-03 Task 3).
```

#### Proof tests used for D-09 judging (uncommitted at H1; carried into the 86-04 revision)

Every test asserts the correct behavior, so a failure at H1 confirms the finding.

Results at H1: 4 failed, 9 passed.

| Test | Finding | Result at H1 |
|---|---|---|
| P1 `test_p1_sonarr_unmonitored_tzless_airdate_not_logged_as_malformed[missing]` / `[cutoff]` | BM WR-01, vibe-check arch-001 (+bugs-001, imp-001) | FAILED: "Sonarr: Skipped 1 missing-queue record(s) with malformed date data (ids=[5])" / same for upgrade-queue |
| P2 `test_p2_returned_cutoff_excludes_record_without_id[radarr]` / `[lidarr]` | BM WR-02 | FAILED: returned cutoff list contains `{'title': 'No id', 'monitored': True}` |
| P3 `test_p3_sonarr_missing_tag_malformed_series_skipped` | vibe-check cov-001 | passed |
| P4 `test_p4_returned_cutoff_has_no_null[radarr/sonarr/lidarr]` | vibe-check cov-002, BM IN-02 (part) | passed |
| P5 `test_p5_radarr_missing_without_id_excluded_from_monitored_and_eligible`, P5c `…lidarr…` | vibe-check cov-003, BM IN-02 (part) | passed |
| P5b `test_p5b_radarr_tzless_release_date_skipped_stays_connected` | BM IN-02 (part) | passed |
| P6 `test_p6_cutoff_tag_unresolved_returns_empty[radarr/lidarr]` | vibe-check cov-004 | passed |

P1 (the failing test that proves the confirmed defect), as run:

```python
@pytest.mark.parametrize("queue", ["missing", "cutoff"])
async def test_p1_sonarr_unmonitored_tzless_airdate_not_logged_as_malformed(queue):
    bad = _make_sonarr_episode(series_id=5, episode_id=5, monitored=False)
    bad["airDateUtc"] = "2026-01-01T00:00:00"  # no timezone
    good = _make_sonarr_episode(series_id=6, episode_id=6)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[bad, good] if queue == "missing" else [good])
    client.get_wanted_cutoff = AsyncMock(return_value=[bad] if queue == "cutoff" else [])
    client.get_library_count = AsyncMock(return_value=2)
    result, ist, log = await _run(refresh_sonarr_counts, "sonarr", client)
    assert result is not None and ist["connected"] is True
    assert "malformed date" not in log, log
```

P2, as run:

```python
@pytest.mark.parametrize("app", ["radarr", "lidarr"])
async def test_p2_returned_cutoff_excludes_record_without_id(app):
    # Radarr: bad = {"title": "No id", "monitored": True}; good has id 2.
    # Lidarr: same, each with artist {"id": 1, "artistName": "A", "tags": []}.
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[bad, good])
    result, ist, _ = await _run(fn, app, client)
    assert all("id" in r for r in result[1]), result[1]
```

`_run` calls the helper with `_make_test_state()`, `_instance_config()` and `make_settings()`, and captures WARNING logs with a loguru `StringIO` sink. These are the same helpers `tests/test_refresh_counts.py` uses.
