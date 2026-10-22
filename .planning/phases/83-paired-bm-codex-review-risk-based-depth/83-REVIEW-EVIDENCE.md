# Phase 83 — Review evidence

Durable record of each Phase 83 review checkpoint (D-10, D-11), written one
section per head SHA per `docs/review-checkpoint-record.md`'s template.
`83-DEMONSTRATIONS.md` is the companion document for the negative-case
demonstration (D-17) and the phase's other checkpoint demonstrations; this
file holds the per-head evidence record itself.

## Quick-task path — head a7995baf187e

<!-- review-checkpoint head=a7995baf187e0e96c3f8152212060cedfc7fd921 -->

Demonstrates REVIEW-02/REVIEW-05 on real work: quick task `261022-l7h`
("Fix card reasons label for skip-only rows"), owner-approved per
`83-QUICK-PROPOSAL.md`'s "Owner decision" (2026-10-22 15:15 EDT).

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `a7995baf187e0e96c3f8152212060cedfc7fd921` |
| PR base SHA | `98c2dc68ff3bf6520bb7c3986140749d288d299f` |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `a7995baf187e0e96c3f8152212060cedfc7fd921` |
| Codex inspected base (`inspected_base_sha`) | `98c2dc68ff3bf6520bb7c3986140749d288d299f` |

Reconciliation: no PR exists yet for this checkpoint (per the contract,
Codex's `PR_URL` placeholder was filled with the literal text
`"none (local checkpoint, not pushed)"`); "PR head/base SHA" above are
this quick task's own `HEAD_SHA`
(its last commit, `a7995ba`) and `BASE_SHA` (the parent of its first commit
`3c78f6c`, per the Invocation step 1 rule for a local checkpoint). All
fields match: `git rev-parse HEAD` equals the recorded head, `git
rev-parse 3c78f6c^` equals the recorded base, and Codex's own
`inspected_head_sha`/`inspected_base_sha` in `.last.json` equal both. No
discrepancy to reconcile.

### Classification

```json
{"schema":1,"head":"a7995baf187e0e96c3f8152212060cedfc7fd921","classification":"code","classes_present":["code","ordinary-docs"],"rationale":"git diff 98c2dc6..a7995ba touches tests/test_app_cards.py and triggarr/templates/partials/cycle_grade.html (application code and tests) alongside .planning/quick/261022-l7h-fix-card-reasons-label-for-skip-only-row/** quick-task artifacts and a .planning/STATE.md quick-task-table row (ordinary-docs/planning). No agent instructions, workflows, hooks, permissions, acceptance/release policy or operational procedures were touched. Per the mixed-changes rule, code is the more consequential class present, so this checkpoint is classified code.","supersedes_head":null}
```

### Risk note (RISK-01)

- **Scope:** local checkpoint only (not yet on a PR -- the code rides in the
  Phase 83 PR prepared in Plan 10). Covers the full quick-task diff
  `98c2dc68ff3bf6520bb7c3986140749d288d299f..a7995baf187e0e96c3f8152212060cedfc7fd921`
  in its entirety, not a follow-up diff: `tests/test_app_cards.py` and
  `triggarr/templates/partials/cycle_grade.html`, plus the quick task's own
  `.planning/quick/**` artifacts and a `.planning/STATE.md` row. Affected
  behavior: the dashboard card's expandable detail-label wording for
  Partial/Failed cycles whose only detail rows are skip-only or
  unevaluated-only; no search/scheduling logic was touched.
- **Risk:** low — a presentation-only text change, covered by 10 new
  regression tests (84/84 in `tests/test_app_cards.py`, 2215/2215 full
  suite) and traced end-to-end from `CycleTally` through `cycle_view()` to
  the template, independently by the quick task's own verifier, by the
  paired Codex pass, and by this plan's own fresh run (below). The two
  reproducible issues found (see Dispositions) both require an
  already-corrupted or hand-tampered `state.json` to trigger, not the
  normal `CycleTally.record_malformed` write path — worst case is a
  cosmetic dashboard mislabel, not a data-integrity or security issue.
- **Recommended review:** quick depth (the only depth BM's quick-task path
  supports, hardcoded) was adequate for this change's actual risk. The
  batched Plan 09 fix for WR-01/WR-02 touches `outcome.py`'s read-side
  grading function directly and should get at least `standard` depth plus
  its own fresh, paired Codex pass on the new head (REVIEW-06) — not quick.
