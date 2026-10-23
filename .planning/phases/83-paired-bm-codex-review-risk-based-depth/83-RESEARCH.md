# Phase 83: Paired BM + Codex Review & Risk-Based Depth - Research

**Researched:** 2026-10-22
**Domain:** Development-process instrumentation — Buildomator (BM) plugin configuration, an independent Codex CLI adversarial review pass, risk-based review-depth recommendation, and a content-based review-classification policy. No application code changes.
**Confidence:** MEDIUM-HIGH (BM 4.9.1's actual behavior is directly verified by local inspection; BM v5.0.3's behavior is verified only from the public CHANGELOG, since v5.0.3 is not yet installed — that gap is precisely what REVIEW-01's baseline/assessment task must close, and it is flagged throughout)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BM update gate (REVIEW-01)**
- **D-01:** The gate proposes BM v5.0.3 as the exact target. It was released 2026-10-22 and is the latest; the installed version is 4.9.1. The blueprint assessed 4.9.3, so the baseline must reassess v5.0.x behavior. If a newer release exists when the gate is presented, the baseline names it, but the owner still approves one exact version.
- **D-02:** v5.0.1 moves BM's `sonnet` and `haiku` tiers to Claude Sonnet 5.5 and Haiku 5.5. This is accepted as part of the version change, and recorded. It is not a separate settings change and models are not pinned. The baseline and later pilot notes must say that the models changed at the same time as the review settings, so comparisons are not misread.
- **D-03:** The approved settings list, which the owner chose deliberately over the blueprint's narrower suggestion: (a) `workflow.code_review` on at `standard` depth. (b) Every specialist/craft-skill lane that v5.0.3 supports, turned on. The gate names the exact supported config keys from the installed v5.0.3. Never invent a key; a lane without a supported key is reported, not faked. Every other setting in `.planning/config.json` is preserved, and proven with a before/after diff.
- **D-04:** If the baseline assessment finds a surprise, stop and bring it to the owner with a proposed adjustment. Example surprise: review doesn't run automatically on quick tasks, or the depth handling differs. Example adjustment: a different version, or a `CLAUDE.md` instruction that fills the gap. Nothing is installed or changed until the owner approves. The update follows BM's supported plugin update procedure, and `/bm:version` confirms the loaded version afterwards.
- **D-05:** Verified during discussion: in v5.0.3, `/bm:review --codex` is a plan review (it pipes the phase plans to `codex exec`). BM's `code-review` workflow has no Codex option. So BM cannot natively pair Codex with code review, and repository instructions must fill that gap (REVIEW-02/03). A Codex plan review never satisfies the independent code review.

**Codex pairing (REVIEW-02, REVIEW-03, REVIEW-04)**
- **D-06:** Claude runs the Codex review automatically after every BM code-review run: phase execution, quick task, explicit `/bm:code-review`, and review after fixes. `CLAUDE.md` instructs this. Codex runs as a separate, read-only session (`codex exec` in a read-only sandbox, Codex CLI 0.153.4 installed locally) against the exact checkpoint commit. It must not edit, commit, push, resolve threads or approve anything. The owner is involved only on failure.
- **D-07:** Codex gets only the fixed, versioned prompt template, based on the blueprint's "Codex adversarial review contract" and its suggested owner prompt. Only the PR URL, full head/base SHAs and scope are filled in. Claude adds no risk notes or framing, so it cannot steer the reviewer. The template lives in the repository.
- **D-08:** After Codex reports, Claude triages: reproduces plausible defects and classifies each finding as a confirmed defect, a false positive (with evidence) or nonblocking debt. Fixes confirmed defects in one batched revision, which then gets fresh tests, a fresh BM review and a fresh Codex review on the new head (REVIEW-06). The owner sees the original Codex report plus the dispositions before acceptance. There is no automatic cross-agent fix loop beyond this.
- **D-09:** If Codex fails (quota, crash, timeout, unparseable output), there is one automatic retry on the same SHA. If that also fails, the review stays incomplete/pending and the owner chooses: wait, retry later, or approve a fallback such as vibe-check. A missing, failed, skipped, stale or wrong-commit report is never reported as clean (REVIEW-03).

**Evidence record (REVIEW-04, REVIEW-05, REVIEW-06, RISK-01)**
- **D-10:** The authoritative record is one PR checkpoint comment per head SHA. It holds BM's risk note and review result, the Codex summary, the classification, the dispositions and the requested-vs-actual depth. A durable copy goes into the phase folder with the phase-closeout docs. Finding dispositions live in this record and so survive bot thread resolution.
- **D-11:** The full, unedited raw Codex output is preserved. The PR comment carries a structured summary linking to it: full head/base SHAs, coverage, exclusions, commands actually run, findings with source/run-qualified IDs (severity, location, trigger, path, consequence, evidence, suggested fix, reproduced vs hypothesis), and limitations. Original findings are kept for comparison after fixes.
- **D-12:** At acceptance time the owner gets one checklist message in the CLI, showing the exact head/base SHAs, each review's status on that head (BM, Codex, Greptile if it ran, vibe-check if selected, CI), every finding with its disposition, and anything incomplete in plain words. This is the manual BM/Codex completion check. The GitHub gate is not extended in this phase (PILOT-03/FUT-03 decide that later).

**Demonstrations, classification and branching (REVIEW-07, REVIEW-08, RISK-02, success criteria)**
- **D-13:** One branch and one PR per phase. No docs-only PRs, ever. Phase 83 runs on branch `paired-review`, cut from `ci-review-workflow` and including the unpushed Phase 82 closeout commit `f5fa98d`. Its PR is prepared at the end of the phase.
- **D-14:** The owner approved removing the ordinary-docs-PR demonstration from REVIEW-08 (a scope change). Phase 83 demonstrates classification on its own PR, which is a sensitive-docs/mixed PR (edits `CLAUDE.md` and agent instructions). The planner must amend the REVIEW-08 text in `.planning/REQUIREMENTS.md` and success criterion 7 in `.planning/ROADMAP.md` to match, and record the owner decision. The REVIEW-07 policy still defines how ordinary docs/planning changes are treated, because they occur as commits inside phase PRs.
- **D-15:** The high-risk checkpoint demo is Phase 83's own PR, if BM honestly assesses it as high (changes to review policy and agent instructions are safeguard changes, which the blueprint table rates high). If assessed high: the PR carries the full RISK-01 note, the explicit vibe-check recommendation with rationale and scope, and the owner's recorded decision. If assessed below high: the RISK-02 demo is recorded as pending/not demonstrated and carried forward to the next real high-risk checkpoint — never claimed as passed.
- **D-16:** The quick-task path is shown with a small, real, owner-authorized 999.x backlog maintenance item (e.g. the former-999.8 atomic-write helper chmod item), run via `/bm:quick` with BM review and paired Codex. Claude proposes the exact item for the owner's OK before running it. That code rides in the Phase 83 PR, and the PR's classification follows its most consequential change.
- **D-17:** The negative case (a missing, stale or wrong-commit Codex report shown as incomplete) is demonstrated locally, with no deliberate push.
- **D-18:** Claude classifies each PR and records the classification and rationale against the exact head SHA, reclassifying when the head changes. The owner can overrule at acceptance. When in doubt, classify upward (to the more consequential class). A "focused consistency review" for ordinary docs/planning content means checking that facts, links, SHAs and STATE/ROADMAP/REQUIREMENTS agree with the code and with each other — no BM code review, Codex code review or vibe-check. Sensitive content (agent instructions, workflows, hooks, permissions, acceptance/release policy, operational procedures) needs a RISK-01 assessment plus the applicable technical review, even in Markdown.

### Claude's Discretion
- The exact wording and layout of the PR checkpoint comment, the acceptance checklist message and the Codex prompt template, within D-07/D-10/D-11/D-12.
- Where in the repository the Codex template and the classification policy text live, and how `CLAUDE.md` references them. Keep `CLAUDE.md` concise.
- How `codex exec` is invoked (flags, sandbox mode, output capture) and how the raw output is stored, provided it is read-only and SHA-bound.
- The order in which the four BM review paths are demonstrated, provided each is shown once on real work.

### Deferred Ideas (OUT OF SCOPE)
- **Phase 85 / ACCEPT-03 impact:** ACCEPT-03's verification currently includes an "ordinary-docs PR" case. With the owner's no-docs-only-PRs rule (D-13/D-14), Phase 85's discussion must revisit how that case is demonstrated, or amend it. Not changed here.
- Turning on `/bm:review --codex` for plan reviews is a plan-stage addition, outside this phase.
- Extending the GitHub acceptance gate to require BM/Codex reports is PILOT-03/FUT-03, not this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REVIEW-01 | Record a baseline, assess the proposed target BM version's native review/fixer behavior, get owner approval of exact version + bounded settings list, update via supported procedure, confirm with `/bm:version` | Confirmed installed version (4.9.1), confirmed current `workflow.code_review=false`, confirmed `workflow.code_review`/`code_review_depth`/`agent_skills.<type>` are the real supported keys, confirmed v5.0.3's CHANGELOG has no code-review-relevant entries (MEDIUM confidence — not a live v5.0.3 test), flagged the craft-skill-lane mechanism as needing direct re-verification (Assumption A1, Open Question 1) |
| REVIEW-02 | Pair an independent Codex adversarial pass with every BM code-review run (phase execution, quick task, explicit command, review after fixes); request explicitly and track pending if BM cannot invoke Codex | Directly confirmed (by reading the installed workflow files) that 3 of 4 paths already auto-invoke BM's reviewer when `workflow.code_review=true`, and that none of the four natively invoke Codex (D-05 confirmed); documented two concrete Codex invocation mechanisms (raw `codex exec --output-schema`, and the installed `codex` plugin's app-server client) with tradeoffs |
| REVIEW-03 | Missing/failed/skipped/wrong-commit/stale Codex evidence reported incomplete, never clean; demonstrated with a negative case | Documented the schema field (echoed inspected head/base SHA) that makes a wrong-commit report self-detectable; documented Codex job-status vocabulary (`queued`/`running`/`completed`/`failed`/`cancelled`) from the installed codex plugin as a reusable reference for "incomplete" states |
| REVIEW-04 | Codex report schema: full head/base SHAs, coverage, exclusions, commands run, findings (ID, severity, location, trigger, path, consequence, evidence, suggested fix, reproduced vs. hypothesis), limitations; dispositions survive bot thread resolution | Compared the installed codex plugin's default `review-output.schema.json` against this field list and found concrete gaps (no stable ID, no reproduced/hypothesis, no coverage/exclusions/commands-run/limitations); recommended building a custom `--output-schema` file instead |
| REVIEW-05 | Record requested vs. actual depth; report BM's effective-depth reduction (e.g. deep → standard above 50 files) rather than mislabeling it | Found and quoted BM 4.9.1's exact large-scope downgrade logic and its stdout warning text (`code-review.md`), giving a concrete string to capture verbatim in the evidence record |
| REVIEW-06 | Evidence bound to one frozen pushed head; after any fix, refresh tests/dispositions/reviews for the new head; preserve originals for comparison | Found that BM's own re-review step overwrites `REVIEW.md` in place (Pitfall 2) — this is the key mechanical fact the plan must handle with an explicit snapshot step; reused Phase 82's D-34 separated-commit-identity pattern as a model for the evidence record |
| REVIEW-07 | Written content-based classification policy; ordinary docs/planning get a focused consistency review; sensitive content (agent instructions, workflows, hooks, permissions, acceptance/release policy, operational procedures) needs risk assessment + technical review even in Markdown; mixed PR follows its most consequential change | Confirmed (via repository-wide grep) there is no literal "every PR" string to remove from `CLAUDE.md` today — the "blanket" framing is conceptual, located in specific named `CLAUDE.md` sections, which must be restructured rather than string-replaced (Pitfall 5) |
| REVIEW-08 | Each PR records classification + rationale against exact head SHA, reclassified when head changes; blanket wording removed from `CLAUDE.md` and BM/repository instructions while REVIEW-02's Codex pairing is kept; demonstrated on an ordinary-docs PR and a sensitive-docs PR | Same grep finding as REVIEW-07; flagged D-14's scope change (ordinary-docs-PR demo removed, replaced by this phase's own sensitive-docs PR) as an open item for the planner to reconcile with REQUIREMENTS.md/ROADMAP.md text per the owner's explicit instruction |
| RISK-01 | At each checkpoint, record scope (PR, full head/base SHAs, affected behavior, full-PR vs. follow-up), risk level + concrete failure scenarios, recommended depth/specialist focus, required evidence — refreshed when revisions change SHA or risk | Documented as a BM checkpoint-report addition (no new scoring engine); Architecture Patterns diagram places this between BM's native review and the Codex pass |
| RISK-02 | When risk is high, explicitly recommend an additional vibe-check with rationale/scope and record the owner's decision; never substitutes for Codex/Greptile, never waives findings, never reduces mandatory coverage; demonstrated on a high-risk checkpoint | Confirmed that Phase 83's own PR (editing `CLAUDE.md`/agent instructions) is the planned high-risk demonstration per D-15; documented the explicit "recorded as pending, never claimed passed" fallback if BM assesses it below high |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Directives from `/Users/julianamacbook/triggarr/CLAUDE.md` that this phase's plan must not contradict:

- **Buildomator + Greptile pilot section:** "This is a staged migration; keep the existing review process until the checklist is complete. Use feature branches and PRs. Buildomator's review hook is advisory, and a Greptile review does not replace running tests or product acceptance. After fixes, require fresh checks and review of the current commit. Do not weaken CI, suppress findings, or push directly to main to make a task appear complete." — Phase 83 restructures this section but must preserve its substance (fresh review after fixes, no weakening CI/findings, no direct-to-main pushes).
- **Deep Code Review Convention:** "Before pushing to main or creating a release tag, offer `/deep-review` to the user." This pre-existing convention is distinct from the new BM+Codex pairing; the plan should clarify how/whether it coexists with the new classification policy rather than silently dropping it.
- **Planning file format:** "Before creating or updating `.planning/STATE.md`, `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`, BM and other agents must read and follow [the Roadmaps planning format](docs/PLANNING-FORMAT.md)... Keep their milestone and phase status consistent, update `last_updated` whenever editing `STATE.md`, and do not mark an in-review phase finished... Preserve unrelated in-flight planning edits." Applies to every STATE.md/ROADMAP.md/REQUIREMENTS.md edit this phase makes (including the D-14 REVIEW-08/criterion-7 amendment).
- **Deferred review-workflow proposal — after v2.12:** "Greptile is optional since 2026-10-22 (owner decision)... Do not update BM, enable new review settings, or retire vibe-check for this proposal during v2.12." This milestone (v2.13) is the authorized point to act on this — the deferral has expired for Phase 83 specifically, per the roadmap and CONTEXT.md, but the "do not retire vibe-check" clause stays in force (routine vibe-check continues until Phase 86/PILOT-03).
- **Active owner approval through Claude CLI:** "Follow [owner CLI acceptance]... Never infer approval, approve autonomously, reuse it after a commit/run change, or bypass a gate. This is approval transport only... This standing permission does not approve any pending PR." Governs how the Phase 83 PR itself gets accepted at the end of the phase — unchanged by this phase's new evidence record.

From the global `~/.claude/CLAUDE.md` (user-level, applies across all projects): "Technical decisions are yours to own... Recommend one, and frame the tradeoff in terms I can evaluate: user impact, risk, time, maintenance burden." This governs how REVIEW-01's baseline/version-and-settings choice should be presented to the owner — as a recommendation with plain-terms tradeoffs, not a menu of equally-weighted technical options.

## Summary

This phase has no new libraries to adopt. It wires together three things that already exist in this environment: Buildomator's native `workflow.code_review` pipeline (installed at 4.9.1, currently disabled in `.planning/config.json`), the locally-installed Codex CLI (0.153.4, authenticated, read-only sandbox available), and the repository's existing evidence/acceptance plumbing (`REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS` GitHub variables, the `review-acceptance` protected environment, `docs/owner-cli-acceptance.md`). Research confirms the central design fact the CONTEXT.md decisions already assume: BM's own code-review workflow has no Codex option, and BM's `/bm:review --codex` reviews *plans*, not committed code — so the Codex pairing, the risk-based depth recommendation, and the classification policy must all be written as repository instructions (`CLAUDE.md` + supporting docs), not as a BM config flag.

Two findings materially sharpen the plan beyond what CONTEXT.md already locked in. First, in the installed BM 4.9.1, code review already auto-fires on three of the four paths REVIEW-02 must demonstrate (phase execution via `execute-phase.md`'s required `code_review_gate` step, `/bm:code-review` explicitly, and `/bm:code-review --fix --auto`'s re-review loop) once `workflow.code_review=true` — the fourth path, `/bm:quick` in full mode, also auto-fires at `quick` depth. The "surprise" D-04 anticipates (e.g., "review doesn't run automatically on quick tasks") does **not** reproduce in 4.9.1; the baseline task must still re-verify this against the actually-installed v5.0.3, because nothing in the v5.0.0–v5.0.3 changelog touches this logic, but it should not be assumed without checking. Second, BM's own re-review step (`/bm:code-review --fix --auto`) **overwrites** the prior `REVIEW.md` in place — it is the only way BM has to "re-review," and it destroys the original finding record unless something snapshots it first. REVIEW-04/D-11's requirement to preserve original findings for comparison after a fix therefore needs an explicit archive step in the repository instructions; BM will not do this for you.

On the Codex side, this machine already has a second, more capable integration than BM's own `codex exec -` piping pattern: the installed `codex` Claude Code plugin ships `/codex:review` and `/codex:adversarial-review` commands backed by a `codex app-server` JSON-RPC client (`codex-companion.mjs`), with built-in read-only sandboxing, `--output-schema` enforcement, and persistent job tracking (`/codex:status`, `/codex:result`) that survives across Claude sessions. Its default review schema (`severity`/`title`/`body`/`file`/`line_start`/`line_end`/`confidence`/`recommendation`) is close to, but does not fully satisfy, REVIEW-04's required fields (no stable finding ID, no reproduced-vs-hypothesis flag, no coverage/exclusions/commands-run/limitations fields, and its own prompt template adds its own "challenge the approach" framing on top of whatever focus text is supplied — which conflicts with D-07's "no extra framing" requirement). The two realistic options — hand-rolled `codex exec --sandbox read-only --output-schema <custom>.json -` with the blueprint's fixed prompt piped verbatim, versus the installed `/codex:adversarial-review --base <SHA>` slash command with its own template and schema — are both viable; this research recommends the former for schema fidelity and documents the latter as a background-job-tracking fallback. This decision is explicitly Claude's discretion per D-19.

**Primary recommendation:** Treat REVIEW-01 as a verification task against the *actually installed* version, not a repeat of this document's BM-4.9.1 findings or the blueprint's v4.9.3 findings. Build the Codex pass on raw `codex exec --sandbox read-only --output-schema <findings-schema>.json -` with the blueprint's fixed prompt piped verbatim (never through BM, never through the codex plugin's canned adversarial-review template), capture the full session transcript and structured JSON for archival, and write every PR-checkpoint evidence record as a new `gh pr comment` per head SHA (never editing away a prior head's comment) plus a durable copy in the phase folder.

## Architectural Responsibility Map

This phase has no browser/API/DB tiers; "tiers" here are the layers of the review-and-acceptance pipeline.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BM baseline recording + version/settings approval | Owner checkpoint (human, non-autonomous) | BM plugin (`/bm:version`, `/bm:settings`) | REVIEW-01 is explicitly a gate: nothing installs or changes until the owner approves an exact version + bounded settings list (D-04) |
| BM native code review | BM plugin (`code-review.md` workflow, `bm-code-reviewer` agent) | Repository config (`.planning/config.json`) | Review depth, scope and the >50-file downgrade rule are all BM-internal; Phase 83 only flips the config gate and documents the behavior, never forks BM |
| Independent Codex adversarial pass | External CLI (Codex CLI via `codex exec` or the `codex` Claude Code plugin's app-server client) | Repository instructions (`CLAUDE.md`, fixed prompt template file) | BM cannot invoke Codex for code review (D-05); this must live as a documented, scripted repository procedure, read-only and SHA-bound |
| Risk assessment + vibe-check recommendation | BM reporting (checkpoint note in the PR comment) | Owner checkpoint (decision recorded) | A documented decision step per the blueprint, not a new scoring engine or gate selector |
| Evidence record (BM/Codex/Greptile/vibe-check status, dispositions, depth-requested-vs-actual) | Repository/PR (GitHub PR comment, one per head SHA) | Phase folder (durable copy) | D-10: committing evidence into the head itself creates a new head that needs its own evidence — a PR comment is the only place that doesn't recurse |
| Review-classification policy | Repository instructions (`CLAUDE.md` + a dedicated policy doc) | — | Content-based classification is pure policy text; it has no runtime component in this phase (ACCEPT-03/Phase 85 is where GitHub enforces it) |
| GitHub acceptance gate | GitHub Actions (`review-acceptance.yml`/`.cjs`, unchanged) | Owner CLI acceptance (`docs/owner-cli-acceptance.md`) | Explicitly out of scope — Phase 83 adds a manual owner-checked completion message (D-12); it does not touch the GitHub job |

## Standard Toolchain

There is no application library to select — this phase's "stack" is the already-installed tools it must wire together correctly. No `npm install`/`pip install` is performed by this phase.

### Core

| Tool | Installed version | Purpose | Provenance |
|------|---------|---------|--------------|
| Buildomator (BM) plugin | 4.9.1 (installed); **target 5.0.3** per D-01, not yet installed | Planning, implementation, verification, native code review | [VERIFIED: local inspection — `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/.claude-plugin/plugin.json`] |
| Codex CLI | 0.153.4 | `codex exec` — the independent adversarial-review runner | [VERIFIED: local inspection — `codex --version`, `codex exec --help`] |
| `codex` Claude Code plugin ("codex-companion" runtime) | 1.0.4 | `/codex:review`, `/codex:adversarial-review`, `/codex:status`, `/codex:result` — a richer, job-tracked wrapper around the Codex app-server | [VERIFIED: local inspection — `~/.claude/plugins/cache/openai-codex/codex/1.0.4/`] |
| GitHub CLI (`gh`) | authenticated as `thejuran`, scopes `repo`,`workflow` | PR comments (evidence record), pending-deployment approval (existing owner-CLI-acceptance procedure) | [VERIFIED: local inspection — `gh auth status`] |

### Supporting

| Tool | Purpose | When to use |
|------|---------|-------------|
| `bm-sdk query config-get` / `config-set` | Read/write `.planning/config.json` keys through BM's supported interface | REVIEW-01's settings change; never hand-edit `config.json` for BM-owned keys |
| `node .../gsd-tools.cjs craft-skill ...` (v4.9.2+, not present in installed 4.9.1) | Insert a specialist/craft-skill lane into an agent's spawn, ephemeral by default or `--sticky` | Only after the owner-approved update to v5.0.3; the baseline assessment must confirm this is the actual mechanism for "every craft-skill lane turned on" (D-03b) — see Assumptions Log A1 |
| `gh pr comment <number> [--create-if-none] [--edit-last]` | Write the one-comment-per-head-SHA evidence record (D-10) | Each new head gets a **new** comment (do not `--edit-last` across heads); within one head, additional evidence may update the same comment |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Raw `codex exec --sandbox read-only --output-schema <custom>.json -` with the blueprint's fixed prompt piped verbatim | `/codex:adversarial-review --base <SHA> "<fixed prompt text>"` (installed codex plugin) | The plugin gives background-job tracking, persisted results (`/codex:result`), and a built-in read-only sandbox — but it wraps the supplied text in its *own* "challenge the approach" template (`buildAdversarialReviewPrompt`) and enforces its *own* schema (`review-output.schema.json`), which lacks stable finding IDs, reproduced-vs-hypothesis, coverage/exclusions/commands-run, and limitations fields required by REVIEW-04, and which D-07 would likely call "framing Claude didn't author." Raw `codex exec` with a custom `--output-schema` avoids both problems at the cost of hand-rolling job tracking and retry (D-09's one-retry-then-incomplete rule). |
| `codex exec` piped prompt (text in, text out) | `codex exec review --commit <SHA>` / `--base <BRANCH>` (native Codex CLI review subcommand, distinct from the plugin) | Native subcommand understands commit/base diffs out of the box, but its own built-in review framing is not documented to match the blueprint's "adversarial review contract" field list; would need `--output-schema` layered on top regardless, so it offers little over plain `codex exec -` with a custom prompt. |
| New config key for "codex pairing" | Pure `CLAUDE.md` + repository-instruction procedure (chosen in CONTEXT.md D-06/D-07) | BM has no supported config surface for an external reviewer pairing (confirmed: `workflow.code_review_command` exists only inside `ship.md`'s optional PR-creation step, is a single advisory hook, not a per-code-review-run pairing, and is not currently set in `.planning/config.json`) |

**Installation:** none. This phase changes documentation and `.planning/config.json` values through BM's supported `config-set` interface; it does not add dependencies to `pyproject.toml`/`uv.lock`.

**Version verification:** `/bm:version` after the owner-approved update is the authoritative check (D-01). Do not infer the loaded version from the CHANGELOG alone.

## Package Legitimacy Audit

Not applicable. This phase installs no new third-party packages into the application or its lockfiles. The one "update" involved is the BM Claude Code plugin itself, applied through BM's own supported `/bm:update` procedure (a Claude Code plugin-marketplace operation, not an npm/pip/cargo dependency) — and only after explicit owner approval of the exact target version per REVIEW-01/D-01–D-04. The Codex CLI and `codex` plugin are already installed and are read-only inspection tools in this phase's design, not new supply-chain additions. If a future phase adds an actual package (e.g., a CI tool), run the Package Legitimacy Gate protocol then.

## Architecture Patterns

### System Architecture Diagram

```
                      ┌────────────────────────────────────────────┐
                      │  REVIEW-01 gate (owner checkpoint)          │
                      │  baseline recorded → target version +      │
                      │  settings list proposed → owner approves   │
                      │  → /bm:update → /bm:version confirms        │
                      └───────────────────┬──────────────────────────┘
                                           │ (nothing below runs until this passes)
                                           ▼
   ┌─────────────┐   ┌─────────────────────────────┐   ┌──────────────────────────┐
   │ BM review   │──▶│ BM native code review         │──▶│ BM risk assessment note  │
   │ trigger:    │   │ (bm-code-reviewer agent,      │   │ (scope, risk+rationale,  │
   │ phase exec, │   │  depth: quick/standard/deep,  │   │  recommended depth,      │
   │ quick, cmd, │   │  >50 files → deep downgraded  │   │  required evidence,      │
   │ post-fix    │   │  to standard, reported not    │   │  vibe-check recommend-   │
   └─────────────┘   │  silently relabelled)         │   │  ation when high-risk)   │
                      └───────────────┬───────────────┘   └────────────┬─────────────┘
                                      │ checkpoint commit (head SHA, frozen)
                                      ▼
                      ┌───────────────────────────────────────────────┐
                      │ Independent Codex adversarial pass              │
                      │ codex exec --sandbox read-only                  │
                      │   --output-schema findings.schema.json -        │
                      │ (fixed prompt template; only PR URL/SHAs/scope  │
                      │  filled in; one retry on failure, else pending) │
                      └───────────────────┬──────────────────────────────┘
                                           │
                     ┌─────────────────────┼─────────────────────┐
                     ▼                     ▼                     ▼
             ┌──────────────┐     ┌──────────────┐      ┌──────────────────┐
             │ Greptile     │     │ vibe-check    │      │ CI (GitHub)      │
             │ (optional,   │     │ (only if      │      │ (unchanged)      │
             │ same head)   │     │ owner picks   │      └──────────────────┘
             └──────┬───────┘     │  it)          │
                    │             └──────┬────────┘
                    └──────────┬──────────┘
                               ▼
                 ┌─────────────────────────────────────┐
                 │ Claude triages: reproduce, classify  │
                 │ (confirmed / false positive /        │
                 │  nonblocking debt), fix in ONE       │
                 │  batched revision → new head →       │
                 │  refresh tests + every review        │
                 └───────────────────┬───────────────────┘
                                     ▼
                 ┌─────────────────────────────────────┐
                 │ Evidence record: one PR comment per  │
                 │ head SHA (BM+Codex+Greptile+vibe-    │
                 │ check status, dispositions, depth    │
                 │ requested-vs-actual) + durable copy   │
                 │ in the phase folder                   │
                 └───────────────────┬───────────────────┘
                                     ▼
                 ┌─────────────────────────────────────┐
                 │ Owner acceptance checklist (CLI)      │
                 │ — manual BM/Codex completion check;   │
                 │ GitHub gate (Greptile + CI only) is    │
                 │ NOT extended in this phase (Phase 85)  │
                 └─────────────────────────────────────┘
```

### Recommended Repository Layout for New Artifacts

```
CLAUDE.md                                   # restructured review section(s); references
                                             # the classification policy and the Codex
                                             # contract rather than re-stating them inline
docs/
├── codex-adversarial-review-contract.md    # the fixed, versioned prompt template (D-07) —
│                                            # lives outside CLAUDE.md so it can be filled in
│                                            # programmatically without touching instructions
├── review-classification-policy.md         # REVIEW-07's written policy (content-based,
│                                            # not extension-based); CLAUDE.md references it
└── bm-review-baseline-<date>.md            # REVIEW-01's recorded baseline + before/after
                                             # settings diff (durable, outlives the PR comment)
.planning/phases/83-.../
└── 83-REVIEW-EVIDENCE.md                   # durable copy of every PR-checkpoint comment
                                             # this phase produces (D-10's "durable copy")
```

### Pattern 1: Checkpoint-bound evidence with separated commit identities

**What:** Record PR head SHA, PR base SHA, and (if different) the tested/merge SHA as separate fields with an explicit reconciliation line, mirroring Phase 82's D-34 pattern.
**When to use:** Every PR-checkpoint comment (D-10) and every Codex report (REVIEW-04).
**Example:**
```markdown
<!-- Source: pattern established in .planning/phases/82-ci-tests-what-we-ship/82-CONTEXT.md D-34 -->
- PR head SHA: `<full 40-char sha>`
- PR base SHA: `<full 40-char sha>`
- Tested/merge SHA (if CI ran on a synthetic merge commit): `<full 40-char sha>` — reconciliation: <one line explaining any difference>
```

### Pattern 2: Codex invocation with enforced output schema (read-only, SHA-pinned)

**What:** Pipe the fixed prompt (PR URL + exact head/base SHA + scope filled in, nothing else) to `codex exec`, forcing the response into a schema that has every REVIEW-04 field.
**When to use:** The one and only Codex invocation shape for this phase — never the plan-review path, never the codex plugin's canned adversarial template.
**Example:**
```bash
# Source: local inspection of `codex exec --help` (0.153.4) and the installed codex
# plugin's use of --output-schema (~/.claude/plugins/cache/openai-codex/codex/1.0.4/
# scripts/lib/codex.mjs, schemas/review-output.schema.json — schema shape adapted here
# to add the fields REVIEW-04 requires that the plugin's default schema omits)
cat docs/codex-adversarial-review-contract.md \
  | codex exec --sandbox read-only --skip-git-repo-check \
      --output-schema .claude/schemas/codex-review-findings.schema.json \
      --json --output-last-message /tmp/codex-review-<head_sha>.json \
      - > /tmp/codex-review-<head_sha>.jsonl
```
A custom schema file for this invocation needs (at minimum, beyond the codex plugin's default): `finding.id` (stable, source/run-qualified per D-11), `finding.reproduced` (boolean) vs `finding.hypothesis` (string, when not reproduced), `coverage`, `exclusions`, `commands_run` (array), `limitations` (array), and `inspected_head_sha`/`inspected_base_sha` echoed back from the prompt so a wrong-commit response is self-detectable.

### Pattern 3: Snapshot before BM's re-review overwrites REVIEW.md

**What:** Before invoking `/bm:code-review <N> --fix --auto` (BM's "review after fixes" path), copy the current `REVIEW.md` to a dated/SHA-stamped archive path.
**When to use:** Every fix-and-re-review cycle, because BM's own workflow overwrites `REVIEW.md` in place with no built-in history.
**Example:**
```bash
# Source: local inspection, ~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/
# code-review-fix.md line ~272: "This overwrites REVIEW_PATH with latest review state"
cp "${PHASE_DIR}/${PADDED_PHASE}-REVIEW.md" \
   "${PHASE_DIR}/${PADDED_PHASE}-REVIEW-${OLD_HEAD_SHA:0:12}.md"
```

### Anti-Patterns to Avoid

- **Treating `workflow.code_review=true` as proof review runs everywhere:** confirmed true for phase execution, `/bm:code-review`, and `/bm:code-review --fix --auto` in 4.9.1 and true for `/bm:quick` (full mode only — `/bm:fast` has no review step at all). Re-verify on the installed v5.0.3; do not assume parity.
- **Letting the codex plugin's canned `/codex:adversarial-review` template stand in for the blueprint's fixed prompt:** it interpolates user focus text into its *own* wrapper template and enforces its *own* schema — using it as-is adds framing D-07 forbids and omits fields REVIEW-04 requires.
- **Editing away a prior head's PR comment with `--edit-last` across different heads:** D-10 wants one comment per head SHA, not a single comment mutated in place (that would destroy the per-head audit trail REVIEW-06 needs).
- **Inventing a BM config key for "every craft-skill lane on":** D-03 explicitly forbids this. The real mechanism (per the v4.9.2/v4.9.3 changelog) is `gsd-tools craft-skill` insertion into `agent_skills.<agent-type>`, which is either ephemeral-per-task or `--sticky`, tracked in `.planning/craft-skills/pins.json` — not a single boolean. Confirm the exact v5.0.3 surface before writing it into the baseline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polling for Codex completion / retry logic | A custom scheduler or polling service | The installed `codex` plugin's job-control (`/codex:status`, `/codex:result`, statuses `queued`/`running`/`completed`/`failed`/`cancelled`) if using that path; otherwise a single bounded `timeout <n> codex exec ...` with a documented one-retry rule (D-09) | The blueprint and REQUIREMENTS.md explicitly prohibit a new orchestrator or polling service; the codex plugin already persists job state across Claude sessions |
| Tracking review dispositions outside bot-thread resolution | A new disposition database/table | The existing `REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS` GitHub-variable schema style (schema v1, `{head, decision, evidence}` per finding) as the *pattern* for the new PR-checkpoint record, even though Codex/BM dispositions live in the PR comment, not the GitHub variable (D-10) | Reusing a proven schema shape avoids re-litigating what "evidence" and "decision" mean; the existing acceptance script (`review-acceptance.cjs`) already enforces this shape for Greptile and is a working reference implementation |
| Enforcing "Codex ran on the right commit" | A hand-written SHA string-match script | Echo the inspected head/base SHA back inside the Codex response (schema field), then compare programmatically against the actual PR head before accepting the report as current | Prevents a stale or wrong-commit report from silently being treated as clean (REVIEW-03) without inventing new tooling |
| GitHub-side enforcement of the classification policy | Any GitHub Actions change in this phase | Nothing — explicitly deferred to Phase 85/ACCEPT-03 | REQUIREMENTS.md and ROADMAP.md both scope this phase as instruction-enforced only; CONTEXT.md D-14/D-15 are explicit that the GitHub gate is untouched here |

**Key insight:** every piece this phase needs already exists somewhere in this environment (BM's review pipeline, the Codex CLI, the codex plugin's app-server client, the GitHub evidence-register pattern). The work is instruction-writing and wiring, not new tooling.

## Common Pitfalls

### Pitfall 1: Assuming the blueprint's BM 4.9.1/4.9.3 findings still hold at v5.0.3
**What goes wrong:** The baseline gate (REVIEW-01) gets written as "BM v5.0.3 behaves like the blueprint said v4.9.3 did," skipping the actual re-verification D-01 and D-04 require.
**Why it happens:** The blueprint is dated 2026-10-18 and assessed 4.9.3; v5.0.0–v5.0.3 shipped 2026-10-20–10-22, after the blueprint. The public CHANGELOG (verified in this research) shows no entry touching code-review auto-invocation or the >50-file depth rule between 4.9.1 and v5.0.3 — but "no changelog entry" is not the same as "verified unchanged."
**How to avoid:** Re-run the equivalent of this research's local-inspection steps (grep the installed `workflows/code-review.md`, `execute-phase.md`, `quick.md`) against the actually-installed v5.0.3 files after the owner approves the update, before writing the baseline report.
**Warning signs:** The baseline report cites this RESEARCH.md or the blueprint as its evidence instead of the installed v5.0.3 files.

### Pitfall 2: BM's re-review silently destroying the original REVIEW.md
**What goes wrong:** `/bm:code-review --fix --auto` overwrites `REVIEW.md` with the post-fix state; if nothing archived the pre-fix version, REVIEW-04's "original findings preserved for comparison" requirement cannot be satisfied after the fact.
**Why it happens:** BM's workflow is explicit about this (`code-review-fix.md`: "This overwrites REVIEW_PATH with latest review state") and treats it as the correct behavior for its own purposes (BM only needs the current state).
**How to avoid:** Snapshot `REVIEW.md` (and the prior Codex report) before triggering any re-review/re-fix cycle (Pattern 3 above).
**Warning signs:** Only one `REVIEW.md` exists in the phase folder after a fix-and-reverify cycle that should have produced two comparable snapshots.

### Pitfall 3: Craft-skill "lanes" are not a boolean config key
**What goes wrong:** The baseline proposes a config key like `craft_skills.enabled: true` or similar, which does not exist and gets reported as faked per D-03's "never invent a key" rule.
**Why it happens:** The CONTEXT.md phrasing ("every specialist/craft-skill lane that v5.0.3 supports, turned on") sounds like a settings toggle, but the v4.9.2/v4.9.3 changelog describes an insertion mechanism (`gsd-tools craft-skill`, `agent_skills.<agent-type>`, `.planning/craft-skills/pins.json`) with ephemeral-by-default, `--sticky`-for-persistent semantics.
**How to avoid:** The baseline must name the actual command(s)/key(s) from the installed v5.0.3, and if "every lane always on" has no direct `--sticky`-for-all equivalent, report that gap to the owner per D-04 rather than approximating it.
**Warning signs:** The settings diff promised by D-03's "before/after diff" has no entry visibly corresponding to craft-skill lanes.

### Pitfall 4: Using the codex plugin's default schema as if it satisfies REVIEW-04
**What goes wrong:** Someone invokes `/codex:adversarial-review --base <SHA> "<contract text>"` and treats its JSON (`verdict`/`summary`/`findings[severity,title,body,file,line_start,line_end,confidence,recommendation]`/`next_steps`) as the complete evidence record.
**Why it happens:** The plugin is already installed, already works, and is close enough to look sufficient at a glance.
**How to avoid:** Diff the plugin's `schemas/review-output.schema.json` against REVIEW-04's required field list before deciding; if using the plugin, wrap its output with the missing fields (stable ID, reproduced/hypothesis, coverage/exclusions/commands-run, limitations, echoed head/base SHA) rather than passing it through unchanged.
**Warning signs:** The Codex section of a PR checkpoint comment has no "reproduced vs. hypothesis" distinction anywhere.

### Pitfall 5: Looking for a literal "every PR" string to delete
**What goes wrong:** REVIEW-08 gets treated as a find-and-replace task; since `CLAUDE.md` contains no literal "every PR" text today (confirmed by repository-wide grep), the task appears already done.
**Why it happens:** REQUIREMENTS.md/CONTEXT.md use the phrase "blanket 'every PR' wording" descriptively, not as a literal string to search for.
**How to avoid:** Read `CLAUDE.md`'s "Buildomator + Greptile pilot," "Deep Code Review Convention," and "Deferred review-workflow proposal" sections for *unconditional* framing (reviews/checks implied to apply to every change regardless of content) and restructure those sections to express the new content-based classification, rather than searching for a specific phrase.
**Warning signs:** A diff of `CLAUDE.md` for this phase contains no net change to the review-related sections.

## Code Examples

### Reading and writing the one BM setting this phase changes

```bash
# Source: local inspection, ~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/settings.md
bm-sdk query config-get workflow.code_review          # currently: false (.planning/config.json)
bm-sdk query config-set workflow.code_review true
bm-sdk query config-set workflow.code_review_depth standard   # default if unset; explicit per D-03(a)
/bm:version                                             # confirms the loaded plugin version post-update
```

### Detecting BM's own large-scope depth downgrade (so it can be reported, not hidden)

```bash
# Source: local inspection, workflows/code-review.md — the workflow itself prints this warning
# "Warning: ${#REVIEW_FILES[@]} files is a large review scope." / "Switching from deep to
# standard depth for large file count." when REVIEW_FILES > 50 and depth=deep.
# The repository-instruction layer must capture this stdout line and surface it verbatim
# in the PR checkpoint comment's "requested vs. actual depth" field (REVIEW-05).
```

### Codex readiness probe (confirms the environment this phase depends on)

```bash
# Source: local execution, ~/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs setup --json
# Returned (this environment, 2026-10-22): ready=true, codex-cli 0.153.4, ChatGPT login active.
node ~/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs setup --json
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| BM `opus` tier → `claude-opus-5` | `opus` tier → `claude-opus-5-5` | v4.9.1 (2026-09-24) | Already in effect; not part of this phase's settings diff |
| No BM craft-skill catalog | Curated external craft-skill catalog (`gsd-tools craft-skill`), 8 entries by v4.9.3, "propose-on-fit" on 9 command surfaces including `code-review` | v4.9.2 (2026-10-14) → v4.9.3 (2026-10-17) [CITED: GitHub raw CHANGELOG.md, tag v5.0.3] | Directly relevant to D-03(b); the mechanism is insertion/pinning, not a boolean |
| `sonnet`/`haiku` tiers → Claude Sonnet 5/Haiku-equivalent | `sonnet` → `claude-sonnet-5-5`, `haiku` → `claude-haiku-5-5` (context window 200K→1M for haiku) | v5.0.1 (2026-10-20) [CITED: GitHub raw CHANGELOG.md, tag v5.0.3] | Matches D-02 exactly; must be recorded as a model change bundled with the version bump, not a separate decision |
| `gsd-<role>`/`gsd-sdk`/`/gsd:` retirement planned for v5.0 | Retirement **deferred to a later major**; both spellings still resolve | v5.0.0 (2026-10-20) [CITED: GitHub raw CHANGELOG.md, tag v5.0.3] | No action needed for Phase 83; the installed-4.9.1-era `gsd-`/`bm-` dual naming keeps working |
| BM debugger/fixer apply the narrowest patch for a divergence | Debugger/fixer now present *two* options (minimal-fix-keeps-split vs. fix-removes-split) with blast radius, for a ruling | v5.0.3 (2026-10-22) [CITED: GitHub raw CHANGELOG.md] | Not directly relevant to code-review pairing, but may surface during the fix-confirmed-findings step (D-08) — expect a choice prompt rather than a silent patch for divergence-shaped findings |
| BM's own code-review workflow has zero Codex awareness | Still true at v5.0.3 — the CHANGELOG has no Codex-integration entry anywhere in v4.9.1–v5.0.3 | unchanged | Confirms D-05 holds at the target version too, to the extent the CHANGELOG is complete |

**Deprecated/outdated:** The CONTEXT.md's own example of a "surprise" ("review doesn't run automatically on quick tasks") does not match 4.9.1's actual behavior (it does auto-run in `/bm:quick` full mode) — treat this as a hypothesis to falsify against v5.0.3, not a known gap.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Every craft-skill lane turned on" maps to pinning each catalog entry into `agent_skills.<agent-type>` via `gsd-tools craft-skill ... --sticky` (or an equivalent always-on mechanism), not a single config boolean — based on the v4.9.2/v4.9.3 CHANGELOG description, not on an installed v5.0.3 test | Standard Toolchain; Pitfall 3 | If v5.0.3 actually exposes a simpler toggle, the baseline over-engineers the settings change; if it exposes no "always on" mechanism at all, D-04's "stop and bring it to the owner" path triggers |
| A2 | BM's auto-invocation behavior for phase execution / `/bm:code-review` / `/bm:quick` full-mode / `/bm:code-review --fix --auto` is unchanged from 4.9.1 through v5.0.3, because no CHANGELOG entry in that range touches `code-review.md`, `execute-phase.md`, or `quick.md` logic | Summary; Pitfall 1; State of the Art | If an undocumented behavior change exists, REVIEW-02's "demonstrated once per path" claim could rest on stale evidence |
| A3 | The codex plugin's `/codex:review`/`/codex:adversarial-review` commands are a viable *fallback* integration path but not the primary mechanism, because their fixed wrapper template and narrower schema conflict with D-07/REVIEW-04 — this is a design judgment, not a verified incompatibility test (no actual Codex call was made during this research) | Architecture Patterns Pattern 2; Alternatives Considered; Pitfall 4 | If the schema gap turns out to be easy to patch around (e.g., the plugin's prompt interpolation fully preserves a verbatim fixed template with no added framing), the hand-rolled `codex exec` path may be unnecessary extra work |
| A4 | `workflow.code_review_command` (the `ship.md` external-review hook) is unrelated to this phase's Codex pairing and should not be repurposed for it, because it fires once per PR-creation event with a single pass/fail verdict schema, not per-code-review-run with the full REVIEW-04 field set | Alternatives Considered | If the owner intended to reuse this hook, the design changes substantially |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Does the installed v5.0.3 expose a single "enable every craft-skill lane" operation, or must each of the (currently 8+) catalog entries be pinned individually?**
   - What we know: v4.9.2/v4.9.3 introduced per-skill, per-agent-type insertion (`gsd-tools craft-skill`), not a catalog-wide switch.
   - What's unclear: whether v5.0.0–v5.0.3 added a bulk/"enable all" operation; the CHANGELOG is silent on this.
   - RESOLVED: 83-01 Task 2 checks the installed/tagged v5.0.3 craft-skill surface directly and names the exact command(s), reporting any gap to the owner (D-04).
   - Recommendation: the REVIEW-01 baseline task must check `gsd-tools craft-skill --help` (or equivalent) against the installed v5.0.3 directly and name the exact command(s); if none exists, report the gap to the owner per D-04 rather than approximating "every lane on" as `agent_skills.<type>` containing every known skill name.

2. **Should the Codex pass use raw `codex exec` or the installed codex plugin's app-server client?**
   - What we know: raw `codex exec --output-schema` gives full schema control and a verbatim fixed prompt (favoring D-07); the plugin gives job persistence/background tracking across Claude sessions (useful for D-09's retry/pending semantics) but wraps the prompt and narrows the schema.
   - What's unclear: whether the plugin's `codex app-server` backend can be driven directly (bypassing the slash-command wrapper) to get both the job tracking and a custom schema — this would require reading `lib/codex.mjs`'s exported functions rather than only the commands, which this research did not fully trace.
   - RESOLVED: raw `codex exec --sandbox read-only --output-schema` is used (Claude's discretion; 83-02 contract and schema).
   - Recommendation: default to raw `codex exec` for the first implementation; revisit the app-server client only if retry/background tracking proves to be a recurring pain point during the pilot (Phase 86).

3. **What exactly must change in `CLAUDE.md` to satisfy REVIEW-08, given no literal "every PR" string exists today?**
   - What we know: the "blanket" framing is conceptual (unconditional review/check language in the "Buildomator + Greptile pilot" and "Deep Code Review Convention" sections), not a specific string.
   - What's unclear: whether the owner wants those two sections merged, one retired in favor of the new classification-policy reference, or both kept with added conditionals.
   - RESOLVED: 83-06 restructures the named CLAUDE.md review sections to point at the 83-04 classification policy; the owner reviews the result at PR acceptance.
   - Recommendation: surface this explicitly in planning/discussion rather than silently picking one; D-14 already shows the owner actively adjusts phase scope here, so this is a live decision point, not a research gap.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| BM plugin | Entire phase | Partial — 4.9.1 installed, **5.0.3 is the target and not yet installed** | 4.9.1 → target 5.0.3 | None; REVIEW-01 is the gate that performs this install, after owner approval. No phase work proceeds without it (D-04) |
| Codex CLI | REVIEW-02/03/04 (the adversarial pass) | ✓ | 0.153.4 | — |
| Codex ChatGPT auth | Same | ✓ | logged in as `jules1651@gmail.com` via ChatGPT auth | If auth lapses, Codex calls fail closed — treat as D-09's "Codex fails" case, not a silent skip |
| `codex` Claude Code plugin | Alternative Codex integration path (Pattern 2 discretion) | ✓ | 1.0.4 | Raw `codex exec` works independently if this plugin is ever absent |
| `gh` CLI | Evidence record (PR comments), existing owner-CLI-acceptance procedure | ✓ | authenticated as `thejuran`, scopes `repo`,`workflow` | — |
| Node.js / npm | BM's own tooling, `gsd-tools.cjs`, `codex-companion.mjs` | ✓ | node v25.9.0, npm 11.12.1 | — |

**Missing dependencies with no fallback:** BM v5.0.3 is not installed — this is intentional; REVIEW-01's gate performs the install after owner approval, so it is not a blocker to *researching or planning* this phase, only to executing past the gate.

**Missing dependencies with fallback:** none beyond the Codex-auth note above.

## Validation Architecture

> `workflow.nyquist_validation` is absent from `.planning/config.json`, so it is treated as enabled. This phase, however, produces no application code — every success criterion in ROADMAP.md is explicitly marked "(Instruction-enforced)." There is no pytest/unit-test surface to map requirements onto; "evidence" for this phase means demonstration artifacts (PR comments, archived REVIEW.md/Codex-report snapshots, before/after config diffs, the acceptance checklist message), each with an explicit positive case and, where ROADMAP.md calls for it, a deliberate negative case.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None (process/instruction phase) — `pytest` (existing, `tests/`) is unaffected and need not change |
| Config file | n/a |
| Quick run command | n/a |
| Full suite command | `uv run pytest tests/ -x -q` (regression-only: confirms this phase touched no application code) |

### Phase Requirements → Evidence Map

| Req ID | Behavior | Evidence Type | Positive Case | Negative Case |
|--------|----------|----------------|----------------|----------------|
| REVIEW-01 | Baseline recorded, exact version + settings approved before any change | Durable doc (`docs/bm-review-baseline-<date>.md`) + before/after `config.json` diff | Update proceeds only after a recorded owner approval; `/bm:version` confirms loaded version | An attempted update/settings change with no recorded approval does not happen (demonstrate by describing the stop, not by actually attempting an unauthorized change) |
| REVIEW-02 | Codex paired with every BM code-review run, across all 4 paths | PR checkpoint comment(s) showing a Codex report per path | One real demonstration per path (phase execution, `/bm:quick`, `/bm:code-review`, review-after-fix) | If BM cannot invoke Codex, an explicit pending/request record, never silently "clean" |
| REVIEW-03 | Missing/stale/wrong-commit Codex evidence reported incomplete | A deliberately constructed local case (stale report, wrong SHA) | — | The constructed case is shown as "incomplete," never passed off as reviewed (D-17: demonstrated locally, no deliberate push) |
| REVIEW-04 | Codex report schema completeness | The custom `--output-schema` JSON for one real run | Full head/base SHA, coverage, exclusions, commands run, findings with required fields present | A finding missing a required field would fail schema validation at the `codex exec` call itself (fail closed) |
| REVIEW-05 | Requested vs. actual depth recorded, large-scope downgrade reported | PR checkpoint comment's depth field | A normal-size review shows requested=actual | A deliberately large (>50 file) review shows the standard-downgrade warning text captured verbatim, not silently labelled "deep" |
| REVIEW-06 | Evidence refreshed per head; originals preserved | Snapshot files (Pattern 3) + new PR comment on the new head | A fix cycle produces two dated REVIEW.md/Codex-report snapshots and two PR comments | An evidence record from an earlier head is never cited as satisfying a later head (checked by SHA comparison in the comment itself) |
| REVIEW-07/08 | Written classification policy; `CLAUDE.md` restructured; no blanket wording | `docs/review-classification-policy.md` + `CLAUDE.md` diff | Demonstrated on the phase's own PR (sensitive-docs, per D-14/D-15) | A misclassification would be caught by "when in doubt, classify upward" (D-18) — demonstrate by showing the upward reclassification reasoning for this very PR |
| RISK-01/02 | Risk recorded at each checkpoint; vibe-check recommended when high | PR checkpoint comment's risk section | The phase's own PR, if BM assesses it high (D-15) | If assessed below high, explicitly recorded as "pending/not demonstrated," never claimed passed |

### Sampling Rate

- **Per checkpoint (push):** full demonstration cycle (BM review → Codex pass → risk note → evidence comment)
- **Per phase gate:** `uv run pytest tests/ -x -q` (confirms zero unintended application-code drift) + the owner acceptance checklist message (D-12)

### Wave 0 Gaps

- [ ] `docs/codex-adversarial-review-contract.md` — the fixed prompt template (REVIEW-02/REVIEW-04 depend on it existing before any Codex call)
- [ ] `.claude/schemas/codex-review-findings.schema.json` (or equivalent path) — the custom `--output-schema` file with every REVIEW-04 field
- [ ] `docs/review-classification-policy.md` — REVIEW-07's written policy, referenced from `CLAUDE.md`
- [ ] A snapshot/archive convention for `REVIEW.md` before each re-review (Pattern 3) — no existing file does this
- [ ] `docs/bm-review-baseline-<date>.md` — REVIEW-01's baseline record, created at the start of Wave 0 before anything else proceeds

## Security Domain

`security_enforcement` is absent from `.planning/config.json` (treated as enabled). This phase is process-instrumentation, not an application security change, so most ASVS categories don't apply — but two things in this phase are themselves security-relevant and the written policy (REVIEW-07) explicitly says sensitive content needs this assessment even in Markdown.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture/Design | Partial | The review-pairing and classification design itself is the artifact under review — covered by RISK-01's checkpoint risk assessment, not a separate control |
| V5 Input Validation | No (new input surface) | n/a — no new user input |
| V6 Cryptography | No | n/a |
| V7 Error Handling/Logging | Partial | The Codex invocation must not log/echo secrets; it runs `--sandbox read-only`, which blocks the writes (e.g. to `.env`) that would be needed to exfiltrate anything beyond what git already exposes |
| V13 API/Config | Yes | The fixed Codex prompt template must never embed a live credential, API token, or `.env` value — only the PR URL, SHAs, and scope (D-07) |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A Codex session with write access accidentally commits/pushes/approves something | Elevation of Privilege | `codex exec --sandbox read-only`; the fixed contract explicitly forbids edit/commit/push/resolve/approve (D-06, blueprint's "Codex adversarial review contract") |
| A stale/wrong-commit Codex report is accepted as current | Tampering (of evidence) | Echo the inspected head/base SHA back in the schema; compare against the actual PR head before treating the report as current (REVIEW-03) |
| Review-classification policy is gamed by mislabeling a sensitive change as "ordinary docs" to skip review | Repudiation / Elevation of Privilege | "When in doubt, classify upward" (D-18); classification + rationale recorded against the exact head, so a later audit can catch a misclassification even though GitHub itself doesn't enforce it yet (ACCEPT-03 is Phase 85) |
| The fixed Codex prompt template is edited per-run to "help" the reviewer | Tampering (of the review process itself) | D-07: only PR URL/SHAs/scope are filled in; the template file itself should be the single source Claude reads from, not re-typed per invocation |

## Sources

### Primary (HIGH confidence — local inspection, this session)
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/code-review.md` — file-scope tiers, >50-file deep→standard downgrade, config gates
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/execute-phase.md` (step `code_review_gate`, line ~1214) — confirms phase execution auto-invokes review when `workflow.code_review=true`
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/quick.md` (step 6.25) — confirms `/bm:quick` full-mode auto-invokes review at `quick` depth
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/code-review-fix.md` — confirms re-review overwrites `REVIEW.md` in place
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/ship.md` (`optional_review` step) — `workflow.code_review_command` external-hook mechanics
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/review.md` — confirms `/bm:review --codex` is a plan review (`codex exec --model ... --skip-git-repo-check -`), no code-review Codex option
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/settings.md`, `settings-integrations.md` — `workflow.code_review`/`code_review_depth`/`code_review_command` and `agent_skills.<agent-type>` config key documentation
- `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/.claude-plugin/plugin.json`, `CHANGELOG.md` — installed version 4.9.1 confirmed
- `~/.claude/plugins/cache/openai-codex/codex/1.0.4/commands/review.md`, `commands/adversarial-review.md`, `commands/status.md`, `commands/result.md`, `scripts/codex-companion.mjs`, `scripts/lib/codex.mjs`, `schemas/review-output.schema.json` — the installed `codex` plugin's review mechanics, schema, job tracking, sandbox defaults
- `codex exec --help`, `codex exec review --help` (local, 0.153.4) — CLI flags including `--sandbox`, `--output-schema`, `--json`, `--output-last-message`
- `node .../codex-companion.mjs setup --json` (local execution) — confirmed Codex ready/authenticated in this environment
- `.github/workflows/review-acceptance.yml`, `.github/scripts/review-acceptance.cjs` — confirms the GitHub acceptance gate checks Greptile only, not BM/Codex (the gap this phase's evidence record deliberately does not close)
- `.planning/config.json` — confirms `workflow.code_review: false` today
- `git log`/`git branch -vv` (local) — confirms branch `paired-review` cut from `ci-review-workflow` at `f5fa98d`, matching D-13

### Secondary (MEDIUM confidence — WebFetch, verified against an official source)
- [buildomator/buildomator CHANGELOG.md, raw, tag v5.0.3](https://raw.githubusercontent.com/buildomator/buildomator/refs/tags/v5.0.3/CHANGELOG.md) — v4.9.1 through v5.0.3 entries (craft-skill catalog growth, Sonnet/Haiku 5.5 move, gsd-/bm- retirement deferral, debugger/fixer divergence handling). [CITED: GitHub raw CHANGELOG.md]

### Tertiary (LOW confidence — not independently re-verified this session)
- `docs/bm-greptile-codex-blueprint.md`'s own BM 4.9.3 assessment (dated 2026-10-18) — treated as the owner-confirmed design source per CONTEXT.md, not re-verified against 4.9.3 specifically in this session (only against the installed 4.9.1 and the external v5.0.3 CHANGELOG)

## Metadata

**Confidence breakdown:**
- BM 4.9.1 review-invocation behavior: HIGH — directly read from the installed workflow files
- BM v5.0.3 behavior (not yet installed): MEDIUM — CHANGELOG-verified absence of relevant changes, not a live test; this is precisely what REVIEW-01's own baseline task must close
- Codex CLI / codex plugin mechanics: HIGH — directly read from installed scripts/schemas and one live readiness probe
- Craft-skill "every lane on" mechanism: LOW-MEDIUM — CHANGELOG-described, not confirmed against an installed v5.0.3; flagged as Assumption A1 and Open Question 1
- Classification-policy wording gap ("every PR"): HIGH — confirmed by direct repository-wide grep (no literal match in `CLAUDE.md`)

**Research date:** 2026-10-22
**Valid until:** ~7 days for the BM-version-specific claims (BM is shipping near-daily; re-check `/bm:version` behavior if REVIEW-01 execution happens more than a week after this research). ~30 days for the Codex CLI/plugin mechanics and the GitHub acceptance-gate findings (slower-moving).
