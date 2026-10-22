# Phase 83: Paired BM + Codex Review & Risk-Based Depth - Context

**Gathered:** 2026-10-22
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase changes the review workflow, not the application. It has five parts:

1. A recorded BM baseline, and a gated BM update and settings change approved by the owner (REVIEW-01).
2. An independent, exact-commit Codex adversarial review after every BM code-review run, including the incomplete/pending handling (REVIEW-02 to REVIEW-06).
3. A risk assessment at each checkpoint, with an explicit vibe-check recommendation when the risk is high (RISK-01, RISK-02).
4. A written review-classification policy that replaces the blanket "every PR" wording in `CLAUDE.md` and the BM/repository instructions (REVIEW-07, REVIEW-08).
5. All of the above implemented through `CLAUDE.md`, supported BM configuration and repository instructions. No BM fork, no new orchestrator, no GitHub gate change (Phase 85/ACCEPT-03 and the later FUT-03 own the GitHub side).

These rules stay in force unchanged:
- routine vibe-check while the owner keeps it (Phase 86 decides whether to retire it);
- Greptile is optional;
- every PR needs exact-commit owner acceptance;
- batched pushes.

</domain>

<decisions>
## Implementation Decisions

### BM update gate (REVIEW-01)
- **D-01:** The gate proposes **BM v5.0.3** as the exact target. It was released 2026-10-22 and is the latest; the installed version is 4.9.1. The blueprint assessed 4.9.3, so the baseline must reassess v5.0.x behavior. If a newer release exists when the gate is presented, the baseline names it, but the owner still approves one exact version.
- **D-02:** v5.0.1 moves BM's `sonnet` and `haiku` tiers to Claude Sonnet 5.5 and Haiku 5.5. This is **accepted as part of the version change, and recorded**. It is not a separate settings change and models are not pinned. The baseline and later pilot notes must say that the models changed at the same time as the review settings, so comparisons are not misread.
- **D-03:** The approved settings list, which the owner chose deliberately over the blueprint's narrower suggestion:
  - (a) `workflow.code_review` on at `standard` depth.
  - (b) **Every specialist/craft-skill lane that v5.0.3 supports, turned on.**
  - The gate names the exact supported config keys from the installed v5.0.3. Never invent a key; a lane without a supported key is reported, not faked.
  - Every other setting in `.planning/config.json` is preserved, and proven with a before/after diff.
- **D-04:** If the baseline assessment finds a surprise, **stop and bring it to the owner** with a proposed adjustment. Example surprise: review doesn't run automatically on quick tasks, or the depth handling differs. Example adjustment: a different version, or a `CLAUDE.md` instruction that fills the gap. Nothing is installed or changed until the owner approves. The update follows BM's supported plugin update procedure, and `/bm:version` confirms the loaded version afterwards.
- **D-05:** Verified during discussion: in v5.0.3, `/bm:review --codex` is a **plan** review (it pipes the phase plans to `codex exec`). BM's `code-review` workflow has **no** Codex option. So BM cannot natively pair Codex with code review, and repository instructions must fill that gap (REVIEW-02/03). A Codex plan review never satisfies the independent code review.

### Codex pairing (REVIEW-02, REVIEW-03, REVIEW-04)
- **D-06:** **Claude runs the Codex review automatically** after every BM code-review run: phase execution, quick task, explicit `/bm:code-review`, and review after fixes. `CLAUDE.md` instructs this. Codex runs as a separate, read-only session (`codex exec` in a read-only sandbox, Codex CLI 0.153.4 installed locally) against the exact checkpoint commit. It must not edit, commit, push, resolve threads or approve anything. The owner is involved only on failure.
- **D-07:** Codex gets **only the fixed, versioned prompt template**, based on the blueprint's "Codex adversarial review contract" and its suggested owner prompt. Only the PR URL, full head/base SHAs and scope are filled in. Claude adds no risk notes or framing, so it cannot steer the reviewer. The template lives in the repository.
- **D-08:** After Codex reports, **Claude triages**:
  - It reproduces plausible defects and classifies each finding as a confirmed defect, a false positive (with evidence) or nonblocking debt.
  - It fixes confirmed defects in **one batched revision**, which then gets fresh tests, a fresh BM review and a fresh Codex review on the new head (REVIEW-06).
  - The owner sees the original Codex report plus the dispositions before acceptance.
  - There is no automatic cross-agent fix loop beyond this.
