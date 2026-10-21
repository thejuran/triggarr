# Requirements: Triggarr v2.13 CI & Review Workflow

**Defined:** 2026-10-21
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Sources (owner-confirmed 2026-10-21, as written):** `docs/ci-reference-baseline-plan.md` and `docs/bm-greptile-codex-blueprint.md`.

Every requirement whose acceptance claims a gate needs **positive and negative evidence** (the correct case passes, a deliberately broken case fails). Each requirement records whether it is **GitHub-enforced** or **instruction-enforced** (BM/Claude follows written rules; nothing on GitHub blocks a violation).

**Standing rules for the whole milestone:**
- The current review process — Greptile, routine manually requested vibe-check, and exact-commit owner acceptance — stays in force on every PR until the owner explicitly retires a part of it (PILOT-03). No pilot comparison, new control or recommendation waives it earlier.
- The BM update is planned work with a recorded baseline and an owner-approved target (REVIEW-01), not something implied by this requirements discussion.
- Codex plan-checker routing (PLANCHK) is a separately gated investigation; nothing from it is activated in this repository without owner approval.

## v2.13 Requirements

### CI tests what we ship

- [ ] **CISHIP-01**: CI starts the exact image it will publish, through its normal entrypoint, with isolated test config and mocked/test services, and verifies health, setup/login, static assets, writable config and persistence across a restart. A broken entrypoint and a missing static asset each make the check fail.
- [ ] **CISHIP-02**: A small browser regression suite covers the connection-pill request-loop regression and critical setup/login behavior, asserting observable behavior (not screenshots). Reintroducing the polling bug makes it fail; failure logs/screenshots are uploaded as artifacts without secrets.
- [ ] **CISHIP-03**: Before any version-tag publication, CI rejects a tag that disagrees with the package metadata or image version. Mismatch and match cases are tested without publishing a production tag; exact-commit CI and artifact identity checks are preserved.
- [ ] **CISHIP-04**: The new mandatory jobs join the existing required aggregate gate and consistency checks together. A missing or skipped mandatory job cannot let the gate pass, and the published image is still the tested, audited artifact (not rebuilt).

### Follow-on CI improvements

- [ ] **CIMAINT-01**: The Docker image installs runtime dependencies from the same locked set CI tests (uv.lock), keeping compiled frontend assets and runtime behavior unchanged.
- [ ] **CIMAINT-02**: Grouped, bounded automated update PRs exist for uv dependencies, SHA-pinned Actions and the Docker base image. No auto-merge; manual acceptance stays.
- [ ] **CIMAINT-03**: The shipped image's OS packages are scanned, under a written policy for severity, fix availability, scanner errors and time-limited documented exceptions, defined before the gate is enforced. No duplicate equivalent scanners.
- [ ] **CIMAINT-04**: Workflow changes are linted (actionlint). Skipping the lint when workflows are unchanged cannot let the required gate pass when mandatory validation was omitted.
- [ ] **CIMAINT-05**: The built wheel's metadata is validated, and it is installed in a clean environment and started via the supported interface with packaged templates/assets present. Python distributions stay release deliverables unless the owner explicitly decides to drop them; if so, that decision is recorded instead.
- [ ] **CIMAINT-06**: The CI pytest run produces a branch-coverage `coverage.xml` artifact bound to the tested full commit SHA and run (PR head distinguished from the synthetic merge commit), without a percentage gate and without masking test failures. vibe-check's test-sufficiency lane can discover it; a wrong-commit or missing report is rejected as evidence. Test-runtime overhead is recorded.
- [ ] **CIMAINT-07**: Publishing `:main`/`:dev` images no longer requires repository contents-write permission; only tagged GitHub release creation holds it.

### Acceptance usability

- [ ] **ACCEPT-01**: Before final owner approval is requested, the PR is marked ready and the machine-checkable prerequisites are visible, so avoidable repeat approvals are not needed. SHA binding is unchanged.
- [ ] **ACCEPT-02**: The acceptance register is shown to handle concurrent PRs without one PR's update erasing another's evidence or satisfying another PR's gate; until that is shown, final acceptance updates are serialized and the rule is documented.

