# Requirements: Triggarr v2.13 CI & Review Workflow

**Defined:** 2026-10-21
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Sources (owner-confirmed 2026-10-21, as written):** `docs/ci-reference-baseline-plan.md` and `docs/bm-greptile-codex-blueprint.md`.

Every requirement whose acceptance claims a gate needs **positive and negative evidence** (the correct case passes, a deliberately broken case fails). Each requirement records whether it is **GitHub-enforced** or **instruction-enforced** (BM/Claude follows written rules; nothing on GitHub blocks a violation).

**Standing rules for the whole milestone:**
- The current review process — routine manually requested vibe-check and exact-commit owner acceptance, plus Greptile when it runs — stays in force for code and control changes until the owner explicitly retires a part of it (PILOT-03). No pilot comparison, new control or recommendation waives it earlier.
- **Greptile is optional (owner decision 2026-10-22).** The repository is on Greptile's free open-source tier (300 reviews per billing period), and paid credits are not bought when it runs out. `Greptile Review` is no longer a required status check, and review acceptance passes on a head with no Greptile review. A Greptile review that does run must still finish successfully, and its findings still need current-head dispositions. Where a requirement below names Greptile, it applies only when Greptile ran on that head. When Greptile is unavailable, a safeguard change still gets independent inspection by another reviewer (for example a Codex review).
- Ordinary documentation and planning-only changes follow the content-based classification policy (REVIEW-07, REVIEW-08) once Phase 83 defines it. Until Phase 85's GitHub mechanism (ACCEPT-03) is implemented and verified, existing GitHub protections stay exactly as they are, and any review that still runs automatically on a docs-only PR (currently Greptile, while free credits last) is disclosed in that PR rather than described as unnecessary. Phase 85 D-01 (2026-10-26) resolves the mechanism as no fast path: required checks stay unconditional for every PR, and automatic reviews on docs content keep being disclosed.
- Exact-commit owner acceptance applies to every PR, whatever its classification.
- Pushes are batched, because every push to a PR uses one of the limited free Greptile reviews (owner instruction 2026-10-21; paid credits are not bought). Docs-only, evidence and tracking commits are held locally and go out with the next substantive push. Fixes are batched into one checkpoint push, not pushed one at a time. Deliberately broken demonstration pushes are kept to the minimum the plan requires. This is instruction-enforced: nothing on GitHub blocks an extra push.
- The BM update is planned work with a recorded baseline and an owner-approved target (REVIEW-01), not something implied by this requirements discussion.
- Codex plan-checker routing (PLANCHK) is a separately gated investigation; nothing from it is activated in this repository without owner approval.

## v2.13 Requirements

### CI tests what we ship

- [x] **CISHIP-01**: CI starts the exact image it will publish, through its normal entrypoint, with isolated test config and mocked/test services, and verifies health, setup/login, static assets, writable config and persistence across a restart. A broken entrypoint and a missing static asset each make the check fail.
- [x] **CISHIP-02**: A small browser regression suite covers the connection-pill request-loop regression and critical setup/login behavior, asserting observable behavior (not screenshots). Reintroducing the polling bug makes it fail; failure logs/screenshots are uploaded as artifacts without secrets.
- [x] **CISHIP-03**: Before any version-tag publication, CI rejects a tag that disagrees with the package metadata or image version. Mismatch and match cases are tested without publishing a production tag; exact-commit CI and artifact identity checks are preserved.
- [x] **CISHIP-04**: The new mandatory jobs join the existing required aggregate gate and consistency checks together. A missing or skipped mandatory job cannot let the gate pass, and the published image is still the tested, audited artifact (not rebuilt).

### Follow-on CI improvements

- [ ] **CIMAINT-01**: The Docker image installs runtime dependencies from the same locked set CI tests (uv.lock), keeping compiled frontend assets and runtime behavior unchanged.
- [ ] **CIMAINT-02**: Grouped, bounded automated update PRs exist for uv dependencies, SHA-pinned Actions and the Docker base image. No auto-merge; manual acceptance stays.
- [ ] **CIMAINT-03**: The shipped image's OS packages are scanned, under a written policy for severity, fix availability, scanner errors and time-limited documented exceptions, defined before the gate is enforced. No duplicate equivalent scanners.
- [ ] **CIMAINT-04**: Workflow changes are linted (actionlint). Skipping the lint when workflows are unchanged cannot let the required gate pass when mandatory validation was omitted.
- [ ] **CIMAINT-05**: The built wheel's metadata is validated, and it is installed in a clean environment and started via the supported interface with packaged templates/assets present. Python distributions stay release deliverables unless the owner explicitly decides to drop them; if so, that decision is recorded instead. Owner decision 2026-10-26 (Phase 85 D-14): Python distributions are dropped. Releases ship the Docker image only; the wheel/sdist release assets and their distribution-only CI/release steps are removed, no clean-install wheel smoke test is built, and existing releases' assets are left untouched.
- [ ] **CIMAINT-06**: The CI pytest run produces a branch-coverage `coverage.xml` artifact bound to the tested full commit SHA and run (PR head distinguished from the synthetic merge commit), without a percentage gate and without masking test failures. vibe-check's test-sufficiency lane can discover it; a wrong-commit or missing report is rejected as evidence. Test-runtime overhead is recorded.
- [ ] **CIMAINT-07**: Publishing `:main`/`:dev` images no longer requires repository contents-write permission; only tagged GitHub release creation holds it.

