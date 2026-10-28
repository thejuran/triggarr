<!-- review-checkpoint head=5a97e1f98982b47672ba108e357a024e0f2a44e2 -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `5a97e1f98982b47672ba108e357a024e0f2a44e2` |
| PR base SHA | `decd5f1e6f1e649d3da79e6cd6db398d11aa1df9` |
| Tested SHA (if different from PR head) | same as PR head |
| Codex inspected head (`inspected_head_sha`) | `5a97e1f98982b47672ba108e357a024e0f2a44e2` |
| Codex inspected base (`inspected_base_sha`) | `decd5f1e6f1e649d3da79e6cd6db398d11aa1df9` |

Reconciliation: All fields match; no reconciliation needed. (Reviewed base = `git merge-base <PR base> head` = PR base, branch is up to date with main.)

### Classification

```json
{"schema":1,"head":"5a97e1f98982b47672ba108e357a024e0f2a44e2","classification":"code","classes_present":["code","sensitive","ordinary-docs"],"rationale":"Full PR range decd5f1..5a97e1f. Sensitive: .github/workflows/{ci,release,review-acceptance}.yml; .github/scripts/*.cjs (acceptance-readiness, ci-job-consistency, codex-fallback, coverage-provenance, os-scan-gate, release-policy, review-acceptance, review-register, artifact-promotion test); .github/dependabot.yml; .github/os-scan-exceptions.json; tests/codex_review_run.py and tests/codex_report_status.py (Codex harness/checker); tests/test_required_jobs_no_skip.py and tests/test_ci_gate.py (required-check safeguard tests); docs/codex-adversarial-review-contract.md, docs/review-checkpoint-record.md, docs/review-classification-policy.md, docs/owner-cli-acceptance.md, docs/buildomator-greptile-pilot.md; .claude/plugins/planchk-router/** (agent-routing hook); all 27 *-PLAN.md files (agent instructions, D-17). Code: Dockerfile, pyproject.toml, uv.lock, .github/scripts/image_lock_consistency.py, remaining tests/test_*.py. Ordinary-docs: README.md, SECURITY.md, docs/os-scan-policy.md, docs/ci-negative-demonstrations.md, other .planning/**/*.md records and Codex evidence. Mixed changes rule: code + sensitive -> classified code with the full sensitive-content risk assessment.","supersedes_head":"4f4783398e912d0a7c4f37197462505382449d5e"}
```

### Risk note (RISK-01)

- **Scope:** thejuran/triggarr PR #36, head `5a97e1f98982b47672ba108e357a024e0f2a44e2`, base `decd5f1e6f1e649d3da79e6cd6db398d11aa1df9`. Every required CI job (now incl. `os-scan`, `actionlint`), the shipped image's dependency install path (exact `uv.lock` set), release permissions (tag-only `github-release`), the acceptance gate and register schema 1→2, the Codex harness/checker trust boundary, the no-skip guard, and a local agent-routing hook. This record covers the whole PR.
- **Risk:** high — a defect in the gate/guard/harness can let an unreviewed head be accepted or block every merge; the image now pins runtime deps to the lock.
- **Recommended review:** BM standard (done, iterations 1-8) + paired Codex (incomplete, see below) + full-PR vibe-check deep review as owner-approved fallback.
- **Required evidence:** green required checks on this head (done); readiness check output; schema-2 variable migration before merge; P1-P6 human UAT in `85-HUMAN-UAT.md`.
- **What this recommendation cannot establish:** that no deliberate tampering with the gate steps is possible (owner-accepted residual); that the reviewer-name independence check is spoof-proof (owner-accepted residual); whether Dependabot-triggered runs receive `REVIEW_*` variables (deferred).

### Vibe-check (RISK-02)

- **Recommendation:** run `/vibe-check:deep-review` on the full PR at this head as the independent fallback for the incomplete Codex pass.
- **Owner's decision:** "Fallback via full deep review (Recommended)" — then: "Approve the vibe-check deep-review fallback for PR #36 at head 5a97e1f98982."
- **Routine vibe-check status:** ran. Phase-85 code range deep review (4 passes, APPROVED at `d7889b8`, `.turingmind/REVIEW.md`); full-PR deep review at this head (8 lanes, 0 critical/warning, 2 medium, 23 sub-threshold).

Vibe-check never substitutes for a complete Codex pass; Codex remains INCOMPLETE/PENDING with the Fallback row below.

### BM review

