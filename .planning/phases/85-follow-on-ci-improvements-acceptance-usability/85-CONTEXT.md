# Phase 85: Follow-on CI Improvements & Acceptance Usability - Context

**Gathered:** 2026-10-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the remaining CI gaps and make acceptance usable under real PR traffic (CIMAINT-01..07, ACCEPT-01..03):

- the Docker image installs runtime dependencies from `uv.lock`
- grouped, bounded update PRs
- an OS-package scan of the shipped image under a written policy
- actionlint, with a skip rule that can't fake a pass
- a resolution of the Python distribution deliverable (dropped, see D-14)
- exact-commit branch-coverage evidence
- least-privilege `:main`/`:dev` publishing
- ready-state visibility before acceptance
- a concurrency-safe acceptance register
- GitHub required checks that honor the Phase 83 review classification

The phase also absorbs the owner-selected carry-forward items listed in D-16..D-19. It extends the Phase 82 CI baseline. It builds no orchestrator and adds no coverage-percentage gate.

</domain>

<decisions>
## Implementation Decisions

### Docs-only check path (ACCEPT-03)
- **D-01:** **No docs fast path. Every PR runs every required check, whatever its classification.** The ACCEPT-03 mechanism works like this:
  - (a) A classification can never reduce or skip a GitHub required check.
  - (b) GitHub requires nothing that the policy exempts ordinary docs from. Required checks today are `CI ready`, CodeQL and Review acceptance. Greptile has been optional since 2026-10-22, and Codex and vibe-check run locally.

  Rationale: under D-13 (no docs-only PRs), docs never arrive alone. A content-classifier fast path would add a new safeguard component that carries misclassification risk, all to save CI minutes on a case that hardly occurs. The planner amends the ACCEPT-03 wording in `.planning/REQUIREMENTS.md` and Phase 85 criterion 7 in `.planning/ROADMAP.md` to record this owner decision (2026-10-26). The pattern is the D-14 amendment from Phase 83. Update `docs/review-classification-policy.md`'s "GitHub does not yet check it (Phase 85, ACCEPT-03)" status line to match.
- **D-02:** **Verification uses a permanent test plus this phase's own PR. There are no throwaway PRs.**
  - Extend the existing workflow/job-consistency tests (`.github/scripts/ci-job-consistency.cjs` and its tests). The test fails if anyone adds a path filter, `paths-ignore`, a file-type condition or another skip condition that could let any PR bypass a required job or let `CI ready` pass without it.
  - Run fixture diffs for all four cases through it: ordinary-docs, sensitive-docs, mixed docs+code, and misclassified (claims ordinary docs but contains code).
  - Phase 85's own PR (mixed docs + code + sensitive workflow changes) is the real GitHub run.
  - Record in the evidence that three of the four cases are proven by test, not by separate real GitHub runs.
  - Per Phase 82 D-03/D-04, each negative case asserts its specific rejection reason and feeds input to the same script CI invokes.
- **D-03:** Greptile still runs automatically on every PR while free credits last. Disclose this in the PR as the standing rule requires; don't describe it as unnecessary.

### Automated update PRs (CIMAINT-02)
- **D-04:** **Routine update PRs open monthly.**
- **D-05:** **Updates are grouped per ecosystem, with major versions split out.** Up to three grouped PRs per cycle:
  - uv/Python dependencies
  - SHA-pinned GitHub Actions (updates must keep full-SHA pins with version comments)
  - Docker base image

  Each group holds the minor/patch bumps. A major-version bump gets its own PR. Set an open-PR limit so a backlog can't pile up. No auto-merge, ever.
- **D-06:** **Security updates open right away as separate PRs**, outside the monthly cycle.
- **D-07 amendment (owner, 2026-10-27, during planning):** The isolated Codex review for untrusted heads (bot and fork PRs) is split into **Phase 85.1**, because its security boundary kept failing plan checks on paper. Until 85.1 ships, an untrusted-mode Codex run is refused and recorded INCOMPLETE (never clean), and a bot PR gets CI plus a per-PR owner-approved fallback review under D-16. D-07 below remains the goal; 85.1 delivers it.
- **D-07:** **Bot PRs get no special review lane.** They are classified by content like any PR. A runtime dependency, Actions or base-image change is consequential, so it gets CI plus the paired BM + Codex review and exact-commit owner acceptance. Before choosing exact configuration, recheck current Dependabot ecosystem support for uv, github-actions with SHA pins, and docker, plus grouping and cooldown behavior (per the CI baseline plan).