### Acceptance usability

- [ ] **ACCEPT-01**: Before final owner approval is requested, the PR is marked ready and the machine-checkable prerequisites are visible, so avoidable repeat approvals are not needed. SHA binding is unchanged.
- [ ] **ACCEPT-02**: The acceptance register is shown to handle concurrent PRs without one PR's update erasing another's evidence or satisfying another PR's gate; until that is shown, final acceptance updates are serialized and the rule is documented.
- [ ] **ACCEPT-03**: GitHub's required checks honor the REVIEW-07 classification without weakening protection for code or control changes. The mechanism is designed and then verified with four cases: an ordinary-docs PR, a sensitive-docs PR (e.g. agent instructions or a workflow file), a mixed docs-and-code PR, and a misclassified PR that claims ordinary docs but contains a consequential change and must still get the full checks. Required checks are never disabled ad hoc; exact-commit owner acceptance stays required for every PR. Until this is verified, existing protections are preserved and remaining automatic docs reviews are disclosed (see standing rules). Owner decision 2026-10-26 (Phase 85 D-01): there is no docs fast path. Every PR runs every required check whatever its classification; a classification can never reduce or skip a GitHub required check, and GitHub requires nothing that the policy exempts ordinary docs from (required checks: CI ready, CodeQL, Review acceptance). The mechanism is a permanent test that fails if any path filter or skip condition could let a PR bypass a required job (D-02). The ordinary-docs, sensitive-docs and misclassified cases are proven by that test with fixture diffs, not by separate GitHub runs; Phase 85's own mixed PR is the real GitHub run. Greptile still runs automatically while free credits last and is disclosed in each PR (D-03).

### Paired BM + Codex review

- [ ] **REVIEW-01**: Before any BM change, a baseline is recorded (current configuration saved, plugin and runtime versions) and the proposed target BM version's native review and fixer behavior is assessed: which review paths run review automatically, depth handling, fix loop, and whether it can invoke or request an external pass. The owner approves an exact target version and a bounded list of settings changes. BM is then updated through its supported procedure, the loaded version is confirmed with `/bm:version`, and only the approved settings change (expected: `workflow.code_review` on at `standard` depth); all other settings are preserved.
- [ ] **REVIEW-02**: Every BM code-review run — phase execution, quick task, explicit review command, and review after fixes — is followed by an independent Codex adversarial pass on the same checkpoint commit (this pairs Codex with each code-review run; it does not force code-review runs for ordinary planning edits, per REVIEW-07), controlled by `CLAUDE.md` and supported BM configuration/instructions (no BM fork, no new orchestrator). Repository instructions fill only the gaps REVIEW-01 found in BM's native behavior; they do not duplicate it. Each path is demonstrated in practice.
- [ ] **REVIEW-03**: If BM cannot invoke Codex, it requests the exact-SHA review explicitly and tracks it as pending. Missing, failed, skipped, wrong-commit or stale Codex evidence is reported as incomplete, never as a clean review — demonstrated with a negative case.
- [ ] **REVIEW-04**: Each Codex report states the inspected full head and base SHAs, coverage, exclusions, commands run, findings (source/run-qualified ID, severity, location, trigger, path, consequence, evidence, suggested fix; reproduced vs hypothesis) and limitations. Finding dispositions survive bot thread resolution.
- [ ] **REVIEW-05**: Each review records requested versus actual depth and the instruction/configuration files responsible; any BM effective-depth reduction (e.g. deep → standard above 50 files) is reported rather than labelled deep.
- [ ] **REVIEW-06**: Checkpoint evidence is bound to one pushed head: Greptile reviews the same head as Codex, the head stays frozen while independent reviews run, and after any fix the affected tests, finding dispositions and every applicable review are refreshed for the new head, with the original findings preserved for comparison. Evidence from an earlier head never counts for a later one.
- [ ] **REVIEW-07**: A written review-classification policy exists. Ordinary documentation and planning-only changes receive a focused consistency review; Greptile, independent Codex code review and vibe-check are not routinely required for them. Classification depends on content, not file extension: changes to agent instructions, executable workflows, hooks, permissions, acceptance or release policy, or operational procedures are sensitive and require a risk assessment (RISK-01) and the applicable technical review, even when they live in Markdown. A mixed PR follows the requirements of its most consequential change.
- [ ] **REVIEW-08**: Each PR records its classification and the rationale against its exact head SHA, and is reclassified when the head changes. Blanket "every PR" review wording is removed from `CLAUDE.md` and the BM/repository instructions and replaced by the REVIEW-07 policy, while REVIEW-02's pairing of Codex with every BM code-review run is kept. Demonstrated on Phase 83's own sensitive-docs/mixed PR (owner decision 2026-10-22, Phase 83 D-14: the ordinary-docs-PR demonstration is removed because docs-only PRs are no longer opened; the policy still defines how ordinary docs/planning commits inside phase PRs are treated).

