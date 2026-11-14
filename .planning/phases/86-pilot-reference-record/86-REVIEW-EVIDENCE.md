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

### Head 1062097a7676fddcdde3caf500f96ba1ea04d65c (final head)

PR comment: https://github.com/thejuran/triggarr/pull/54#issuecomment-6537692648 (PR #54; CI run 41158788891; Review acceptance run 41158788888)

```markdown
<!-- review-checkpoint head=1062097a7676fddcdde3caf500f96ba1ea04d65c -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `1062097a7676fddcdde3caf500f96ba1ea04d65c` (local checkpoint, no PR yet) |
| PR base SHA | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` (merge-base with origin/main) |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| Codex inspected base (`inspected_base_sha`) | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` |

Reconciliation: All fields match; no reconciliation needed.

### Classification

{"schema":1,"head":"1062097a7676fddcdde3caf500f96ba1ea04d65c","classification":"code","classes_present":["code"],"rationale":"H1 plus the 86-04 batched revision: refresh_sonarr_counts runs filter_monitored before the airDateUtc screen on both chains (engine.py), with a regression test (tests/test_refresh_counts.py). Runtime code and tests only.","supersedes_head":"03182462100e9f71defc9408245410d2b99110a5"}

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr, local checkpoint (not pushed), head `1062097a7676fddcdde3caf500f96ba1ea04d65c`, base `d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Whole-PR review (H1 plus the batched revision `a794c8a` test, `1062097` fix).
- **Risk:** moderate, unchanged from H1. The revision adds one `filter_monitored` call per Sonarr refresh chain. Counts cannot change, because `filter_sonarr_episodes` already drops unmonitored episodes; only log lines change. The H1 failure scenarios still apply to the PR as a whole.
- **Recommended review:** BM standard depth on the full PR, plus the paired Codex pass; routine vibe-check (code class).
- **Required evidence:** the WR-01 regression test, `test_refresh_sonarr_counts_unmonitored_tzless_airdate_not_logged_as_malformed` (fails at H1, passes at H_final); full suite and ruff at H_final.
- **What this recommendation cannot establish:** behavior against live Radarr/Sonarr/Lidarr payload variants not represented in fixtures; how the dashboard renders the counts in a browser.

### Vibe-check (RISK-02)

- Risk below high: no additional vibe-check recommended.
- **Routine vibe-check status:** ran on this head (`/vibe-check:deep-review`, stock invocation, range `d5a4467..1062097`). Because the H1 pass left state, it ran as pass 2: it reviewed the change since H1 and rechecked every carried H1 finding at H_final. Exact-head local coverage was prepared first and its provenance `check` passed. Report: `vibe-check/1062097a7676-refresh-routine.{md,json}`. Result: the Sonarr ordering finding was resolved on recheck by all three agents that raised it. Two test-gap rows remain (Warning: Sonarr missing-tag path untested; Medium: returned cutoff list not asserted). No product defect.

### BM review

| Field | Value |
|---|---|
| Path | review after fixes (`/bm:code-review 86 --files=triggarr/search/engine.py,tests/test_refresh_counts.py,tests/test_malformed_records_client_path.py`) |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow file/step: `bm/5.0.3/workflows/code-review.md:spawn_reviewer` |
| Report location | `.planning/phases/86-pilot-reference-record/86-REVIEW-refresh-1062097a7676.md` |
| Status | complete (2 warning, 3 info, 1 set aside for a ruling) |

As at H1: `diff_base` was the merge-base; no catalog skill; the report was not committed to the pilot branch, so H_final stayed the tip.

### Codex

| Field | Value |
|---|---|
| Status | complete (trusted mode; `.status.json` complete, 0 findings, `inspected_head` = H_final) |
| Fallback | none |
| Attempts | 1 |
| Raw output paths | `codex/1062097a7676-pilot-refresh-final-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}` |
| Review complete | `review_complete: true`, `incomplete_reasons: []` (report schema v2) |
| Coverage | All three changed files including all test changes; non-object records traced through client pagination and all six refresh queues; nested objects, tags, integer keys, timezone-less dates, monitoring and release filters vs scheduled-cycle behavior; unresolved tags, retained counts, scoped stamps, recovery, backstops; refresh route locking, rate limiting, rendering, discarded return values; no CI/acceptance/audit/publication policy changes |
| Exclusions | Planning markdown other than changed `*-PLAN.md`, `.planning/**/*.jsonl`, generated review artifacts under `.planning/**/codex/**`; files outside the working copy |
| Commands run | 15, all exit 0 (as reported in `.last.json`) |
| Limitations | Pytest not rerun in the read-only sandbox (harness: 3281 passed, 1 skipped); no live services; "new real-client success tests assert missing eligibility but do not assert surviving cutoff contents or Sonarr cutoff counts" |

