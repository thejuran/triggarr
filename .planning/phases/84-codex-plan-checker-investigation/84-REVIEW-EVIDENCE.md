# Phase 84 branch — review checkpoint records (local, before a PR exists)

Per `docs/review-checkpoint-record.md` ("Before a PR exists"): one heading per head SHA.
These cover quick task 261026-s2v (Codex-routed plan-checker activation), which rides on
the Phase 84 branch `codex-plan-checker`. Base for every record: the parent of the first
commit in scope (quick-task rule), `cbec881f9f0cb4d523bef67a376396f12da31ccb`.

Superseded heads are listed first, newest record last. Evidence from an earlier head never
counts for a later head (REVIEW-06).

## Superseded heads (summary)

| Head | BM review | Codex | Why superseded |
|---|---|---|---|
| `e261c58f8464ad3e634ec88bb854d64ad707aa9a` | quick task path, quick depth, complete: 0 blockers, WR-01..04, IN-01, SA-01 (`.planning/quick/261026-s2v-.../261026-s2v-REVIEW.md`) | complete, attempt 1, 1 finding `codex:e261c58f8464:a1:F001` (medium, README disable semantics, hypothesis) | fix round 1 (WR-01..04, IN-01, F001) |
| `3c52116dd27882288ca8b8ecf45a9b43ce9029cb` | review after fixes, quick, complete: prior findings fixed; new WR-05 (`261026-s2v-REVIEW-2.md`) | **not run on this head** — superseded by the WR-05 fix before the paired pass; never counted as reviewed | fix WR-05 |
| `b4e4a3115cda707e0bea2eb5c83e33ec93806e93` | review after fixes, quick, complete: WR-05 fixed; new WR-06, WR-07 (`261026-s2v-REVIEW-3.md`) | **not run on this head** — superseded before the paired pass; never counted as reviewed | fix WR-06/WR-07 |
| `a805f3f69d439ce2ab874bc0c08a5356f251d732` | review after fixes, quick, complete: WR-06/07 fixed, 1 info (`261026-s2v-REVIEW-4.md`) | complete, attempt 1, 1 finding `codex:a805f3f69d43:a1:F001` (low, README negative-check `--plugin-dir` path, hypothesis) | fix Codex F001 |

SA-01 (BM, e261c58: negative guard check used a scratch sideload, not the real
registration) was resolved by live evidence on 2026-10-26: from the Triggarr root with
`--settings '{"env":{"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS":"0"}}'`, the debug log showed the
hooks module gated, the guard refused the `bm:bm-plan-checker` spawn in session output, and
`modelUsage` held only the orchestrator model (session `c1d23d00-1ca5-4fe1-a605-fabf5040f84c`,
`~/scratch/planchk-activation/smoke/negative-live.stream.jsonl`).

## Head 4d7e6774ef0c1e787d59727ea941a413fe9c18ad (current)

<!-- review-checkpoint head=4d7e6774ef0c1e787d59727ea941a413fe9c18ad -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `4d7e6774ef0c1e787d59727ea941a413fe9c18ad` (local checkpoint, no PR yet) |
| PR base SHA | `cbec881f9f0cb4d523bef67a376396f12da31ccb` (quick-task rule: parent of first commit in scope) |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `4d7e6774ef0c1e787d59727ea941a413fe9c18ad` |
| Codex inspected base (`inspected_base_sha`) | `cbec881f9f0cb4d523bef67a376396f12da31ccb` |

Reconciliation: All fields match; no reconciliation needed.

### Classification

```json
{"schema":1,"head":"4d7e6774ef0c1e787d59727ea941a413fe9c18ad","classification":"sensitive","classes_present":["sensitive"],"rationale":"Adds a Claude Code plugin under .claude/plugins/ (marketplace manifest, agent.spawn function hook that reroutes bm:bm-plan-checker's model, PreToolUse command hook that can refuse Agent spawns, tests, README operating procedure). .claude/** and hooks are sensitive; no application code under triggarr/ changed.","supersedes_head":"a805f3f69d439ce2ab874bc0c08a5356f251d732"}
```

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr, local branch `codex-plan-checker`, `cbec881..4d7e677`, whole quick-task scope (7 files under `.claude/plugins/`). Activation switch is local only (gitignored `.claude/settings.local.json`); clones are unaffected.
- **Risk:** high — the change alters which model gates every Triggarr plan (BM plan checker routed to a Codex gateway model) and adds a guard that refuses agent spawns. Failure scenarios: (1) router module fails to load after a Claude Code update while the flag stays set → checker silently runs on Claude (residual; guard checks the flag, not the load); (2) PreToolUse payload/tool-name change → guard stops matching, same silent fallback; (3) unparseable guard input → every Agent/Task spawn in Triggarr is refused (visible, blocks BM work); (4) Codex checker timeouts on large plans (900s seen in Phase 84) → visible incomplete checks; (5) an operator picks "Accept verification" on a failed Codex check → unchecked plan treated as passed.
- **Recommended review:** BM quick (quick-task hardcode) + paired Codex on the full scope — done; plus a vibe-check focused on `guard.mjs` fail-closed paths and the README operating procedure.
- **Required evidence:** node tests 11/11; `claude plugin validate` both levels; live positive smoke (checker → codex `gpt-6-astra`, orchestrator → anthropic, session `df8296a0-…`); live negative check from the real registration (session `c1d23d00-…`); shared and user-global settings hashes unchanged; pytest 2432 passed, ruff clean.
- **What this recommendation cannot establish:** that the router keeps loading after future Claude Code updates; full BM step-12 revision/recheck loop with the Codex checker (never exercised); effort equivalence between Codex and Claude checkers; `claude-code-proxy` billing internals; plugin tests are not in CI.