- **Required evidence:** already satisfied for this checkpoint by the 10
  new targeted regression tests, the full suite (2215/2215), and clean
  ruff. For the Plan 09 fix: new regression tests reproducing the WR-01
  truncation case and the WR-02 `malformed_skipped`/`malformed_by_queue`
  disagreement case, plus a fresh BM review and fresh Codex pass on the new
  head.
- **What this recommendation cannot establish:** that `outcome.py`'s row
  wording will never change in a way that silently reintroduces the
  original bug through the template's text-sniffing (that is WR-01's own
  architectural concern, not resolved by this review and not resolved
  until Plan 09's structural fix lands); live browser/htmx rendering
  (Codex and this plan both verified text only, never a running browser);
  or that a production `state.json` will ever actually reach the
  `malformed_skipped`/`malformed_by_queue` disagreement outside of a
  hand-tampered file or a future write-path bug.

### Vibe-check (RISK-02)

Risk below high: no additional vibe-check recommended.

- **Routine vibe-check status:** not run. This is a local, unpushed
  checkpoint; the owner's standing vibe-check rule (CLAUDE.md's "Deep Code
  Review Convention") is keyed to pushing/tagging, and this quick task's
  code rides in the Phase 83 PR prepared in Plan 10, where vibe-check is
  offered before that push.

### BM review

| Field | Value |
|---|---|
| Path | quick task |
| Requested depth | `standard` (`.planning/config.json` key `workflow.code_review_depth`) |
| Actual depth | `quick` (disclosed even though it differs from requested) |
| Large-scope warning | not printed (2 files reviewed; below any large-scope threshold) |
| Responsible files | `.planning/config.json` key `workflow.code_review_depth` (the requested setting; not read by this path) and `~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/quick.md` Step 6.25 "Code review (auto)" (actual depth hardcoded to `quick` on this path, line 929's literal `Depth: quick`; `$FULL_MODE` is the gate for whether the step runs at all, line 890 — per `docs/bm-review-baseline-2026-10-22.md`'s installed-behavior re-check) |
| Report location | `.planning/quick/261022-l7h-fix-card-reasons-label-for-skip-only-row/261022-l7h-REVIEW.md` |
| Status | complete |

### Codex

| Field | Value |
|---|---|
| Status | complete (checker result; see Incomplete items below for the report's own disclosed verification gap) |
| Attempts | 1 |
| Raw output paths | `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/a7995baf187e-quick-a1.jsonl`, `.last.json`, `.status.json` |
| Coverage | all nine changed files (recovering truncated output via targeted reads); traced `CycleTally.to_record` → `cycle_view` → `_build_app_context` → `partial_app_card` → `app_card.html` → `cycle_grade.html`; checked singular/plural wording, record-vs-row counts, legacy aggregate records, mixed failures/skips, unevaluated queues, eligible-but-unsearched work, and fetch failures; executed the 10 added tests' assertions in-memory against the real `cycle_view()` and Jinja template (HEAD: 10 passed; base: 3 passed, 7 failed — matching the quick task's own RED/GREEN claim); executed 96 generated `CycleTally` combinations; reviewed refresh/stale-state and security/policy implications (autoescaping intact, no CI/acceptance/publication config changed) |
| Exclusions | live browser/htmx interaction and external *arr services; full repository test suite and lint execution (blocked by the read-only sandbox — see Incomplete items); hypothetical future wording changes and manually-inconsistent persisted counters, not treated as demonstrated production defects |
| Commands run | 19 commands recorded in `.last.json`'s `commands_run`, each with its own exit code and purpose — `git rev-parse HEAD` (0), `git cat-file -e <base>` (0), repository/template/test reads (0), an `rg`/`.venv` probe that found no local `.venv` (exit 1, external interpreter found instead), the route-level pytest attempt blocked before collection by the read-only sandbox (exit 1), a rejected heredoc attempt (exit 1), and the successful in-memory assertion harness and 96-combination matrix (0) |
| Limitations | see Incomplete items below |

