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

## Phase PR classification — head 4f4783398e912 (pre-review)

```json
{"schema":1,"head":"4f4783398e912d0a7c4f37197462505382449d5e","classification":"code","classes_present":["code","sensitive","ordinary-docs"],"rationale":"Full range BASE b07e532dfd16a701b7631c6d7a3da6382960557d..HEAD 4f4783398e912d0a7c4f37197462505382449d5e (git diff --name-only, ~160 files). Sensitive files: .github/workflows/ci.yml, .github/workflows/release.yml, .github/workflows/review-acceptance.yml; .github/scripts/*.cjs (ci-job-consistency, release-policy, review-acceptance, review-register, codex-fallback, acceptance-readiness, coverage-provenance, os-scan-gate, artifact-promotion); .github/dependabot.yml; .github/os-scan-exceptions.json; tests/codex_review_run.py and tests/codex_report_status.py (the Codex harness and its schema/checker); docs/codex-adversarial-review-contract.md, docs/review-checkpoint-record.md, docs/review-classification-policy.md, docs/owner-cli-acceptance.md, docs/buildomator-greptile-pilot.md (review/acceptance/release policy); .claude/plugins/planchk-router/** (agent-routing hook); every *-PLAN.md phase/quick-task plan file under .planning/phases/ and .planning/quick/ (agent instructions BM executors follow, per Phase 85 D-17). Code files: Dockerfile, pyproject.toml, uv.lock, tests/test_*.py (test_image_lock_consistency, test_dependabot_config, test_ci_followon_wiring, test_github_workflows, test_acceptance_docs, test_review_checkpoint_record, test_review_machinery_lists, test_codex_review_contract, test_ci_gate). Ordinary-docs files: every *-SUMMARY.md, *-CONTEXT.md, *-RESEARCH.md, *-PATTERNS.md, *-DISCUSSION-LOG.md, *-VALIDATION.md, *-REVIEW*.md and this 85-REVIEW-EVIDENCE.md itself; README.md, SECURITY.md, docs/os-scan-policy.md, docs/ci-negative-demonstrations.md; .planning/PROJECT.md, .planning/STATE.md, .planning/ROADMAP.md, .planning/REQUIREMENTS.md, .planning/backlog/MAINTENANCE.md; the unpushed Phase 84 records, the quick 261026-s2v planning docs, and the raw Codex evidence artifacts under .planning/**/codex/** carried on this branch since before Phase 85 (excluded from the Codex review diff itself by the contract's own pathspecs, but still ordinary-docs for classification purposes). Per docs/review-classification-policy.md's Mixed changes rule, a PR with both code and sensitive content is classified code and still carries the full sensitive-content risk assessment; ordinary-docs content never dilutes either.","supersedes_head":null}
```

This record is reclassified on every new head (D-18): the hand-off's H1, H2
and H3 each need their own classification JSON against their own exact SHA,
not a copy of this one.

## RISK-01 note (pre-review)

- **Scope:** repository `thejuran/triggarr`, full range `BASE
  b07e532dfd16a701b7631c6d7a3da6382960557d .. HEAD
  4f4783398e912d0a7c4f37197462505382449d5e`. Affected behavior: every GitHub
  required-check job (`test`, `lint`, `docker`, `secrets`, `dependencies`,
  `image-smoke`, `browser-e2e`, `os-scan`, `actionlint`, `CI ready`); the
  Docker image's runtime dependency install path; `release.yml`'s publish
  permissions and the new tag-only `github-release` job; the acceptance
  gate's code (`review-acceptance.cjs`/`.yml`) and its pinned gate commit;
  the acceptance register's schema (1 → 2) and its migration; the Codex
  harness (`tests/codex_review_run.py`, `tests/codex_report_status.py`), its
  fixed prompt (now version 6), and its trust boundary. This review covers
  the whole PR, not a follow-up diff.