### Vibe-check (RISK-02)

- **Recommendation:** run vibe-check locally on `cbec881..4d7e677` before the end-of-phase push, focused on `guard.mjs` fail-closed behavior and the README procedure (disable vs. fail-closed, post-update rechecks).
- **Owner's decision:** "skip vibe-check, add tests to CI in Phase 85" (2026-10-26)

- **Routine vibe-check status:** not run on this head.

Vibe-check never substitutes for Codex or Greptile, never waives a finding and never reduces required coverage.

### BM review

| Field | Value |
|---|---|
| Path | review after fixes |
| Requested depth | `quick` |
| Actual depth | `quick` |
| Large-scope warning | not printed |
| Responsible files | quick-task hardcode (`workflows/quick.md` Step 6.25, "Depth: quick"); BM 5.0.3 |
| Report location | `.planning/quick/261026-s2v-activate-the-codex-routed-plan-checker-f/261026-s2v-REVIEW-5.md` (targeted follow-up scope `a805f3f..4d7e677`, README only; full scope reviewed at e261c58 and fix rounds in REVIEW..REVIEW-4) |
| Status | complete — 0 blockers, 0 warnings, 1 info (IN-01 line wrap, README:87) |

### Codex

| Field | Value |
|---|---|
| Status | complete |
| Attempts | 1 |
| Raw output paths | `.planning/phases/84-codex-plan-checker-investigation/codex/4d7e6774ef0c-quick-261026-s2v-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}` |
| Review complete | `review_complete: true`, `incomplete_reasons: []` (schema v2) |
| Coverage | manifests, module registration, classic-hook dispatch, guard flag/unrelated-agent/malformed-input/stdin-error paths, model-only rewrite and rejection propagation, test assertions and limits, activation/disable/upgrade docs, shared settings and CI config (as reported) |
| Exclusions | `.planning/**/codex/**`, `.planning/**/*.jsonl`, `.planning/**/*.md` (background only), files outside the working copy |
| Commands run | git rev-parse/cat-file/diff (0), node --test plugin tests (0), rg searches (0; two planning-file searches 1 = no match), CI config read (0) |
| Limitations | did not rerun pytest (used harness evidence: exit 0); no live Claude Code/gateway sessions; guard checks the flag not the load; plugin tests not in CI glob |

Findings: none (`finding_count: 0`).

Secret checks before commit: `gitleaks detect --no-git` on the codex dir — no leaks; 32-hex scan — no files listed.

### Greptile

not run on this head (local checkpoint, not pushed).

### CI

not run on this head (local checkpoint, not pushed). Local: pytest 2432 passed (harness, exact head), ruff clean, plugin node tests 11/11.

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `codex:e261c58f8464:a1:F001` | codex | `e261c58…` | fixed | README disable section rewritten (`3c52116`) | `4d7e677` |
| `codex:a805f3f69d43:a1:F001` | codex | `a805f3f…` | fixed | README negative check uses live-verified `--settings` override; sideload points at plugin dir (`4d7e677`) | `4d7e677` |
| BM WR-01..WR-04, IN-01 | bm | `e261c58…` | fixed | `d8d6d84`, `341db6f`, `e884e32`, `3ee5120`, `3c52116` | `4d7e677` |
| BM SA-01 | bm | `e261c58…` | fixed | live negative check from real registration (session `c1d23d00-…`) | `3c52116` |
| BM WR-05 | bm | `3c52116…` | fixed | `b4e4a31`; test fails on prior guard (0 vs 2) | `4d7e677` |
| BM WR-06, WR-07 | bm | `b4e4a31…` | fixed | `a805f3f`; prior guard hang now fails cleanly (null vs 2) | `4d7e677` |
| BM IN-01 (REVIEW-4: stderr write callback ignores err) | bm | `a805f3f…` | nonblocking_debt | exit code 2 unaffected; message loss only if stderr already closed | `4d7e677` |
| BM IN-01 (REVIEW-5: README line wrap) | bm | `4d7e677…` | nonblocking_debt | cosmetic | `4d7e677` |
| Plugin tests not in CI | bm/codex | `4d7e677…` | nonblocking_debt | owner 2026-10-26: add to CI in Phase 85 (`.planning/backlog/MAINTENANCE.md`) | — |

### Incomplete items

- Greptile and CI: not run (local checkpoint; run at end-of-phase push).
