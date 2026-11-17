<!-- review-checkpoint head=8c683587f2d96a7265f14b2edfc6b16bde7ee8e0 -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `8c683587f2d96a7265f14b2edfc6b16bde7ee8e0` |
| PR base SHA | `3cede40099a1f8a5d6db45542e66c650bfa98952` |
| Tested SHA (if different from PR head) | `88832ef99dea96e925301dff0d3103370e3b3783` |
| Codex inspected head (`inspected_head_sha`) | `8c683587f2d96a7265f14b2edfc6b16bde7ee8e0` (PR-head run `pr62-a1`; earlier local-checkpoint run `phase-fix5-a1` inspected `88832ef99dea96e925301dff0d3103370e3b3783`) |
| Codex inspected base (`inspected_base_sha`) | `3cede40099a1f8a5d6db45542e66c650bfa98952` |

Reconciliation: Codex `pr62-a1` inspected the exact PR head. BM (iteration 6), the local-checkpoint Codex run (phase-fix5 a1), the vibe-check deep review and the exact-head coverage all ran on `88832ef99dea96e925301dff0d3103370e3b3783`. The PR head `8c683587f2d96a7265f14b2edfc6b16bde7ee8e0` adds only the iteration-6 review report and the Codex evidence under `.planning/` (`git diff 88832ef9 8c683587 --stat -- . ':(exclude).planning'` is empty), so every file in the review scope is byte-identical at the PR head.

### Classification

```json
{"schema":1,"head":"8c683587f2d96a7265f14b2edfc6b16bde7ee8e0","classification":"code","classes_present":["code","ordinary-docs"],"rationale":"Range 3cede40..8c68358. Code: triggarr/web/routes.py, triggarr/config.py, triggarr/state.py, triggarr/templates/settings.html and their tests (settings writes, concurrency under search_lock, state-file recovery, instance-removal cancellation). Ordinary-docs: .planning/** (phase plans, summaries, review reports, Codex evidence, milestone and backlog docs). No CI workflow, dependency, CLAUDE.md or review-policy change.","supersedes_head":null}
```

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr PR #62, head `8c683587f2d96a7265f14b2edfc6b16bde7ee8e0` (code head `88832ef99dea96e925301dff0d3103370e3b3783`), base `3cede40099a1f8a5d6db45542e66c650bfa98952`. Covers instance removal, add-instance and settings-save ordering and locking, atomic settings-write logging, state-file corruption recovery, and the Settings page's removal error. Whole PR.
- **Risk:** high. A defect here can lose or corrupt the user's instance configuration on disk, leave the running app out of step with the settings file (a removed instance keeps searching, or a removed instance comes back on the next save), or crash startup on a damaged state file.
- **Recommended review:** BM standard + paired Codex on the whole PR, plus the required vibe-check.
- **Required evidence:** targeted regression tests for every failure and concurrency path (write failure, refused thread start, cancellation through a three-layer BaseHTTPMiddleware stack, overlapping save/add/remove, corrupt/unreadable state file); full suite and ruff on the exact head; human UAT of the Settings page, including the screen reader.
- **What this recommendation cannot establish:** behaviour under a real uvicorn shutdown or a real client disconnect (modelled with BaseHTTPMiddleware layers and task cancellation in tests); filesystem-specific write semantics on the production NAS volume.

### Vibe-check (RISK-02)

- **Required vibe-check:** risk is high (settings and state-file persistence). Scope: the phase's net code change `de058335..HEAD` excluding `.planning/`.
- **Vibe-check status:** ran because risk is high. `/vibe-check:deep-review phase 87`, 4 passes, `70f79434` → `88832ef9`, closed out ✅ APPROVED on `88832ef99dea96e925301dff0d3103370e3b3783`. Pass 1 raised a cancelled-removal divergence (Codex + bugs, reproduced) → fixed `f9186e87`. Pass 2 raised an unclosed client under BaseHTTPMiddleware cancellation (reproduced) → fixed `9c2fc602`. Pass 3 raised an unlogged cancelled close → fixed `88832ef9`. Each fix was rechecked by a lane other than the fixer. Owner decisions: 2 compliance warnings dismissed (false positive, shown by execution); the `save_settings` close loop, a shutdown-only self-cancelled close edge and the startup copy I/O deferred (outside phase scope). Vibe-check's own Codex runs: needs-attention (pass 1), then approve (passes 2–4). Report location: `.turingmind/REVIEW.md` (local, not published); pass state archived locally.

