# Phase 85: Follow-on CI Improvements & Acceptance Usability - Research

**Researched:** 2026-10-27
**Domain:** GitHub Actions CI/CD hardening (Docker/uv dependency consistency, Dependabot, OS-package vulnerability scanning, workflow linting, coverage evidence, least-privilege release permissions) + GitHub-side review-classification enforcement + concurrency-safe acceptance registers + review-tooling hardening (Codex harness)
**Confidence:** HIGH for stack/APIs verified against official docs and the live repo; MEDIUM for exact CI timing/overhead estimates; LOW (flagged `[ASSUMED]`) for anything requiring a live GitHub Actions run to confirm (e.g. exact runner Node version, GHCR package-link state)

## Summary

This phase extends the Phase 82 CI baseline (`ci.yml`/`release.yml`/`ci-job-consistency.cjs`/`release-policy.cjs`) and the Phase 83 review-classification policy (`docs/review-classification-policy.md`) rather than building anything new from scratch. Every one of CIMAINT-01..07 and ACCEPT-01..03 has a concrete, low-risk implementation path that reuses an existing pattern already live in this repository: pinned-version tool invocation (`uvx --from pip-audit==2.10.1 ...`), stdlib-only Node test scripts (`ci-job-consistency.cjs`, `release-policy.cjs`), the `set +e / capture / set -e` pattern already used in `browser-e2e`, and the exact-artifact-promotion discipline already enforced in `release.yml`.

Three findings materially change the plan shape versus a naive reading of the roadmap:

1. **Do not use `aquasecurity/trivy-action` or `aquasecurity/setup-trivy`.** Both GitHub Actions were directly compromised in March 2026 (CVE-2026-33634, GHSA-69fq-xp46-6x23) — a malicious Trivy binary was published and 76 of 77 `trivy-action` git tags were force-pushed to credential-stealing commits. This is not a generic "pin by SHA" footnote; it is the exact failure mode CIMAINT-03's "Claude's Discretion: pin it by version/SHA" note is warning about. The researched recommendation is to install the Trivy **CLI binary** directly (pinned version + committed SHA-256 checksum), the same pattern already used for Tailwind CSS and `pip-audit` in this repo, and never depend on a third-party Action for this job.
2. **`--ignore-unfixed` cannot be used as specified.** D-09 requires Critical/High findings with no fix to be *reported, not hidden*. Trivy's `--ignore-unfixed` flag removes them from the output entirely, which violates D-09. The design needs a single full (unfiltered) `trivy image --format json` scan, parsed by a small Node/Python script (same pattern as `ci-job-consistency.cjs`) that classifies findings into "blocks" (Critical/High + fix available, no valid exception) vs. "reports only" (everything else), and writes all of them to the job summary.
3. **`coverage.xml`'s consumer (vibe-check's `test-sufficiency` lane) discovers the file by a fixed repo-relative glob (`coverage.xml`, `cobertura-coverage.xml`, `cobertura.xml`) inside the worktree being reviewed, not by artifact name.** This pins the exact on-disk filename CI must produce and confirms the SHA-binding problem is real: a `pull_request` trigger's `github.sha` is the **synthetic merge commit**, not the PR head, so the coverage artifact must carry an explicit provenance record distinguishing `github.event.pull_request.head.sha` from `github.sha`.

**Primary recommendation:** Treat this phase as "harden seven independent CI jobs/configs + three acceptance-usability scripts + one Codex-harness hardening pass," not as one integrated system — each CIMAINT/ACCEPT item maps to one bounded diff against an existing file, verified by a Node-stdlib test in `.github/scripts/*.test.cjs` plus a real-or-fixture-based negative case, exactly like Phase 82's pattern.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Docker image dependency installation (CIMAINT-01) | CI/Build pipeline | Docker image (runtime) | The *install* step runs in the image build; the *consistency check* (lockfile vs. installed) runs in CI, not at runtime |
| Dependency/Action/base-image update PRs (CIMAINT-02) | CI/Build pipeline (Dependabot, GitHub-native) | — | Entirely a GitHub platform feature (`.github/dependabot.yml`); no application code involved |
| OS-package vulnerability scan (CIMAINT-03) | CI/Build pipeline | Database/Storage (exception file is committed repo state) | Scan runs against the already-built image artifact in CI; the exception file is reviewed repo content, not runtime config |
| Workflow lint (CIMAINT-04) | CI/Build pipeline | — | Static analysis of `.github/workflows/*.yml`; never touches the app |
| Python distribution smoke test / drop decision (CIMAINT-05) | CI/Build pipeline | — | Pure release-artifact concern; D-14 removes this tier's deliverable entirely |
| Coverage evidence (CIMAINT-06) | CI/Build pipeline | — | Artifact generation in CI; consumed by a *separate* local review tool (vibe-check), not by the running app |
| Least-privilege publish permissions (CIMAINT-07) | CI/Build pipeline | — | `GITHUB_TOKEN` permissions are a workflow-file concern only |
| PR ready-state visibility (ACCEPT-01) | CI/Build pipeline | API/Backend (GitHub REST API calls from `review-acceptance.cjs`) | Reads GitHub's own check/PR state; no app server involved |
| Concurrency-safe acceptance register (ACCEPT-02) | CI/Build pipeline | Database/Storage (GitHub repo variables as the register) | The register *is* storage (`vars.REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS`), read/written only by workflow scripts |
| GitHub required-check classification honoring (ACCEPT-03) | CI/Build pipeline | — | Per D-01, resolved as "no new mechanism" — required checks stay unconditional; the "mechanism" is a test proving no skip path exists |
| Codex harness hardening (D-16..D-18) | CI/Build pipeline (review tooling, not shipped product) | — | `tests/codex_review_run.py`/`codex_report_status.py` are developer/review tooling that never ships in the Docker image |
| planchk-router tests in CI (D-13) | CI/Build pipeline | — | `.claude/plugins/planchk-router` is repo tooling, not the Triggarr application |

No capability in this phase touches the Browser/Client or Frontend-SSR tiers — this is exclusively a CI/Build-pipeline and repo-governance phase, consistent with the roadmap's framing ("extends the Phase 82 baseline," "builds no orchestrator").

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Docs-only check path (ACCEPT-03)**
- **D-01:** No docs fast path. Every PR runs every required check, whatever its classification. (a) A classification can never reduce or skip a GitHub required check. (b) GitHub requires nothing that the policy exempts ordinary docs from. Required checks today are `CI ready`, CodeQL and Review acceptance. Greptile has been optional since 2026-10-22, and Codex and vibe-check run locally. Rationale: under D-13 (no docs-only PRs), docs never arrive alone. A content-classifier fast path would add a new safeguard component that carries misclassification risk, all to save CI minutes on a case that hardly occurs. The planner amends the ACCEPT-03 wording in `.planning/REQUIREMENTS.md` and Phase 85 criterion 7 in `.planning/ROADMAP.md` to record this owner decision (2026-10-26). The pattern is the D-14 amendment from Phase 83. Update `docs/review-classification-policy.md`'s "GitHub does not yet check it (Phase 85, ACCEPT-03)" status line to match.
- **D-02:** Verification uses a permanent test plus this phase's own PR. There are no throwaway PRs. Extend the existing workflow/job-consistency tests (`.github/scripts/ci-job-consistency.cjs` and its tests). The test fails if anyone adds a path filter, `paths-ignore`, a file-type condition or another skip condition that could let any PR bypass a required job or let `CI ready` pass without it. Run fixture diffs for all four cases through it: ordinary-docs, sensitive-docs, mixed docs+code, and misclassified (claims ordinary docs but contains code). Phase 85's own PR (mixed docs + code + sensitive workflow changes) is the real GitHub run. Record in the evidence that three of the four cases are proven by test, not by separate real GitHub runs. Per Phase 82 D-03/D-04, each negative case asserts its specific rejection reason and feeds input to the same script CI invokes.
- **D-03:** Greptile still runs automatically on every PR while free credits last. Disclose this in the PR as the standing rule requires; don't describe it as unnecessary.

**Automated update PRs (CIMAINT-02)**
- **D-04:** Routine update PRs open monthly.
- **D-05:** Updates are grouped per ecosystem, with major versions split out. Up to three grouped PRs per cycle: uv/Python dependencies; SHA-pinned GitHub Actions (updates must keep full-SHA pins with version comments); Docker base image. Each group holds the minor/patch bumps. A major-version bump gets its own PR. Set an open-PR limit so a backlog can't pile up. No auto-merge, ever.
- **D-06:** Security updates open right away as separate PRs, outside the monthly cycle.
- **D-07:** Bot PRs get no special review lane. They are classified by content like any PR. A runtime dependency, Actions or base-image change is consequential, so it gets CI plus the paired BM + Codex review and exact-commit owner acceptance. Before choosing exact configuration, recheck current Dependabot ecosystem support for uv, github-actions with SHA pins, and docker, plus grouping and cooldown behavior (per the CI baseline plan).

**OS-image security scan (CIMAINT-03)**
- **D-08:** A vulnerability blocks when it is Critical or High severity and a fix is available. Lower severities are reported, not enforced.
- **D-09:** Critical and High vulnerabilities with no fix available are reported in the CI summary and don't block.
- **D-10:** Exceptions require owner approval and expire after at most 30 days. Each exception is an entry in a repository file: vulnerability ID, affected package, reason, owner approval, and expiry date. An expired exception blocks again automatically. An exception with no expiry, or with an expiry more than 30 days out, is rejected. Adding or changing an exception is a sensitive change and goes through normal review. The written policy (severity, fix availability, scanner errors, exceptions) is committed **before** the gate is enforced.
- **D-11:** The gate applies everywhere: it is part of `CI ready` on PRs, main pushes and releases, so a publishable image always passed the scan. The response to an overnight red is a base-image rebuild (via the update PRs) or a 30-day exception.
- **D-12:** Scanner errors fail closed. Examples are a DB download failure or an unparseable result. This matches the existing `pip-audit --strict` job. The scan runs against the exact audited image artifact. It uses one OS-package scanner, which must not duplicate pip-audit's Python coverage as a second equivalent gate.

**Scope edges**
- **D-13:** The planchk-router plugin tests join CI. This was the owner's decision on 2026-10-26, carried from quick 261026-s2v. Run `node --test .claude/plugins/planchk-router/test/planchk-router.test.mjs` with an explicit file path or glob; on Node 25.9, `node --test <dir>/` does not recurse.
- **D-14:** The owner drops the Python distributions (2026-10-26). Releases ship the Docker image only. Remove the wheel/sdist release assets: `dist/*` in `release.yml`'s `gh release create`/`upload`, and the related build/assert steps in CI wherever they exist only for distribution. Record this decision as CIMAINT-05's outcome in REQUIREMENTS/ROADMAP. No clean-install wheel smoke test is built. Check that nothing else consumes `dist/`, such as release-policy tests or artifact checks, before removing it. Update those tests rather than leaving dangling assertions. Existing releases' assets are left untouched.

