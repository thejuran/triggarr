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

## Explicit /bm:code-review path — head d501a68316b2

<!-- review-checkpoint head=d501a68316b2c3a032634741f8c73d373870e9f2 -->

Demonstrates REVIEW-02/REVIEW-04/REVIEW-05 on a real, explicit
`/bm:code-review 83` run (no `--depth` flag) paired with an independent
Codex pass on the same frozen commit: the full Phase 83 diff to date, not
the quick task's narrower sub-diff.

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `d501a68316b2c3a032634741f8c73d373870e9f2` |
| PR base SHA | `6f3841aaae4f2511efe6796f7f5c7ad50b423f90` |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `d501a68316b2c3a032634741f8c73d373870e9f2` |
| Codex inspected base (`inspected_base_sha`) | `6f3841aaae4f2511efe6796f7f5c7ad50b423f90` |

Reconciliation: no PR exists yet (per the contract, Codex's `PR_URL`
placeholder was filled with the literal text `"none (local checkpoint,
not pushed)"`); "PR head/base SHA" above are this checkpoint's own
`HEAD_SHA` (`git rev-parse HEAD`) and `BASE_SHA` (`git merge-base
origin/main HEAD`, phase scope per the Invocation step 1 rule for a local
checkpoint). All fields match: `git rev-parse HEAD` equals the recorded
head, `git merge-base origin/main HEAD` equals the recorded base, and
Codex's own `inspected_head_sha`/`inspected_base_sha` in `.last.json`
equal both. No discrepancy to reconcile.

### Classification

```json
{"schema":1,"head":"d501a68316b2c3a032634741f8c73d373870e9f2","classification":"sensitive","classes_present":["sensitive","code"],"rationale":"git diff 6f3841aa..d501a683 (BASE_SHA..HEAD_SHA, the full phase scope, not a follow-up diff) touches CLAUDE.md (commit 719359a) and docs/owner-cli-acceptance.md (sensitive: agent instructions and acceptance policy), plus docs/codex-adversarial-review-contract.md, docs/review-checkpoint-record.md, docs/review-classification-policy.md and docs/bm-review-baseline-2026-10-22.md (sensitive: operational review-procedure documents), alongside application code and tests classified code (tests/codex_report_status.py, tests/test_app_cards.py, tests/test_codex_report_status.py, tests/test_codex_review_contract.py, tests/test_review_instructions.py, triggarr/templates/partials/cycle_grade.html, .claude/schemas/codex-review-findings.schema.json). Per the owner's 2026-10-22 WR-04 ruling (\"Apply both\"), a PR containing both classes gets every review either class requires, so both classes are recorded present and neither's required review is diluted; classification is recorded as the more consequential single label (sensitive) per D-18's classify-upward rule. Supersedes the quick-task-scoped head a7995baf187e, whose record covered only that sub-diff and was classified code alone.","supersedes_head":"a7995baf187e0e96c3f8152212060cedfc7fd921"}
```

### Risk note (RISK-01)

- **Scope:** local checkpoint only (not yet on a PR -- the code rides in
  the Phase 83 PR prepared in Plan 10). Covers the full phase diff
  `6f3841aaae4f2511efe6796f7f5c7ad50b423f90..d501a68316b2c3a032634741f8c73d373870e9f2`
  (14 real files outside `.planning/`, the whole phase to date), not a
  follow-up diff. Affected behavior: the Codex-report completeness
  checker (`tests/codex_report_status.py`) and its schema, the
  checkpoint-record/classification/contract documentation, `CLAUDE.md`'s
  review wiring, and the (already-queued) dashboard card template.
