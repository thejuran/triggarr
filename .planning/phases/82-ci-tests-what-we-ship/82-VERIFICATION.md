---
phase: 82-ci-tests-what-we-ship
verified: 2026-10-22T14:11:25Z
status: passed
score: 4/4 roadmap success criteria verified
has_blocking_gaps: false
overrides_applied: 0
waived:
  - must_have: "CISHIP-02 — reintroducing the polling bug makes the suite fail, demonstrated as a GitHub gate-enforcement case (pill-loop / pill-disabled on an isolated draft PR)"
    reason: "Owner decision 2026-10-22 (verbatim in 82-DEMONSTRATIONS.md): push only the broken-entrypoint demonstration as a draft PR; retain the local pill sensitivity evidence; explicitly record that the pill mutations were not demonstrated on GitHub. Treated as waived, not passed, because a pushed pill mutation is caught earlier by the existing tests/test_header_redesign.py guard in the `test` job (which `docker` needs), so it can never reach `browser-e2e` without weakening that guard — which D-32 forbids."
    accepted_by: "owner (thejuran)"
    accepted_at: "2026-10-22"
  - must_have: "CISHIP-03 — tag-triggered publication proof"
    reason: "D-31e / owner decision 2026-10-21: a deliberately red tag-triggered run is not required and is not performed. Permanent rehearsal + structural wiring tests inside green CI runs are the accepted bounded evidence. Verbatim limitation sentence recorded in both 82-DEMONSTRATIONS.md and 82-09-SUMMARY.md: \"Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release.\""
    accepted_by: "owner (thejuran)"
    accepted_at: "2026-10-21"
---

# Phase 82: CI Tests What We Ship — Verification Report

