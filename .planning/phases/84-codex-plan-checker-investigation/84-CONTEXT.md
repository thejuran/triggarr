# Phase 84: Codex Plan-Checker Investigation - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Investigate — and record — whether a narrowly scoped `agent.spawn` hook can route only `bm:bm-plan-checker` through model-gateway to a Codex model, and how a Codex-backed BM checker compares with the ordinary BM checker on the original Phase 81 plans (blind comparison per the blueprint). Requirements PLANCHK-01, PLANCHK-02, PLANCHK-03.

Investigation only: nothing from this phase is activated in the Triggarr repository (no hook registration, settings, plugin or workflow change in Triggarr) without a separate owner approval. The phase does not block or bundle into Phases 85/86. Closeout separates what was actually investigated (evidence + result) from what was deferred or not run (with reason).

</domain>

<decisions>
## Implementation Decisions

### Runtime update gate (PLANCHK-01)
- **D-01:** First verify the **installed** runtime (Claude Code 2.1.281 at discussion time; latest seen 2.1.309) for `agent.spawn` hook support: event fields, model selection, permissions, resume. Record a negative result as unsupported/unavailable, never assumed.
- **D-02:** If 2.1.281 lacks the hook, the owner **pre-authorizes updating Claude Code globally** (the main `claude` install, not a side-by-side copy). Before applying, Claude presents the exact target version and the relevant changelog items and gets the owner's go-ahead in-session — the update is proposed visibly, never applied silently (criterion 1). Record before/after versions. Re-run the hook verification on the updated runtime.
- **D-03:** The blueprint's fallback (a separately named custom checker with Codex model frontmatter, full BM checker instructions preserved, `${CLAUDE_PLUGIN_ROOT}` refs resolved) is piloted **only if the hook is unsupported or unreliable even after the update**. If the hook works, the fallback is not tested.
- **D-04:** Routed checker model: **the strongest Codex model the gateway offers at pilot time** (blueprint saw `claude-gpt-6-astra[1m]`, `claude-gpt-5.6-sol[1m]`; recheck the live catalog). Catalog presence is not proof — routing must be proven from gateway metadata.
- **D-05:** Both the ordinary BM checker and the Codex-routed checker run at **highest reasoning effort** with matched limits, context, tools and instructions.

### Scratch pilot and isolation (PLANCHK-02)
- **D-06:** The pilot lives in a **separate directory outside the repo** (e.g. `~/scratch/planchk-pilot`) with its own copied inputs and its own `.claude` settings/hook. The hook must not be able to affect Triggarr sessions. No patching of the host, tool schema, global model aliases or installed plugin cache.
- **D-07:** Pilot exercises (per blueprint steps 3-6): initial check, a known-defective plan, structured BLOCKER/WARNING output, planner revision + recheck, post-bounce checks, resume path; unavailable gateway/model and incomplete output must show as incomplete with an explicit error (no silent pass, no silent fallback to Claude); disabling the opt-in restores ordinary checking in a new session.

### Recovering Phase 81 originals (PLANCHK-03)
- **D-08:** Git does **not** contain original plans 81-01..81-09 (only 81-10/81-11 from 2026-10-19 onward; `.planning/` is excluded via `.git/info/exclude`). Search the **Time Machine backups (MaguffyNAS destination) read-only**; copy candidate files into the scratch area only. Never modify the backup or reset the active checkout. Record snapshot provenance and SHA-256 of every input.
- **D-09:** The "original" cutoff is **evidence-based**: pin the time of the first manual Codex findings from timestamps (commits, session logs, Codex output files). A snapshot qualifies only if it predates that point and all nine plans plus contemporaneous context/research/patterns/validation docs are present and mutually consistent. Anything less is labelled partial, not original.
- **D-10:** If exact originals are unrecoverable: record the true comparison as **unavailable**, then run a **separately labelled reconstructed benchmark** (rebuilt from session logs and the revision record). It is never presented as the original and its results are reported as weaker evidence.
- **D-11:** Adjudication: a **fresh Claude session** that never saw either reviewer's run scores the frozen outputs against the withheld answer key, with reproduction evidence per verdict, and checks false positives as carefully as hits. The owner spot-checks a plain-language summary plus any disputed calls (owner is not asked to read code).