**Folded carry-forward (from `.planning/backlog/MAINTENANCE.md` → "Phase 83 carry-forward to Phase 85")**
- **D-15:** The owner folded in all three carry-forward groups offered. Items not listed below stay in the backlog: the card-template text-matching refactor (product code) and the craft-skill `code-reviewer` sticky accept (needs separate clone approval). When an item is completed, remove it from MAINTENANCE.md or mark it resolved.
- **D-16:** Codex fallback definition (round-7 WR-01 + IN-01 + IN-02): Define what counts as an owner-approved fallback when a paired Codex pass stays INCOMPLETE/PENDING, and add a field in the checkpoint record to capture it. State explicitly in the contract and record docs that "wait" and "retry later" block acceptance. Add the paired Codex review to the pilot checklist's approval precondition. Vibe-check must not be named as a Codex substitute in a way that contradicts the checkpoint record. Resolve the contradiction.
- **D-17:** Review-list drift guard (arch-1 + SA-03): Add one test asserting that three hand-kept lists of review-machinery files agree: the classification policy's sensitive row, the Codex scope exclusions, and the acceptance-prerequisite list. Treat `*-PLAN.md` files as agent instructions (sensitive) for classification. Align the Codex review diff's blanket `.planning/**/*.md` exclusion accordingly.
- **D-18:** Codex runner hardening. All items are in review tooling: `tests/codex_review_run.py`, `tests/codex_report_status.py`, the schema and the contract prompt.
  - A changed checker, runner, schema or prompt must not be the only grader of its own PR. Add a base-checker run and/or an `audited_inputs_changed_in_diff` record (WR-03/ARCH-03/impact-001).
  - Verify `--trusted` independently instead of trusting the operator (SA-01).
  - SIGTERM/SIGHUP must not leave the Codex/pytest process group orphaned (round-6 WR-01).
  - Put a time limit on the post-kill output drain (bugs-002).
  - A `null` exit_code or a trivial command must not count as evidence (hollow-report guard).
  - Log, rather than silently skip, a `getpass.getuser()` failure in `redact_local_paths()`.
  - Correct the overclaiming docstring, and redact home paths in future raw `.jsonl`/`.last.json` output (WR-04). Already-committed raw evidence stays as published.
  - `_write_evidence_copy` cleans up the empty directory it leaves when `os.open()` fails (rm-001).

  Each fix gets a focused regression test. Because this phase changes the review machinery, the D-18 audited-inputs mechanism should be in place before the phase's own final Codex pass relies on it. Otherwise, disclose that the phase PR's grader was changed in the same diff.

**Acceptance usability (ACCEPT-01, ACCEPT-02), Claude's approach as presented to the owner**
- **D-19:** The register lives today in two repository-wide variables, `REVIEW_DISPOSITIONS` and `REVIEW_BLOCKERS`, which `review-acceptance.yml` reads. With concurrent PRs, one PR's update can overwrite another's. Key every entry by PR number + full head SHA so one PR's update can't erase another's evidence or satisfy another's gate. Prove this with tests that use concurrent-update fixtures. Until that proof exists, serialize final acceptance updates and document the rule in `docs/owner-cli-acceptance.md` / `docs/buildomator-greptile-pilot.md`. SHA binding is unchanged. Changing the pinned gate commit in `review-acceptance.yml` is a safeguard change that needs independent inspection.
- **D-20:** ACCEPT-01: before final approval is requested, the PR is marked ready and the machine-checkable prerequisites are visible in one place. Prerequisites: CI on the head, Codex status, dispositions written, register entries present. This avoids an approval that fails because of a missing record, followed by a repeat approval. Build it on the existing D-12 (Phase 83) acceptance checklist; don't build a new orchestrator.

**Carried forward (locked in earlier phases, not re-asked)**
- Phase 82 evidence standard (D-01..D-10, D-34): Negative tests pass only on the specific expected rejection, and use the same entry points CI invokes. Wiring is tested separately from function behavior. A claim that GitHub enforces something needs a real GitHub run. Every deliberately broken push needs the owner's separate go-ahead at execution time. Never main, never a production tag. Evidence records PR head, base and tested SHA separately, with a reconciliation line. This matters for CIMAINT-06's head-vs-merge-commit binding.
- Phase 82 D-14/D-15/D-16: there is a ~5-minute added-PR-time target. If added time exceeds it, investigate and report the tradeoff to the owner before expanding the budget. No retries that turn a failure into a pass. Never remove required coverage to get green.
- Phase 83 D-13 and memory: one branch (`ci-followon`, cut 2026-10-26 from `codex-plan-checker` at `2682386`, carrying the unpushed Phase 84 records and quick 261026-s2v); one PR at phase end; no docs-only PRs; batched pushes, with docs commits held until the next substantive push.
- Phase 83 review workflow: paired BM + Codex on every BM review run; PR classification recorded per head; RISK-01 note and vibe-check recommendation when risk is high; exact-commit owner acceptance via `review-acceptance`. This phase edits workflows, acceptance policy and review machinery, so expect a **high** risk assessment.

### Claude's Discretion

- OS-package scanner choice. One scanner only; pin it by version/SHA. Recheck current tools.
- How the Dockerfile consumes `uv.lock` (CIMAINT-01). Compiled Tailwind assets and runtime behavior stay unchanged. Design the lockfile/image consistency check so that a deliberately mismatched lockfile fails it.
- actionlint wiring, and the "skip when workflows are unchanged can't fake a pass" rule (CIMAINT-04). Example: `CI ready` verifies that the lint job either ran or was legitimately not needed, decided by a check that can't be bypassed.
- Coverage tooling and artifact naming (CIMAINT-06): branch coverage; no percentage gate; test failure exit status preserved; artifact bound to tested SHA + run, recording PR head vs synthetic merge; generated files kept out of commits; test-runtime overhead recorded; discoverable by vibe-check's test-sufficiency lane; a wrong-commit or missing report rejected as evidence.
- How the release job is split for least privilege (CIMAINT-07). Only tagged GitHub Release creation holds `contents: write`. Demonstrate a successful `:main`/`:dev` publish under the narrower permission, without building an orchestration framework.
- Exact Dependabot keys, open-PR limits and schedule day.
- Plan/wave structure. The phase is large: 10 requirements plus three carry-forward groups.

### Deferred Ideas (OUT OF SCOPE)

- **Docs-only CI fast path**: rejected for now (D-01). Revisit only if docs-only changes ever become common, which would also require revisiting D-13.
- **Wheel clean-install smoke test**: not needed because distributions are dropped (D-14). Revisit if a pip/PyPI install path is ever added.
- **Remaining backlog items** stay in `.planning/backlog/MAINTENANCE.md`: the card-template text-matching refactor and the craft-skill `code-reviewer` sticky accept (needs separate clone approval).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CIMAINT-01 | Docker image installs runtime deps from `uv.lock`, compiled frontend/runtime behavior unchanged | `uv`'s own Docker guide (verified via WebFetch) gives the `uv sync --locked`/`--no-install-project` pattern; the lower-risk variant for this repo's existing `pip install .` structure is `uv export --locked --no-dev --no-emit-project --no-hashes` + `pip install --no-deps`, mirroring the *already-live* `dependencies` job exactly. Consistency check design (diff exported lock vs. `image-requirements.txt`) reuses the existing `docker` job's `pip freeze` artifact. |
| CIMAINT-02 | Grouped, bounded update PRs for uv/Actions/Docker; no auto-merge | Verified via WebSearch + GitHub changelog: Dependabot GA for `uv` version updates (2025-03-13) and security updates (2025-12-16); `groups`/`applies-to`/`cooldown`/`open-pull-requests-limit` semantics confirmed, including the Docker/Actions `cooldown` restriction (only `default-days` works, not `semver-*-days`) and Dependabot's native SHA-pin-plus-comment update support for `github-actions` (since 2022, still current). |
| CIMAINT-03 | OS-package scan with severity/fix/scanner-error/exception policy, no scanner duplication | Scanner choice (Trivy) and invocation flags (`--pkg-types os`, not deprecated `--vuln-type`) verified via WebSearch against `trivy.dev` docs discussion threads; `.trivyignore.yaml`'s native `expired_at` field verified; the March 2026 `trivy-action`/`setup-trivy` compromise (CVE-2026-33634) is the decisive reason to install the CLI binary directly rather than use either Action. |
| CIMAINT-04 | actionlint runs on workflow changes; skip can't fake required-gate pass | Verified: actionlint v1.7.12 (2026-03-30) is the current upstream release and is installed locally for cross-check; pinning options (binary+checksum vs. Docker digest vs. third-party Action) researched with tradeoffs. Recommended design: make the job **unconditional** (always runs; cheap), which trivially satisfies "a skip can't fake a pass" without new skip-detection logic — matches the `ci-reference-baseline-plan.md` "avoid custom orchestrators" guidance. |
| CIMAINT-05 | Wheel/sdist dropped per D-14; remove dist-only CI/release steps and dangling test assertions | Confirmed via grep: `artifact-promotion.test.cjs`'s `'both exact-run artifacts are downloaded...'` test explicitly asserts 2 `run-id:` references and the two dist-only step names — this test (not just the workflow) must be edited, or it will fail after removing the dist download steps. |
| CIMAINT-06 | Branch-coverage `coverage.xml` bound to exact SHA+run, no % gate, discoverable by vibe-check | Verified directly from the installed vibe-check plugin (`~/.claude/plugins/cache/thejuran/vibe-check/2.12.0/phases/deep-review/01d-coverage.md` + `agents/test-sufficiency.md`): discovery globs are `coverage.xml`/`cobertura-coverage.xml`/`cobertura.xml` at repo-relative paths in the **worktree being reviewed** — this pins the required on-disk filename. pytest-cov 7.1.0 (current, PyPI-confirmed) + `--cov-branch --cov-report=xml` verified via WebSearch against pytest-cov's own docs. |
| CIMAINT-07 | `:main`/`:dev` publish needs only `packages: write`+`contents: read`; only tag-triggered GitHub Release holds `contents: write` | Verified via WebSearch against GitHub's own permissions docs: `packages: write` is sufficient for GHCR push; `contents: write` is required only for `gh release create`. Confirmed the current single `release` job in `release.yml` holds both unconditionally and must be split into two jobs with job-level `permissions:` and `needs:`-based output passing. |
| ACCEPT-01 | PR ready + visible machine-checkable prerequisites before approval is requested | `docs/review-checkpoint-record.md`'s existing "Owner acceptance checklist" template (D-12, Phase 83) already lists exactly these fields (BM, Codex, Greptile, vibe-check, CI, findings/dispositions, incomplete items) — this phase assembles/automates presenting that checklist plus a `ready_for_review` check, not a new design. |
| ACCEPT-02 | Register handles concurrent PRs without cross-PR overwrite, or updates are serialized | Read `.github/scripts/review-acceptance.cjs`/`.yml` directly: today's register is two **repository-wide** variables (`REVIEW_DISPOSITIONS`, `REVIEW_BLOCKERS`) with no PR/head keying at all — confirms D-19's premise exactly. `gh variable set` is a whole-value overwrite (no merge/patch primitive), which is the root concurrency hazard and the reason D-19 allows "serialize until proven" as a valid interim state. |
| ACCEPT-03 | GitHub required checks honor Phase 83 classification without weakening protection | D-01 resolves this to "no new skip mechanism" — required checks (`CI ready`, CodeQL, Review acceptance) always run in full. The only code change is a **permanent negative test** in `ci-job-consistency.cjs` proving no skip condition (`paths-ignore`, file-type `if:`, etc.) exists anywhere in `ci.yml`, run against four fixture diffs (ordinary-docs/sensitive-docs/mixed/misclassified). |
| D-13 (carry-forward) | planchk-router tests join CI | Confirmed 11 tests in `.claude/plugins/planchk-router/test/planchk-router.test.mjs`, stdlib-only (`node:test`), already pass locally on Node v25.9.0; CI's `lint` job's `node --test .github/scripts/*.test.cjs` glob must be extended with an explicit second path (not a directory glob, since `node --test <dir>/` does not recurse on this Node version). |
| D-16..D-18 (carry-forward) | Codex fallback definition, review-list drift guard, Codex runner hardening | All 8 D-18 sub-items located and confirmed present/absent by direct code reading of `tests/codex_review_run.py` and `tests/codex_report_status.py` (see Common Pitfalls and Code Examples below for exact line-level findings). |
</phase_requirements>