### OS-image security scan (CIMAINT-03)
- **D-08:** **A vulnerability blocks when it is Critical or High severity and a fix is available.** Lower severities are reported, not enforced.
- **D-09:** **Critical and High vulnerabilities with no fix available are reported in the CI summary and don't block.**
- **D-10:** **Exceptions require owner approval and expire after at most 30 days.**
  - Each exception is an entry in a repository file: vulnerability ID, affected package, reason, owner approval, and expiry date.
  - An expired exception blocks again automatically.
  - An exception with no expiry, or with an expiry more than 30 days out, is rejected.
  - Adding or changing an exception is a sensitive change and goes through normal review.
  - The written policy (severity, fix availability, scanner errors, exceptions) is committed **before** the gate is enforced.
- **D-11:** **The gate applies everywhere: it is part of `CI ready` on PRs, main pushes and releases**, so a publishable image always passed the scan. The response to an overnight red is a base-image rebuild (via the update PRs) or a 30-day exception.
- **D-12:** **Scanner errors fail closed.** Examples are a DB download failure or an unparseable result. This matches the existing `pip-audit --strict` job. The scan runs against the exact audited image artifact. It uses one OS-package scanner, which must not duplicate pip-audit's Python coverage as a second equivalent gate.

### Scope edges
- **D-13:** The planchk-router plugin tests join CI. This was the owner's decision on 2026-10-26, carried from quick 261026-s2v. Run `node --test .claude/plugins/planchk-router/test/planchk-router.test.mjs` with an explicit file path or glob; on Node 25.9, `node --test <dir>/` does not recurse.
- **D-14:** **The owner drops the Python distributions (2026-10-26).** Releases ship the Docker image only.
  - Remove the wheel/sdist release assets: `dist/*` in `release.yml`'s `gh release create`/`upload`, and the related build/assert steps in CI wherever they exist only for distribution.
  - Record this decision as CIMAINT-05's outcome in REQUIREMENTS/ROADMAP. No clean-install wheel smoke test is built.
  - Check that nothing else consumes `dist/`, such as release-policy tests or artifact checks, before removing it. Update those tests rather than leaving dangling assertions.
  - Existing releases' assets are left untouched.

### Folded carry-forward (from `.planning/backlog/MAINTENANCE.md` → "Phase 83 carry-forward to Phase 85")
- **D-15:** The owner folded in all three carry-forward groups offered. Items not listed below stay in the backlog: the card-template text-matching refactor (product code) and the craft-skill `code-reviewer` sticky accept (needs separate clone approval). When an item is completed, remove it from MAINTENANCE.md or mark it resolved.
- **D-16:** **Codex fallback definition** (round-7 WR-01 + IN-01 + IN-02):
  - Define what counts as an owner-approved fallback when a paired Codex pass stays INCOMPLETE/PENDING, and add a field in the checkpoint record to capture it.
  - State explicitly in the contract and record docs that "wait" and "retry later" block acceptance.
  - Add the paired Codex review to the pilot checklist's approval precondition.
  - Vibe-check must not be named as a Codex substitute in a way that contradicts the checkpoint record. Resolve the contradiction.
- **D-17:** **Review-list drift guard** (arch-1 + SA-03):
  - Add one test asserting that three hand-kept lists of review-machinery files agree: the classification policy's sensitive row, the Codex scope exclusions, and the acceptance-prerequisite list.
  - Treat `*-PLAN.md` files as agent instructions (sensitive) for classification. Align the Codex review diff's blanket `.planning/**/*.md` exclusion accordingly.
- **D-18:** **Codex runner hardening.** All items are in review tooling: `tests/codex_review_run.py`, `tests/codex_report_status.py`, the schema and the contract prompt.
  - A changed checker, runner, schema or prompt must not be the only grader of its own PR. Add a base-checker run and/or an `audited_inputs_changed_in_diff` record (WR-03/ARCH-03/impact-001).
  - Verify `--trusted` independently instead of trusting the operator (SA-01).
  - SIGTERM/SIGHUP must not leave the Codex/pytest process group orphaned (round-6 WR-01).
  - Put a time limit on the post-kill output drain (bugs-002).
  - A `null` exit_code or a trivial command must not count as evidence (hollow-report guard).
  - Log, rather than silently skip, a `getpass.getuser()` failure in `redact_local_paths()`.
  - Correct the overclaiming docstring, and redact home paths in future raw `.jsonl`/`.last.json` output (WR-04). Already-committed raw evidence stays as published.
  - `_write_evidence_copy` cleans up the empty directory it leaves when `os.open()` fails (rm-001).

  Each fix gets a focused regression test. Because this phase changes the review machinery, the D-18 audited-inputs mechanism should be in place before the phase's own final Codex pass relies on it. Otherwise, disclose that the phase PR's grader was changed in the same diff.