Findings: none (verdict `no-findings`).

### Greptile

not run: not pushed

### CI

| Required check | Run ID | Result |
|---|---|---|
| all | — | not run: not pushed |

Local evidence: full suite at H_final: 3281 passed, 1 skipped. This was run three times: the 86-04 final-head gate with HEAD asserted, the vibe-check coverage run, and `codex/1062097a7676-pilot-refresh-final-a1.pytest.txt`. `ruff check triggarr/ tests/` is clean.

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:03182462100e:WR-01` | bm | `03182462100e9f71defc9408245410d2b99110a5` | fixed | regression test fails at H1, passes at H_final; vibe-check recheck resolved (architecture, bugs, impact); BM and Codex on H_final raise nothing on it | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:WR-01` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | Same issue as H1 `WR-02`, now with more examples: the returned cutoff list can hold records with a bad `id` or tags, or unmonitored ones. The approved H1 tally labelled it unproven, because the only caller (`routes.py`) discards the list. | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:WR-02` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | Design note: the refresh filter chains duplicate the cycle chains, and they drifted once (fixed in this PR). There is no current behavioral defect. Candidate backlog item: a shared per-app chain helper, or a parity test. | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:IN-01` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | same as H1 `IN-01` | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:IN-02` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | test gap; same family as H1 `IN-02` and vibe-check cov-002 | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:IN-03` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | docstring wording ("an other-unexpected-fault") | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:SA-01` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | decided (owner, D-02) | Skips are visible only in System Logs. This is the owner's recorded decision in 86-CONTEXT D-02: "No new dashboard warning." Nothing new to rule on. | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `vibe-check:1062097a7676:cov-001` | vibe-check | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | Sonarr missing-tag path untested; H1 proof test P3 passed for its case | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `vibe-check:1062097a7676:cov-002` | vibe-check | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | returned cutoff list not asserted; H1 proof test P4 passed for its case | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |

### Incomplete items

- Greptile and CI: not run (not pushed; 86-07).
- No new confirmed defect on H_final, so there is no owner fix-vs-debt decision under the Triage rule.
```

#### Original vs. refreshed findings (H1 → H_final)

| H1 finding | Status at H_final |
|---|---|
| BM WR-01 / vibe-check arch-001 (+bugs-001, imp-001): Sonarr ordering logs misleading skips | **Fixed.** The regression test passes; vibe-check resolved it on recheck; BM and Codex on H_final no longer raise it. |
| BM WR-02: comment overstates what the returned cutoff list guarantees | Carried forward as BM H_final WR-01, with more examples; still nonblocking debt, since no caller reads the list. |
| BM IN-01: Radarr/Lidarr `filtered_cutoff` built and discarded | Carried forward (H_final IN-01) |
| BM IN-02: e2e test doesn't check the cutoff side | Carried forward (H_final IN-02) |
| BM IN-03: `monkeypatch.undo()` midway | Not re-raised at H_final (BM raised docstring wording instead). It remains in the H1 record as nonblocking debt. |
| vibe-check cov-001: Sonarr missing-tag path untested | Carried forward; vibe-check recheck says it still applies (Warning 82) |
| vibe-check cov-002: returned cutoff list not asserted | Carried forward; recheck says it still applies (Medium 72) |
| vibe-check cov-003, cov-004 (sub-threshold at H1) | Not re-raised |
| Codex: no findings | Codex at H_final: no findings |