- **D-09:** If Codex fails (quota, crash, timeout, unparseable output), there is **one automatic retry on the same SHA**. If that also fails, the review stays **incomplete/pending** and the owner chooses: wait, retry later, or approve a fallback such as vibe-check. A missing, failed, skipped, stale or wrong-commit report is never reported as clean (REVIEW-03).

### Evidence record (REVIEW-04, REVIEW-05, REVIEW-06, RISK-01)
- **D-10:** **The authoritative record is one PR checkpoint comment per head SHA.** It holds BM's risk note and review result, the Codex summary, the classification, the dispositions and the requested-vs-actual depth.
  - Rationale: committing evidence about head X into the PR creates head Y, which would itself need fresh evidence. A PR comment costs no push and no Greptile credit.
  - A **durable copy** goes into the phase folder with the phase-closeout docs, so it outlasts GitHub.
  - Finding dispositions live in this record and so survive bot thread resolution.
- **D-11:** **The full, unedited raw Codex output is preserved.** The PR comment carries a structured summary linking to it: full head/base SHAs, coverage, exclusions, commands actually run, findings with source/run-qualified IDs (severity, location, trigger, path, consequence, evidence, suggested fix, reproduced vs hypothesis), and limitations. Original findings are kept for comparison after fixes.
- **D-12:** **At acceptance time the owner gets one checklist message in the CLI.** It shows:
  - the exact head and base SHAs;
  - each review's status *on that head*: BM, Codex, Greptile if it ran, vibe-check if selected, CI;
  - every finding with its disposition;
  - anything incomplete, in plain words.

  This is the manual BM/Codex completion check. The GitHub gate is not extended in this phase (PILOT-03/FUT-03 decide that later).

### Demonstrations, classification and branching (REVIEW-07, REVIEW-08, RISK-02, success criteria)
- **D-13:** **One branch and one PR per phase. No docs-only PRs, ever.** Phase 83 runs on the new branch `paired-review`, cut from `ci-review-workflow` and including the unpushed Phase 82 closeout commit `f5fa98d`. Its PR is prepared at the end of the phase. This is an owner instruction from 2026-10-22, recorded in memory.
- **D-14:** **The owner approved removing the ordinary-docs-PR demonstration from REVIEW-08 (a scope change).** Phase 83 demonstrates classification on its own PR, which is a **sensitive-docs/mixed PR** because it edits `CLAUDE.md` and agent instructions. The planner must amend the REVIEW-08 text in `.planning/REQUIREMENTS.md` and success criterion 7 in `.planning/ROADMAP.md` to match, and record the owner decision. The REVIEW-07 policy still *defines* how ordinary docs/planning changes are treated, because they occur as commits inside phase PRs.
- **D-15:** **The high-risk checkpoint demo is Phase 83's own PR, if BM honestly assesses it as high.** Changes to review policy and agent instructions are safeguard changes, which the blueprint table rates high.
  - If it is assessed high, that PR carries the full RISK-01 note, the explicit vibe-check recommendation with rationale and scope, and the owner's recorded decision.
  - If it is assessed below high, the RISK-02 demo is recorded as **pending/not demonstrated** and carried forward to the next real high-risk checkpoint. It is never claimed as passed.
- **D-16:** **The quick-task path is shown with a small, real, owner-authorized 999.x backlog maintenance item**, for example 999.8 (atomic-write helper chmod), run via `/bm:quick` with BM review and paired Codex. Claude proposes the exact item for the owner's OK before running it. That code rides in the Phase 83 PR, and the PR's classification follows its most consequential change.
- **D-17:** **The negative case (a missing, stale or wrong-commit Codex report shown as incomplete) is demonstrated locally**, with no deliberate push.
- **D-18:** **Claude classifies each PR** and records the classification and rationale against the exact head SHA, reclassifying when the head changes. The owner can overrule at acceptance. **When in doubt, classify upward** (to the more consequential class).
  - A "focused consistency review" for ordinary docs/planning content means checking that facts, links, SHAs and STATE/ROADMAP/REQUIREMENTS agree with the code and with each other. It involves no BM code review, Codex code review or vibe-check.
  - Sensitive content needs a RISK-01 assessment plus the applicable technical review, even in Markdown. Sensitive content means agent instructions, workflows, hooks, permissions, acceptance/release policy and operational procedures.