### Acceptance usability (ACCEPT-01, ACCEPT-02), Claude's approach as presented to the owner
- **D-19:** The register lives today in two repository-wide variables, `REVIEW_DISPOSITIONS` and `REVIEW_BLOCKERS`, which `review-acceptance.yml` reads. With concurrent PRs, one PR's update can overwrite another's.
  - Key every entry by PR number + full head SHA so one PR's update can't erase another's evidence or satisfy another's gate. Prove this with tests that use concurrent-update fixtures.
  - Until that proof exists, serialize final acceptance updates and document the rule in `docs/owner-cli-acceptance.md` / `docs/buildomator-greptile-pilot.md`.
  - SHA binding is unchanged.
  - Changing the pinned gate commit in `review-acceptance.yml` is a safeguard change that needs independent inspection.
- **D-20:** ACCEPT-01: before final approval is requested, the PR is marked ready and the machine-checkable prerequisites are visible in one place. Prerequisites: CI on the head, Codex status, dispositions written, register entries present. This avoids an approval that fails because of a missing record, followed by a repeat approval. Build it on the existing D-12 (Phase 83) acceptance checklist; don't build a new orchestrator.

### Carried forward (locked in earlier phases, not re-asked)
- Phase 82 evidence standard (D-01..D-10, D-34):
  - Negative tests pass only on the specific expected rejection, and use the same entry points CI invokes.
  - Wiring is tested separately from function behavior.
  - A claim that GitHub enforces something needs a real GitHub run.
  - **Every deliberately broken push needs the owner's separate go-ahead at execution time.** Never main, never a production tag.
  - Evidence records PR head, base and tested SHA separately, with a reconciliation line. This matters for CIMAINT-06's head-vs-merge-commit binding.
- Phase 82 D-14/D-15/D-16: there is a ~5-minute added-PR-time target. If added time exceeds it, investigate and report the tradeoff to the owner before expanding the budget. No retries that turn a failure into a pass. Never remove required coverage to get green.
- Phase 83 D-13 and memory:
  - one branch (`ci-followon`, cut 2026-10-26 from `codex-plan-checker` at `2682386`, carrying the unpushed Phase 84 records and quick 261026-s2v)
  - one PR at phase end
  - no docs-only PRs
  - batched pushes, with docs commits held until the next substantive push
- Phase 83 review workflow:
  - paired BM + Codex on every BM review run
  - PR classification recorded per head
  - RISK-01 note and vibe-check recommendation when risk is high
  - exact-commit owner acceptance via `review-acceptance`

  This phase edits workflows, acceptance policy and review machinery, so expect a **high** risk assessment.

### Claude's Discretion
- OS-package scanner choice. One scanner only; pin it by version/SHA. Recheck current tools.
- How the Dockerfile consumes `uv.lock` (CIMAINT-01). Compiled Tailwind assets and runtime behavior stay unchanged. Design the lockfile/image consistency check so that a deliberately mismatched lockfile fails it.
- actionlint wiring, and the "skip when workflows are unchanged can't fake a pass" rule (CIMAINT-04). Example: `CI ready` verifies that the lint job either ran or was legitimately not needed, decided by a check that can't be bypassed.
- Coverage tooling and artifact naming (CIMAINT-06):
  - branch coverage
  - no percentage gate
  - test failure exit status preserved
  - artifact bound to tested SHA + run, recording PR head vs synthetic merge
  - generated files kept out of commits
  - test-runtime overhead recorded
  - discoverable by vibe-check's test-sufficiency lane
  - a wrong-commit or missing report rejected as evidence
- How the release job is split for least privilege (CIMAINT-07). Only tagged GitHub Release creation holds `contents: write`. Demonstrate a successful `:main`/`:dev` publish under the narrower permission, without building an orchestration framework.
- Exact Dependabot keys, open-PR limits and schedule day.
- Plan/wave structure. The phase is large: 10 requirements plus three carry-forward groups.

</decisions>

<specifics>
## Specific Ideas

- Treat the CI reference-baseline plan's "Retain / do not copy blindly" list as constraints:
  - Retain exact-artifact promotion, checks tied to the intended commit, full-SHA action enforcement, read-default credentials, timeouts, and cancellation/serialization.
  - Avoid rebuild-after-test publication, registry-write permissions in PR tests, arbitrary coverage percentages, redundant AI reviewers, and custom orchestrators.