## Standard Stack

### Core

| Tool/Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `trivy` (CLI binary, not the GitHub Action) | `0.76.1` (current as of 2026-10-21) `[ASSUMED — recheck at execution time against https://github.com/aquasecurity/trivy/releases]` | OS-package vulnerability scanning of the shipped image tarball | Industry-standard scanner with native `docker-archive`/`--input` tarball support, `--pkg-types os` filtering (avoids duplicating `pip-audit`), and a native `.trivyignore.yaml` exception format with a built-in `expired_at` field — the only scanner researched that gives D-10's expiry requirement a native enforcement hook |
| `pytest-cov` | `7.1.0` `[VERIFIED: PyPI registry — confirmed via pip index and WebSearch cross-reference against pytest-cov's own docs]` | Branch coverage + `coverage.xml` (Cobertura) generation during the existing `pytest tests/` run | Already the de facto pytest coverage plugin; 7.1.0 is the first line confirmed compatible with pytest 9.x (this repo already pins `pytest>=9.0.3`) |
| `coverage` (pytest-cov's dependency) | `>=7.10.6` `[CITED: pytest-cov 7.1.0 changelog/docs]` | Underlying coverage engine; branch coverage support | Required floor for pytest-cov 7.x; `coverage>=7.10.6` is pulled in transitively, no direct pin needed unless a stricter floor is wanted |
| `actionlint` (binary, pinned + checksummed) | `1.7.12` (2026-03-30) `[VERIFIED: locally installed via Homebrew, matches upstream rhysd/actionlint release tag]` | Static lint of `.github/workflows/*.yml` | De facto standard GitHub Actions workflow linter; shells out to `shellcheck` automatically for `run:` step bash when shellcheck is on `PATH` (GitHub's `ubuntu-latest` runner image ships `shellcheck` by default `[ASSUMED — recheck runner image tool manifest at execution time]`) |

### Supporting

| Tool | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dependabot.yml` (`package-ecosystem: uv`) | GitHub-native, GA since 2025-03-13 (version updates) / 2025-12-16 (security updates) `[CITED: github.blog changelog]` | Grouped uv/Python dependency updates | CIMAINT-02's uv group |
| `dependabot.yml` (`package-ecosystem: github-actions`) | GitHub-native | Grouped SHA-pinned Action updates, with automatic version-comment updates | CIMAINT-02's Actions group — Dependabot has natively updated the `# vX.Y.Z` comment next to a SHA pin since 2022; no third-party action needed |
| `dependabot.yml` (`package-ecosystem: docker`) | GitHub-native | Grouped Docker base-image updates | CIMAINT-02's Docker group — **only `cooldown.default-days` is supported for this ecosystem**; `semver-*-days` keys are silently rejected and break the *entire* `dependabot.yml` file, not just that block `[CITED: multiple corroborating GitHub issues/PRs, cross-verified]` |
| `kjanat/actionlint` fork | `1.17.0` (2026-09-13) | Drop-in actionlint replacement if upstream `rhysd/actionlint` (last release 2026-03-30) is judged stale by plan/execution time | Only if upstream actionlint's runner-label list (e.g. missing `ubuntu-26.04`) causes false positives against this repo's `runs-on: ubuntu-latest` — not expected to matter here, note only |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Trivy (binary, pinned) | `aquasecurity/trivy-action` / `aquasecurity/setup-trivy` (GitHub Actions) | **Rejected.** Both were directly compromised in March 2026 (malicious binary release + 76/77 hijacked tags). A full-SHA pin alone is not sufficient protection here because the compromise also poisoned an actual tagged *release* of the Trivy binary itself for ~3 hours, and `trivy-action`'s own dependency pinning only started in April 2025 — i.e., even a SHA pin made before that date could still pull a malicious `setup-trivy`. Installing the CLI binary directly (pinned version + committed checksum, same pattern as this repo's Tailwind/pip-audit installs) avoids trusting either Action's maintenance/release process at all. |
| Trivy | Grype (Anchore) | Grype has **no native ignore-rule expiry** (`expired_at`-equivalent is undocumented/unsupported as of Grype 0.121.0; a long-open feature request, anchore/grype#452, remains unresolved) and no built-in `--vuln-type os`-equivalent flag (requires a separate Syft SBOM step with `--select-catalogers os`). Both gaps mean more custom scripting to meet D-10's native-expiry intent and D-12's "don't duplicate pip-audit" intent. Grype remains a reasonable fallback if Trivy's compromise history is judged disqualifying at plan time — flagged as an open question below. |
| `uv sync --locked --no-editable` (full venv-based Dockerfile rewrite) | `uv export --locked --no-dev --no-emit-project --no-hashes` + `pip install --no-deps -r <file>` + `pip install --no-deps .` | The venv-based rewrite (uv's own documented Docker pattern) is architecturally cleaner but requires shipping the `uv` binary in or alongside the final image and restructuring the entrypoint/CMD to point at `.venv/bin/triggarr`. The `export`+`pip install --no-deps` variant reuses the **exact command already running** in `ci.yml`'s `dependencies` job, keeps the final image's install mechanism unchanged (`pip`, no `uv` runtime dependency), and is a much smaller diff — recommended unless the planner wants the fuller uv-native rewrite. |
| Splitting `release.yml`'s single `release` job | A new reusable/composite workflow for "least privilege" | **Rejected** — `ci-reference-baseline-plan.md`'s "Retain / do not copy blindly" list explicitly warns against "custom orchestrators"; two ordinary jobs with scoped `permissions:` blocks and `needs:`/`outputs:` wiring is sufficient and is the pattern GitHub's own docs recommend. |

**Installation (CI-side, illustrative — exact pins to be verified again at plan/execution time):**
```bash
# actionlint: pinned binary + committed checksum (no Action)
curl -fsSLO "https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz"
echo "<COMMITTED_SHA256>  actionlint_1.7.12_linux_amd64.tar.gz" | sha256sum -c -
tar -xzf actionlint_1.7.12_linux_amd64.tar.gz actionlint

# trivy: pinned binary + committed checksum (no Action) — recheck version against
# https://github.com/aquasecurity/trivy/releases and the advisory at
# https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23
# before pinning; must postdate the March 2026 compromise remediation.
curl -fsSLO "https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz"
curl -fsSLO "https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_checksums.txt"
sha256sum -c --ignore-missing trivy_0.76.1_checksums.txt
tar -xzf trivy_0.76.1_Linux-64bit.tar.gz trivy
```
```toml
# pyproject.toml [project.optional-dependencies].dev addition
"pytest-cov>=7.1.0",
```

**Version verification:** confirmed live against PyPI (`pip index versions pytest-cov` → `7.1.0`) and cross-checked against pytest-cov's own 2026-03-21 changelog entry. `pip index versions pip-audit` in this research environment showed a max of `2.9.0`, which is *older* than the `2.10.1` already pinned in `ci.yml` — this is almost certainly a stale/limited local index mirror, not evidence the existing pin is wrong, but the planner should re-run `pip index versions pip-audit` (or `uv pip index versions`) from the actual CI runner or a fresh network path before touching that pin, since this phase does not intend to change it. `[ASSUMED — recheck pip-audit's pin only if touched]`

## Package Legitimacy Audit

> Only one new package-manager dependency is proposed in this phase: `pytest-cov` (Python dev extra). Trivy and actionlint are installed as standalone, checksum-verified binaries in CI — not declared as project dependencies in any manifest — so they are not registry packages subject to this gate, but the binary-pinning discipline above (committed checksum, no `curl | sh`, no third-party Action) is the equivalent control for them.

```
$ slopcheck scan --pkg pypi pytest-cov --json
[{"package":"pytest-cov","ecosystem":"pypi","status":"OK","flags":[{"signal":"NO_REPO","severity":"info","message":"No source repository linked. Harder to verify what this code actually does."}],"suggestion":null}]
```

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `pytest-cov` | PyPI | ~15 years (first released 2010) `[ASSUMED, well-known package]` | Tens of millions/week `[ASSUMED, well-known package]` | `github.com/pytest-dev/pytest-cov` (slopcheck's `NO_REPO` flag reflects a PyPI metadata linkage gap, not an actual missing repo — verified by direct knowledge of the project) | `OK` (info-level `NO_REPO` flag only) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
 PR opened/pushed                 main push                      v* tag push
       │                              │                                │
       ▼                              ▼                                │
 ┌───────────────────────────── ci.yml ─────────────────────────────┐  │
 │ test ── lint ── docker ── secrets ── dependencies ── os-scan(NEW) │  │
 │   │        │        │                                  │          │  │
 │   │        │        └─▶ image-smoke ── browser-e2e      │          │  │
 │   │        │                                            │          │  │
 │   └────────┴──────────────── actionlint(NEW, always) ───┤          │  │
 │                                                          ▼          │  │
 │                                   ci-ready (aggregate, needs ALL) ──┘  │
 └────────────────────────────────────────────┬──────────────────────┘  │
                                                │ workflow_run(success)   │
                                                ▼                        ▼
                                         ┌──────────────── release.yml ─────────────┐
                                         │ preflight (exact-commit CI verification)  │
                                         │        │                                  │
                                         │        ▼                                  │
                                         │ publish-images (packages:write only) ─────┤
                                         │        │ (tag only)                       │
                                         │        ▼                                  │
                                         │ create-github-release (contents:write only)│
                                         └────────────────────────────────────────────┘

 PR opened/synchronize ──▶ review-acceptance.yml ──▶ review-acceptance.cjs:assess()
                                   │                        │
                                   │                reads vars.REVIEW_DISPOSITIONS /
                                   │                vars.REVIEW_BLOCKERS, now keyed
                                   │                by (pr_number, head_sha) (NEW)
                                   ▼
                        protected `review-acceptance` environment
                        (owner approves via GitHub UI or Claude CLI
                         transport, docs/owner-cli-acceptance.md)

 Local dev loop (not GitHub-hosted):
 BM code review ──▶ tests/codex_review_run.py ──▶ codex exec (read-only, --sandbox read-only)
      │                      │                              │
      │              SIGTERM/SIGHUP handler (NEW) ──▶ kills process group
      │                      │
      └──▶ tests/codex_report_status.py ──▶ checkpoint record (docs/review-checkpoint-record.md)
```

A reader can trace the primary use case (a PR's code reaching a publishable, audited, owner-accepted image) by following the arrows top-to-bottom: PR → `ci.yml`'s mandatory jobs (now including `os-scan` and unconditional `actionlint`) → `ci-ready` aggregate → `release.yml` (split-permission jobs) → the owner-acceptance gate, with the Codex harness running as a parallel, separately-hardened local process feeding evidence into the acceptance checklist.

### Recommended Project Structure

No new top-level directories. Changes land in existing locations:

```
.github/
├── dependabot.yml                      # NEW
├── workflows/
│   ├── ci.yml                          # +os-scan job, +actionlint job (unconditional), +coverage step
│   ├── release.yml                     # release job split: publish-images / create-github-release
│   └── review-acceptance.yml           # register lookup now keyed by PR+head
├── scripts/
│   ├── ci-job-consistency.cjs          # +skip-condition detector (ACCEPT-03/D-02)
│   ├── os-scan-gate.cjs (or .py)       # NEW — Trivy JSON → block/report classification + exception enforcement
│   ├── release-policy.cjs              # REQUIRED_JOBS gains "os-scan" (and "actionlint" if made mandatory-by-name)
│   └── review-acceptance.cjs           # assess() keyed by (pr_number, head) — concurrency fix
docs/
├── os-scan-policy.md (or a SECURITY.md section)  # NEW — D-10's written policy, committed before enforcement
└── review-checkpoint-record.md         # +fallback field (D-16)
security/ or .github/
└── os-scan-exceptions.yml              # NEW — D-10's exception register (id, package, reason, owner, expiry)
tests/
├── codex_review_run.py                 # D-18 fixes (signal handling, drain timeout, hollow-report, rm-001, getpass log)
├── codex_report_status.py              # D-18 hollow-report fix (null exit_code / trivial command)
└── test_*.py                           # new regression tests per D-18 sub-item, per CIMAINT item
```

### Pattern 1: Dockerfile consumes `uv.lock` without re-resolving (CIMAINT-01)

**What:** Replace the production stage's `pip install .` with an export-then-install sequence sourced from `uv.lock`, reusing the exact command already running in `ci.yml`'s `dependencies` job.
**When to use:** Any time the image's dependency *versions* must match the lockfile CI already audited, without adding `uv` as a runtime dependency inside the final image.
**Example:**
```dockerfile
# Source: this repo's ci.yml `dependencies` job (verified live), adapted for a build stage.
FROM python:3.13-slim AS deps
WORKDIR /build
COPY pyproject.toml uv.lock .
RUN pip install --no-cache-dir uv==<PINNED_VERSION> \
    && uv export --locked --no-dev --no-emit-project --no-hashes \
         --format requirements-txt --output-file requirements-locked.txt

# ---- Stage 2: Production image (unchanged base) ----
FROM python:3.13-slim
WORKDIR /app
COPY --from=deps /build/requirements-locked.txt .
RUN pip install --no-cache-dir --no-deps -r requirements-locked.txt
COPY pyproject.toml .
COPY triggarr/ triggarr/
COPY CHANGELOG.md .
RUN pip install --no-cache-dir --no-deps .
```
**Critical detail:** both `pip install` calls **must** use `--no-deps`. `pyproject.toml`'s `[project.dependencies]` list uses loose constraints (`httpx`, `loguru`, no pins) — without `--no-deps` on the second call, `pip install .` would re-resolve and potentially install versions that disagree with `uv.lock`, defeating the entire point of CIMAINT-01.

### Pattern 2: Lockfile/image consistency check (CIMAINT-01, the negative demonstration)

**What:** Diff the CI-exported lockfile requirements against the already-existing `image-requirements.txt` artifact (`docker` job already produces this via `pip freeze --all --exclude triggarr`).
**When to use:** As a new step in the `docker` job, immediately after the existing "Audit actual image dependencies" step.
```bash
# Source: pattern derived from this repo's own ci.yml `dependencies` job + `docker` job.
uv export --locked --no-dev --no-emit-project --no-hashes \
  --format requirements-txt --output-file requirements-locked.txt
# Normalize both to "name==version" lowercase sorted lines, then:
diff <(sort -f requirements-locked.txt) <(sort -f image-requirements.txt) \
  || { echo "Docker image dependencies disagree with uv.lock" >&2; exit 1; }
```
**Negative demonstration:** temporarily edit a dependency's version in a scratch branch's `uv.lock` (without rebuilding the image with that version) and confirm the diff step fails — exactly the Phase 82-style "deliberately mismatched lockfile fails the check" proof CIMAINT-01's criterion requires.

### Pattern 3: Dependabot grouped, bounded updates (CIMAINT-02)

**What:** Three ecosystem blocks, each grouping minor/patch together and letting majors open their own PR, each with an open-PR limit and a monthly schedule; security updates bypass the schedule automatically (GitHub's security-update mechanism is independent of `schedule:`).
```yaml
# Source: verified against docs.github.com/.../dependabot-options-reference
# and docs.astral.sh/uv/guides/integration/dependabot/ (2026-10 current).
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule: { interval: "monthly" }
    open-pull-requests-limit: 5
    groups:
      uv-minor-patch:
        applies-to: version-updates
        update-types: ["minor", "patch"]
    # uv's own guide recommends a `cooldown` matching any `exclude-newer` in pyproject.toml;
    # this repo has none configured today — omit unless one is added.

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "monthly" }
    open-pull-requests-limit: 5
    cooldown: { default-days: 5 }   # semver-*-days NOT supported for this ecosystem
    groups:
      actions-minor-patch:
        applies-to: version-updates
        update-types: ["minor", "patch"]

  - package-ecosystem: "docker"
    directory: "/"
    schedule: { interval: "monthly" }
    open-pull-requests-limit: 3
    cooldown: { default-days: 5 }   # semver-*-days NOT supported for this ecosystem
    groups:
      docker-minor-patch:
        applies-to: version-updates
        update-types: ["minor", "patch"]
```
**Major-version split:** omitting `update-types: ["major"]` from each group's `patterns` means Dependabot opens an *ungrouped*, individual PR for any major bump — satisfying D-05's "a major-version bump gets its own PR" without extra configuration, since majors simply aren't captured by the `minor/patch`-scoped group.
**Security updates:** D-06 ("security updates open right away, outside the monthly cycle") is GitHub's *default* behavior for Dependabot security updates — they are not controlled by `schedule:` at all. No extra config needed; this is confirmed via GitHub's own security-updates documentation (triggered by advisory disclosure, independent of the version-update schedule).
**One confirmed gotcha:** an invalid/unsupported key anywhere in `dependabot.yml` (e.g. a `semver-minor-days` key under `docker` or `github-actions`) silently disables **all** version updates repo-wide, not just the offending block, and the published JSON schema does not catch it. Validate the file against a real Dependabot dry run (or GitHub's "Dependabot" tab after merge) before trusting it.

### Pattern 4: OS-package scan with report-not-hide unfixed findings (CIMAINT-03)

**What:** One full, unfiltered Trivy scan against the audited image tarball, classified by a small script (same pattern/language as `ci-job-consistency.cjs`) into blocking vs. reporting-only buckets — because `--ignore-unfixed` would violate D-09 by removing unfixed Critical/High findings from the output entirely.
```bash
# Source: flag names/behavior verified via WebSearch against trivy.dev docs + GitHub discussions
# (aquasecurity/trivy#862, #7915, #4268 — exit-code-vs-DB-failure gotcha).
# DO NOT use the aquasecurity/trivy-action or aquasecurity/setup-trivy GitHub Actions —
# both were compromised March 2026 (CVE-2026-33634). Install the pinned+checksummed binary only.

trivy image --input image.tar \
  --pkg-types os \
  --format json \
  --output trivy-results.json
TRIVY_EXIT=$?
# A non-zero exit here (DB download failure, unparseable image, etc.) must itself fail
# the job closed — do NOT swallow it. This mirrors the existing pip-audit --strict job.
if [ "$TRIVY_EXIT" -ne 0 ]; then
  echo "Trivy scan failed (exit $TRIVY_EXIT) — failing closed per D-12" >&2
  exit 1
fi
# Hand trivy-results.json + the exceptions file to a classification script that:
#  - reports every finding (any severity, fixed or not) in the job summary
#  - blocks only on severity in {CRITICAL,HIGH} AND FixedVersion non-empty AND no valid,
#    unexpired, owner-approved exception matches
node .github/scripts/os-scan-gate.cjs --report trivy-results.json --exceptions os-scan-exceptions.yml
```
**Key flag corrections vs. likely first-draft assumptions:**
- `--vuln-type` was renamed `--pkg-types` in Trivy v0.54.0; the old flag is deprecated. Use `--pkg-types os`.
- Flags must come **after** the `image` subcommand (`trivy image --pkg-types os --input ...`, not `trivy --pkg-types os image --input ...`) — a documented Trivy gotcha where flag placement silently changes behavior.
- `--exit-code` is **not** set by Trivy on a DB-download or other operational failure — those always exit `1` regardless of what `--exit-code` value was requested for vulnerability findings. If a distinct "vulnerabilities found" exit code is wanted (e.g. `100`), it must be interpreted by the wrapper script, not assumed to disambiguate from a scanner-error `1`.
- DB download: Trivy already fails (non-zero exit, no scan performed) by default when it cannot reach its vulnerability DB and `--skip-db-update`/`--offline-scan` is not passed — this is the fail-closed behavior D-12 wants, with no extra flag required, **provided the job does not swallow Trivy's exit code**.

### Pattern 5: Exception file with native + custom expiry enforcement (CIMAINT-03/D-10)

**What:** Trivy's `.trivyignore.yaml` natively supports `expired_at: yyyy-mm-dd` (an entry stops being honored once that date passes) — but it has no `owner approval` field and no mechanism preventing someone from setting an expiry 90 days out. D-10 needs both, so keep a richer, custom exceptions file as the human-reviewed source of truth, validated by a repo script, which *generates* the `.trivyignore.yaml` Trivy actually reads.
```yaml
# os-scan-exceptions.yml (custom, repo-owned schema — Trivy never reads this file directly)
exceptions:
  - id: CVE-2026-XXXXX
    package: openssl
    reason: "Base image rebuild scheduled next monthly cycle; no exploitable path in this deployment."
    approved_by: thejuran
    expires: 2026-11-20   # script rejects: missing expiry, or expiry > 30 days from approval date
```
```javascript
// os-scan-exceptions-gate.cjs — Source: pattern modeled on this repo's ci-job-consistency.cjs
// (Node stdlib only, fail-closed on any structural problem).
function validateExceptions(exceptions, today) {
  const problems = [];
  for (const e of exceptions) {
    if (!e.id || !e.package || !e.reason || !e.approved_by) problems.push(`${e.id || '?'}: missing required field`);
    if (!e.expires) { problems.push(`${e.id}: no expiry — rejected`); continue; }
    const days = (new Date(e.expires) - today) / 86400000;
    if (days > 30) problems.push(`${e.id}: expiry ${e.expires} is more than 30 days out — rejected`);
    if (days < 0) problems.push(`${e.id}: expired ${e.expires} — no longer suppresses, reported as blocking again`);
  }
  return problems; // non-empty => fail the job (malformed exception file is itself a sensitive-change bug)
}
```
Generate Trivy's `.trivyignore.yaml` from only the *currently valid* (non-expired, well-formed) entries in `os-scan-exceptions.yml` as a CI step before invoking `trivy`, so Trivy's own `expired_at` check is defense-in-depth on top of the custom script's enforcement, not the sole enforcement mechanism (Trivy's date check also depends on the runner's system clock being correct, which the custom check doesn't change but is worth noting as a residual assumption).

### Pattern 6: Unconditional actionlint job (CIMAINT-04)

**What:** Rather than building change-detection logic to decide "did workflows change, should lint run," make the job unconditional — it is a single static-analysis pass over `.github/workflows/*.yml`, cheap enough (sub-second after binary download) that skip-detection machinery adds risk without saving meaningful CI time.
```yaml
# New job in ci.yml, added to ci-ready's `needs` alongside the existing mandatory jobs.
actionlint:
  timeout-minutes: 5
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<pinned-sha> # v6
    - name: Install actionlint (pinned + checksum-verified)
      run: |
        curl -fsSLO "https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz"
        echo "<COMMITTED_SHA256>  actionlint_1.7.12_linux_amd64.tar.gz" | sha256sum -c -
        tar -xzf actionlint_1.7.12_linux_amd64.tar.gz actionlint
    - name: Lint workflows
      run: ./actionlint -color
```
This closes the CONTEXT's example loophole ("CI ready verifies that the lint job either ran or was legitimately not needed") by construction: there is no "legitimately not needed" case to verify, because the job always runs and is already in `ci-ready`'s `needs` set (which `ci-job-consistency.cjs` already enforces cannot silently drop a job).

### Pattern 7: Coverage artifact with explicit PR-head-vs-merge-commit provenance (CIMAINT-06)

**What:** Add coverage flags to the existing `test` job's pytest invocation, preserving exit status exactly like `browser-e2e` already does, and publish a provenance JSON alongside `coverage.xml` naming both possible SHAs explicitly.
```yaml
# Source: pattern combines this repo's existing browser-e2e "set +e / capture / set -e"
# idiom with pytest-cov's documented --cov-report=xml flag.
- name: Run tests with coverage
  run: |
    set +e
    uv run --no-sync pytest tests/ -q --junitxml=test-results.xml \
      --cov=triggarr --cov-branch --cov-report=xml:coverage.xml
    TEST_EXIT=$?
    set -e
    echo "test_exit=$TEST_EXIT" >> "$GITHUB_OUTPUT"
    python3 - <<'PY'
    import json, os, time
    provenance = {
        "pr_head_sha": os.environ.get("PR_HEAD_SHA") or "n/a (not a pull_request event)",
        "merge_commit_sha": os.environ["GITHUB_SHA"],
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "workflow": os.environ["GITHUB_WORKFLOW"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open("coverage-provenance.json", "w") as f:
        json.dump(provenance, f, indent=2)
    PY
  env:
    PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
- name: Fail the job if tests failed (coverage collection must never mask this)
  if: steps.<step-id>.outputs.test_exit != '0'
  run: exit 1
```
**Critical fact (verified from the vibe-check plugin source, not assumed):** vibe-check's `test-sufficiency` lane discovers coverage by globbing a **fixed, repo-relative filename** inside the worktree it is reviewing — `coverage.xml`, `cobertura-coverage.xml`, or `cobertura.xml` — not by any GitHub Actions artifact name. This means: (a) the CI artifact's filename should literally be `coverage.xml` (already satisfied above), and (b) whoever runs vibe-check for a given head must first download that exact CI run's artifact and place it at the review worktree's repo root before the review starts — this is an operational step for the reviewer/BM, not something CI itself can automate, and should be documented in `docs/review-checkpoint-record.md` or the acceptance checklist.
**Artifact naming (binds to tested SHA + run):**
```yaml
- uses: actions/upload-artifact@<pinned-sha> # v4
  with:
    name: coverage-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}
    path: |
      coverage.xml
      coverage-provenance.json
    if-no-files-found: error
    retention-days: 14
```

### Pattern 8: Split release permissions (CIMAINT-07)

**What:** Two jobs instead of one, each with only the `GITHUB_TOKEN` permissions it needs, with outputs passed via `needs.<job>.outputs`.
```yaml
# Source: pattern verified against GitHub's own docs (Controlling permissions for GITHUB_TOKEN)
# and this repo's existing release.yml structure (preflight -> release becomes
# preflight -> publish-images -> create-github-release).
publish-images:
  needs: preflight
  permissions:
    contents: read      # was contents: write — no longer needed to push images
    packages: write      # GHCR push
    actions: read
  outputs:
    sha: ${{ steps.recheck.outputs.sha }}
    run_id: ${{ steps.recheck.outputs.run_id }}
  steps:
    # ... identical to today's steps through "Publish audited image without rebuilding" ...

create-github-release:
  needs: [preflight, publish-images]
  if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
  permissions:
    contents: write      # ONLY this job holds it, and only for tag pushes
  steps:
    - name: Create GitHub Release
      env:
        GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        TAG_NAME: ${{ github.ref_name }}
      run: |
        if gh release view "$TAG_NAME" &>/dev/null; then
          echo "Release $TAG_NAME already exists"
        else
          gh release create "$TAG_NAME" --title "Triggarr $TAG_NAME" --generate-notes --latest
        fi
```
**D-14 interaction:** since distributions are dropped, `create-github-release` no longer downloads/verifies/uploads `dist/*` at all — it becomes a pure `gh release create` with generated notes, no assets. This also removes 2 of the 4 step-name assertions and one of the two `run-id:` references `artifact-promotion.test.cjs` currently checks for (see CIMAINT-05 below) — that test file needs editing, not just the workflow.

### Pattern 9: ACCEPT-02's register keyed by PR + head SHA

**What:** `review-acceptance.cjs`'s `assess()` function today takes `dispositions`/`blockers` as flat objects (`{schema, items: {COMMENT_ID: {...}}}` / `{schema, open: [...]}`) read verbatim from two repo-wide variables. D-19 requires keying by `(pr_number, head_sha)` so one PR's `gh variable set` (a whole-value overwrite) cannot erase another PR's in-flight evidence.
```javascript
// Illustrative shape change — register now nests by "pr:head" key.
// {"schema":2,"by_pr_head":{"42:abc123...":{"items":{...}}}}
// review-acceptance.yml passes `context.payload.pull_request.number` and the head SHA
// so assess() can look up only this PR+head's slice, never touching another PR's entry.
```
**Concurrency proof requirement (D-19):** a test using two concurrent-update fixtures — simulate PR A writing its slice, then PR B writing its slice, then assert PR A's slice is unchanged — is the "prove this with tests that use concurrent-update fixtures" D-19 calls for. Until that test exists and passes, D-19 explicitly permits keeping today's serialized-update discipline (documented, not code-enforced) as the interim safe state — this is not a blocking gap for planning, just a sequencing note: the test must exist before (or as part of) claiming ACCEPT-02 done.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Workflow YAML linting | A custom YAML-schema checker for Actions syntax | `actionlint` (pinned binary) | actionlint already understands `needs`, `if:` expression syntax, matrix expansion, and shells out to `shellcheck` for embedded bash — reimplementing any slice of this is pure risk for no benefit |
| OS-package vulnerability database | A custom CVE feed / NVD poller | Trivy's bundled vulnerability DB (auto-updated, downloaded per scan or cached) | Vulnerability feeds require constant curation across multiple OS package ecosystems (apt/apk/rpm); Trivy's DB is the maintained, trusted source here |
| Dependency update scheduling/grouping/PR creation | A custom bot or script polling PyPI/npm/Docker Hub for new versions | Dependabot (`dependabot.yml`) | This is a first-party GitHub feature with native grouping, cooldown, and security-update integration — a custom bot would need to reinvent all of it with none of GitHub's native PR/commit-signing integration |
| Coverage report parsing for the test-sufficiency reviewer | A custom coverage-to-risk-score pipeline feeding vibe-check | vibe-check's existing `test-sufficiency` agent + its documented discovery contract | The consumer side already exists and is fully specified (file-glob discovery, byte caps, branch-data handling); building a second pipeline would duplicate it and risk disagreeing with what vibe-check actually reads |
| Exception-expiry enforcement | A fully custom vulnerability-exception database/UI | A small committed YAML file + a Node/Python validation script (same pattern as `ci-job-consistency.cjs`) on top of Trivy's native `.trivyignore.yaml` `expired_at` | D-10's fields (owner approval, reason) aren't natively supported by Trivy, but the gap is small — a committed file + ~40-line validator, not a database or service |
| Least-privilege job permission splitting | A reusable composite "release orchestrator" action | Two ordinary jobs with job-level `permissions:` + `needs:`/`outputs:` | GitHub Actions already supports exactly this pattern natively; a composite action adds an abstraction layer with no capability gain |

**Key insight:** every CIMAINT/ACCEPT item in this phase has a first-party or already-adopted tool that does 90% of the work; the repository-specific 10% (D-10's owner-approval field, D-19's PR+head keying, the actionlint-is-unconditional simplification) is intentionally small, hand-rolled glue — consistent with `ci-reference-baseline-plan.md`'s explicit "no custom orchestrators" guidance.

## Common Pitfalls

### Pitfall 1: Trusting a third-party security-scanner Action because it's "the standard tool"
**What goes wrong:** `aquasecurity/trivy-action`/`setup-trivy` look like the obvious, officially-blessed way to run Trivy in CI, and are what most tutorials show.
**Why it happens:** Tutorials and most existing CI configs predate or don't mention the March 2026 compromise; "it's the vendor's own Action" reads as inherently safer than it is.
**How to avoid:** Install the Trivy CLI binary directly, pinned by version with a checksum committed to the repo (same pattern as this repo's Tailwind/pip-audit installs) — never depend on `trivy-action`/`setup-trivy`'s tag or release integrity.
**Warning signs:** Any workflow diff that adds `uses: aquasecurity/trivy-action@...` or `uses: aquasecurity/setup-trivy@...` should be treated as a finding in review, not approved as routine.

### Pitfall 2: `--ignore-unfixed` silently violating D-09
**What goes wrong:** `--ignore-unfixed` is the obvious flag name for "don't block on things I can't fix," but it removes those findings from Trivy's output entirely — so the CI summary would show nothing for an unfixed Critical, violating D-09's "reported... and don't block."
**Why it happens:** The flag name reads like a "downgrade severity" knob; it's actually a "delete from results" knob (it's shorthand for `--ignore-status affected,will_not_fix,fix_deferred,end_of_life`).
**How to avoid:** Run Trivy with no result-filtering flags at all; do all blocking/reporting classification in a small wrapper script that sees every finding.
**Warning signs:** A CI summary that shows zero OS-package findings on an image that definitely has some (even low-severity or unfixed ones) — that's the filter hiding data, not a clean scan.

### Pitfall 3: `pip install .` without `--no-deps` silently re-resolving dependencies
**What goes wrong:** After exporting and `pip install --no-deps`-ing the locked requirements, a plain `pip install .` for the project itself will still try to resolve `pyproject.toml`'s unpinned `[project.dependencies]` list, potentially pulling a different (newer) version than the one just installed from the lockfile.
**Why it happens:** `pip install .`'s default behavior resolves and installs dependencies unless told not to; the preceding `--no-deps` install doesn't change this call's defaults.
**How to avoid:** Use `--no-deps` on **every** `pip install` call in the production stage once dependencies are sourced from the lockfile export.
**Warning signs:** `image-requirements.txt` showing a version that doesn't match `uv.lock` even after switching to the export-based pattern — almost always a missing `--no-deps`.

### Pitfall 4: `github.sha` on a `pull_request` trigger is the synthetic merge commit, not the PR head
**What goes wrong:** A coverage artifact (or any evidence) tagged only with `${{ github.sha }}` on a PR run records the ephemeral merge commit GitHub creates for the PR, which doesn't exist as a reachable commit after the PR closes/rebases — not the actual head commit that will be reviewed/merged.
**Why it happens:** `pull_request`-triggered workflows checkout and report `github.sha` as the test merge commit by design (for `test` and most jobs); this is well-documented but easy to overlook when wiring a new artifact.
**How to avoid:** Always capture `github.event.pull_request.head.sha` explicitly alongside `github.sha` in any provenance record (exactly as Pattern 7 above does), and make the distinction visible in the artifact itself, not just in a comment.
**Warning signs:** A reviewer tool reports "coverage for commit X" where X cannot be found via `git show` in the checked-out history — classic merge-commit-vs-head confusion.

### Pitfall 5: An invalid Dependabot `cooldown` key for `docker`/`github-actions` silently disables ALL version updates
**What goes wrong:** Copy-pasting a `cooldown` block with `semver-minor-days`/`semver-major-days`/`semver-patch-days` into the `docker` or `github-actions` ecosystem entries (valid for `uv`/`npm`/`pip`, **not** valid for `docker`/`github-actions`) breaks the entire `dependabot.yml` file's version-update behavior, repo-wide — not just that one ecosystem block.
**Why it happens:** The published Dependabot JSON schema accepts these keys for every ecosystem (it doesn't enforce the per-ecosystem restriction), so schema validation gives false confidence.
**How to avoid:** For `docker` and `github-actions` ecosystem blocks, use only `cooldown.default-days`. Confirm the file is actually being honored by checking the repo's Dependabot "Insights" tab (or the Dependabot logs) after the file merges, not just that it passes schema validation.
**Warning signs:** Zero Dependabot PRs appear at all, across every ecosystem, weeks after the config merged — check for this exact mistake first.

### Pitfall 6: `node --test <directory>/` does not recurse (Node v25.9.0, this machine's version)
**What goes wrong:** Extending CI's Node test step to "also run planchk-router's tests" by pointing at the plugin's `test/` directory instead of the exact file silently runs zero tests (or errors, depending on Node version) rather than discovering `planchk-router.test.mjs`.
**Why it happens:** `node --test`'s directory-recursion behavior has changed across Node versions; relying on it is version-fragile.
**How to avoid:** Per D-13, always pass the explicit file path (or an explicit glob matching `.test.mjs`/`.test.cjs` patterns), exactly as `ci.yml`'s existing `node --test .github/scripts/*.test.cjs` already does for the Node scripts in this repo.
**Warning signs:** A CI "tests passed" result with a suspiciously low or zero test count after adding a new directory-based `node --test` invocation.

### Pitfall 7: `exit_code` is not disambiguated between "vulnerabilities found" and "scanner/DB error" by `trivy`'s default behavior
**What goes wrong:** A naive `if [ $? -ne 0 ]; then echo "vulnerabilities found"` treats a DB-download failure identically to "found a blocking CVE" — which is actually fine for D-12's fail-closed intent (both should fail the job) but is the wrong signal if the job ever needs to distinguish the two cases (e.g., to post a different, more actionable error message, or to retry only on transient DB errors).
**Why it happens:** Trivy's `--exit-code` flag only affects the "vulnerabilities found" case; DB/network/parse errors always exit `1` regardless of the requested exit code.
**How to avoid:** If the distinction matters to the design (D-12 doesn't strictly require it — "fail closed" covers both), request a non-default `--exit-code` value (e.g. `100`) for the findings case and treat any other non-zero exit as the ambiguous "scanner error" bucket. (Planning resolution: no retry on DB errors is adopted — see Open Questions 3, RESOLVED; every non-zero Trivy exit fails the job.)
**Warning signs:** A job failure message that says "vulnerabilities found, see summary" when the actual cause was a registry rate-limit on the vulnerability DB mirror.

### Pitfall 8: SIGTERM/SIGHUP to `tests/codex_review_run.py` bypasses its own cleanup (D-18, confirmed present)
**What goes wrong:** The runner's `run_command()` helper correctly kills the pytest/codex process group when a *Python-visible* exception occurs (timeout, or any `except BaseException`) — but Python's default disposition for `SIGTERM`/`SIGHUP` terminates the process immediately without raising any exception, so an external kill of the harness (e.g. a CI job cancellation, or an operator `Ctrl-C`-adjacent signal) leaves the child process group orphaned.
**Why it happens:** No `signal.signal(signal.SIGTERM, ...)`/`SIGHUP` handler is registered anywhere in `tests/codex_review_run.py` (confirmed by direct code read — only `SIGKILL` appears, used *by* `_kill_group`, never trapped).
**How to avoid:** Register handlers for `SIGTERM`/`SIGHUP` at the top of `main()` that call the same `_kill_group`-equivalent cleanup (tracking the active `Popen` in a module-level or `contextvars` reference) before re-raising/exiting.
**Warning signs:** An orphaned `codex`/`pytest` process still running (consuming CPU, possibly still holding file handles) after the harness script itself has exited.

### Pitfall 9: Post-kill output drain has no timeout (D-18 bugs-002, confirmed present)
**What goes wrong:** On a `TimeoutExpired`, `run_command()` calls `_kill_group(proc)` then `proc.communicate()` **again with no timeout** to collect the partial output — if any descendant process still holds stdout/stderr open after the `SIGKILL`, this second `communicate()` call can hang indefinitely, defeating the whole point of the original timeout.
**Why it happens:** `subprocess.Popen.communicate()`'s default `timeout=None` behavior is to wait forever; the code path added the kill but didn't bound the subsequent drain.
**How to avoid:** Pass a short, bounded timeout to the post-kill `communicate()` call too, and fall back to whatever partial output was captured (or an explicit "drain timed out" marker) if that second call also times out — never let it hang the whole run.
**Warning signs:** A Codex review run that never finishes and never produces even a status stub, after a timeout should have fired.

### Pitfall 10: `--trusted`/`--untrusted` is a pure operator-supplied flag with no independent verification (D-18 SA-01, confirmed present)
**What goes wrong:** Anyone invoking `codex_review_run.py` decides trust by passing `--trusted` or `--untrusted` themselves; nothing in the code cross-checks this claim against the actual PR's `head_repository`/`author_association` via the GitHub API.
**Why it happens:** The flag was added as a `required=True` mutually-exclusive group with no validation beyond "one of the two must be present" — it trusts the caller's judgment entirely.
**How to avoid:** Have the caller (or the runner itself, given a `--pr-number`) fetch `gh pr view <N> --json headRepositoryOwner,authorAssociation` (or equivalent) and refuse to proceed with `--trusted` if the PR is actually from a fork or from `dependabot[bot]`.
**Warning signs:** A Codex review marked `complete` for a PR that, on inspection, came from an external fork — exactly the case the untrusted-source carve-out exists to prevent.

## Code Examples

### Hollow-report guard gap (D-18, exact confirmed location)

```python
# tests/codex_report_status.py, current logic (confirmed by direct read, ~line 411-424):
commands = report.get("commands_run")
if isinstance(commands, list) and not any(
    isinstance(entry, dict) and _non_blank(entry.get("command")) for entry in commands
):
    reasons.append("no commands run: the report gives no evidence the diff was inspected")
```
**Gap:** this only checks the `command` string is non-blank. A report with `{"command": "echo hi", "exit_code": null}` passes this check even though it proves nothing was actually inspected. The fix needs to additionally require at least one entry with a non-null `exit_code` (and, per MAINTENANCE.md's own framing, optionally flag a denylist of trivially-uninformative commands such as `echo`/`true`/`pwd` — left as a planner decision since "trivial" is otherwise unbounded):
```python
# Illustrative fix direction, not a finished patch:
has_real_evidence = any(
    isinstance(entry, dict) and _non_blank(entry.get("command")) and entry.get("exit_code") is not None
    for entry in commands
)
if isinstance(commands, list) and not has_real_evidence:
    reasons.append("no commands run with a recorded exit code: the report gives no evidence the diff was inspected")
```

### `_write_evidence_copy`'s directory leak on `os.open()` failure (D-18 rm-001, exact confirmed location)

```python
# tests/codex_review_run.py, current logic (confirmed by direct read, ~line 347-366):
def _write_evidence_copy(worktree: Path, text: str) -> None:
    relative_dir = Path(EVIDENCE_RELPATH).parent
    directory = worktree / relative_dir
    if os.path.lexists(directory):
        raise RunnerError(...)
    try:
        directory.mkdir()                           # succeeds
        fd = os.open(worktree / EVIDENCE_RELPATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        raise RunnerError(...) from exc               # <- directory from the mkdir() above is left behind
```
**Fix direction:** since the preceding `lexists` check guarantees the directory did not exist before this call, any directory present after a failure here was created by this call and is always safe to remove on the exception path:
```python
    try:
        directory.mkdir()
        fd = os.open(worktree / EVIDENCE_RELPATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        with contextlib.suppress(OSError):
            directory.rmdir()
        raise RunnerError(...) from exc
```

### `getpass.getuser()` failure is silently swallowed (D-18 compliance-002, exact confirmed location)

```python
# tests/codex_review_run.py, current logic (confirmed by direct read, ~line 329-332):
try:
    user = getpass.getuser()
except (KeyError, OSError):
    user = ""     # <- silent; no log, matching MAINTENANCE.md's description exactly
```
**Fix direction:** add a `print(...)` (this file's own documented convention — plain `print()`, not loguru, per its module docstring) noting the fallback, so the redaction gap is visible rather than silent:
```python
try:
    user = getpass.getuser()
except (KeyError, OSError) as exc:
    print(f"warning: getpass.getuser() failed ({type(exc).__name__}); username redaction in evidence text is skipped")
    user = ""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `trivy --vuln-type os ...` | `trivy --pkg-types os ...` | Trivy v0.54.0 | `--vuln-type` is deprecated and scheduled for eventual removal; using it now risks a future breaking removal with no warning in this repo's pinned-version world unless re-verified at each Trivy version bump |
| Dependabot has no `uv` ecosystem support (workaround: `package-ecosystem: pip`, which doesn't regenerate `uv.lock`, causing lockfile drift) | `package-ecosystem: "uv"` (native, GA) | 2025-03-13 (version updates), 2025-12-16 (security updates) | CIMAINT-02 is now directly implementable with zero workarounds; the old `pip`-ecosystem workaround (seen in older blog posts) must not be used |
| Dependabot version updates had no built-in delay/"settle" period | A default 3-day `cooldown` applies repo-wide unless overridden | 2026-07-14 (GitHub made this the default across all ecosystems) | This repo's new `dependabot.yml` inherits a 3-day cooldown even on keys that don't explicitly set one; D-05's "bounded" updates get this for free, and any explicit `cooldown` block should be considered relative to this new default, not a greenfield decision |
| `trivy-action`/`setup-trivy` (GitHub Actions) treated as the default, officially-recommended Trivy CI integration | Aqua Security's own post-incident guidance: pin binaries/images by digest/checksum, verify signatures, treat tag-based references as compromised until proven otherwise | March 2026 (CVE-2026-33634) | This is the single most consequential "state of the art" shift for this phase — any pre-2026-03 tutorial or this repo's own prior assumptions about "just use trivy-action" are now actively unsafe guidance |
| GitHub Actions release workflows commonly bundle `contents: write` + `packages: write` on one job "because it's simpler" | Per-job least-privilege `permissions:` blocks, scoped to exactly what each job's steps need | Longstanding GitHub guidance, newly actionable here via CIMAINT-07 | Directly closes the gap `ci-reference-baseline-plan.md` flagged in the original Triggarr-vs-Seedsyncarr comparison |

**Deprecated/outdated:**
- `trivy --vuln-type`: deprecated since v0.54.0; use `--pkg-types`.
- `aquasecurity/trivy-action`/`aquasecurity/setup-trivy` as a trusted default: not deprecated by the project, but materially distrusted by this research given the March 2026 compromise; this repo's existing pattern of pinning *tools*, not *wrapper Actions*, already points away from them.
- Dependabot's old `package-ecosystem: pip`-for-uv-projects workaround: superseded by native `uv` support; using the workaround now risks the exact lockfile drift it was trying to avoid.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Trivy `0.76.1` is the correct version to pin at execution time | Standard Stack, Code Examples | Low — explicitly flagged to recheck against the live releases page and the compromise advisory before pinning; wrong pin just means re-running the version-check step, not a security gap, provided the checksum-verification step is still present |
| A2 | GitHub's `ubuntu-latest` runner image ships `shellcheck` by default, so actionlint's embedded bash linting works out of the box | Standard Stack | Low — if false, actionlint simply skips the shellcheck-dependent checks (it degrades gracefully; this is documented actionlint behavior), so no CI breakage, only reduced lint coverage |
| A3 | `pip-audit==2.10.1` (this repo's existing pin, untouched by this phase) is still current/correct | Standard Stack note | Low — this phase does not plan to touch that pin; flagged only because the local research environment's `pip index` showed an older max version, which is most likely a stale local index, not evidence of a real problem |
| A4 | GitHub's `ubuntu-latest` runner's system Node (no `actions/setup-node` step in `ci.yml` today) supports `node:test` and ESM imports needed by `planchk-router.test.mjs` | Phase Requirements (D-13), Pitfall 6 | Medium — if the runner's system Node is older than expected, the new test step could fail outright; verify the actual runner Node version in a scratch CI run before relying on it, or add an explicit `actions/setup-node` step pinned to a known-good major version |
| A5 | Grype's `.grype.yaml`/VEX ignore mechanism truly has no native expiry field (vs. an undocumented one that happens to work) | Standard Stack (Alternatives Considered) | Low — this only affects the Trivy-vs-Grype tradeoff narrative; since Trivy is the primary recommendation, this doesn't block planning, only the "why not Grype" justification |
| A6 | A single `pip install . --no-deps` after a `pip install --no-deps -r <locked-requirements>` step correctly installs Triggarr's own package metadata without pulling any transitive dependency change | Architecture Patterns, Pattern 1 | Medium — this is standard pip behavior but should be verified by actually building the image and diffing `pip freeze` against the lockfile export as part of CIMAINT-01's own negative-case demonstration, which the plan already needs to build anyway |
| A7 | GitHub's `ubuntu-latest` runners do not need any additional setup (e.g. `qemu`) to run `trivy image --input` against a tarball built for the runner's own architecture | Architecture Patterns, Pattern 4 | Low — this repo's images are already amd64-only (ARM64 explicitly out of scope per REQUIREMENTS.md), so there is no cross-architecture scanning concern |

**If this table is empty:** N/A — see entries above. None of these assumptions block planning; all are either low-risk or already have a built-in verification step in the recommended design (e.g. A6 is proven by CIMAINT-01's own required negative demonstration).

## Open Questions (RESOLVED)

All three questions below were resolved at planning time (2026-10-26/27). The resolutions are what Plans 85-01, 85-12 and 85-15 implement; the original analysis is kept for context.

1. **Where should the written OS-scan policy (D-10) live — a new `docs/os-scan-policy.md`, or a new "Supply chain / CI scanning" section in the existing root `SECURITY.md`?**
   - What we know: `SECURITY.md` already exists and documents the *application's* security model (auth, CSRF, SSRF, etc.); it's a natural home for a scanning policy but currently has no "build pipeline" content at all. `docs/` already hosts the review/acceptance policy docs this phase extends.
   - What's unclear: whether the owner considers CI/supply-chain policy "security policy" (→ `SECURITY.md`) or "operations/process policy" (→ `docs/`).
   - Recommendation: default to a new `docs/os-scan-policy.md` (consistent with how `docs/review-classification-policy.md` and `docs/codex-adversarial-review-contract.md` already house this phase's other written policies), and cross-link it from `SECURITY.md`'s existing structure. Low-cost either way; the planner can decide without blocking.
   - **RESOLVED:** `docs/os-scan-policy.md`, cross-linked from `SECURITY.md` (Plan 85-01 Task 2). It is committed before the gate is enforced (Plan 85-15 depends on 85-01), as D-10 requires.

2. **Should the OS-scan job additionally gate on Trivy's own misconfiguration/secret scanners, or stay narrowly scoped to `--pkg-types os` vulnerabilities only?**
   - What we know: D-12 explicitly says "must not duplicate pip-audit's Python coverage as a second equivalent gate," and this repo already has a dedicated `secrets` job (gitleaks). Trivy's misconfiguration scanner would overlap with neither existing job, but was not asked for by any CIMAINT-03 criterion.
   - What's unclear: whether "one OS-package scanner" in D-12 is read strictly (vulnerabilities only) or loosely (whatever Trivy finds in the image, scoped to non-Python).
   - Recommendation: scope strictly to `--pkg-types os` vulnerability scanning only, per the literal CIMAINT-03 wording ("shipped image's OS packages are scanned"). Flag misconfiguration/secret-in-image scanning as a possible future backlog item, not in this phase.
   - **RESOLVED:** strict scope — `--scanners vuln --pkg-types os` against the exact audited image artifact (Plan 85-15 Task 1); the policy states misconfiguration and secret scanning are out of scope (Plan 85-01). No backlog item is created by this phase.

3. **Does the owner want Trivy's DB downloaded fresh on every CI run, or cached across runs (with a staleness check) to reduce both runtime and dependency on Trivy's DB-distribution registries during the exact window this phase is implemented (so soon after the March 2026 compromise)?**
   - What we know: a cached-DB approach reduces per-run network dependency and runtime, but needs its own staleness guard (one 2026 report found Trivy prints no warning when scanning with a deliberately stale cached DB and `--skip-db-update`).
   - What's unclear: whether the ~5-minute added-PR-time budget (Phase 82 D-14/D-15) makes a fresh DB download per run acceptable, or whether caching is needed to stay inside it.
   - Original recommendation (superseded): a separate `--download-db-only` step with retry/backoff across mirror registries.
   - **RESOLVED:** fresh DB download on every run, no cache, no `--skip-db-update`/`--offline-scan`, no custom mirror list, and **no in-step retry or backoff** (Plan 85-15 Task 1; Plan 85-01 policy). Reconciliation with the retry idea above: D-12 makes scanner errors — including a DB download failure — fail closed, and Phase 82 D-15 forbids retries that turn a failure into a pass. A DB download failure therefore fails the `os-scan` job and `CI ready`; the remedy is a visible re-run of the job (a new, recorded run attempt), never an automatic retry inside the step. Runtime is measured locally in Plan 85-12 and on the phase PR's CI run (85-19 pending item P1); if the added time exceeds the ~5-minute target, the tradeoff (including caching with a staleness guard) goes to the owner before anything is changed (Phase 82 D-14).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | CIMAINT-01, CIMAINT-03 (local verification / existing CI jobs) | ✓ (local dev machine) | 29.4.3 | — (already a hard CI dependency via existing `docker` job) |
| uv | CIMAINT-01 | ✓ (local dev machine) | 0.12.17 | — (already a hard CI/Dockerfile dependency) |
| Node.js | D-13 (planchk-router tests), existing `.github/scripts/*.test.cjs` | ✓ (local dev machine) | v25.9.0 | GitHub Actions runner's system Node version not independently confirmed in this research (A4 above) — add an explicit version-check step or `actions/setup-node` if the existing implicit-system-Node approach proves insufficient |
| `trivy` CLI | CIMAINT-03 | ✗ (not installed locally) | — | Install as a pinned+checksummed binary inside the CI job only; no local dev requirement implied by this phase |
| `actionlint` | CIMAINT-04 | ✓ (local dev machine, via Homebrew) | 1.7.12 | Matches the pin recommended for CI; confirms the version/release exists and is installable |
| `shellcheck` | CIMAINT-04 (actionlint's embedded bash linting) | ✓ (local dev machine, via Homebrew) | 0.11.0 | GitHub's `ubuntu-latest` runner image is expected to ship this by default (A2); if not, actionlint degrades gracefully (skips those checks) rather than failing |
| `gh` CLI | ACCEPT-01, ACCEPT-02, release.yml's `gh release create` | ✓ (local dev machine) | 2.86.0 | Already a hard CI/release dependency |
| `slopcheck` | Package Legitimacy Gate (this research only) | ✓ (local, via pip --user) | 0.6.1 | — |

**Missing dependencies with no fallback:** none — `trivy` is the only "missing locally" item, and it is designed to be CI-only (pinned binary, no local dev install implied).

**Missing dependencies with fallback:** none beyond the GitHub Actions runner's system Node version (A4), which has a documented fallback (`actions/setup-node`) if the implicit system Node proves insufficient.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python, via `uv run pytest`) + `node:test` (Node stdlib, via `node --test`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`); no separate Node test config — scripts are run directly by path/glob |
| Quick run command | `uv run pytest tests/test_<module>.py -x -q` / `node --test .github/scripts/<file>.test.cjs` |
| Full suite command | `uv run pytest tests/ -x -q` (per CLAUDE.md) + `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CIMAINT-01 | Docker image deps match `uv.lock`; mismatch fails | integration (CI job logic) | `diff` step inside `docker` job + a Node test asserting the step exists/orders correctly | ❌ Wave 0 (new `.github/scripts/*.test.cjs` test + workflow step) |
| CIMAINT-02 | Dependabot config present, valid, grouped per ecosystem | config validation (manual/CI dry-run; Dependabot config has no unit-test surface) | N/A — verified by a real Dependabot run after merge, per Phase 82's "a claim that GitHub enforces something needs a real GitHub run" rule | ❌ Wave 0 (no file; verified live) |
| CIMAINT-03 | OS scan blocks Critical/High-with-fix, reports-not-hides unfixed/lower, fails closed on scanner error, enforces exception expiry | unit (gate script) + integration (CI job) | `node --test .github/scripts/os-scan-gate.test.cjs` (or `.py` equivalent) | ❌ Wave 0 (new script + tests) |
| CIMAINT-04 | actionlint runs unconditionally; a bad workflow fails it | integration (CI job) + fixture | New actionlint job + a deliberately-bad-workflow fixture test, following Phase 82's pattern of feeding a fixture into the same entry point CI invokes | ❌ Wave 0 |
| CIMAINT-05 | `dist/*` steps/assertions removed cleanly, no dangling test references | unit (existing test file edit) | `node --test .github/scripts/artifact-promotion.test.cjs` (edited) | ✅ (file exists, needs editing — confirmed via grep) |
| CIMAINT-06 | `coverage.xml` + provenance generated, bound to exact SHA/run, test-failure exit status preserved | integration (CI job) | New step in `ci.yml`'s `test` job; verify via a deliberately-failing test fixture that the job still reports failure with coverage collection on | ❌ Wave 0 |
| CIMAINT-07 | `:main`/`:dev` publish succeeds with only `packages: write`+`contents: read`; tag release still works with split jobs | integration (real GitHub run, since this is a GitHub-enforced permissions claim) | `node --test .github/scripts/release-policy.test.cjs` (ordering/consistency) + a real `:main`/`:dev` publish demonstration | ✅ (file exists, needs editing) |
| ACCEPT-01 | Readiness checklist assembled correctly from CI/Codex/dispositions/register state | unit | New test in `.github/scripts/review-acceptance.test.cjs` or a new script's own test file | ❌ Wave 0 |
| ACCEPT-02 | Register keyed by PR+head; concurrent updates don't cross-contaminate | unit (concurrent-fixture test) | `node --test .github/scripts/review-acceptance.test.cjs` (new concurrent-fixture cases) | ✅ (file exists, needs new test cases — D-19's explicit requirement) |
| ACCEPT-03 | No skip condition exists that lets `CI ready` pass without a required job, across 4 fixture classes | unit (fixture-diff test) | `node --test .github/scripts/ci-job-consistency.test.cjs` (new skip-condition-detector cases) | ✅ (file exists, needs new detector + test cases) |
| D-13 | planchk-router's 11 tests run in CI | unit (already-written tests, new CI wiring) | `node --test .claude/plugins/planchk-router/test/planchk-router.test.mjs` | ✅ (tests exist; only CI wiring is new) |
| D-16..D-18 | Codex harness hardening (8 sub-items) | unit (regression test per sub-item) | `uv run pytest tests/test_codex_review_run.py tests/test_codex_report_status.py -x -q` (existing files, new test cases per sub-item) | ✅ (files exist, confirmed via `ls tests/`) |

### Sampling Rate
- **Per task commit:** the relevant `node --test <specific-file>` or `uv run pytest tests/test_<module>.py -x -q` for the file(s) touched.
- **Per wave merge:** `uv run pytest tests/ -x -q` + `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` + `uv run ruff check triggarr/ tests/`.
- **Phase gate:** full suite green, plus the four ACCEPT-03 fixture cases and CIMAINT-01's lockfile-mismatch negative case, before `/bm:verify-work`.

### Wave 0 Gaps
- [ ] `.github/scripts/os-scan-gate.test.cjs` (or `.py`) — covers CIMAINT-03's severity/fix/exception/scanner-error classification logic
- [ ] New fixture workflow-diff files for ACCEPT-03's four cases (ordinary-docs, sensitive-docs, mixed, misclassified) — covers ACCEPT-03
- [ ] New concurrent-update fixtures for `review-acceptance.test.cjs` — covers ACCEPT-02/D-19
- [ ] `os-scan-exceptions.yml` validator script + its own test — covers CIMAINT-03/D-10
- [ ] Per-D-18-subitem regression tests in `tests/test_codex_review_run.py`/`tests/test_codex_report_status.py` (8 cases) — covers D-16..D-18
- [ ] A deliberately-mismatched-lockfile fixture (scratch branch or local-only demonstration, never pushed to main) — covers CIMAINT-01's required negative case, per Phase 82 D-01..D-10's "every deliberately broken push needs the owner's separate go-ahead at execution time" rule

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture, Secure SDLC | Yes | Supply-chain integrity for CI tooling itself: pinned binaries + committed checksums (never `curl \| sh`, never an unpinned third-party Action) for Trivy and actionlint; full-SHA pinning for all GitHub Actions (already enforced repo-wide) |
| V2 Authentication | No | This phase touches no application authentication code |
| V3 Session Management | No | Not applicable |
| V4 Access Control | Yes | `GITHUB_TOKEN` least-privilege scoping (CIMAINT-07): `packages: write` for image publish, `contents: write` reserved only for the tag-triggered release-creation job |
| V5 Input Validation | Partial | The OS-scan exception file and Dependabot config are repo-committed structured data; the validator script for `os-scan-exceptions.yml` must reject malformed/incomplete entries (fail closed, matching D-10) |
| V6 Cryptography | No | No cryptographic code is touched; checksum verification (SHA-256) for pinned binaries is integrity verification, not cryptographic design, and uses standard `sha256sum -c` rather than hand-rolled hashing |
| V10 Malicious Code / Supply Chain Integrity | Yes (central to this phase) | Never depend on `aquasecurity/trivy-action`/`setup-trivy` given their March 2026 compromise; pin all CI tooling (Trivy, actionlint) by version + committed checksum; Dependabot updates are classified and reviewed like any other PR (D-07), never auto-merged |
| V14 Configuration | Yes | GitHub Actions workflow configuration is the primary artifact of this phase: `permissions:` least privilege, `actionlint` static validation, Dependabot update governance, and the acceptance-register's concurrency-safety are all "secure configuration" concerns in ASVS V14's sense |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Mutable Action tag/release hijack (as happened to `trivy-action`/`setup-trivy`, March 2026) | Tampering, Spoofing | Full-SHA pin all Actions (already enforced); for non-Action tools (Trivy, actionlint) install pinned binaries with committed checksums instead of trusting any Action wrapper |
| Overly broad `GITHUB_TOKEN` permissions enabling lateral capability (e.g. a compromised publish step also able to mutate repo contents) | Elevation of Privilege | CIMAINT-07's per-job least-privilege split: `packages: write` only where pushing images, `contents: write` only in the tag-triggered release job |
| Dependency-confusion / typosquatting via automated update PRs | Tampering | Dependabot only proposes updates to already-declared dependencies at their canonical registry coordinates (no new package names introduced); D-07's "bot PRs get no special review lane" ensures a malicious-looking version bump still gets the full BM+Codex+owner-acceptance review path |
| Permanent, unreviewed vulnerability suppression via an exception file that never expires or is never re-reviewed | Repudiation | D-10's ≤30-day expiry + owner-approval field + "adding/changing an exception is a sensitive change" classification, enforced by both Trivy's native `expired_at` and the custom validator script |
| Concurrent-PR race on a shared, whole-value-overwrite acceptance register (`gh variable set`) letting one PR's approval leak into or clobber another's | Tampering, Repudiation | ACCEPT-02/D-19's PR+head-SHA-keyed register design, with concurrent-update fixture tests proving isolation, or documented serialization until that proof exists |
| A review-tooling change (Codex runner/checker/schema/prompt) grading its own PR, masking a defect in the very tool meant to catch it | Repudiation, Tampering | D-18's `audited_inputs_changed_in_diff` record / base-checker run requirement — a changed grader is flagged, not silently trusted, on its own PR |

## Sources

### Primary (HIGH confidence)
- Live repository files (read directly in this session): `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/review-acceptance.yml`, `.github/scripts/ci-job-consistency.cjs`(+test), `.github/scripts/release-policy.cjs`(+test), `.github/scripts/review-acceptance.cjs`(+test), `.github/scripts/artifact-promotion.test.cjs`, `Dockerfile`, `pyproject.toml`, `tests/codex_review_run.py`, `tests/codex_report_status.py`, `.claude/plugins/planchk-router/test/planchk-router.test.mjs`, `docs/ci-reference-baseline-plan.md`, `docs/review-classification-policy.md`, `docs/owner-cli-acceptance.md`, `docs/buildomator-greptile-pilot.md`, `docs/codex-adversarial-review-contract.md`, `docs/review-checkpoint-record.md`, `.planning/backlog/MAINTENANCE.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/85-.../85-CONTEXT.md`
- `~/.claude/plugins/cache/thejuran/vibe-check/2.12.0/phases/deep-review/01d-coverage.md` + `agents/test-sufficiency.md` + `scripts/coverage_gate.py` — installed plugin source, read directly (not inferred)
- [uv Docker integration guide](https://docs.astral.sh/uv/guides/integration/docker/) — fetched via WebFetch, confirms `uv sync --locked`/`--frozen`/`--no-install-project` semantics
- GitHub's own docs on Dependabot options reference, Dependabot security updates configuration, and `GITHUB_TOKEN` permissions — confirmed via multiple cross-verified WebSearch results quoting the official docs directly

### Secondary (MEDIUM confidence)
- [Dependabot version updates now support uv in general availability](https://github.blog/changelog/2025-03-13-dependabot-version-updates-now-support-uv-in-general-availability/) and [Dependabot security updates now support uv](https://github.blog/changelog/2025-12-16-dependabot-security-updates-now-support-uv/) — GitHub's own changelog, WebSearch-verified
- [Trivy Filtering docs (`.trivyignore.yaml` / `expired_at`)](https://trivy.dev/docs/latest/guide/configuration/filtering/) — WebSearch-verified against official Trivy docs
- Multiple corroborating 2026 GitHub issues/PRs on the Dependabot `cooldown` ecosystem restriction (`docker`/`github-actions` only support `default-days`) — cross-verified across several independent repos' CI fix PRs, not a single source
- [aquasecurity/trivy security advisory GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23) and corroborating reporting from Snyk, Microsoft, Wiz, Sysdig, The Hacker News, StepSecurity — cross-verified across 6+ independent security vendors, consistent on the core facts (malicious binary + hijacked tags, CVE-2026-33634)
- actionlint pinning options (binary+checksum, Docker digest, `reviewdog/action-actionlint`, third-party setup actions) and the `kjanat/actionlint` fork context — WebSearch, cross-referenced against the locally-installed `actionlint --version` (1.7.12) matching upstream's own release tag

### Tertiary (LOW confidence)
- Exact Trivy release version to pin (`0.76.1`) and exact actionlint checksum values quoted in search results — not independently re-verified against the live releases page in this session; flagged in Assumptions Log (A1) for recheck at plan/execution time
- `pip-audit`'s true current latest version — this research environment's `pip index versions` showed an older max than this repo's existing pin, most likely a stale local mirror; flagged (A3) and explicitly out of this phase's touch-scope

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every tool/version claim was either read directly from the live repo, fetched from official docs (uv, GitHub), or cross-verified across 3+ independent sources (Trivy compromise, Dependabot cooldown restriction)
- Architecture: HIGH — every pattern reuses a verified-existing pattern in this exact repository (pinned-tool installs, stdlib-only Node scripts, `set +e`/capture/`set -e`, exact-artifact promotion); no speculative new architecture introduced
- Pitfalls: HIGH for D-18's eight sub-items (each located and confirmed present/absent by direct code reading, with exact line context) and for the Trivy flag/exit-code gotchas (cross-verified against Trivy's own GitHub issue tracker); MEDIUM for CI-timing/overhead estimates (no live CI run available in this research session)

**Research date:** 2026-10-27
**Valid until:** 2026-11-26 (30 days) for the stable parts (repo-internal patterns, ASVS mapping); **recheck before execution** specifically for the Trivy pinned version, actionlint pinned version/checksum, and Dependabot GA status if execution slips materially past this window, since CI tooling versions and the Trivy security-advisory situation are fast-moving as of this research date.