| Field | Value |
|---|---|
| Path | review after fixes (iterations 6-8; phase-execution review iterations 1-5) |
| Requested depth | `standard` |
| Actual depth | `standard` |
| Large-scope warning | not printed (iterations 6-8 used explicit 8/4/2-file scopes) |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth`; BM workflow file/step: `workflows/code-review.md:compute_file_scope` (`--files` scope) |
| Report location | `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md` (iteration 8, reviewed head `2f2e8fc`; `5a97e1f` adds only the report itself) + `85-REVIEW.iter1..7.md` |
| Status | complete — iteration 8: 0 critical, 0 warning, 4 info; iteration 7 warning owner-accepted residual |

### Codex

| Field | Value |
|---|---|
| Status | INCOMPLETE/PENDING — both attempts self-declared incomplete: the full diff and the 27 plans exceeded output limits; changed tests, docs and `uv.lock` not fully inspected. Base checker also incomplete. |
| Fallback | owner-approved fallback record `5a97e1f98982-fallback.json`, validated by `node .github/scripts/codex-fallback.cjs validate --file … --pr 36 --head 5a97e1f… --base decd5f1… --pr-author thejuran --head-trust trusted --codex-out …/5a97e1f98982-phase85-pr-a2` → `fallback valid for 5a97e1f98982b47672ba108e357a024e0f2a44e2`. Codex stays INCOMPLETE/PENDING. |
| Attempts | 2 (`a1`, `a2`) |
| Raw output paths | `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/codex/5a97e1f98982-phase85-pr-a{1,2}.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt,base-status.json}` |
| Review complete | `review_complete: false` (both); reasons as above |
| Coverage | workflows, Dockerfile, Dependabot, all `.github/scripts` implementations, runner/checker substantially; 1 of 27 plans fully (a1) |
| Exclusions | `.planning/**/codex/**`, `.planning/**/*.jsonl`, planning markdown other than `*-PLAN.md`, files outside the working copy |
| Commands run | a1: 28, a2: 19 (as recorded in `.last.json`) |
| Limitations | no independent pytest in the read-only sandbox (relied on exact-head harness evidence: 2,688 passed); no live Actions/Docker/publication |

Findings:

| Qualified ID | Severity | Location | Reproduced / hypothesis | Title |
|---|---|---|---|---|
| `codex:5a97e1f98982:a1:F001` | medium | `.github/scripts/acceptance-readiness.cjs` | reproduced | Allow validated fallback after an incomplete base cross-grade |
| `codex:5a97e1f98982:a2:F001` | low | `tests/codex_report_status.py` | reproduced | Classifying only the first shell token misgrades review evidence |

### Greptile

not run on this head (optional since 2026-10-22).

### CI

| Required check | Run ID | Result |
|---|---|---|
| test | 40751931306 | success |
| lint | 40751931306 | success |
| docker | 40751931306 | success |
| secrets | 40751931306 | success |
| dependencies | 40751931306 | success |
| image-smoke | 40751931306 | success |
| browser-e2e | 40751931306 | success |
| os-scan | 40751931306 | success |
| actionlint | 40751931306 | success |
| CI ready | 40751931306 | success |
| CodeQL (Analyze actions/python) | 40751925455 | success |
| Review acceptance | 40751931289 | waiting (environment approval) |

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `codex:fb8da6e2abe5:a1:F001` / `a2:F001` | codex | `fb8da6e2abe505add73ebfff5b04a5e64f81cf13` | fixed | drain-timeout bytes/str TypeError; fixed in `2f2e8fc` with regression tests (fail before, pass after); BM iteration 8 confirmed | `5a97e1f98982b47672ba108e357a024e0f2a44e2` |
| `codex:5a97e1f98982:a1:F001` | codex | `5a97e1f98982b47672ba108e357a024e0f2a44e2` | nonblocking_debt | readiness blocks before validateFallback only when head checker complete and base incomplete; not this PR's case (head incomplete); recorded in `.planning/backlog/MAINTENANCE.md` | `5a97e1f98982b47672ba108e357a024e0f2a44e2` |
| `codex:5a97e1f98982:a2:F001` | codex | `5a97e1f98982b47672ba108e357a024e0f2a44e2` | nonblocking_debt | hollow-report guard first-token heuristic; recorded in `.planning/backlog/MAINTENANCE.md` | `5a97e1f98982b47672ba108e357a024e0f2a44e2` |
| fallback review (25 findings) | vibe-check | `5a97e1f98982b47672ba108e357a024e0f2a44e2` | nonblocking_debt (18 deferred, 7 accepted) | per-finding dispositions in `5a97e1f98982-fallback.json`; 0 critical/warning | `5a97e1f98982b47672ba108e357a024e0f2a44e2` |

### Incomplete items

- Codex is INCOMPLETE/PENDING on this head (diff too large for one pass); covered by the owner-approved fallback above, not by a complete Codex review.
- `Review acceptance` awaits the owner's environment approval; the schema-2 repository-variable migration must happen before that run.
- Human UAT P1-P6 (`85-HUMAN-UAT.md`) not yet confirmed.
- Deferred before the first Dependabot actions PR / milestone archive: hardcoded action SHAs in `ci-job-consistency.test.cjs`; `test_ci_followon_wiring.py` reading a phase-85 planning file.