### Paired BM + Codex review

- [ ] **REVIEW-01**: Before any BM change, a baseline is recorded (current configuration saved, plugin and runtime versions) and the proposed target BM version's native review and fixer behavior is assessed: which review paths run review automatically, depth handling, fix loop, and whether it can invoke or request an external pass. The owner approves an exact target version and a bounded list of settings changes. BM is then updated through its supported procedure, the loaded version is confirmed with `/bm:version`, and only the approved settings change (expected: `workflow.code_review` on at `standard` depth); all other settings are preserved.
- [ ] **REVIEW-02**: Every BM code review — phase execution, quick task, explicit review command, and review after fixes — is followed by an independent Codex adversarial pass on the same checkpoint commit, controlled by `CLAUDE.md` and supported BM configuration/instructions (no BM fork, no new orchestrator). Repository instructions fill only the gaps REVIEW-01 found in BM's native behavior; they do not duplicate it. Each path is demonstrated in practice.
- [ ] **REVIEW-03**: If BM cannot invoke Codex, it requests the exact-SHA review explicitly and tracks it as pending. Missing, failed, skipped, wrong-commit or stale Codex evidence is reported as incomplete, never as a clean review — demonstrated with a negative case.
- [ ] **REVIEW-04**: Each Codex report states the inspected full head and base SHAs, coverage, exclusions, commands run, findings (source/run-qualified ID, severity, location, trigger, path, consequence, evidence, suggested fix; reproduced vs hypothesis) and limitations. Finding dispositions survive bot thread resolution.
- [ ] **REVIEW-05**: Each review records requested versus actual depth and the instruction/configuration files responsible; any BM effective-depth reduction (e.g. deep → standard above 50 files) is reported rather than labelled deep.
- [ ] **REVIEW-06**: Checkpoint evidence is bound to one pushed head: Greptile reviews the same head as Codex, the head stays frozen while independent reviews run, and after any fix the affected tests, finding dispositions and every applicable review are refreshed for the new head, with the original findings preserved for comparison. Evidence from an earlier head never counts for a later one.

### Risk-based review depth

- [ ] **RISK-01**: At each checkpoint, BM's report records scope (PR, full head/base SHAs, affected behavior, full-PR vs follow-up), risk level with concrete failure scenarios, recommended depth and specialist focus, and the required evidence — refreshed when revisions change the SHA or risk.
- [ ] **RISK-02**: When risk is high, BM explicitly recommends an additional vibe-check with rationale and scope, and records the owner's decision. It never substitutes vibe-check for Codex or Greptile, never waives findings and never reduces mandatory coverage. Demonstrated on a high-risk checkpoint.

### Codex plan-checker investigation

- [ ] **PLANCHK-01**: Whether the installed Claude Code runtime supports an `agent.spawn` hook that changes only `bm:bm-plan-checker`'s model through model-gateway is verified and recorded (fields, model selection, permissions, resume). Any needed runtime update is proposed separately, not applied silently.
- [ ] **PLANCHK-02**: If supported, a scratch-project pilot routes only the plan checker, proves the routed backend from gateway metadata while other agents stay on their models, and exercises initial check, a known-defective plan, revision/recheck and post-bounce checks. Unavailable gateway/model or incomplete output leaves the check incomplete with an explicit error. Nothing is activated in this repository without owner approval.
- [ ] **PLANCHK-03**: The blind comparison on the original Phase 81 plans runs per the blueprint (recovered, hashed inputs; matched sessions; withheld answer key; separate revision round), or is recorded as unavailable if exact originals cannot be recovered. Adoption criteria are set before the runs.

### Pilot and reference record