### Adoption criteria (locked before any runs)
- **D-12:** Blind first-pass hit bar: the Codex checker must find **clearly more consequential defects than the ordinary BM checker — at least 2 more of the 7 answer-key defects**. Credit requires the concrete trigger, consequence and boundary, not a broad warning.
- **D-13:** False-positive cap: **no more than 1 false positive per 2 real findings** (adjudicated).
- **D-14:** All of these must also hold (owner's qualifications, verbatim intent):
  - End-to-end loop: preserves BM's checker instructions, structured output, revision/recheck, post-bounce and resume behavior.
  - Fail closed: unavailable routing or incomplete output stays visibly incomplete; no silent fallback.
  - Revision quality: judged on independently adjudicated findings, including false positives; blind first-pass results kept separate from the feedback-informed round; must hold up at least as well as the ordinary checker.
  - Time/cost: within the limits in D-17/D-18; actual duration and observable usage recorded; unavailable measurements marked **unknown**, never assumed.
  - Proof of the routed backend/model from gateway metadata correlated to the checker invocation (a model label alone is not proof).
  - Confirmation that every other agent's model (orchestrator, planner, researcher, etc.) remains unchanged.
  - A tested way to disable the integration and restore ordinary checking.
- **D-15:** A **mixed result counts as "not met"**: the record recommends not adopting and explains what fell short. The owner may still choose to adopt as their own decision.

### Records, PR shape and budget
- **D-16:** Phase 84 records **stay local** — they are not pushed and get no PR of their own (honours "no docs-only PRs"). Phase-local artifacts live in the git-excluded phase directory. Tracked planning files touched by normal BM workflow (STATE.md/ROADMAP.md) ride along with the next substantive phase PR in the usual way; do not open a PR for them.
- **D-17:** Matched runs: **2 fresh runs per checker for the blind first pass, 1 per checker for the revision round.** Every run is reported with its spread; no cherry-picking, repeats disclosed.
- **D-18:** Ceiling: **15 minutes wall-clock per checker run**, and the whole phase stays within the owner's ChatGPT subscription (no paid API overage). A run hitting the limit is recorded as incomplete, not a pass.

### Claude's Discretion
- Exact scratch directory name/layout and packet assembly mechanics.
- Exact timestamp sources used to pin the cutoff (must be cited).
- Hook implementation details within the blueprint's constraints.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Investigation method (primary spec)
- `docs/bm-greptile-codex-blueprint.md` §"Deferred investigation: Codex plan checker through model-gateway" — evidence/limits, preferred pilot steps 1-6, fallback route, activation boundary
- `docs/bm-greptile-codex-blueprint.md` §"Blind comparison: original Phase 81 plans" — input recovery/freezing, blind packet contents and exclusions, matched runs, reproduction instructions, evaluator-only answer key (7 defects), revision-review round, report-before-adoption

### Requirements and scope
- `.planning/REQUIREMENTS.md` — PLANCHK-01..03
- `.planning/ROADMAP.md` §"Phase 84: Codex Plan-Checker Investigation" — goal and 4 success criteria

### Review workflow context (do not conflate)
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-CONTEXT.md` — D-05 (`/bm:review --codex` is a plan review, not this), D-13 (one PR per phase, no docs-only PRs)
- `docs/codex-adversarial-review-contract.md` — the separate post-implementation Codex code review (not the plan checker)
- `docs/PLANNING-FORMAT.md` — required for STATE/ROADMAP edits

### Phase 81 inputs
- `.planning/phases/81-correct-sonarr-grab-attribution/` — current (revised) Phase 81 files; NOT the originals; useful only for provenance/diffing and the revision-round snapshot

### Local inspection sources (recheck installed versions)
- BM: `~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/plan-phase.md`, `agents/bm-plan-checker.md` (installed BM is now 5.0.3, not the 4.9.1 the blueprint inspected)
- model-gateway 0.51.2: `skills/model-gateway/SKILL.md`, `lib/request-worker.js` in the installed plugin cache
- External: https://code.claude.com/docs/en/sub-agents#choose-a-model, https://code.claude.com/docs/en/plugins/mods/reference#subagents

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No Triggarr application code changes are in scope. Reusable pieces are workflow artifacts: BM 5.0.3 plan-phase step that spawns `bm:bm-plan-checker`, the model-gateway plugin, and the Phase 83 Codex runner/template patterns for recording raw outputs and evidence.

### Established Patterns
- Evidence discipline from Phase 83: raw outputs preserved, exact identities (SHA/hash/version) recorded, missing/failed evidence never reported as clean.
- Owner gates: stop-and-ask on anything outside approved scope; owner decides adoption.

### Integration Points
- Only the scratch project gets a hook. Triggarr's `.claude/` settings, BM config and CLAUDE.md are untouched in this phase.
- Environment facts at discussion time: Claude Code 2.1.281 (`~/.local/bin/claude` → versioned install), latest 2.1.309; model-gateway 0.51.2; BM 5.0.3; Time Machine destination on MaguffyNAS.

</code_context>

<specifics>
## Specific Ideas

- Owner explicitly wants the global update path rather than a side-by-side install, accepting that it changes the CLI used for all work.
- The 7 evaluator-only answer-key defects and the later-snapshot findings are listed in the blueprint; they must stay out of every reviewer packet and out of any prompt given to the checkers.

</specifics>

<deferred>
## Deferred Ideas

- Activating any Codex plan-checker integration in Triggarr — requires separate owner approval after this phase's report.
- Running the blind comparison on another phase (e.g. 82/83) — considered and not chosen; would be a scope change.

</deferred>

---

*Phase: 84-codex-plan-checker-investigation*
*Context gathered: 2026-10-23*