### Risk-based review depth

- [ ] **RISK-01**: At each checkpoint, BM's report records scope (PR, full head/base SHAs, affected behavior, full-PR vs follow-up), risk level with concrete failure scenarios, recommended depth and specialist focus, and the required evidence — refreshed when revisions change the SHA or risk.
- [ ] **RISK-02**: When risk is high, BM explicitly recommends an additional vibe-check with rationale and scope, and records the owner's decision. It never substitutes vibe-check for Codex or Greptile, never waives findings and never reduces mandatory coverage. Demonstrated on a high-risk checkpoint.

### Codex plan-checker investigation

- [x] **PLANCHK-01**: Whether the installed Claude Code runtime supports an `agent.spawn` hook that changes only `bm:bm-plan-checker`'s model through model-gateway is verified and recorded (fields, model selection, permissions, resume). Any needed runtime update is proposed separately, not applied silently.
- [x] **PLANCHK-02**: If supported, a scratch-project pilot routes only the plan checker, proves the routed backend from gateway metadata while other agents stay on their models, and exercises initial check, a known-defective plan, revision/recheck and post-bounce checks. Unavailable gateway/model or incomplete output leaves the check incomplete with an explicit error. Nothing is activated in this repository without owner approval.
- [x] **PLANCHK-03**: The blind comparison on the original Phase 81 plans runs per the blueprint (recovered, hashed inputs; matched sessions; withheld answer key; separate revision round), or is recorded as unavailable if exact originals cannot be recovered. Adoption criteria are set before the runs.

### Pilot and reference record

- [ ] **PILOT-01**: 3–5 representative PRs run under the paired workflow, drawn from suitable authorized work (this milestone's own PRs and owner-authorized maintenance or backlog work). Aim to include a small fix, state/error-path logic, a UI or security-sensitive change and at least one larger change; no product change is invented to fill a category, and any category without suitable work is recorded as a gap. Each PR records, per reviewer: confirmed consequential defects, false positives, later-found misses, revision rounds, review time, observable usage/cost and owner effort.
- [ ] **PILOT-02**: At least one substantial pilot PR gets a recorded side-by-side comparison of vibe-check against the paired workflow. This is in addition to routine vibe-check, which continues on every pilot PR that the current process requires it for until the owner retires it.
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
| CISHIP-01 | Phase 82 | Complete |
| CISHIP-02 | Phase 82 | Complete |
| CISHIP-03 | Phase 82 | Complete |
| CISHIP-04 | Phase 82 | Complete |
| REVIEW-01 | Phase 83 | Pending |
| REVIEW-02 | Phase 83 | Pending |
| REVIEW-03 | Phase 83 | Pending |
| REVIEW-04 | Phase 83 | Pending |
| REVIEW-05 | Phase 83 | Pending |
| REVIEW-06 | Phase 83 | Pending |
| REVIEW-07 | Phase 83 | Pending |
| REVIEW-08 | Phase 83 | Pending |
| RISK-01 | Phase 83 | Pending |
| RISK-02 | Phase 83 | Pending |
| PLANCHK-01 | Phase 84 | Complete (verified-present on 2.1.281; needs early-access CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1) |
| PLANCHK-02 | Phase 84 | Complete (routing + fail-closed proven; full BM loop partially validated — revise/recheck not exercised) |
| PLANCHK-03 | Phase 84 | Complete via recorded-unavailable route (true originals not recovered; recovered set was post-review; comparison invalid/not measurable) |
| CIMAINT-01 | Phase 85 | Pending |
| CIMAINT-02 | Phase 85 | Pending |
| CIMAINT-03 | Phase 85 | Pending |
| CIMAINT-04 | Phase 85 | Pending |
| CIMAINT-05 | Phase 85 | Pending |
| CIMAINT-06 | Phase 85 | Pending |
| CIMAINT-07 | Phase 85 | Pending |
| ACCEPT-01 | Phase 85 | Pending |
| ACCEPT-02 | Phase 85 | Pending |
| ACCEPT-03 | Phase 85 | Pending |
| PILOT-01 | Phase 86 | Pending |
| PILOT-02 | Phase 86 | Pending |
| PILOT-03 | Phase 86 | Pending |
| PILOT-04 | Phase 86 | Pending |

**Coverage:**
- v2.13 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-21*
*Last updated: 2026-10-26 after recording the owner's Phase 85 D-01 (ACCEPT-03) and D-14 (CIMAINT-05) decisions*