- Keep update-PR and scan noise manageable. The baseline plan's "definition of ready" asks for clear ownership and manageable noise.
- At phase start there are 0 open Dependabot alerts and no open PRs (checked 2026-10-26). Recheck at release-planning time per the global release rule.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` § Phase 85: goal and success criteria 1–7. Criterion 4 (wheel) and 7 (ACCEPT-03) get amended per D-14/D-01.
- `.planning/REQUIREMENTS.md`: CIMAINT-01..07, ACCEPT-01..03, and the standing rules at the top (push batching, docs-review disclosure).
- `docs/ci-reference-baseline-plan.md`: "Next bounded improvements", "Coverage evidence for review", "Acceptance usability and permissions", "Retain / do not copy blindly", "Definition of ready".

### Review workflow and acceptance
- `docs/review-classification-policy.md`: the classes ACCEPT-03 honors, and its status line to update.
- `docs/owner-cli-acceptance.md`: the acceptance procedure (ready state, register write timing, exact-SHA rules).
- `docs/buildomator-greptile-pilot.md`: the register shape (`REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS`), checkpoints, and the pilot checklist (D-16).
- `docs/codex-adversarial-review-contract.md`: the Codex contract and its fallback wording (D-16).
- `docs/review-checkpoint-record.md`: the per-head record, which gets a fallback field (D-16).
- `docs/bm-greptile-codex-blueprint.md`: the background blueprint.

### Carry-forward
- `.planning/backlog/MAINTENANCE.md` → "Phase 83 carry-forward to Phase 85" and "Quick 261026-s2v carry-forward to Phase 85": the exact items folded in by D-13, D-16..D-18.
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW-EVIDENCE.md`: original finding IDs and context for the carry-forward items.

### Prior decisions
- `.planning/phases/82-ci-tests-what-we-ship/82-CONTEXT.md`: evidence standard (D-01..D-10), time budget (D-14), commit-identity fields (D-34).
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-CONTEXT.md`: review pairing, classification, and PR shape.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/scripts/ci-job-consistency.cjs` + `.test.cjs`: the place for the ACCEPT-03 no-skip wiring test (D-02), new required jobs (OS scan, actionlint, planchk tests), and the gate-bypass checks.
- `.github/scripts/release-policy.cjs` (`REQUIRED_JOBS`, `parseReleaseTag`, `releaseIdentityGate`) + tests: the release gate. New mandatory jobs must be added here and to `CI ready` together.
- `.github/scripts/review-acceptance.cjs` (`assess`) + `.test.cjs`: the register logic for ACCEPT-02. The workflow pins it to policy commit `25f1ecd…`.
- `.github/workflows/ci.yml` `dependencies` job: the `uv export --locked` + `pip-audit --strict` pattern, fail-closed. Model the OS scan's error handling on it.
- `.github/workflows/ci.yml` `docker` job: the saved `audited-image` artifact (`image.tar`, `image-id.txt`, `image-requirements.txt`). The OS scan and the lockfile/image consistency check run against this exact artifact.
- `tests/codex_review_run.py`, `tests/codex_report_status.py`, `.claude/schemas/codex-review-findings.schema.json`: the D-18 hardening targets.

### Established Patterns
- Actions are pinned by full SHA with a version comment, and the repository enforces it. Dependabot updates must preserve this.
- `permissions: contents: read` by default at workflow level. Only `release.yml`'s `release` job has `contents: write` today; that is the target of CIMAINT-07.
- `CI ready` aggregates `needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e]`. New required jobs join it, and a skipped job never counts as success.
- The Dockerfile's builder stage compiles Tailwind. The runtime stage runs `pip install .` from `pyproject.toml` (the CIMAINT-01 gap).

### Integration Points
- `release.yml`: `preflight` → `release`, triggered by `workflow_run` (main → `:main`/`:dev`) and `v*` tags (→ GitHub Release with `dist/*`, which is removed per D-14).
- `review-acceptance.yml`: reads `vars.REVIEW_DISPOSITIONS` / `vars.REVIEW_BLOCKERS`, `concurrency: acceptance-<PR>`, protected `review-acceptance` environment.
- `.claude/plugins/planchk-router/test/planchk-router.test.mjs`: new CI test target (D-13). CI's Node step currently globs only `.github/scripts/*.test.cjs`.

</code_context>

<deferred>
## Deferred Ideas

- **Docs-only CI fast path**: rejected for now (D-01). Revisit only if docs-only changes ever become common, which would also require revisiting D-13.
- **Wheel clean-install smoke test**: not needed because distributions are dropped (D-14). Revisit if a pip/PyPI install path is ever added.
- **Remaining backlog items** stay in `.planning/backlog/MAINTENANCE.md`: the card-template text-matching refactor and the craft-skill `code-reviewer` sticky accept (needs separate clone approval).

</deferred>

---

*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Context gathered: 2026-10-26*