New at H_final: BM WR-02 (duplicated chains, design note); BM SA-01 (already decided by D-02); vibe-check cov-003 (sub-threshold: the new cutoff-variant test doesn't assert the cutoff count).

#### Review time and usage at H_final (D-13)

| Reviewer | Start (UTC) | End (UTC) | Wall clock | Usage printed |
|---|---|---|---|---|
| BM | 2026-10-31T01:09:28Z | 2026-10-31T01:11:46Z | 2 min 18 s | none; harness reported 83k reviewer subagent tokens |
| Codex (paired) | 2026-10-31T01:09:19Z | 2026-10-31T01:11:51Z | 2 min 32 s (incl. full-suite run) | `.jsonl` `turn.completed`: input 529,508 tokens (446,208 cached), output 3,072, reasoning 144 |
| vibe-check (routine, pass 2) | 2026-10-31T01:12:05Z | 2026-10-31T01:16:57Z | 4 min 52 s (plus 111 s exact-head coverage beforehand) | none from the tool; harness subagent tokens: triage 85k, bugs 70k, security 73k, architecture 62k, impact 66k, test-sufficiency 73k, compliance 77k, language-python 79k, framework-fastapi 72k |

BM and Codex ran at the same time on the frozen head. Vibe-check started after both had finished.

## Card-template PR

Branch `pilot-card-reason-kind`, cut from `origin/main` at
`d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Local checkpoint only; nothing pushed.

Scope: UI-template change; no visible difference. 86-05's divergence analysis
concluded **no reachable divergence**. Old text matching and new kind-based
classification group every reason row the same way for every input the
application's own code can produce. Divergence needs either text that
`_sanitize_exc` and the fixed unevaluated-row prefix never generate, or tampered
records (for example, malformed or eligible counts of 70+ digits). So 86-05
Task 2 (owner decision on a visible change) did not run.

### Head 46c39194249d1e7bcd2362a91d238d0997539f3f (H1)

PR comment: https://github.com/thejuran/triggarr/pull/55#issuecomment-6537692830 (PR #55; CI run 41158791610; Review acceptance run 41158791675)

```markdown
<!-- review-checkpoint head=46c39194249d1e7bcd2362a91d238d0997539f3f -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `46c39194249d1e7bcd2362a91d238d0997539f3f` (local checkpoint, no PR yet) |
| PR base SHA | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` (merge-base with origin/main) |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| Codex inspected base (`inspected_base_sha`) | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` |

Reconciliation: All fields match; no reconciliation needed.

### Classification

{"schema":1,"head":"46c39194249d1e7bcd2362a91d238d0997539f3f","classification":"code","classes_present":["code"],"rationale":"cycle_view() (triggarr/search/outcome.py) adds a structured kind/skip_count to each reason row and cycle_grade.html classifies by kind instead of display text; plus tests. Runtime code and a template; no agent instructions, workflows or policy.","supersedes_head":null}

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr, local checkpoint (not pushed), head `46c39194249d1e7bcd2362a91d238d0997539f3f`, base `d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Whole-PR review: the card's reason rows are classified by a structured `kind` instead of display text, with no visible change intended (D-03).
- **Risk:** low. The worst realistic failure is a wrong summary label on the dashboard card ("Show N skipped records" instead of "Show N failure reasons"), or a template error if a malformed row ever lacked `skip_count`. Both construction sites set it, and a test enforces that. Nothing persisted changes, and search behavior is untouched.
- **Recommended review:** BM standard on the full PR, plus the paired Codex pass; routine vibe-check (code class).
- **Required evidence:** `cycle_view` dict tests pinning `kind`/`skip_count`; existing card rendering tests unchanged and passing; full suite and ruff at H1.
- **What this recommendation cannot establish:** browser rendering, and labels for tampered records outside what the application writes.

### Vibe-check (RISK-02)

- Risk below high: no additional vibe-check recommended.
- **Routine vibe-check status:** ran on this head (`/vibe-check:deep-review`, stock, range `d5a4467..46c3919`, pass 1); exact-head local coverage was prepared first and its provenance `check` passed. Report: `vibe-check/46c39194249d-card-routine.{md,json}`. Result: 1 Medium (no rendering test for the template switch), 3 sub-threshold; no product defect.

### BM review

| Field | Value |
|---|---|
| Path | explicit `/bm:code-review 86 --files=triggarr/search/outcome.py,triggarr/templates/partials/cycle_grade.html,tests/test_outcome.py,tests/test_app_cards.py` |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow file/step: `bm/5.0.3/workflows/code-review.md:spawn_reviewer` |
| Report location | `.planning/phases/86-pilot-reference-record/86-REVIEW-card-46c39194249d.md` |
| Status | complete (1 warning, 2 info, 1 set aside) |

As on the Refresh-counts PR: `diff_base` was the merge-base; no catalog skill was inserted; the report was not committed to the pilot branch, so H1 stayed the tip.

### Codex

| Field | Value |
|---|---|
| Status | complete (trusted mode; `.status.json` complete, 0 findings, `inspected_head` = H1) |
| Fallback | none |
| Attempts | 1 |
| Raw output paths | `codex/46c39194249d-pilot-card-a1.{prompt.txt,meta.json,last.json,status.json,pytest.txt}`; `.jsonl` withheld (see Withheld files below) |
| Review complete | `review_complete: true`, `incomplete_reasons: []` (report schema v2) |
| Coverage | All changes in the three files; all six reason-construction paths, count validation, legacy aggregate fallback, malformed state, truncation, ordering; persisted records traced through `cycle_view` into connected and unreachable card templates; existing rendering assertions; no persisted schema or shared state; escaping and policy |
| Exclusions | Planning markdown other than changed `*-PLAN.md`, planning JSONL, generated artifacts under `.planning/**/codex/**` |
| Commands run | 12, as reported in `.last.json` (exit codes 0 and 1; exit 1 = searches with no match) |
| Limitations | Pytest not rerun in the read-only sandbox (harness: 3271 passed, 1 skipped); "Existing rendering tests protect current labels but do not explicitly mutate display wording to prove classification remains independent of text"; no browser verification |

Findings: none (verdict `no-findings`).

### Greptile

not run: not pushed

### CI

| Required check | Run ID | Result |
|---|---|---|
| all | — | not run: not pushed |

Local evidence: full suite at H1 3271 passed, 1 skipped (86-05 final-head gate with HEAD asserted; this plan's coverage run; `codex/46c39194249d-pilot-card-a1.pytest.txt`); `ruff check triggarr/ tests/` clean (86-05).

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:46c39194249d:WR-01` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (D-09: unproven; real test gap, no defect) | Reproduced: with the pre-change `cycle_grade.html` swapped into the H1 working tree (uncommitted, then restored), `tests/test_app_cards.py` + `tests/test_outcome.py` gave 148 passed. The new template behaves correctly. BM's example divergence needs a tampered record, for which the new label is the correct one. | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `bm:46c39194249d:IN-01` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | kind names are string literals in three places; no current mismatch (test enforces the closed set) | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `bm:46c39194249d:IN-02` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | test hardcodes `"malformed"` in its seen-set and has a redundant subset assert; legacy row checked directly elsewhere | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `bm:46c39194249d:SA-01` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven; predates this PR) | A tampered record can show both malformed rows and an "eligible not searched" row; records the app writes don't produce it. A candidate later-phase tightening. | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `vibe-check:46c39194249d:cov-001` | vibe-check | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | same gap as `bm:…:WR-01`; same reproduction | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `vibe-check:46c39194249d:arch-001`, `cov-002`, `cov-003` (sub-threshold) | vibe-check | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | arch-001 = BM IN-01; cov-003 = BM IN-02; cov-002 guard paths predate this PR | `46c39194249d1e7bcd2362a91d238d0997539f3f` |

D-09 tally for this head: confirmed 0, false positive 0, unproven 5 BM-side (WR-01, IN-01, IN-02, SA-01; Codex 0) and 4 vibe-check-side (cov-001 reported; arch-001, cov-002, cov-003 filtered).

### Incomplete items

- Greptile and CI: not run (not pushed; 86-07).
```

#### Withheld files

- `codex/46c39194249d-pilot-card-a1.jsonl` failed publication-gate check 3 (local user name). One event in Codex's transcript is an `ls -l` listing that shows the file owner. Codex files are never edited after grading, so the file was moved out of the repository to a private location on the owner's machine instead of being redacted. The graded report (`.last.json`), status (`.status.json`), prompt, meta and pytest evidence for this attempt all passed the gate and are published. Codex completion is graded from `.last.json`, so it does not depend on the withheld transcript. No re-run was needed for completeness; the token-usage figures below were read from the transcript before it was withheld.

#### Review time and usage at H1 (D-13)

| Reviewer | Start (UTC) | End (UTC) | Wall clock | Usage printed |
|---|---|---|---|---|
| BM | 2026-10-31T01:31:38Z | 2026-10-31T01:33:37Z | 1 min 59 s | none; harness reported 44k reviewer subagent tokens |
| Codex (paired) | 2026-10-31T01:31:31Z | 2026-10-31T01:33:42Z | 2 min 11 s (incl. full-suite run) | `.jsonl` `turn.completed`: input 220,995 tokens (153,856 cached), output 2,097, reasoning 123 |
| vibe-check (routine) | 2026-10-31T01:33:37Z | 2026-10-31T01:37:46Z | 4 min 9 s (plus 105 s exact-head coverage beforehand, run while BM and Codex were active) | none from the tool; harness subagent tokens: triage 50k, bugs 72k, security 77k, architecture 69k, impact 73k, test-sufficiency 68k, compliance 84k, language-python 72k |

#### Final head (86-06 Task 2)

H_final = H1 (`46c39194249d1e7bcd2362a91d238d0997539f3f`). D-09 triage found no confirmed defect on the card-template PR, so no revision was made. The BM review, paired Codex pass and routine vibe-check recorded above for H1 are this PR's final-head evidence. `git rev-list --count 46c3919..pilot-card-reason-kind` is 0.


## Durable copy: PR #54 checkpoint comment

Posted 2026-10-30 at https://github.com/thejuran/triggarr/pull/54#issuecomment-6537692648. The text below is exactly as posted.

````markdown
<!-- review-checkpoint head=1062097a7676fddcdde3caf500f96ba1ea04d65c -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `1062097a7676fddcdde3caf500f96ba1ea04d65c` (PR #54) |
| PR base SHA | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` (merge-base with origin/main) |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| Codex inspected base (`inspected_base_sha`) | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` |

Reconciliation: All fields match; no reconciliation needed.

### Classification

{"schema":1,"head":"1062097a7676fddcdde3caf500f96ba1ea04d65c","classification":"code","classes_present":["code"],"rationale":"H1 plus the 86-04 batched revision: refresh_sonarr_counts runs filter_monitored before the airDateUtc screen on both chains (engine.py), with a regression test (tests/test_refresh_counts.py). Runtime code and tests only.","supersedes_head":"03182462100e9f71defc9408245410d2b99110a5"}

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr, PR #54 (reviewed as a local checkpoint before the push; same head), head `1062097a7676fddcdde3caf500f96ba1ea04d65c`, base `d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Whole-PR review (H1 plus the batched revision `a794c8a` test, `1062097` fix).
- **Risk:** moderate, unchanged from H1. The revision adds one `filter_monitored` call per Sonarr refresh chain. Counts cannot change, because `filter_sonarr_episodes` already drops unmonitored episodes; only log lines change. The H1 failure scenarios still apply to the PR as a whole.
- **Recommended review:** BM standard depth on the full PR, plus the paired Codex pass; routine vibe-check (code class).
- **Required evidence:** the WR-01 regression test, `test_refresh_sonarr_counts_unmonitored_tzless_airdate_not_logged_as_malformed` (fails at H1, passes at H_final); full suite and ruff at H_final.
- **What this recommendation cannot establish:** behavior against live Radarr/Sonarr/Lidarr payload variants not represented in fixtures; how the dashboard renders the counts in a browser.

### Vibe-check (RISK-02)

- Risk below high: no additional vibe-check recommended.
- **Routine vibe-check status:** ran on this head (`/vibe-check:deep-review`, stock invocation, range `d5a4467..1062097`). Because the H1 pass left state, it ran as pass 2: it reviewed the change since H1 and rechecked every carried H1 finding at H_final. Exact-head local coverage was prepared first and its provenance `check` passed. Report: `vibe-check/1062097a7676-refresh-routine.{md,json}`. Result: the Sonarr ordering finding was resolved on recheck by all three agents that raised it. Two test-gap rows remain (Warning: Sonarr missing-tag path untested; Medium: returned cutoff list not asserted). No product defect.

### BM review

| Field | Value |
|---|---|
| Path | review after fixes (`/bm:code-review 86 --files=triggarr/search/engine.py,tests/test_refresh_counts.py,tests/test_malformed_records_client_path.py`) |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow file/step: `bm/5.0.3/workflows/code-review.md:spawn_reviewer` |
| Report location | `.planning/phases/86-pilot-reference-record/86-REVIEW-refresh-1062097a7676.md` |
| Status | complete (2 warning, 3 info, 1 set aside for a ruling) |

As at H1: `diff_base` was the merge-base; no catalog skill; the report was not committed to the pilot branch, so H_final stayed the tip.

### Codex

| Field | Value |
|---|---|
| Status | complete (trusted mode; `.status.json` complete, 0 findings, `inspected_head` = H_final) |
| Fallback | none |
| Attempts | 1 |
| Raw output paths | `codex/1062097a7676-pilot-refresh-final-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}` |
| Review complete | `review_complete: true`, `incomplete_reasons: []` (report schema v2) |
| Coverage | All three changed files including all test changes; non-object records traced through client pagination and all six refresh queues; nested objects, tags, integer keys, timezone-less dates, monitoring and release filters vs scheduled-cycle behavior; unresolved tags, retained counts, scoped stamps, recovery, backstops; refresh route locking, rate limiting, rendering, discarded return values; no CI/acceptance/audit/publication policy changes |
| Exclusions | Planning markdown other than changed `*-PLAN.md`, `.planning/**/*.jsonl`, generated review artifacts under `.planning/**/codex/**`; files outside the working copy |
| Commands run | 15, all exit 0 (as reported in `.last.json`) |
| Limitations | Pytest not rerun in the read-only sandbox (harness: 3281 passed, 1 skipped); no live services; "new real-client success tests assert missing eligibility but do not assert surviving cutoff contents or Sonarr cutoff counts" |

Findings: none (verdict `no-findings`).

### Greptile

did not run on this head (optional since 2026-10-22)

### CI

| Required check | Run ID | Result |
|---|---|---|
| CI ready (test, lint, secrets, actionlint, dependencies, docker, image-smoke, browser-e2e, os-scan) | 41158788891 | pass |
| CodeQL (Analyze python/actions/javascript-typescript) | 41158787037 | pass |
| Review acceptance | 41158788888 | pending (owner acceptance) |

Readiness (`acceptance-readiness.cjs --pr 54 --codex-out .planning/phases/86-pilot-reference-record/codex/1062097a7676-pilot-refresh-final-a1`): **Ready to request approval** (PR open, not draft, head matches, CI ready success, CodeQL success, Greptile did not run (optional), acceptance gate dry run ok with 0 Greptile findings, Codex complete). Register slices `54:1062097…` written empty for blockers and dispositions.

Local evidence: full suite at H_final: 3281 passed, 1 skipped. This was run three times: the 86-04 final-head gate with HEAD asserted, the vibe-check coverage run, and `codex/1062097a7676-pilot-refresh-final-a1.pytest.txt`. `ruff check triggarr/ tests/` is clean.

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:03182462100e:WR-01` | bm | `03182462100e9f71defc9408245410d2b99110a5` | fixed | regression test fails at H1, passes at H_final; vibe-check recheck resolved (architecture, bugs, impact); BM and Codex on H_final raise nothing on it | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:WR-01` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | Same issue as H1 `WR-02`, now with more examples: the returned cutoff list can hold records with a bad `id` or tags, or unmonitored ones. The approved H1 tally labelled it unproven, because the only caller (`routes.py`) discards the list. | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:WR-02` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | Design note: the refresh filter chains duplicate the cycle chains, and they drifted once (fixed in this PR). There is no current behavioral defect. Candidate backlog item: a shared per-app chain helper, or a parity test. | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:IN-01` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | same as H1 `IN-01` | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:IN-02` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | test gap; same family as H1 `IN-02` and vibe-check cov-002 | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:IN-03` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | docstring wording ("an other-unexpected-fault") | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `bm:1062097a7676:SA-01` | bm | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | decided (owner, D-02) | Skips are visible only in System Logs. This is the owner's recorded decision in 86-CONTEXT D-02: "No new dashboard warning." Nothing new to rule on. | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `vibe-check:1062097a7676:cov-001` | vibe-check | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | Sonarr missing-tag path untested; H1 proof test P3 passed for its case | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |
| `vibe-check:1062097a7676:cov-002` | vibe-check | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | nonblocking_debt | returned cutoff list not asserted; H1 proof test P4 passed for its case | `1062097a7676fddcdde3caf500f96ba1ea04d65c` |

### Incomplete items

- Greptile did not run (optional). Nothing else is incomplete for review.
- No new confirmed defect on H_final, so there is no owner fix-vs-debt decision under the Triage rule.

### Owner effort (D-12)

2 so far (PILOT-02 tally approval; push approval).

The first-head (H1 `0318246`) record and the PILOT-02 comparison are kept in the phase record (`86-REVIEW-EVIDENCE.md`, `86-PILOT-RECORD.md`). This comment covers the pushed head only.
````


## Durable copy: PR #55 checkpoint comment

Posted 2026-10-30 at https://github.com/thejuran/triggarr/pull/55#issuecomment-6537692830. The text below is exactly as posted.

````markdown
<!-- review-checkpoint head=46c39194249d1e7bcd2362a91d238d0997539f3f -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `46c39194249d1e7bcd2362a91d238d0997539f3f` (PR #55) |
| PR base SHA | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` (merge-base with origin/main) |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| Codex inspected base (`inspected_base_sha`) | `d5a4467a4c38f8f675fb057d9a77bcc3030c379d` |

Reconciliation: All fields match; no reconciliation needed.

### Classification

{"schema":1,"head":"46c39194249d1e7bcd2362a91d238d0997539f3f","classification":"code","classes_present":["code"],"rationale":"cycle_view() (triggarr/search/outcome.py) adds a structured kind/skip_count to each reason row and cycle_grade.html classifies by kind instead of display text; plus tests. Runtime code and a template; no agent instructions, workflows or policy.","supersedes_head":null}

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr, PR #55 (reviewed as a local checkpoint before the push; same head), head `46c39194249d1e7bcd2362a91d238d0997539f3f`, base `d5a4467a4c38f8f675fb057d9a77bcc3030c379d`. Whole-PR review: the card's reason rows are classified by a structured `kind` instead of display text, with no visible change intended (D-03).
- **Risk:** low. The worst realistic failure is a wrong summary label on the dashboard card ("Show N skipped records" instead of "Show N failure reasons"), or a template error if a malformed row ever lacked `skip_count`. Both construction sites set it, and a test enforces that. Nothing persisted changes, and search behavior is untouched.
- **Recommended review:** BM standard on the full PR, plus the paired Codex pass; routine vibe-check (code class).
- **Required evidence:** `cycle_view` dict tests pinning `kind`/`skip_count`; existing card rendering tests unchanged and passing; full suite and ruff at H1.
- **What this recommendation cannot establish:** browser rendering, and labels for tampered records outside what the application writes.

### Vibe-check (RISK-02)

- Risk below high: no additional vibe-check recommended.
- **Routine vibe-check status:** ran on this head (`/vibe-check:deep-review`, stock, range `d5a4467..46c3919`, pass 1); exact-head local coverage was prepared first and its provenance `check` passed. Report: `vibe-check/46c39194249d-card-routine.{md,json}`. Result: 1 Medium (no rendering test for the template switch), 3 sub-threshold; no product defect.

### BM review

| Field | Value |
|---|---|
| Path | explicit `/bm:code-review 86 --files=triggarr/search/outcome.py,triggarr/templates/partials/cycle_grade.html,tests/test_outcome.py,tests/test_app_cards.py` |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow file/step: `bm/5.0.3/workflows/code-review.md:spawn_reviewer` |
| Report location | `.planning/phases/86-pilot-reference-record/86-REVIEW-card-46c39194249d.md` |
| Status | complete (1 warning, 2 info, 1 set aside) |

As on the Refresh-counts PR: `diff_base` was the merge-base; no catalog skill was inserted; the report was not committed to the pilot branch, so H1 stayed the tip.

### Codex

| Field | Value |
|---|---|
| Status | complete (trusted mode; `.status.json` complete, 0 findings, `inspected_head` = H1) |
| Fallback | none |
| Attempts | 1 |
| Raw output paths | `codex/46c39194249d-pilot-card-a1.{prompt.txt,meta.json,last.json,status.json,pytest.txt}`; `.jsonl` withheld (see Withheld files below) |
| Review complete | `review_complete: true`, `incomplete_reasons: []` (report schema v2) |
| Coverage | All changes in the three files; all six reason-construction paths, count validation, legacy aggregate fallback, malformed state, truncation, ordering; persisted records traced through `cycle_view` into connected and unreachable card templates; existing rendering assertions; no persisted schema or shared state; escaping and policy |
| Exclusions | Planning markdown other than changed `*-PLAN.md`, planning JSONL, generated artifacts under `.planning/**/codex/**` |
| Commands run | 12, as reported in `.last.json` (exit codes 0 and 1; exit 1 = searches with no match) |
| Limitations | Pytest not rerun in the read-only sandbox (harness: 3271 passed, 1 skipped); "Existing rendering tests protect current labels but do not explicitly mutate display wording to prove classification remains independent of text"; no browser verification |

Findings: none (verdict `no-findings`).

### Greptile

did not run on this head (optional since 2026-10-22)

### CI

| Required check | Run ID | Result |
|---|---|---|
| CI ready (test, lint, secrets, actionlint, dependencies, docker, image-smoke, browser-e2e, os-scan) | 41158791610 | pass |
| CodeQL (Analyze python/actions/javascript-typescript) | 41158789982 | pass (the CodeQL summary check shows `skipping` on this head) |
| Review acceptance | 41158791675 | pending (not presented: after #54 merges this PR is integrated with main and re-reviewed, per 86-10) |

Readiness: not run for acceptance on this head. It will be behind main once #54 merges, so acceptance moves to the integrated head (86-10).

Local evidence: full suite at H1 3271 passed, 1 skipped (86-05 final-head gate with HEAD asserted; this plan's coverage run; `codex/46c39194249d-pilot-card-a1.pytest.txt`); `ruff check triggarr/ tests/` clean (86-05).

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:46c39194249d:WR-01` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (D-09: unproven; real test gap, no defect) | Reproduced: with the pre-change `cycle_grade.html` swapped into the H1 working tree (uncommitted, then restored), `tests/test_app_cards.py` + `tests/test_outcome.py` gave 148 passed. The new template behaves correctly. BM's example divergence needs a tampered record, for which the new label is the correct one. | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `bm:46c39194249d:IN-01` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | kind names are string literals in three places; no current mismatch (test enforces the closed set) | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `bm:46c39194249d:IN-02` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | test hardcodes `"malformed"` in its seen-set and has a redundant subset assert; legacy row checked directly elsewhere | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `bm:46c39194249d:SA-01` | bm | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven; predates this PR) | A tampered record can show both malformed rows and an "eligible not searched" row; records the app writes don't produce it. A candidate later-phase tightening. | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `vibe-check:46c39194249d:cov-001` | vibe-check | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | same gap as `bm:…:WR-01`; same reproduction | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| `vibe-check:46c39194249d:arch-001`, `cov-002`, `cov-003` (sub-threshold) | vibe-check | `46c39194249d1e7bcd2362a91d238d0997539f3f` | nonblocking_debt (unproven) | arch-001 = BM IN-01; cov-003 = BM IN-02; cov-002 guard paths predate this PR | `46c39194249d1e7bcd2362a91d238d0997539f3f` |

D-09 tally for this head: confirmed 0, false positive 0, unproven 5 BM-side (WR-01, IN-01, IN-02, SA-01; Codex 0) and 4 vibe-check-side (cov-001 reported; arch-001, cov-002, cov-003 filtered).

### Incomplete items

- Greptile did not run (optional). Nothing else is incomplete for review.

### Owner effort (D-12)

1 so far (push approval).
````

## PR #54 acceptance

- Owner approval, quoted word for word (2026-10-30): "Approve review acceptance for PR #54 at 1062097a7676fddcdde3caf500f96ba1ea04d65c, run 41158788888."
- Register slices `54:1062097a7676fddcdde3caf500f96ba1ea04d65c` were written (blockers `{"open":[]}`, dispositions `{"items":{}}`) and verified by read-back.
- Attempt 1 of run 41158788888 was created before the register write, so it was cancelled and re-run. The owner approved attempt 2.
- Step 5 recheck immediately before submission: head unchanged, run waiting on attempt 2, `review-acceptance` pending with `current_user_can_approve` true, readiness "Ready to request approval", main unchanged at `d5a4467`.
- Submitted via the pending-deployments endpoint (environment `review-acceptance`; deployment 7452918282 for sha `1062097…`). Review acceptance run 41158788888 attempt 2 completed with **success**. PR merge state is CLEAN.

Merged: b80c3e26cf9456dde7245350d7033f6feb94db0f (by owner)

- Merged 2026-11-14T03:23:00Z (2026-11-13 local) as a merge commit, matching the repository's earlier PR merges. Main moved from `d5a4467` to `b80c3e2`.
- How it was merged: the owner instructed "merge pr 54" in the Claude CLI session, and Claude ran the merge under the owner's GitHub account, pinned to the accepted head (`--match-head-commit 1062097a7676fddcdde3caf500f96ba1ea04d65c`). This differs from the plan, which had the owner run the merge personally (T-86-22). The decision to merge was the owner's.
- Recheck immediately before the merge: head unchanged at `1062097…`, all 15 checks passing including Review acceptance (run 41158788888 attempt 2), merge state CLEAN, main unchanged at `d5a4467`.
- PR #55 was not presented for acceptance. It is open at `46c39194249d1e7bcd2362a91d238d0997539f3f` and now behind main; 86-10 integrates it and gathers fresh exact-head evidence.