- **Risk:** moderate — two critical-severity gaps (CR-01, CR-02; CR-01
  cross-confirmed by Codex's F001) mean the one module whose entire job
  is "never let a malformed Codex report count as a clean review" fails
  open on several malformed inputs (null or wrong-typed required fields,
  a non-string finding `id`, contradictory `verdict`/`findings`,
  whitespace-only `hypothesis`, boolean integers). In the normal path
  Codex's own `--output-schema` constrains output shape, so this is
  unlikely to trigger from a real Codex run; it is the fallback gate for
  a hand-edited, truncated, or future-tooling-produced report, and today
  it would wrongly certify such a report "complete." No production
  application security boundary is affected — this is audit tooling. The
  CLI (WR-02) also crashes with a traceback instead of reporting a
  plain-language reason on a non-UTF-8 or directory report path. The
  documented re-review/update procedure has two reproduced gaps (WR-03's
  stale "no history" claim; Codex's F002, an invalid `gh api` field
  syntax) that would confuse or block someone who follows the docs
  verbatim during a future re-review.
- **Recommended review:** `standard` depth (what ran) was adequate to
  surface these findings. The batched Plan 09 fix — covering the checker
  (CR-01, CR-02, WR-01, WR-02, IN-03, IN-04, IN-05, and Codex F001/F002),
  the review-process docs (WR-03, WR-04, WR-05, IN-06), and the dashboard
  card (carried from Plan 07, reconfirmed here as IN-01/IN-02/SA-01) —
  touches security-adjacent audit tooling and the review process itself,
  and should get at least `standard` depth plus its own fresh, paired
  Codex pass on the new head (REVIEW-06), not quick.
- **Required evidence:** for Plan 09: new parametrized negative tests for
  every malformed-input case reproduced in this record (null/wrong-type
  required fields, non-string `id`, `verdict`/`findings` mismatch,
  non-UTF-8/directory report path, `--attempt <= 0`, whitespace
  `hypothesis`, boolean ints), replacing IN-03's tautological test with
  one that actually asserts `status == "incomplete"` on each; a fresh BM
  review and a fresh Codex pass on the new head.
- **What this recommendation cannot establish:** that a real Codex run
  will ever actually emit one of these malformed shapes (the
  `--output-schema` flag should prevent most of them at the source); that
  fixing the checker for the cases enumerated here closes every possible
  malformed-report shape, only the ones demonstrated; live GitHub comment
  behavior for the corrected `gh api` command (not run against a real PR
  in this plan — F002 was reproduced only as a local argument-parsing
  failure).

### Vibe-check (RISK-02)

Risk below high: no additional vibe-check recommended.

- **Routine vibe-check status:** not run. This is a local, unpushed
  checkpoint; the owner's standing vibe-check rule (CLAUDE.md's "Deep
  Code Review Convention") is keyed to pushing/tagging, and this
  checkpoint's code rides in the Phase 83 PR prepared in Plan 10, where
  vibe-check is offered before that push.

### BM review

| Field | Value |
|---|---|
| Path | explicit `/bm:code-review` (`/bm:code-review 83`, no `--depth` flag) |
| Requested depth | `standard` (`.planning/config.json` key `workflow.code_review_depth`) |
| Actual depth | `standard` (matches requested; disclosed per REVIEW-05's rule even when they agree) |
| Large-scope warning | not printed (12 files reviewed; below the `-gt 50` downgrade threshold) |
| Responsible files | `.planning/config.json` key `workflow.code_review_depth` (consumed on this path — contrast with the quick-task path, which ignores it per `docs/bm-review-baseline-2026-10-22.md`); BM workflow file/steps: `~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/code-review.md` step `resolve_depth` (priority `--depth` flag > config value > default `standard`) and step `compute_file_scope` (the `SUMMARY.md`-derived 12-file list) |
| Report location | `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW.md` |
| Status | `issues_found` (BM's own frontmatter status value — the review ran to completion and reported findings; not an incomplete or skipped run) |

No downgrade occurred; downgrade handling is documented in
`docs/review-checkpoint-record.md` and was not exercised (12 files is
well under the 50-file threshold).

**Scoping quirk (recorded, not fixed in this plan):** BM's file scope is
read from `83-SUMMARY.md` key-files entries and skips any path with no
`/` in it. `CLAUDE.md` and `docs/owner-cli-acceptance.md` both changed in
`BASE_SHA..HEAD_SHA` (`git diff --name-only` lists 14 files outside
`.planning/`) but are missing from BM's 12-file list — `CLAUDE.md` has no
`/`, and `docs/owner-cli-acceptance.md` was changed by a commit
(`f5fa98d`) outside this plan's own SUMMARY entries. BM's own reviewer
caught this gap and raised it as SA-02 (see Dispositions below); the
paired Codex pass in this record independently covered both files (its
`commands_run` includes direct reads and diffs of `CLAUDE.md` and
`docs/owner-cli-acceptance.md`), closing the gap for this specific head.

**Craft-skill record:** `craft-skill.match` proposed the catalog's
`code-reviewer` entry (`github.com/Jeffallan/claude-skills` pinned at
`1be15d8064f88fc25216442406d40add8fd23b53`, MIT, trust tier A, allow) for
`bm-code-reviewer` ahead of this review's reviewer spawn. The owner
answered "Accept sticky (persist for bm-code-reviewer)." It was **not**
inserted: no local checkout exists at the pinned commit, and BM's
procedure fetches nothing on its own —
`craft-skill: candidate code-reviewer not inserted (no checkout at pin);
review manually`. A sticky insert would also be a BM settings change
outside the two keys `docs/bm-review-baseline-2026-10-22.md` approved
(`workflow.code_review`, `workflow.code_review_depth`), and would require
separately cloning third-party code at the pin plus its own owner
approval. This review ran with BM's default reviewer, not the
catalog skill.

### Codex

| Field | Value |
|---|---|
| Status | complete (checker result — two reproduced findings present; see Incomplete items below for the report's own disclosed verification gaps, which the checker's "complete" word does not capture) |
| Attempts | 1 |
| Raw output paths | `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.jsonl`, `.last.json`, `.status.json` |
| Coverage | 8 entries in `.last.json`'s `coverage` array: confirmed requested HEAD/base existence and a clean working tree; reviewed the checker, schema, associated tests, the fixed review contract, checkpoint procedure, classification policy, and configuration/acceptance-instruction changes; traced card rendering `CycleTally.to_record` → `cycle_view` → `_build_app_context` → `partial_app_card` → `app_card.html` → `cycle_grade.html`; ran 39 checker/schema/instruction tests (passed, two file-backed CLI tests deselected); executed all 10 added card tests plus one existing test through the real router/templates in-memory (11 passed); ran the same 10 tests against the base template (7 failed, 3 passed, matching the quick task's own RED/GREEN claim); checked missing/failed/stale/wrong-head/malformed report handling, legacy records, mixed failures/skips, unevaluated queues, template escaping, and acceptance-boundary preservation; `git diff --check` passed |
| Exclusions | 3 entries: exhaustive inspection of archived Codex JSONL content and all ancillary planning/research/summary text (several large reads were truncated); live browser/htmx behavior, external *arr services, Docker execution, hosted CI and GitHub protection verification; independent verification of historical BM-installation, owner-decision and test-run claims recorded in documents |
| Commands run | 29 commands recorded in `.last.json`'s `commands_run`, each with its own exit code and purpose — 27 exited 0; 2 exited 1 by design/demonstration (the targeted-suite pytest attempt blocked before collection because the read-only sandbox has no writable temp directory, and the reproduction of the documented `gh api --field body@FILE` command, which is F002 itself) |
| Limitations | see Incomplete items below (5 entries, quoted verbatim) |

Findings:

| Qualified ID | Severity | Location | Reproduced / hypothesis | Title |
|---|---|---|---|---|
| `codex:d501a68316b2:a1:F001` | high | `tests/codex_report_status.py:61-80` | reproduced | Schema-invalid reports are accepted as complete reviews |
| `codex:d501a68316b2:a1:F002` | medium | `docs/review-checkpoint-record.md:16` | reproduced | Checkpoint comment update command has invalid field syntax |

### REVIEW-04 field-completeness table

All 12 top-level schema fields are present in `.last.json`
(`python3 -c "import json; d=json.load(open('…last.json')); print(len(d))"` → `12`, matching `.claude/schemas/codex-review-findings.schema.json`'s `required` list exactly):

| Field | Value / count found |
|---|---|
| `schema_version` | `"1"` |
| `inspected_head_sha` | `d501a68316b2c3a032634741f8c73d373870e9f2` (matches `HEAD_SHA`) |
| `inspected_base_sha` | `6f3841aaae4f2511efe6796f7f5c7ad50b423f90` (matches `BASE_SHA`) |
| `pr_url` | `"none (local checkpoint, not pushed)"` |
| `scope` | `"Phase 83 changes: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90..d501a68316b2c3a032634741f8c73d373870e9f2"` |
| `verdict` | `"findings"` |
| `summary` | present (1 string, 2 sentences, discloses the review is incomplete) |
| `coverage` | 8 entries |
| `exclusions` | 3 entries |
| `commands_run` | 29 entries, each with `command`/`exit_code`/`purpose` |
| `findings` | 2 entries (F001 high, F002 medium) |
| `limitations` | 5 entries |

Requested depth and actual depth appear as separate fields in the BM
review table above (both `standard`).

### Greptile

not run (local checkpoint)

### CI

not run (local checkpoint)

### Dispositions

Reproduction method: a scratch script
(`tests/codex_report_status.py`'s own `assess_report`/`_load_schema`,
invoked via `runpy.run_path`, never modified) was run against mutated
copies of a minimally-valid report for the checker-level findings; the
CLI entry point (`uv run python tests/codex_report_status.py ...`) was
run directly against a non-UTF-8 file and a directory path for WR-02;
`gh api --method PATCH ... --field body@FILE` was run directly (no
comment existed to change) for F002. All scratch inputs stayed in the
session scratchpad; none was committed. No source or test file was
edited.

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:d501a68316b2:CR-01` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — carried to Plan 09 batched fix | Reproduced every mutation in the review's own table: `findings: null`, `findings: "none"`, `coverage: null`, `coverage: "all"`, `schema_version: "2"`, and `summary: 5` on an otherwise-valid report each returned `status=complete, finding_count=0, reasons=()`. Cross-confirms `codex:d501a68316b2:a1:F001` (same root cause, same file/line range). | N/A (not fixed in this plan) |
| `bm:d501a68316b2:CR-02` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — carried to Plan 09 batched fix (same fix as CR-01 per the review's own note) | Reproduced: a report with `findings[0]["id"] = 7` (int) alongside a valid string-ID finding returned `status=complete, finding_count=2, qualified_ids=('codex:aaaaaaaaaaaa:a1:F002',)` — exactly one qualified ID for two counted findings, matching the review's claim precisely. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:WR-01` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — carried to Plan 09 batched fix | Reproduced both directions: `verdict: "no-findings"` with 2 findings present, and `verdict: "findings"` with `findings: []`, both returned `status=complete, reasons=()`. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:WR-02` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — carried to Plan 09 batched fix | Reproduced both sub-claims directly against the real CLI: a 2-byte non-UTF-8 file (`\xff\xfe`) raised `UnicodeDecodeError`, and a directory path raised `IsADirectoryError`; both exited the process with a Python traceback and exit code 1, no JSON `status`/`reasons` payload printed. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:WR-03` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect (documentation inaccuracy) — carried to Plan 09 batched fix | Confirmed by direct read, no reproduction needed: `docs/review-checkpoint-record.md:131` says BM's `--fix --auto` re-review "has no built-in history," but the installed `~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/code-review-fix.md:270-272` contains the exact `cp "${REVIEW_PATH}" "${REVIEW_PATH%.md}.iter${ITERATION}.md"` backup-before-overwrite step, matching `docs/bm-review-baseline-2026-10-22.md`'s own citations. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:WR-04` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | **owner ruling received (2026-10-22): "Apply both"** — a PR with both `sensitive` and `code` present gets every review either class requires (code's routine vibe-check/CI while still required, plus sensitive's RISK-01/RISK-02 risk assessment). Disposition: policy-wording fix carried to Plan 09 batched fix. | `docs/review-classification-policy.md:15-19,41` confirmed by direct read to lack an explicit ranking rule between `sensitive` and `code`, exactly as the review describes; this record's own Classification section above already applies the owner's ruling in practice (classes_present lists both, review conducted satisfies the union). | N/A (not fixed in this plan) |
| `bm:d501a68316b2:WR-05` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect (process gap) — carried to Plan 09 batched fix | Confirmed by direct read: `docs/codex-adversarial-review-contract.md:46-52` force-adds (`git add -f`) the full unedited `.jsonl` stream to the public repo with pattern-based `gitleaks` as the only safeguard; the fixed prompt (lines 15-31) contains no instruction to avoid reading files outside the detached worktree or any credential/config file. `CLAUDE.md:29` ("No API keys in logs") is the standing rule this gap could violate. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:IN-01` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | duplicate of already-confirmed `bm:a7995baf187e:WR-01` (same unchanged code: `git log a7995baf187e..d501a68316b2 -- triggarr/templates/partials/cycle_grade.html triggarr/search/outcome.py` is empty) — nonblocking_debt, already carried to Plan 09 | This run's reviewer re-found the same text-matching coupling at a lower severity (info vs the earlier warning) but it is the identical code and the identical underlying gap already triaged in `83-REVIEW-EVIDENCE.md`'s "Quick-task path" section. No new reproduction needed; cross-referenced rather than re-triaged as new. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:IN-02` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | duplicate of already-confirmed `bm:a7995baf187e:WR-02` (same unchanged code) — confirmed_defect, already carried to Plan 09 | Identical claim to the already-reproduced `malformed_by_queue`/`malformed_skipped` disagreement (`{"missing": 2}` vs `0`) that renders `"Show 1 failure reason"` instead of a skipped-record label; same file, same lines, same unchanged code since the prior head. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:IN-03` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect (test-quality gap) — nonblocking_debt, carried to Plan 09 batched fix | Confirmed by direct read: `tests/test_codex_report_status.py:319-339`'s `test_never_reports_clean` only asserts the literal substring `"clean"` never appears in `status + " " + reasons`; no code path in `assess_report` can emit that word, so the test cannot fail on the real regression CR-01 demonstrates. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:IN-04` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — nonblocking_debt, carried to Plan 09 batched fix | Reproduced: `--attempt 0` produced qualified ID `codex:aaaaaaaaaaaa:a0:F001`; `--attempt -3` produced `codex:aaaaaaaaaaaa:a-3:F001`; both exited 0 with `status: complete`, neither rejected by argparse. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:IN-05` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — carried to Plan 09 batched fix (same fix family as CR-01) | Reproduced both sub-claims: a finding with `hypothesis: "   "` (3 spaces) and `reproduced: false` passed with no reason recorded; a finding with `line_start: true` (bool) passed the integer check (`isinstance(True, int)` is `True` in Python). | N/A (not fixed in this plan) |
| `bm:d501a68316b2:IN-06` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect (documentation gap) — nonblocking_debt, carried to Plan 09 batched fix | Confirmed by direct read: `docs/codex-adversarial-review-contract.md:56` allows an owner-approved third attempt after attempt 2 is also incomplete ("retry later"), but `docs/review-checkpoint-record.md:86`'s template row literally reads `Attempts \| 1 \| 2`, with no guidance for a third. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:SA-01` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | **owner ruling received (2026-10-22): "Failure wording on red cards"** — red Failed-grade cards always say "failure reason(s)"; the neutral "details" label applies only on Partial/Success cards. Disposition: confirmed_change, carried to Plan 09 batched fix. | Confirmed by direct code read: `cycle_grade.html:28,30-31` ties the neutral "detail(s)" label only to `no_failure` (which requires `app.last_cycle.failed == 0`), so a red Failed-grade card whose only rows are unevaluated queues can render the neutral label today, exactly as SA-01 described — the fix narrows that branch to exclude `grade == 'failed'`. | N/A (not fixed in this plan) |
| `bm:d501a68316b2:SA-02` | bm | `d501a68316b2c3a032634741f8c73d373870e9f2` | nonblocking_debt — resolved for this head by the paired Codex pass; BM's own scope-computation gap is recorded, not fixed, in this plan | `CLAUDE.md` and `docs/owner-cli-acceptance.md` were outside BM's 12-file scope (the scoping quirk above) but were both directly read and diffed by Codex's pass per `.last.json`'s `commands_run` (e.g. `cat CLAUDE.md docs/owner-cli-acceptance.md`, `git diff 6f3841aa..d501a68 -- CLAUDE.md docs/owner-cli-acceptance.md docs/buildomator-greptile-pilot.md .planning/config.json`), so this specific head's review is not missing those files in substance — only BM's own file-listing step missed them, which is the scoping quirk already recorded above rather than a fresh defect in the reviewed product. | N/A (not fixed in this plan) |
| `codex:d501a68316b2:a1:F001` | codex | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect — cross-confirms `bm:d501a68316b2:CR-01` (same root cause, same file/lines); carried to Plan 09 batched fix | Reproduced with Codex's own `reproduction_command` (`python -c '...assess_report(...)'` against an all-null required-fields report): `Assessment(status='complete', reasons=(), qualified_ids=(), finding_count=0, ...)`, matching `.last.json`'s evidence field exactly. | N/A (not fixed in this plan) |
| `codex:d501a68316b2:a1:F002` | codex | `d501a68316b2c3a032634741f8c73d373870e9f2` | confirmed_defect (new finding, not raised by BM) — carried to Plan 09 batched fix | Reproduced with Codex's own `reproduction_command`: `gh api --method PATCH repos/thejuran/triggarr/issues/comments/ID --field body@FILE` exited 1 with `invalid key: "body@FILE"` — no comment existed to change, matching `.last.json`'s evidence exactly. | N/A (not fixed in this plan) |

### Incomplete items

- Codex's own report discloses, verbatim, that this is **not** a clean
  approval: `.last.json`'s `limitations` array (5 entries, quoted in
  full) —
  1. "This is an incomplete review, not a clean approval: full-diff
     output and several recovery reads were truncated, leaving some
     planning/transcript content uninspected."
  2. "The initial pytest command failed before collection because
     read-only execution provides no writable temporary directory. The
     subsequent 39-test run deliberately excluded two temporary-file CLI
     tests."
  3. "Card assertions ran with an alternate in-memory application setup;
     the original SQLite/tmp_path fixtures and the full repository suite
     were not executed."
  4. "Tests used the existing external virtual environment rather than a
     freshly installed environment."
  5. "No files were edited, committed, pushed, or published. The
     malformed gh command failed locally without updating GitHub."
- The checker (`tests/codex_report_status.py`) returned `status:
  complete` because the report's head/base/schema all reconcile
  correctly — that word means the report is current, well-formed and
  bound to the right commit, not that Codex ran a full pytest suite or
  read every byte of every file. This record treats the checker's
  `complete` result and Codex's own self-declared incompleteness above
  as two distinct facts, never collapsed into one. **This is an
  additional, confirmed checker gap beyond CR-01/CR-02/WR-01/WR-02/F001:
  the checker never reads the content of its own required `limitations`
  array** — a report that is structurally complete but explicitly
  self-discloses an incomplete verification (exactly this report) is
  still reported `complete` with no distinct reason surfaced for that
  case. Not independently closed by this plan's own test run below,
  which only closes the gap for *this* record, not for the checker's
  behavior in general.
- This plan independently closed the specific pytest/ruff gap for this
  record by running the full suite itself outside Codex's sandbox (see
  Verification below): `uv run pytest tests/ -x -q` and `uv run ruff
  check triggarr/ tests/`.
- No other incomplete items.

**This checkpoint is not clean and is not fully reviewed.** Two reproduced
findings remain open (plus the duplicates and set-aside items above),
Codex discloses its own verification as incomplete, and this record is
not owner acceptance.