- [ ] **PILOT-01**: 3–5 representative PRs run under the paired workflow, drawn from suitable authorized work (this milestone's own PRs and owner-authorized maintenance or backlog work). Aim to include a small fix, state/error-path logic, a UI or security-sensitive change and at least one larger change; no product change is invented to fill a category, and any category without suitable work is recorded as a gap. Each PR records, recording per reviewer: confirmed consequential defects, false positives, later-found misses, revision rounds, review time, observable usage/cost and owner effort.
- [ ] **PILOT-02**: At least one substantial pilot PR gets a recorded side-by-side comparison of vibe-check against the paired workflow. This is in addition to routine vibe-check, which continues on every pilot PR until the owner retires it.
- [ ] **PILOT-03**: The owner's decisions are recorded: whether to retire routine vibe-check, and whether BM/Codex completion stays a manual owner check or the existing acceptance gate is extended to require those reports. Recording the decisions completes this requirement. If extension is chosen, it is scheduled as its own later reviewed change (FUT-03) and is not required before this milestone closes, unless the owner explicitly pulls it in.
- [ ] **PILOT-04**: Reusable adoption guidance for other repositories is written, distinguishing instruction-enforced from GitHub-enforced requirements and listing what not to copy blindly.

## Future Requirements

Deferred; not in this roadmap.

- **FUT-01**: Reusable shared workflow for other repositories — only after the pattern is proven in two repositories.
- **FUT-02**: Seedsyncarr adoption (enforceable PR/check rules, exact-artifact publication, security/update coverage).
- **FUT-03**: Automated acceptance-gate enforcement of BM/Codex report presence — scheduled only if the owner chooses it under PILOT-03; a separate reviewed change to the existing gate, after this milestone unless the owner pulls it in.

## Out of Scope

| Feature | Reason |
|---------|--------|
| A new custom orchestrator, polling service or scheduler | Both plans prohibit it; BM + instructions + existing gates only |
| Forking or patching BM, the host, tool schemas or global model aliases | Supported configuration only |
| Auto-merge of dependency PRs | Manual acceptance retained |
| Coverage-percentage merge gate | Coverage informs review; it does not prove correctness |
| ARM64 images | Not currently supported; add only if it becomes intentional |
| Rebuild-after-test publication; registry writes in PR tests | Exact tested artifact must be published |
| Changing Greptile's tier during the comparison | Keeps the reviewer variable fixed |
| Weakening CI, acceptance, action pinning or bypass protections | Existing safeguards stay intact |
| New product/runtime features made for this milestone | It changes CI and review workflow only; pilot PRs use existing authorized work |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CISHIP-01 | Phase 82 | Pending |
| CISHIP-02 | Phase 82 | Pending |
| CISHIP-03 | Phase 82 | Pending |
| CISHIP-04 | Phase 82 | Pending |
| REVIEW-01 | Phase 83 | Pending |
| REVIEW-02 | Phase 83 | Pending |
| REVIEW-03 | Phase 83 | Pending |
| REVIEW-04 | Phase 83 | Pending |
| REVIEW-05 | Phase 83 | Pending |
| REVIEW-06 | Phase 83 | Pending |
| RISK-01 | Phase 83 | Pending |
| RISK-02 | Phase 83 | Pending |
| PLANCHK-01 | Phase 84 | Pending |
| PLANCHK-02 | Phase 84 | Pending |
| PLANCHK-03 | Phase 84 | Pending |
| CIMAINT-01 | Phase 85 | Pending |
| CIMAINT-02 | Phase 85 | Pending |
| CIMAINT-03 | Phase 85 | Pending |
| CIMAINT-04 | Phase 85 | Pending |
| CIMAINT-05 | Phase 85 | Pending |
| CIMAINT-06 | Phase 85 | Pending |
| CIMAINT-07 | Phase 85 | Pending |
| ACCEPT-01 | Phase 85 | Pending |
| ACCEPT-02 | Phase 85 | Pending |
| PILOT-01 | Phase 86 | Pending |
| PILOT-02 | Phase 86 | Pending |
| PILOT-03 | Phase 86 | Pending |
| PILOT-04 | Phase 86 | Pending |

**Coverage:**
- v2.13 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-21*
*Last updated: 2026-10-21 after roadmap creation (5 phases, 82-86, 100% coverage)*