Findings: No findings (verdict: `no-findings`, 0 entries in `.last.json`'s `findings` array).

### Greptile

not run (local checkpoint)

### CI

not run (local checkpoint)

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:a7995baf187e:WR-01` | bm | `a7995baf187e0e96c3f8152212060cedfc7fd921` | confirmed_defect — carried to Plan 09 | Code read confirms the duplicated classification: `cycle_grade.html:20-26`'s prefix/suffix text match re-derives the exact wording `outcome.py:291,303-305,311-313` already produces server-side, with no structural "kind" field passed through today. The truncation sub-claim was independently reproduced: a persisted record with `malformed_by_queue={"missing": 10**110}` (and matching `malformed_skipped`) composes a row text whose length exceeds `outcome.py`'s 120-char `_truncate()` limit; the truncated text no longer ends in `"— malformed data"`, so the template's suffix check buckets the row as `other` and the card renders `"Show 1 failure reason"` instead of a skipped-record label (reproduced via a route-level `TestClient` request built on the test module's own `_last_cycle_record` fixture; disposable scratch script, not committed). This trigger requires a `malformed_by_queue` count on the order of 10^108+, unreachable through `CycleTally.record_malformed`'s normal int-increment write path (`outcome.py:125-136`) — confirmed only via a directly-constructed/tampered record, the same trust boundary as WR-02. | N/A (not fixed in this plan) |
| `bm:a7995baf187e:WR-02` | bm | `a7995baf187e0e96c3f8152212060cedfc7fd921` | confirmed_defect — carried to Plan 09 | Reproduced directly: a persisted record with `malformed_by_queue={"missing": 2}` but `malformed_skipped=0` — a combination `to_record()`'s write path (`outcome.py:176`, which always derives `malformed_skipped = sum(malformed_by_queue.values())`) can never produce, but which `cycle_view()`'s read path (`outcome.py:249` and `294-307`) reads as two independent fields with no cross-validation — renders the card as `"Partial · 1 accepted, 0 failed"` with summary text `"Show 1 failure reason"` instead of `"Show 2 skipped records"`: the exact pre-fix bug this quick task closed, reintroduced via a different, read-side trigger (reproduced via a route-level `TestClient` request; disposable scratch script, not committed). | N/A (not fixed in this plan) |
| `bm:a7995baf187e:IN-01` | bm | `a7995baf187e0e96c3f8152212060cedfc7fd921` | nonblocking_debt | Confirmed by direct code read, no reproduction needed: `outcome.py:259-260` unconditionally appends a fetch-failure row whenever `fetch_failed` is true, and that row's text (`"Couldn't reach {app_label} ({fetch_error})"`) matches neither the unevaluated prefix nor the malformed suffix, so it always lands in `cycle_grade.html`'s `other` bucket, forcing `ns.other >= 1`. The explicit `not app.last_cycle.fetch_failed` conjunct in `no_failure` (`cycle_grade.html:28`) is therefore always implied by `ns.other == 0` under every reachable record — matches the reviewer's own characterization, "not a bug — harmless belt-and-suspenders." Subsumed by WR-01's fix; no standalone action needed. | N/A (no fix required) |

### Incomplete items

- Codex's own report discloses its verification as incomplete in a way the
  checker's structural "complete" status does not capture: route-level
  pytest execution (`tests/test_app_cards.py`) was blocked before
  collection by Codex's read-only sandbox ("no writable temporary directory
  exists"). Codex substituted an in-memory execution of the 10 added
  tests' assertions directly against `cycle_view()` and the real Jinja
  template (HEAD: 10/10 passed; base: 3 passed/7 failed, matching the
  quick task's own RED/GREEN claim) plus 96 generated `CycleTally`
  combinations, and states this "does not validate routing, database
  fixtures, or browser behavior." The checker (`tests/codex_report_status.py`)
  reports status `complete` because the report's head/base/schema all
  reconcile correctly — that word means the report is current,
  well-formed and bound to the right commit, not that a full pytest run
  happened inside Codex's sandbox. This plan closed that specific gap for
  this record by independently running the full suite itself outside
  Codex's sandbox: `uv run pytest tests/ -x -q` → 2215 passed; `uv run ruff
  check triggarr/ tests/` → all checks passed.
- Codex also notes that the existing SUMMARY/VERIFICATION reports' claims
  of "84 card tests" and "2215 total tests passing" were not independently
  reproduced or accepted by Codex as evidence — addressed by this plan's
  own fresh run above, which reproduces both counts exactly.
- No other incomplete items.

This record is not owner acceptance.