- **Risk: HIGH.** Per the blueprint's own risk table (`docs/bm-greptile-codex-blueprint.md`,
  "changes to safeguards/publication" row), this range changes exactly that
  category — CI required-job wiring, release publish permissions, the
  acceptance gate's pinned code, and the review-machinery that grades its
  own PR. This assessment is not adjusted downward to fit a smaller number
  — the actual content drives it high, not line count or file count.
  Concrete failure scenarios:
  1. **A silent required-job regression.** If the new `os-scan`/`actionlint`
     wiring (or the edited `test`/`docker` steps) introduced an unnoticed
     `continue-on-error` or an evaluable `if:`, a PR could pass `CI ready`
     while one of these checks never actually ran — exactly what
     `findSkipConditions` exists to prevent, but a defect in that detector
     itself would go unnoticed without independent review.
  2. **Unscanned image publication.** If `os-scan`'s `needs: [docker]` wiring
     were wrong, or the gate's exception-matching logic had an off-by-one in
     expiry math, a Critical/High vulnerability with a fix available could
     reach `:main`/`:dev` without blocking, defeating CIMAINT-03's whole
     purpose.
  3. **Broken `:main`/`:dev` publishing under narrowed permissions.** If the
     `release` job's narrowed `contents: read` actually needed `contents:
     write` for some step not yet exercised locally, the first real
     main-push Release run (P3) could fail outright, or — worse — fail
     silently in a way that still reports success.
  4. **The changed Codex grader accepting a hollow report.** Since this diff
     changes `tests/codex_report_status.py`, `tests/codex_review_run.py`,
     the schema, and the contract prompt together, a defect in the new
     base-commit cross-grade (`audited_inputs_changed_in_diff` /
     `materialize_grader`) could let a self-graded "complete" result through
     without the base checker's independent confirmation — exactly the
     self-grading risk this phase's D-18 work is meant to close.
  5. **Acceptance register migration ordering.** If the schema-1→2
     migration (hand-off step 12) ran against a register that still had a
     pending schema-1 write in flight, or ran before the gate code
     (`8df9eaf...`) actually merged to main, a later `assess()` call could
     reject a legitimate acceptance request or, worse, silently treat a
     missing slice as satisfied.
- **Recommended review:** BM **deep**, with a specialist focus on the
  review/acceptance machinery itself (not just the application code), plus
  the CI workflow files and the Dockerfile. Full-PR scope, not a targeted
  follow-up — the changes are too interconnected (e.g. CIMAINT-01's Dockerfile
  change and CIMAINT-06's coverage step both live inside the same `test`/
  `docker` jobs) to review piecemeal with confidence.
- **Required evidence:** the paired Codex pass (with its base-commit
  cross-grade recorded, since this diff changes grader files); the real
  phase-PR CI run (P1); the CIMAINT-01/CIMAINT-04 negative demonstrations on
  this exact PR (P6); and, after merge, the real Release run (P3) and the
  real Dependabot run (P4) — none of which this note can substitute for.
- **What this recommendation cannot establish:** that the amd64-specific
  behavior of the Docker/Trivy/actionlint steps matches what this plan
  observed on arm64 (see Deviations) — only a real GitHub Actions run on an
  actual x86_64 runner settles that; that the acceptance register migration
  will run cleanly against the live repository variables (untested outside
  this plan's unit fixtures); and that no human has yet seen the actual
  phase PR's diff rendered on GitHub, which can surface formatting or
  ordering issues no local check catches.

### RISK-02

**Recommendation:** vibe-check on the reviewed head (H1, per the hand-off),
full-PR scope, given the HIGH risk assessment above — specifically because
this range changes release-publish permissions and the review/acceptance
machinery's own grading code, the two categories the blueprint's risk table
names as the clearest HIGH-risk triggers. The owner's decision on whether to
run it is recorded in the checkpoint record after BM's review, per the
hand-off (step 4) — not here; this note only makes the recommendation.

## Disclosures

1. **The phase PR is graded by its own changed Codex grader and prompt.**
   This diff changes `tests/codex_report_status.py`, `tests/codex_review_run.py`,
   the schema, and `docs/codex-adversarial-review-contract.md` (now template
   version 6). Per Plan 85-13's `audited_inputs_changed_in_diff` mechanism,
   the runner records which of these changed and cross-grades the resulting
   report with the base commit's own (unchanged) checker, saved as a
   `.base-status.json`; the run reports complete only if both the head-side
   checker and the base checker agree. This is disclosed, not hidden, in the
   checkpoint record for every head in the hand-off.
2. **The PR changes the acceptance gate's pinned commit to a commit this
   same PR introduces.** `review-acceptance.yml` is now pinned to
   `8df9eaf9d68ad0e5fce469ef8393d05bb4ba3fc3` (Plan 85-05), a commit on this
   branch, not yet on `main`. This PR's own eventual `review-acceptance` run
   therefore uses the new gate code it is itself introducing. Independent
   inspection by the paired Codex pass (and Greptile, when it runs) is
   required precisely because of this; it is not treated as self-evidently
   safe merely because the unit tests pass.
3. **Greptile reviews this PR automatically while free credits last (D-03).**
   This is disclosed per the standing rule, not treated as unnecessary or as
   a reason to decline anything.
4. **The phase PR will carry one deliberately broken negative checkpoint
   head and one restore head (Plan 85-18).** Each is pushed only with the
   owner's separate go-ahead at execution time (Phase 82 D-10), never
   inferred from this document. Greptile may automatically review the first,
   broken, and restored heads (up to three reviews total on this PR) while
   its free credits last; this is disclosed here per D-03, and is not a
   reason to decline the demonstration. Acceptance applies only to the
   restored final head (H3), never to the deliberately broken one (H2).
5. **D-07 for bot and outside-contributor PRs is not yet delivered by this
   phase.** Until Phase 85.1 ships the isolated review, a bot or fork PR
   gets CI, an INCOMPLETE Codex record (`--untrusted` runs nothing; no
   PR-supplied base code is ever executed), and a per-PR owner-approved
   fallback review under D-16 (owner decision 2026-10-27, `85-CONTEXT.md`
   D-07 amendment). No part of this evidence record, or any other document
   in this phase, describes an untrusted head's Codex review as complete.

## Accepted residual risk (owner decision 2026-10-27)

Source: `85-REVIEW.md` iteration 4 (reviewed head `eae6d34`), WR-01 and WR-02.
The owner chose "Close cheap gaps, then stop": these two are recorded, not
fixed.

The static no-skip guard (`tests/test_required_jobs_no_skip.py`, with the
Node detector as a secondary line) is built to catch accidental and obvious
ways a required check could be skipped or switched off. It cannot rule out
someone deliberately tampering with the gate steps themselves:

- **WR-01:** adding `continue-on-error` to the "Fail if tests failed" step.
  The guard does report this, but in CI its own failure is reported through
  that same step, so the change would swallow the guard's failure and "CI
  ready" would still go green.
- **WR-02:** replacing the gate steps' inputs with hard-coded values
  (`RESULTS` on the `ci-ready` gate step, `TEST_EXIT` on "Fail if tests
  failed"), so the gate always sees success.

Both are covered by process rather than by a static check: every workflow
change is classified sensitive, gets BM code review with its paired Codex
pass, and needs the owner's acceptance of the exact commit. Possible future
hardening (backlog, `.planning/backlog/MAINTENANCE.md`): move the gate logic
into a tested script so its inputs and outcome can be checked directly.

## Post-plan review record (2026-10-27)

- **BM phase-execution review (standard depth):** iteration 1 at `b4a47b6` (2 critical, 4 warning); owner-approved fix rounds 1-4 with fresh BM reviews at `252fe61`, `094028e`, `eae6d34`; iteration 5 at `1f8e339` **clean** under the owner's stopping rule (no critical/warning outside the accepted class). Reports: `85-REVIEW.iter1.md` .. `85-REVIEW.iter4.md`, `85-REVIEW.md` (iteration 5), `85-REVIEW-FIX.md` (round 4).
- `ae8e4b2` merges `origin/main` (`decd5f1`, PR #35 merge commit) into the branch with no content change, so `origin/main` is an ancestor of the phase head (PR base / runner PR mode / readiness merge-base rule).
- **Paired Codex pass — local checkpoint refused (not run, nothing recorded):** `tests/codex_review_run.py --trusted` on `b4a47b6` exited 2 before reserving an output: "local checkpoint origin not established: 2948f9880466 was not committed on this machine". Cause: Plan 85-13's local-origin rule accepts only `commit:` reflog entries, but BM's parallel worktree execution lands plan commits through `merge worktree-agent-…` entries and deletes the worker branches (and their reflogs). Every worktree-executed phase therefore fails the local trust check by design. This is **not** a clean or complete Codex result.
- **Owner decision (2026-10-27, live):** run the paired Codex pass by PR URL after the end-of-phase push (`--trusted --pr-url <PR URL>`, trust established via GitHub for the owner's same-repo PR). Codex for this phase is **PENDING** until then; acceptance still requires a complete Codex pass on the final head. Follow-up recorded below.

## Post-execution deep review and BM iterations 6-7 (2026-10-28)

- **vibe-check `/deep-review` (4 deep passes, Codex joined each pass):** closed APPROVED at `d7889b8` (`.turingmind/REVIEW.md`, state archived). Fix commits: `bfe1e38` (runner PR-form `--base` must equal `git merge-base <PR base> <head>`, matching readiness), `0bd95dd` + `66b5581` (reviewer-name independence: rejoin and sub-run check single-letter runs), `0e5a08d` (PyYAML no-skip guard validates `review-acceptance.yml`'s `on:` block; Node detector accepts quoted trigger keys), `ca87b0e` (comment accuracy), `d7889b8` (generic `trigger_problems()`, `ci.yml` trigger contract). Each defect was reproduced and each fix verified by execution. Pass-4 Codex verdict: approve.
- **BM code review iteration 6** at `d7889b8` (standard, 8 changed files): 0 critical, 2 warning (WR-01 dry-run preview omitted the merge-base command; WR-02 `ClaudeCode`/`BM2`/`claude2` accepted), 2 info. Report `85-REVIEW.iter6.md`. Fixes `06ac793` (WR-01, parity test) and `684ae13` (WR-02, camelCase/acronym/letter-digit split); fix report `85-REVIEW-FIX.md` (round-4 report kept as `85-REVIEW-FIX.iter4.md`).
- **BM confirming review iteration 7** at `684ae13`: both fixes confirmed, no regressions; 1 new warning (case-only run-together names `claudecode`, `bmreviewer`, `codexreviewrun` still accepted), 2 info carried. Report `85-REVIEW.md`.
- **Accepted residual risk (owner decision 2026-10-28):** the fallback reviewer-name check (`codex-fallback.cjs` `reviewerNameIsDisallowed`) is a best-effort sanity check over a free-text field, not the control. Deliberately spoofed or mixed spellings (multi-letter fragment splits such as `Cla Ude`, mixed forms such as `X c.o.d.e.x review run`, and iteration 7's case-only run-together names) and false positives on human initials (`B. M. Smith`, SA-06 digit-split cases) are accepted. The control is the owner's verbatim approval of every fallback record. The Dependabot `REVIEW_*` variables question (impact NV, `review-acceptance.yml:33`) is deferred until the first monthly Dependabot PR.
- **Local suite at `e2634b7`:** pytest 2686 passed, node 433 passed, ruff clean. Docker build not run locally (CI runs it).
- **Paired Codex pass:** still **PENDING** — by PR URL after this push, per the 2026-10-27 owner decision. Not reported as clean.

## Hand-off after the last plan

Every step below is marked **not performed by any plan** — this plan writes
the sequence; it does not execute any of it. Head names used throughout: H1
= the final local head after BM review and any fix round; H2 = H1 plus the
demonstration commit; H3 = H2 plus its revert and the evidence commit (the
restored final head).

1. **Not performed by any plan.** Exact-head coverage before the review
   snapshot (checker B09): on a clean checkout of H1, generate coverage and
   run `coverage-provenance.cjs write-local --head <H1>` and `check
   --expected-head <H1>` — the exact procedure this plan proved above on its
   own head. Keep `coverage.xml` ready for the vibe-check worktree root. If a
   later fix round changes the head, redo this for the new head (or reuse
   only if `check --expected-head <new head>` passes on measured-source
   equivalence).
2. **Not performed by any plan.** `execute-phase`'s `code_review_gate` runs
   BM's phase-execution review on H1.
3. **Not performed by any plan.** `git fetch origin main` (the runner
   requires `BASE` on `origin/main`), then the paired Codex pass on H1 per
   the contract (`--trusted --pr-url "none (local checkpoint, not pushed)"`,
   label `phase`); expect `audited_inputs_changed_in_diff` to list the
   changed grader files and a `.base-status.json` to be written. One
   automatic retry; if it stays INCOMPLETE/PENDING, the owner chooses
   wait/retry-later (both block) or an owner-approved fallback recorded and
   validated with `.github/scripts/codex-fallback.cjs`.
4. **Not performed by any plan.** Present the RISK-02 vibe-check
   recommendation above and record the owner's decision; if selected, the
   owner runs vibe-check locally on H1 with the step-1 coverage.xml at the
   worktree root, before the push.
5. **Not performed by any plan.** Offer `/deep-review` before pushing
   (`CLAUDE.md`).
6. **Not performed by any plan.** Any confirmed defect: one batched fix
   round, then steps 1-4 again on the new head (re-bump the
   `review-acceptance` pin if `review-acceptance.cjs` changed again); that
   new head becomes H1.
7. **Not performed by any plan.** The end-of-phase push of `ci-followon` at
   H1 (never `--force`, never `main`) and `gh pr create` ready for review
   (not draft) with the classification, risk level and disclosures above
   (including the planned negative/restore pushes and Greptile) in the body,
   ending with the Claude Code attribution line.
8. **Not performed by any plan.** Post H1's checkpoint comment per
   `docs/review-checkpoint-record.md` (Codex/BM/vibe-check results from the
   local checkpoint, labelled with H1; PR head must equal H1). Record **P1**
   for H1's CI run (positive cases, ~5-minute budget check) and **P2** for
   H1's CI coverage artifact as separate CI evidence — it is not added to
   H1's own review.
9. **Not performed by any plan.** Negative demonstration (**P6**, Phase 82
   D-10): present the go-ahead request already written in
   `85-DEMONSTRATIONS.md` and record the owner's verbatim answer. Only on
   go-ahead: `git apply 85-DEMO-NEGATIVE.patch` on H1, commit "demo(85): DEMO
   ONLY — deliberate lockfile mismatch and bad workflow (reverted next
   push)", push (= H2; never `--force`, never `main`, never a tag). Watch
   the CI run; record PR head, PR base, tested SHA + reconciliation, run
   URL/ID/attempt, job conclusions and the specific failure lines — require
   the docker consistency step's `version mismatch: idna lock 3.15 image
   3.4`, actionlint's `property "missing" is not defined in object type {}
   [expression]`, `CI ready` failed, and no Release run. Never approve H2's
   `review-acceptance` run. If any expectation is not met, stop and report
   to the owner — no further push without a new owner decision. If the
   owner declines, record "not demonstrated on GitHub (owner declined on
   <date>); local evidence only" in `85-DEMONSTRATIONS.md` as a local commit
   that is held, not pushed (docs-only commits ride with the next
   substantive push), skip steps 10-11, and continue at step 12 with H1 as
   the final head: H1's review and checkpoint from steps 2-8 stand, and P1
   for H1 must be complete.
10. **Not performed by any plan.** Restore push: `git revert --no-edit <demo
    commit>`, commit the filled `85-DEMONSTRATIONS.md` evidence, push once
    (= H3; never `--force`). Record any Greptile reviews of H2/H3 in the
    disclosure.
11. **Not performed by any plan.** Fresh review of the restored final head
    H3 (nothing carried over from H1 or H2): wait for H3's CI run (P1 for
    H3: all jobs green, budget); prepare coverage for H3 (its CI artifact if
    `check --expected-head <H3>` passes, otherwise exact-head local
    coverage) before the review snapshot; BM review of H3; paired Codex pass
    on H3 by PR URL after `git fetch origin main` (`--trusted --pr-url <PR
    URL>`; owner-authored same-repo PR whose head and base match GitHub)
    with the same retry/fallback rules as step 3; present a fresh RISK-02
    vibe-check recommendation for H3 and record the owner's decision; post
    H3's checkpoint comment with its own classification.
12. **Not performed by any plan.** Owner go-ahead (a safeguard change to the
    live registers), then run `node .github/scripts/review-register.cjs
    migrate --kind dispositions --apply` and `--kind blockers --apply` after
    saving the current schema-1 values into this file.
13. **Not performed by any plan.** Write the final head's register slices
    (H3, or H1 if the demonstration was declined) with `review-register.cjs`,
    run `acceptance-readiness.cjs` for that head (with `--fallback` only if a
    validated fallback exists), and only when it reports ready present the
    D-12 checklist and follow `docs/owner-cli-acceptance.md` — never infer
    or submit approval without the owner's explicit words.
14. **Not performed by any plan.** Merge is the owner's decision and must
    use a merge commit (not squash), so the pinned gate commit stays on
    `main`.
15. **Not performed by any plan.** After merge, complete **P3**, **P4** and
    **P5** and update STATE/ROADMAP truthfully.

### Confirmation: nothing autonomous happened in this plan

This plan made no `git push`, no `gh pr create`, no `gh variable set`, and no
`pending_deployments` call of any kind. The only `gh api` calls made were the
three read-only GET requests recorded under "Read-only GitHub checks" above
(ruleset, code-scanning default-setup, `allow_auto_merge`) — none of them
wrote anything. This is also stated in this plan's own SUMMARY.md.

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