**Phase Goal:** CI proves the exact artifact it will publish actually works: image startup, critical browser flows and release-version identity are all tested before publication, and a broken instance of each check fails.
**Verified:** 2026-10-22T14:11:25Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — the contract)

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | CI starts the exact publish-candidate image through its normal entrypoint with isolated test config and mocked/test services, verifies health/setup/login/static assets/writable config/persistence across restart; a broken entrypoint and a missing static asset each make the check fail. (GitHub-enforced) | VERIFIED | `image-smoke` job exists in `.github/workflows/ci.yml` (`needs: [docker]`, no `if:`), downloads+identity-verifies `audited-image`, runs `python -m tests.harness.image_smoke run` which executes steps A–E (first-run exit, seeded setup/login/dashboard/config-ownership, restart persistence, missing-static-asset negative, log hygiene) against the real `ENTRYPOINT`. All 3 real GitHub CI runs (39697729420, 39699460532, 39701686221) show `image-smoke: success` with the log line `[smoke] negative static-asset-missing: rejected as expected` + `SMOKE PASSED` — this negative runs on **every** CI run, not a one-off. The broken-entrypoint case was independently demonstrated on GitHub (draft PR #34, run [39790931780](https://github.com/thejuran/triggarr/actions/runs/39790931780)): `image-smoke` job conclusion = `failure` (`SMOKE FAILED [first-run] ...`), `browser-e2e` = `failure`, `CI ready` = `failure` — confirmed live via `gh run view 39790931780` during this verification, matching 82-DEMONSTRATIONS.md exactly. |
| 2 | A small browser regression suite asserts the connection-pill request-loop behavior and critical setup/login behavior as observable behavior (not screenshots); reintroducing the polling bug makes the suite fail; failure logs/screenshots upload as artifacts with no secrets. (GitHub-enforced) | VERIFIED (one sub-claim WAIVED by owner — see below) | `tests/e2e/test_pill_polling.py` and `tests/e2e/test_setup_login_logout.py` exist, run against a real Chromium browser via `page.clock`, assert request counts and DOM text — no screenshot-diffing. `browser-e2e` job is wired into `ci-ready`/`REQUIRED_JOBS` (GitHub-enforced). All 3 real CI runs show `browser-e2e: success` with junit evidence (6 credential_pages + 1 other, 0 skips). Local sensitivity evidence (82-06-SUMMARY, 82-DEMONSTRATIONS.md §"Browser sensitivity evidence (i)"), re-run against the **current PR head's audited image** (run 39701686221, image `sha256:66bbe15a…`): the real suite fails with `connection pill request loop: 113 requests without any scheduled tick` on the loop variant and `did not refresh after a scheduled interval: expected at least 2 requests, saw 1` on the disabled-polling variant. Artifact secret scan confirmed: the session-cookie-bearing trace is withheld, remaining screenshot/logs contain no cookie/API key. **However**, the GitHub gate-enforcement demonstration for these two specific regressions (proving `CI ready` stays red on an isolated draft PR when the pill bug is reintroduced) was explicitly **waived by the owner** (2026-10-22) — see "Owner-Waived Items" below. The general gate-enforcement mechanism (a failing/skipped mandatory job keeps `CI ready` red) IS demonstrated live via the broken-entrypoint case above. |
| 3 | Before any version-tag publication, CI rejects a tag that disagrees with package metadata or image version, and accepts one that matches — both proven without publishing a production tag; exact-commit CI and artifact-identity checks preserved. (GitHub-enforced) | VERIFIED | `release-policy.cjs` exports `parseReleaseTag`/`parseProjectVersion`/`validateReleaseIdentity`/`releaseIdentityGate` (confirmed via `grep -n "module.exports"` → line 110, all 7 names present); `release.yml` calls `releaseIdentityGate` at lines 110-119, strictly before the first `docker/login-action` (line 136) — confirmed by direct `grep -n` ordering check during this verification. `image-smoke`'s per-run rehearsal (`.github/scripts/release-identity-rehearsal.cjs`) calls those *same* entry points against the exact audited image on every CI run; all 3 real runs show all four cases (`matching: accepted 2.12.0`, `mismatched: rejected as expected (disagree)`, `malformed: rejected as expected (malformed)`, `missing: rejected as expected (missing)`). `publication_bypass_violations` (11 parametrized bypass negatives) and `orderingViolations` structurally prove a rejection blocks registry login/push/release creation — confirmed passing in this session's own run of `node --test .github/scripts/ci-job-consistency.test.cjs` (21/21) and the full node suite (117/117). No production tag was pushed (confirmed: `git ls-remote --tags origin \| wc -l` = 58, unchanged throughout). The verbatim D-31d limitation sentence is recorded (see Waived Items). |
| 4 | The CISHIP jobs join the existing required aggregate gate and consistency checks together; a missing or skipped mandatory job cannot let the gate pass; the artifact published afterward is the same tested/audited image, never rebuilt. (GitHub-enforced) | VERIFIED | `ci.yml`'s `ci-ready` job `needs:` and Python `required` set (line 323/333) list all 8 jobs: `test, lint, docker, secrets, dependencies, image-smoke, browser-e2e` (+ `CI ready` itself). `release-policy.cjs`'s `REQUIRED_JOBS` (line 3) lists the identical 8-job set. `ci-job-consistency.test.cjs` verifies these three copies stay in sync (confirmed 21/21 passing in this session). Live demonstration: PR #34's run shows `image-smoke: failure`, `browser-e2e: failure` → `CI ready: failure` with the exact message `Mandatory jobs did not succeed: {'image-smoke': 'failure', 'browser-e2e': 'failure'}` (confirmed via `gh run view 39790931780` during this verification). Both new jobs download-and-verify the `audited-image` artifact (sha256 + image-ID check) before any use and contain no `docker build`/rebuild step (confirmed via `grep` of `ci.yml`); `release.yml` is unchanged in its never-rebuild behavior. |

**Score:** 4/4 roadmap success criteria verified (one sub-claim within SC #2 and one sub-claim within SC #3 are explicitly owner-waived, not silently folded into "verified" — see below).

### Owner-Waived Items (Recorded Decisions, Not Gaps)

These are not implementation gaps. Both are explicit, dated, verbatim-recorded owner decisions that the task brief instructs this verification to surface distinctly rather than silently pass or silently fail.

| # | Item | Disposition | Record |
|---|---|---|---|
| 1 | GitHub gate-enforcement demonstration of the pill-loop and pill-disabled regressions (i.e., proving on GitHub, not just locally, that reintroducing either pill bug keeps `CI ready` red) | **WAIVED — not demonstrated on GitHub, not claimed as passed.** The local browser-sensitivity evidence (real suite, real audited image, local-only) IS verified and stands as the D-07-scoped narrow claim. | Owner decision 2026-10-22, verbatim in `.planning/phases/82-ci-tests-what-we-ship/82-DEMONSTRATIONS.md`: *"Push only the broken-entrypoint demonstration as a draft PR. Record its intended failure and CI ready failure, then close it and delete its demonstration branch. Retain the local pill sensitivity evidence; explicitly record that the pill mutations were not demonstrated on GitHub. Treat those two remote demonstrations as waived, not passed."* Reason the demonstration structurally can't run on GitHub without a bypass: a pushed pill-template mutation is caught by the existing `tests/test_header_redesign.py` guard inside the `test` job, and `docker` (hence `image-smoke`/`browser-e2e`) needs `test` — so the mutation never reaches `browser-e2e`, and making it do so would require weakening the header-test guard, which D-32 forbids. |
| 2 | A deliberately red, tag-triggered publication run (actually pushing a `vX.Y.Z` tag to prove CISHIP-03 end-to-end on a live release) | **Not performed, not required.** Permanent rehearsal (4 cases) + structural bypass tests running inside green CI are the accepted bounded evidence (D-31). | D-31e, owner decision 2026-10-21. Verbatim limitation sentence recorded in `82-DEMONSTRATIONS.md` and `82-09-SUMMARY.md`: *"Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release."* |

### CodeQL / Review-Checks Note (context item b)

The task brief anticipated PR #33's head (`0f08523`) might still show CodeQL red pending a batched push. Live re-check during this verification (`gh pr checks 33 --required`, run against the actual current head) shows **all four required branch-protection checks green**: `CI ready` pass, `CodeQL` pass, `Greptile Review` pass, `Review acceptance` pending (expected — out of scope for this phase per context item d; owner acceptance is a separate, later step). Confirmed via `gh api .../code-scanning/alerts`: alerts #13/#14 `state: fixed`, #15/#16 `state: dismissed, dismissed_reason: "false positive"`, 0 open alerts — matching `82-CI-EVIDENCE.md`'s record exactly. This is better than the task brief's framing implied — CodeQL has already re-evaluated and passed on the current head, not merely pending the next push.

Five additional local commits exist ahead of `origin/ci-review-workflow` (`cd12fc0`, `29aaf40`, `132b2d2`, `0898dd7`, `44d4f7f`) — all docs-only tracking updates, held per the owner's push-batching rule (every push starts a paid Greptile review). This does not affect the phase goal: all code supporting the four CISHIP requirements is already pushed and green at `0f08523`.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `.github/scripts/release-policy.cjs` | `parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate` exports; `REQUIRED_JOBS` extended | ✓ VERIFIED | All 4 exports present at line 110; `REQUIRED_JOBS` (line 3) = 8-job set including `image-smoke`, `browser-e2e` |
| `.github/scripts/release-policy.test.cjs` | Positive/negative cases against real exports | ✓ VERIFIED | Part of 117/117 passing node suite run this session |
| `.github/workflows/release.yml` | Identity-gate steps before publication | ✓ VERIFIED | 3 steps at lines 79-119, strictly before `docker/login-action` (line 136) |
| `.github/scripts/release-identity-rehearsal.cjs` | `rehearseReleaseIdentity(...)` calling the real entry points | ✓ VERIFIED | Confirmed via code read + 3 real CI run logs showing the 4-case output |
| `tests/harness/arr_stub.py` | Stub *arr HTTP service, toggleable up/down | ✓ VERIFIED | Exists, exercised by `tests/test_ci_harness.py` (578 lines, exceeds the plan's 80-line minimum) |
| `tests/harness/checks.py` | `SmokeCheckError`, reason-coded checks, `expect_failure` | ✓ VERIFIED | Exists; reused by `image_smoke.py` and `tests/e2e/conftest.py` |
| `tests/harness/stack.py` | Docker argv builders + `HarnessSession` lifecycle | ✓ VERIFIED | Exists; session-labelled teardown confirmed in 82-04-SUMMARY narrative and code |
| `tests/harness/image_smoke.py` | CLI smoke driver, steps A-E | ✓ VERIFIED | Exists; wired into `ci.yml`'s `image-smoke` job (`uv run --no-sync python -m tests.harness.image_smoke run`) |
| `tests/harness/fixtures/triggarr-ci.toml` | Isolated seeded config | ✓ VERIFIED | Exists; confirmed `arr-stub` reference |
| `tests/e2e/conftest.py` | Session fixtures, capture guard, `SensitiveRegistry` | ✓ VERIFIED | Exists (17KB); `Credentials.password` uses `field(repr=False)` — confirmed by direct read this session |
| `tests/e2e/test_setup_login_logout.py` | D-25 browser flows | ✓ VERIFIED | 121 lines (exceeds 60-line minimum); exercised in all 3 real CI runs |
| `tests/e2e/test_pill_polling.py` | Connection-pill behavioral regression | ✓ VERIFIED | Exists; `clock` usage confirmed; local sensitivity evidence re-confirmed against current audited image |
| `tests/harness/artifact_scan.py` | `scrub(output_dir, sensitive_values)` | ✓ VERIFIED | Exists; `scan-complete.json` marker confirmed in code and in CI job gating logic |
| `.github/workflows/ci.yml` | `image-smoke:`, `browser-e2e:` jobs; extended `ci-ready` | ✓ VERIFIED | Both jobs present (lines 181, 223); `ci-ready` needs/required set extended (lines 323, 333) |
| `tests/test_ci_gate.py` | Runs the real `ci-ready` heredoc with synthetic results | ✓ VERIFIED | Collected and passing as part of the 2164-test full suite run this session |
| `docs/ci-negative-demonstrations.md` | Reproduction recipes, D-09 | ✓ VERIFIED | Exists |
| `.planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md` | Durable positive-run evidence | ✓ VERIFIED | Exists; every run ID/SHA cross-checked live via `gh run view`/`gh api` this session, no discrepancies found |
| `.planning/phases/82-ci-tests-what-we-ship/82-DEMONSTRATIONS.md` | Negative-case evidence, split (i)/(ii) | ✓ VERIFIED | Exists; broken-entrypoint demo cross-checked live via `gh run view 39790931780`, matches exactly |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `.github/workflows/release.yml` (`release` job) | `.github/scripts/release-policy.cjs` | `require('./.github/scripts/release-policy.cjs')` calling `releaseIdentityGate` | WIRED | Confirmed by direct `grep` read this session (line 118-119); runs before `docker/login-action` |
| `.github/scripts/release-identity-rehearsal.cjs` | `.github/scripts/release-policy.cjs` | `require` of `parseReleaseTag`/`releaseIdentityGate` (same entry points `release.yml` calls) | WIRED | Confirmed by code read; this is what makes the per-run rehearsal non-divergent from the real gate (D-31a) |
| `.github/workflows/ci.yml` `ci-ready` | `.github/scripts/release-policy.cjs` `REQUIRED_JOBS` | `ci-job-consistency.cjs` `checkJobListConsistency`, run by `node --test` in the `test` job | WIRED | Confirmed via live `node --test .github/scripts/ci-job-consistency.test.cjs` run this session (21/21 passing) |
| `.github/workflows/ci.yml` `image-smoke` | `tests/harness/image_smoke.py` | `uv run --no-sync python -m tests.harness.image_smoke run` | WIRED | Confirmed via `grep` of `ci.yml` and 3 real CI run logs showing `SMOKE PASSED` |
| `.github/workflows/ci.yml` `browser-e2e` | `tests/e2e` | `TRIGGARR_E2E_IMAGE=... pytest tests/e2e` (two invocations: credential_pages capture-off, others capture-on-failure) | WIRED | Confirmed via 3 real CI run logs showing junit pass counts (6+1, 0 skips each run) |
| `tests/conftest.py` | `tests/e2e` | `collect_ignore` when `TRIGGARR_E2E_IMAGE` unset | WIRED | Confirmed live this session: `pytest tests/e2e` without the env var produces 6 collection **errors**, not silent skips (D-12 "fails, doesn't skip" requirement holds) |

### Behavioral Spot-Checks (run live during this verification)

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full Python suite is green, `tests/e2e` excluded by default | `env -u TRIGGARR_E2E_IMAGE uv run pytest tests/ -x -q` | `2164 passed, 38 warnings in 81.16s` | ✓ PASS |
| No lint regressions in touched code | `uv run ruff check triggarr/ tests/` | `All checks passed!` | ✓ PASS |
| Release-policy / CI-consistency node suite green | `node --test .github/scripts/*.test.cjs` | `117/117 pass` | ✓ PASS |
| `ci-job-consistency` catches real inconsistency | `node --test .github/scripts/ci-job-consistency.test.cjs` | `21/21 pass` (includes negative mutation cases) | ✓ PASS |
| `tests/e2e` fails (not skips) without `TRIGGARR_E2E_IMAGE` | `env -u TRIGGARR_E2E_IMAGE uv run pytest tests/e2e` | `1 passed, 6 errors` (fixture-level `Failed` in `conftest.py:292`) | ✓ PASS |
| Release-identity gate precedes publication steps | `grep -n "Verify release version identity\|docker/login-action" release.yml` | Gate steps at lines 79-119; first `docker/login-action` at line 136 | ✓ PASS |
| `REQUIRED_JOBS` / `ci-ready` 8-job set agreement | `grep -n "REQUIRED_JOBS\|needs:\|required ="` | All three copies list the identical 8-job set | ✓ PASS |

### Probe / Live-Evidence Execution (GitHub, checked directly — not SUMMARY narration)

| Probe | Command | Result | Status |
|---|---|---|---|
| Broken-entrypoint gate demonstration (draft PR #34) | `gh run view 39790931780 --json jobs` | `image-smoke: failure`, `browser-e2e: failure`, `CI ready: failure`, others success | PASS (matches 82-DEMONSTRATIONS.md exactly) |
| PR #34 cleanup | `gh pr view 34 --json state,headRefName` | `state: CLOSED`, branch `demo/82-broken-entrypoint` (deleted on origin) | PASS |
| Remote tag count unchanged | `git ls-remote --tags origin \| wc -l` | `58` | PASS (matches recorded pre/post count) |
| PR #33 current head real-time check | `gh pr checks 33 --required` | `CI ready` pass, `CodeQL` pass, `Greptile Review` pass, `Review acceptance` pending | PASS (Review acceptance pending is expected/out of scope) |
| CodeQL alert history | `gh api repos/thejuran/triggarr/code-scanning/alerts/{13,14,15,16}` | #13/#14 `fixed`; #15/#16 `dismissed`, `false positive`, comments match recorded text exactly | PASS |
| 3 real CI runs for CISHIP evidence | `gh run view {39697729420,39699460532,39701686221} --json conclusion,headSha` | All `conclusion: success`, headSHAs match `82-CI-EVIDENCE.md` exactly | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| CISHIP-01 | 82-02, 82-04, 82-07, 82-08, 82-09 | Shipped-image startup smoke test | ✓ SATISFIED | `image-smoke` job live-green on 3 real runs; broken-entrypoint negative live-demonstrated; missing-static-asset negative runs every CI run |
| CISHIP-02 | 82-02, 82-05, 82-06, 82-07, 82-08, 82-09 | Browser regression suite (pill + setup/login/logout) | ✓ SATISFIED (with one explicitly waived GitHub-demonstration sub-claim, see above) | `browser-e2e` job live-green; local sensitivity evidence re-confirmed against current audited image; artifact secret scan confirmed clean |
| CISHIP-03 | 82-01, 82-03, 82-07, 82-08, 82-09 | Release-version identity gate | ✓ SATISFIED (tag-triggered run intentionally not performed, D-31e, see Waived Items) | `releaseIdentityGate` wired before publication; rehearsal 4-case evidence live on 3 real runs; structural bypass tests pass live this session |
| CISHIP-04 | 82-03, 82-07, 82-08, 82-09 | New jobs join required gate + consistency checks | ✓ SATISFIED | `REQUIRED_JOBS`/`ci-ready`/`ci-job-consistency` all agree (21/21 node tests pass); live-demonstrated gate failure on PR #34 |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s Phase 82 row lists exactly CISHIP-01..04, and all four appear in at least one plan's `requirements:` frontmatter field.

### Anti-Patterns Found

None. Scanned every file touched by this phase (`tests/harness/**`, `tests/e2e/**`, `.github/scripts/release-policy.cjs`, `.github/scripts/release-identity-rehearsal.cjs`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|placeholder|coming soon|not yet implemented|not available` — zero matches. No debt markers. `review-acceptance.yml` confirmed untouched by this phase (`git diff --stat 81eb550..HEAD -- .github/workflows/review-acceptance.yml` empty).

One cosmetic (non-blocking) note recorded by the executor itself in 82-09-SUMMARY.md: the `SMOKE FAILED [first-run]` message names the exit code but not the missing log line, which is slightly ambiguous. Logged there as "a cosmetic follow-up, not a gate defect" — concur with that assessment; not listed as a gap here.

### Human Verification Required

None. All items that would otherwise require human sign-off (the broken-entrypoint and pill-regression demonstrations, the CodeQL disposition, the release-identity evidence) already have explicit, dated, verbatim owner decisions on record, which this verification independently confirmed against the live GitHub state rather than trusting the written record alone. `Review acceptance` (exact-commit owner approval) remains `pending` on the current PR head, but that is a separate, later milestone step explicitly out of scope for this phase's goal.

### Gaps Summary

No gaps. All four ROADMAP success criteria are observably true in the codebase and confirmed live against GitHub (not merely asserted in SUMMARY.md): the shipped image's own entrypoint is smoke-tested every CI run with a permanent missing-asset negative and a live-demonstrated broken-entrypoint negative; the browser suite runs real Chromium against the real audited image and is proven sensitive to both pill regressions on that exact image; the release-identity gate is wired ahead of every publication step and rehearsed against the real audited image on every run; and the required aggregate gate was live-demonstrated to fail closed when either new job fails. Two items are explicitly owner-waived rather than passed (the GitHub-level pill gate demonstrations, and a live tag-triggered publication run) — both are documented, intentional, and outside this phase's required evidence per the recorded owner decisions, not implementation shortfalls.

---

*Verified: 2026-10-22T14:11:25Z*
*Verifier: Claude (bm-verifier)*
