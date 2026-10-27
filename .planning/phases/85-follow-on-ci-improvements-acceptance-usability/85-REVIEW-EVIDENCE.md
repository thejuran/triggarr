# Phase 85 — Review Evidence

Written by Plan 85-19, the phase's closing plan. Records what Plans 85-01
through 85-18 proved locally, states honestly what only a real GitHub run can
still show, classifies the phase PR, and hands off the sequence that happens
after this plan — none of which this plan performs.

## Local verification — head 4f4783398e912d0a7c4f37197462505382449d5e

`LOCAL_HEAD = 4f4783398e912d0a7c4f37197462505382449d5e` (40-hex, confirmed via
`git rev-parse HEAD`). `BASE = b07e532dfd16a701b7631c6d7a3da6382960557d`
(`git merge-base origin/main HEAD`; confirmed an ancestor of `origin/main` via
`git merge-base --is-ancestor`). The working tree was clean (`git status
--porcelain` empty) before any command below ran.

| # | Command | Exit | Summary | Wall-clock |
|---|---|---|---|---|
| 1 | `uv run pytest tests/ -x -q` | 0 | **2564 passed**, 38 pre-existing warnings (starlette/httpx deprecation, unrelated to this plan) | 85.04s |
| 2 | `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` | 0 | **326 passed, 0 failed** | ~0.50s (`duration_ms 500.39`) |
| 3 | `uv run ruff check triggarr/ tests/` | 0 | `All checks passed!` | <1s |
| 4 | `actionlint` | 0 | no output (zero findings) | <1s |
| 5 | Docker build + lockfile consistency check (see below) | 0 | image built, checker reports match | ~5s build + <1s check |

Command 1 (the full pytest suite, ~85s measured here against the planned
~180s estimate) is the phase's integration gate (W07), run once as a whole
rather than as a per-task feedback loop; the per-task feedback commands each
plan already ran and recorded in its own SUMMARY.md are not re-run here.