### Claude's Discretion
- The exact wording and layout of the PR checkpoint comment, the acceptance checklist message and the Codex prompt template, within D-07/D-10/D-11/D-12.
- Where in the repository the Codex template and the classification policy text live, and how `CLAUDE.md` references them. Keep `CLAUDE.md` concise.
- How `codex exec` is invoked (flags, sandbox mode, output capture) and how the raw output is stored, provided it is read-only and SHA-bound.
- The order in which the four BM review paths are demonstrated, provided each is shown once on real work.

</decisions>

<specifics>
## Specific Ideas

- The owner noticed that "one came out today" for BM, which is v5.0.3. The target is the actual latest release, not the version the blueprint assessed.
- The owner asked "doesn't BM have a mode that asks for codex?" It has one, but only for plans (D-05). Downstream docs should say this plainly, so nobody assumes `/bm:review --codex` covers code.
- Owner: "i meant one branch/PR per phase not milestone" and "no more docs only PRs the PR is prepped on branch at the end of a phase".

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Review workflow design (source of truth for this phase)
- `docs/bm-greptile-codex-blueprint.md`: target sequence, risk-based recommendation (scope/risk/recommended review/required evidence/decision, plus the risk table), required implementation, Codex adversarial review contract and suggested prompt, acceptance and evidence, Triggarr rollout steps 1–5, and operating rules (don't change plugin version, depth and reviewer settings together without recording it).
- `.planning/REQUIREMENTS.md`: REVIEW-01 to REVIEW-08 and RISK-01/RISK-02. The standing rules at the top cover optional Greptile, batched pushes, classification and owner acceptance.
- `.planning/ROADMAP.md` § Phase 83: success criteria 1–7. Criterion 7 needs amending per D-14.

### Current review and acceptance process (must stay intact)
- `docs/buildomator-greptile-pilot.md`: routine BM workflow, register shape (`REVIEW_BLOCKERS`/`REVIEW_DISPOSITIONS`), and the rule that bot-resolved threads are not evidence.
- `docs/owner-cli-acceptance.md`: the exact-commit owner approval transport; unchanged by this phase.
- `.github/workflows/review-acceptance.yml`, `.github/scripts/review-acceptance.cjs`: the existing gate. Read-only context; not changed in this phase.
- `CLAUDE.md`: the file to update; this is where the blanket "every PR" wording and the review conventions live.
- `.planning/config.json`: current BM settings, recorded in the baseline and diffed after the update.

### BM v5.0.3 (external, verify against the installed version)
- https://github.com/buildomator/buildomator/releases/tag/v5.0.3 (and v5.0.0–v5.0.2 release notes)
- `dist/bm/workflows/code-review.md` and `dist/bm/skills/review/SKILL.md` at tag v5.0.3: review depth handling, the large-scope depth reduction, and the plan-only `--codex` option.

### Prior phase decisions
- `.planning/phases/82-ci-tests-what-we-ship/82-CONTEXT.md`, including D-34 (separate head/base/tested SHA fields) and D-35 (checkpoint activities).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `codex` CLI 0.153.4 at `/opt/homebrew/bin/codex`, plus the `codex` Claude plugin (codex-companion runtime, `codex:rescue`). BM's own plan review already uses `codex exec ... -` as an invocation pattern.
- The existing acceptance register (`REVIEW_DISPOSITIONS`) holds Greptile dispositions only. Codex/BM dispositions go in the PR checkpoint record (D-10) and do not change the register.

### Established Patterns
- Evidence records separate commit identities (82-CONTEXT D-34): PR head, PR base, tested SHA, and a reconciliation line.
- Pushes are batched for the Greptile budget. Docs/evidence commits are held until the next substantive push.
- Acceptance reads `REVIEW_DISPOSITIONS` when the job starts. Write dispositions before presenting the run (project memory).

### Integration Points
- `CLAUDE.md` (project): the review-pairing instruction, classification policy reference and risk-note requirement.
- `.planning/config.json`: the BM settings changed only per D-03.
- PR comments on the phase PR: the checkpoint records.

</code_context>

<deferred>
## Deferred Ideas

- **Phase 85 / ACCEPT-03 impact:** ACCEPT-03's verification currently includes an "ordinary-docs PR" case. With the owner's no-docs-only-PRs rule (D-13/D-14), Phase 85's discussion must revisit how that case is demonstrated, or amend it. Not changed here.
- Turning on `/bm:review --codex` for plan reviews is a plan-stage addition, outside this phase.
- Extending the GitHub acceptance gate to require BM/Codex reports is PILOT-03/FUT-03, not this phase.

</deferred>

---

*Phase: 83-paired-bm-codex-review-risk-based-depth*
*Context gathered: 2026-10-22*