### BM review

| Field | Value |
|---|---|
| Path | review after fixes (iteration 6; iterations 1–5 at the phase's earlier heads) |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow `workflows/code-review.md:compute_file_scope` (`--files triggarr/web/routes.py,tests/test_web.py`, the only code changed since iteration 5) |
| Report location | `.planning/phases/87-settings-state-file-safety/87-REVIEW.md` (iteration 6, reviewed head `88832ef9`) |
| Status | complete. Iteration 6: 0 critical, 0 warning, 3 info (IN-01 shield wait loops spin under level-triggered cancellation until the write/close finishes; IN-02 the middleware close test polls 500 ms after the request ends; IN-03 a comment names only the write as the cancellation source). Each of the 5 new tests was shown to fail at the parent of its fix. |

### Codex

| Field | Value |
|---|---|
| Status | complete. PR-head run `pr62-a1` (trusted PR-URL run on `8c683587…`): `.status.json` complete, 0 findings, verdict `no-findings`; readiness check: "Codex: ok — complete". Earlier local-checkpoint run `phase-fix5-a1` on `88832ef9…`: complete, 0 findings. |
| Fallback | none |
| Attempts | 1 (each run) |
| Raw output paths | `.planning/phases/87-settings-state-file-safety/codex/8c683587f2d9-pr62-a1.*` (local; committed with the next push) and `…/88832ef99dea-phase-fix5-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}` (all passed the evidence publication gate checks: gitleaks, local user/host name, public-infrastructure and 32-hex scans; no hits) |
| Review complete | `review_complete: true`, `incomplete_reasons: []`, verdict `no-findings` |
| Coverage | removal write-before-swap, guarded executor submission, abandoned vs claimed writes, cancellation and cleanup isolation; concurrent remove/add/save under search_lock; client-close completion under cancellation; atomic writer logging and temp cleanup; state recovery and diagnostic copy; row-local htmx error, escaping, redirects, CSP nonce; all changed tests and phase plans; acceptance and audit safeguards |
| Exclusions | `.planning/**/codex/**`, `.planning/**/*.jsonl`, planning markdown other than changed `*-PLAN.md`; pre-existing defects outside the requested changes |
| Commands run | 22, as recorded in `.last.json` |
| Limitations | pytest not rerun in the read-only sandbox (harness evidence: exit 0 at `88832ef9`); cancellation checked on extracted helpers, middleware stack assessed by source and the harness-run regression tests; browser behaviour not exercised |

Findings: none.

### Greptile

not run on this head (optional).

### CI

| Required check | Run ID | Result |
|---|---|---|
| CI ready (lint, test, dependencies, secrets, actionlint, docker, os-scan, browser-e2e, image-smoke) | 43805045052 | success |
| CodeQL | 43805038921 | success |
| Review acceptance | 43805045101 | waiting (owner approval) |

Local exact-head evidence for `88832ef99dea96e925301dff0d3103370e3b3783`: 3336 passed, 1 skipped on a clean detached checkout; `coverage-provenance.cjs check --expected-head 88832ef9…` passes; ruff clean.

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `bm:88832ef9:IN-01` | bm | `88832ef99dea96e925301dff0d3103370e3b3783` | nonblocking_debt | info; correct result, CPU spin only while a cancelled removal finishes; candidate fix `anyio.CancelScope(shield=True)` | `88832ef99dea96e925301dff0d3103370e3b3783` |
| `bm:88832ef9:IN-02` | bm | `88832ef99dea96e925301dff0d3103370e3b3783` | nonblocking_debt | info; test strictness only | `88832ef99dea96e925301dff0d3103370e3b3783` |
| `bm:88832ef9:IN-03` | bm | `88832ef99dea96e925301dff0d3103370e3b3783` | nonblocking_debt | info; comment wording only | `88832ef99dea96e925301dff0d3103370e3b3783` |

### Incomplete items

- Review acceptance waits for the owner's approval of this exact head.