**Command 5 detail.** The plan specifies `docker build --platform
linux/amd64`. That build failed identically to the already-documented QEMU/
Rust-binary segfault from Plans 85-08 and 85-12 (`qemu: uncaught target
signal 11 (Segmentation fault)` the moment the pip-installed `uv==0.12.17`
binary executes under amd64 emulation on this machine) — see Deviations
below. Substituting `--platform linux/arm64` (this Mac's native platform),
the build succeeded, and the lockfile consistency check ran exactly as the
`docker` job's steps do, against that image:

1. `uv export --locked --no-dev --no-emit-project --no-hashes --format requirements-txt --output-file requirements-locked.txt` — succeeded, 107 lines.
2. `docker run --rm -v "$PWD/.github/scripts:/check:ro" --entrypoint python triggarr:p85-19-final /check/image_lock_consistency.py --dump-environment` — succeeded; dumped environment shows `platform_machine: aarch64` (the arm64 substitution, not amd64 — see Deviations).
3. `uv run --no-project --with packaging==26.0 python .github/scripts/image_lock_consistency.py --locked requirements-locked.txt --freeze image-requirements.txt --environment image-environment.json` — exit 0, printed `Image dependencies match uv.lock`.

The built image and all scratch files were removed after evidence capture
(`docker rmi triggarr:p85-19-final`; scratch dir under `/tmp`, never under the
repository). `git status --porcelain` was empty after cleanup.

### Exact-head coverage proof (checker B09)

Proves, before this plan hands off, that the exact procedure the hand-off's
step 1 will use for the final head works end to end on this head:

1. `uv run pytest tests/ -q --cov=triggarr --cov-branch --cov-report=xml:$TMPDIR/p85-cov/coverage.xml` — exit 0, **2564 passed**, 92.95s; `branches-valid="1364"` in the written Cobertura XML (greater than 0, confirming branch coverage was actually collected).
2. `node .github/scripts/coverage-provenance.cjs write-local --head 4f4783398e912d0a7c4f37197462505382449d5e --coverage $TMPDIR/p85-cov/coverage.xml --test-exit 0 --test-seconds 92.95 --out $TMPDIR/p85-cov/coverage-provenance.json` — exit 0, `Local coverage provenance written to ... for 4f4783398e912d0a7c4f37197462505382449d5e`.
3. `node .github/scripts/coverage-provenance.cjs check --provenance $TMPDIR/p85-cov/coverage-provenance.json --coverage $TMPDIR/p85-cov/coverage.xml --expected-head 4f4783398e912d0a7c4f37197462505382449d5e` — exit 0, `Coverage evidence matches head 4f4783398e912d0a7c4f37197462505382449d5e`.

Both `write-local` and `check` exited 0 against `LOCAL_HEAD`. The files were
written under `$TMPDIR/p85-cov/`, outside the repository, and removed after
this evidence was recorded. This is the local-coverage half of the procedure
the hand-off's step 1 performs again for the final head (H1); a CI coverage
artifact that arrives later is validated and recorded separately (P2 below),
never substituted into a review that already ran.

### Read-only GitHub checks (no setting changed)

- `gh api repos/thejuran/triggarr/rulesets/14805779 --jq '.rules[] | select(.type=="required_status_checks")'` → required checks are exactly **`CI ready`** (integration_id 15368), **`Review acceptance`** (integration_id 15368) and **`CodeQL`** (integration_id 57789), `strict_required_status_checks_policy: true`. Unchanged from the Phase 82/83 record; still CI-ready-only at the branch-protection level — ACCEPT-03's no-skip mechanism (D-01) lives inside `CI ready`'s own required-job set, not as a fourth ruleset entry.
- `gh api repos/thejuran/triggarr/code-scanning/default-setup --jq '{state,languages}'` → `{"languages":["actions","python"],"state":"configured"}` — CodeQL runs as default setup, no repository-side path filter.
- `gh api repos/thejuran/triggarr --jq .allow_auto_merge` → `false`.

No command above wrote anything; all three are read-only `gh api` GET calls, and no repository setting was changed by this plan.

## Requirement evidence

| Requirement | Proved locally / by test | What GitHub has shown so far | Still pending |
|---|---|---|---|
| CIMAINT-01 (lockfile-matched Docker deps) | Dockerfile `deps` stage + hash-checked `--require-hashes --no-deps` install (85-08); `image_lock_consistency.py` + 15 unit tests; wired into `ci.yml`'s `docker` job between the audit and pip-audit/save steps (85-11); positive match reconfirmed on this exact head above (checker exit 0, arm64 substitution noted) | None yet — no GitHub run of this head exists | P1 (phase-PR CI run, positive case); P6 (Recipe 4 negative demonstration) |
| CIMAINT-02 (grouped Dependabot updates) | `.github/dependabot.yml` (85-06) — three grouped, bounded, monthly ecosystems; `tests/test_dependabot_config.py` (8 tests) pins the shape; live Dependabot/uv docs rechecked at execution time (85-06) | None — Dependabot has never run against this config | P4 (first scheduled/triggered Dependabot run after merge; evidence stays with Plan 85-06 per the must-haves) |
| CIMAINT-03 (OS-package scan) | `os-scan-gate.cjs` + 29 tests implementing D-08..D-12 (85-07); Trivy 0.76.1 + actionlint 1.7.12 pins re-verified against the live advisory/releases, local baseline 0 blocking findings (85-12); wired as an unconditional-after-`docker` required job, joined to `ci-ready`/`REQUIRED_JOBS` together (85-15) | None yet — no GitHub run of this head exists | P1 (phase-PR CI run; `os-scan` job conclusion and added time) |
| CIMAINT-04 (actionlint, no-fake-skip) | `actionlint` job has no `needs`/`if`/`continue-on-error` (85-15); local `actionlint` run above: exit 0, zero findings; `findSkipConditions`/`requiredJobsFor` (85-02) prove by permanent test that no filter or condition lets any required job — including `actionlint` — be skipped while `CI ready` still passes | None yet | P1 (phase-PR CI run); P6 (Recipe 5 negative demonstration) |
| CIMAINT-05 (drop Python distributions) | `release.yml`'s dist download/verify/upload steps removed (85-10); `artifact-promotion.test.cjs`/`tests/test_github_workflows.py::test_release_workflow_has_no_python_distributions` assert no `dist/`/`.whl` text anywhere in the workflow; README/SECURITY.md updated to the source-tag install path (85-01) | None — no release has run under this change | P5 (next release's CHANGELOG states wheel/sdist are no longer attached) |
| CIMAINT-06 (coverage provenance) | `coverage-provenance.cjs` (buildProvenance/buildLocalProvenance/checkEvidence) + 33 tests (85-09); wired into `ci.yml`'s `test` job as a run-bound artifact behind a `set+e`/reassert-exit-code sequence that can never mask a real test failure (85-11); exact-head local coverage proof above, both `write-local` and `check` exit 0 | None yet — no CI coverage artifact exists for this head | P2 (download and check the CI coverage artifact once the phase PR runs; whether vibe-check's test-sufficiency lane discovers `coverage.xml`) |
| CIMAINT-07 (least-privilege publish) | `release.yml`'s sole `contents: write` moved into the new tag-only `github-release` job, `needs: [preflight, release]`; the `release` job itself narrowed to `packages: write, contents: read, actions: read` (85-10); `publication_bypass_violations()` extended with three structural checks | None — no main-push Release run has occurred under the narrowed permissions | P3 (first main-push Release run after merge: job permissions, `:main`/`:dev` publish success, digests) |
| ACCEPT-01 (readiness visibility) | `acceptance-readiness.cjs` (`readiness`/`renderChecklist`/`codexStatusFor`/`headTrustFor`) + 40 tests; `codex-fallback.cjs` (`validateFallback`) + 33 tests (both 85-14); `docs/owner-cli-acceptance.md` steps 1 and 5 both invoke it (85-17) | Not yet run against a real PR (the phase PR does not exist yet) | Readiness-check output for the actual phase PR, once opened, per the hand-off |
| ACCEPT-02 (keyed register, concurrency) | `assess()` keyed by `registerKey(prNumber, head)` rejecting drafts and schema-1 registers (85-05); `review-register.cjs` (`upsertSlice`/`verifyWrite`/`migrateSchema1`) with concurrent-update fixtures; `review-acceptance.yml` re-pinned to the schema-2 gate commit `8df9eaf9d68ad0e5fce469ef8393d05bb4ba3fc3` | None — the **live** `REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS` repository variables are still schema 1 as of this plan; the owner-approved `migrate --apply` run is hand-off step 12, not yet performed | The migration itself (hand-off step 12); the first real concurrent-PR proof in production |
| ACCEPT-03 (no-skip, classification-honoring checks) | `findSkipConditions`/`requiredJobsFor`/`aggregateCanPassWith` (85-02); four classification fixtures (ordinary-docs, sensitive-docs, mixed, misclassified) all pass with zero skip-path problems against the real `ci.yml`; D-01 ("no docs fast path") recorded in `.planning/REQUIREMENTS.md`/`.planning/ROADMAP.md` (85-01) and `docs/review-classification-policy.md` (85-16) | None yet for the real mixed case | P1 (the phase PR's own CI run is the real "mixed" case, per D-02) |

## D-07 status

D-07 ("bot PRs get no special review lane; a runtime dependency, Actions or
base-image change gets CI plus the paired BM + Codex review and exact-commit
owner acceptance") is **delivered now for trusted heads** and **not yet
delivered for untrusted heads**, honestly split as follows:

- **Trusted heads** (owner-authored PRs and local checkpoints): delivered.
  `verify_trust()` (85-13) independently checks `--trusted` against GitHub PR
  ownership (`gh pr view`, same-repository, author in `TRUSTED_AUTHORS`, head
  and base matching) or, for a local checkpoint, every commit in `base..head`
  having a `commit`-prefixed reflog entry on this machine — never the
  operator's own assertion, branch membership, or author/committer email.
  `codex-fallback.cjs`/`acceptance-readiness.cjs` (85-14) and the paired
  Codex contract docs (85-17) complete the trusted-head path end to end.
- **Untrusted heads** (bot PRs such as Dependabot, and outside-contributor
  fork PRs): **not yet delivered.** Per the owner's 2026-10-27 amendment to
  D-07 recorded in `85-CONTEXT.md` ("The isolated Codex review for untrusted
  heads... is split into Phase 85.1, because its security boundary kept
  failing plan checks on paper"; see also
  `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-CARRY-IN.md`),
  the isolated review that would let Codex run safely against an untrusted
  head's own code is deferred to Phase 85.1. Until that phase ships, the
  **interim rule** applies: `--untrusted` runs nothing — no checkout, no
  fetch, no tests, no Codex — and records exactly two files (`.meta.json`
  with `review_mode: "untrusted-refused"`, and an incomplete `.status.json`
  naming Phase 85.1 and the D-16 fallback), exiting 2 (85-13). CI still runs
  in full on every bot or fork PR. The owner then decides per PR: approve an
  independent fallback review recorded and validated with
  `.github/scripts/codex-fallback.cjs validate` (D-16, 85-14), or wait/retry
  later (both block acceptance). D-07 is delivered for untrusted heads by
  Phase 85.1, not by this phase.

No document in this phase claims that a bot or fork PR currently gets a
complete Codex review. Each Dependabot PR opened before Phase 85.1 ships is
reviewed under this interim rule (P4 below).

## ACCEPT-03 cases

Per D-02, verification of ACCEPT-03's no-skip mechanism across the four
classification cases uses a permanent test plus this phase's own PR — there
are no throwaway PRs:

- **ordinary-docs, sensitive-docs, misclassified** — proven by the permanent
  `.github/scripts/ci-job-consistency.test.cjs` fixture diffs (85-02): each
  of the three fixtures is run through `requiredJobsFor()` against the real
  `ci.yml`, confirming every required job still runs and nothing is
  skippable, with the `misclassified` fixture additionally proving that an
  added job-level `if:` is caught regardless of the change's claimed
  classification. These three cases are proved **by test, not by separate
  real GitHub runs** — per D-02's instruction, that is sufficient evidence
  for them.
- **mixed** — Phase 85's own PR (mixed docs + code + sensitive workflow
  changes) is the real GitHub run that proves this case. It is **PENDING
  until the phase PR is pushed** (hand-off step 7); this is the one case this
  phase's evidence record cannot yet show, by design (D-02).

The read-only ruleset check above (`gh api .../rulesets/14805779`) confirms
the three GitHub-required checks (`CI ready`, CodeQL, `Review acceptance`)
are unchanged and still the complete required-check set; ACCEPT-03's
no-skip guarantee operates entirely inside `CI ready`'s own required-job
list, which is why no ruleset change was needed or made (D-01).

## Pending — only GitHub can show

Every item below is explicitly **PENDING**. None is marked passed. Each
names the exact evidence to capture, per Phase 82 D-34 (PR head SHA, PR base
SHA, tested SHA with a reconciliation line, image/run identity where
applicable, run URL, run ID and attempt).

**P1 — Phase-PR CI run (positive cases + time budget).** Once the phase PR is
open: record the run ID/URL/attempt; every required job's conclusion,
including `os-scan`, `actionlint`, the lockfile-consistency step inside
`docker`, and the coverage-collection step inside `test`; and the added PR
wall-clock time versus the pre-phase CI baseline, against the ~5-minute
target (Phase 82 D-14/D-15/D-16). If the added time exceeds the target,
investigate and report the tradeoff to the owner before accepting it — never
silently expand the budget.

**P2 — CI coverage artifact, checked per reviewed/accepted head.** For each
head that is reviewed or accepted: `gh run download <run_id> -n
coverage-<run_id>-<run_attempt>`, then `node
.github/scripts/coverage-provenance.cjs check --provenance
coverage-provenance.json --coverage coverage.xml --expected-head <that head>
--expected-run-id <run>`. Record the result as separate CI evidence for that
head — it is never added to a review that already ran. For the restored
head's fresh review (hand-off step 11), use the CI artifact if its check
passes (including measured-source equivalence) and otherwise fall back to
exact-head local coverage; record whether the selected vibe-check's
test-sufficiency lane actually discovered `coverage.xml` (CIMAINT-06).

**P3 — First main-push Release run after merge (CIMAINT-07).** Record the run
ID/URL; the `release` job's actual permissions from its "Set up job" log
(expect `packages: write`, `contents: read`, `actions: read` — no `contents:
write`); confirmation that `:main` and `:dev` were pushed successfully to
`ghcr.io/thejuran/triggarr` (and any configured mirror) under the narrowed
permission; and the pushed image digests.

**P4 — First Dependabot run after merge (CIMAINT-02).** Open the repository's
Dependabot "Insights → Dependency graph → Dependabot" view or the equivalent
`gh api` endpoint, trigger "Check for updates" if offered, and record grouped
PRs or "no updates available" per ecosystem (uv, github-actions, docker),
plus any configuration error. This evidence stays with Plan 85-06's config
and its contract test, per the must-haves. Each Dependabot PR opened before
Phase 85.1 ships is reviewed under the interim rule (CI, `--untrusted`
INCOMPLETE record, owner-approved fallback per PR) and is never recorded as
having received a complete Codex review.

**P5 — Next release's CHANGELOG (D-14).** The next release's CHANGELOG entry
must say that Python wheel/sdist files are no longer attached as release
assets.

**P6 — CIMAINT-01/CIMAINT-04 negative demonstration on the phase PR
(85-18, Recipes 4 and 5).** The owner's go-ahead, the negative head's full
evidence table (PR head/base, tested SHA + reconciliation, run URL/ID/attempt,
every job's conclusion including the specific failure lines quoted in
`85-DEMONSTRATIONS.md`), the restore push, and the fresh review on the
restored head are all **PENDING**, to be filled in during the hand-off (step
9-11), never performed by this plan. `85-DEMONSTRATIONS.md` already carries
the full PENDING skeleton for this evidence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docker build substituted `linux/arm64` for the plan's
`linux/amd64` after an identical, already-documented QEMU segfault**
- **Found during:** Task 1, the local Docker build + lockfile consistency
  check step.
- **Issue:** `docker build --platform linux/amd64 -t triggarr:p85-19-final .`
  crashed inside the Dockerfile's `deps` stage the instant the pip-installed
  `uv==0.12.17` binary executed (`qemu: uncaught target signal 11
  (Segmentation fault) - core dumped`, exit 139) — the identical failure
  mode already recorded as a deviation in Plans 85-08 and 85-12's SUMMARY.md
  on this same machine (a QEMU-user/Rust-binary emulation incompatibility in
  this Docker Desktop install, not a Dockerfile or script defect).
- **Fix:** Built with `docker build --platform linux/arm64
  -t triggarr:p85-19-final .` instead (this Mac's native, non-emulated
  platform); it succeeded end to end. The lockfile consistency check then
  ran against that image, exactly as the `docker` job's steps do.
- **Cost if wrong:** The Debian-package-manager-level dependency set
  compared by the checker (`pip freeze` vs. the `uv export` of `uv.lock`) is
  architecture-independent for this image — the same pure-Python/sdist-only
  runtime dependencies resolve identically on arm64 and amd64. If an
  amd64-specific wheel resolution existed, this substitution could in
  principle miss a mismatch unique to it; no such risk is identified here,
  and the real, non-emulated amd64 answer arrives automatically once the
  phase PR's own CI run executes this exact step on GitHub's actual x86_64
  runners (P1).
- **Files modified:** none — this is a verification-method substitution, not
  a code change. No scan/build artifacts were committed; everything was
  written under `/tmp`, outside the repository, and removed after evidence
  capture.
- **Verification:** `docker build --platform linux/arm64 ...` succeeded; the
  full lockfile-consistency sequence above ran against the resulting image
  and exited 0; `git status --porcelain` was empty before, during and after.
- **Committed in:** this file's own commit (no separate code commit needed;
  nothing in the repository changed because of this substitution).

---

**Total deviations:** 1 auto-fixed (1 blocking — local verification platform
substitution, matching the precedent already recorded in Plans 85-08 and
85-12).
**Impact on plan:** No change to any committed file's content. The
substitution only affects which CPU architecture ran this plan's one-time
local proof; GitHub Actions' real amd64 runners settle the amd64-specific
question for free once the phase PR's CI run executes (P1).

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Plan: 19*
