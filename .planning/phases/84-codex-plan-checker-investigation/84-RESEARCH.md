# Phase 84: Codex Plan-Checker Investigation - Research

**Researched:** 2026-10-23
**Domain:** Claude Code mods/hooks runtime internals, BM 5.0.3 model resolution, model-gateway 0.51.2 routing, git/filesystem forensics for Phase 81 artifact recovery
**Confidence:** HIGH on runtime/hook mechanics and BM/gateway invocation semantics (verified against the installed binary, installed plugin source, and current official docs); MEDIUM on Phase 81 original-plan recoverability (filesystem-mtime evidence, not cryptographic); LOW/BLOCKED on Time Machine snapshot enumeration (environment permission gap, documented below)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Runtime update gate (PLANCHK-01)**
- **D-01:** First verify the **installed** runtime (Claude Code 2.1.281 at discussion time; latest seen 2.1.309) for `agent.spawn` hook support: event fields, model selection, permissions, resume. Record a negative result as unsupported/unavailable, never assumed.
- **D-02:** If 2.1.281 lacks the hook, the owner **pre-authorizes updating Claude Code globally** (the main `claude` install, not a side-by-side copy). Before applying, Claude presents the exact target version and the relevant changelog items and gets the owner's go-ahead in-session — the update is proposed visibly, never applied silently (criterion 1). Record before/after versions. Re-run the hook verification on the updated runtime.
- **D-03:** The blueprint's fallback (a separately named custom checker with Codex model frontmatter, full BM checker instructions preserved, `${CLAUDE_PLUGIN_ROOT}` refs resolved) is piloted **only if the hook is unsupported or unreliable even after the update**. If the hook works, the fallback is not tested.
- **D-04:** Routed checker model: **the strongest Codex model the gateway offers at pilot time** (blueprint saw `claude-gpt-6-astra[1m]`, `claude-gpt-5.6-sol[1m]`; recheck the live catalog). Catalog presence is not proof — routing must be proven from gateway metadata.
- **D-05:** Both the ordinary BM checker and the Codex-routed checker run at **highest reasoning effort** with matched limits, context, tools and instructions.

**Scratch pilot and isolation (PLANCHK-02)**
- **D-06:** The pilot lives in a **separate directory outside the repo** (e.g. `~/scratch/planchk-pilot`) with its own copied inputs and its own `.claude` settings/hook. The hook must not be able to affect Triggarr sessions. No patching of the host, tool schema, global model aliases or installed plugin cache.
- **D-07:** Pilot exercises (per blueprint steps 3-6): initial check, a known-defective plan, structured BLOCKER/WARNING output, planner revision + recheck, post-bounce checks, resume path; unavailable gateway/model and incomplete output must show as incomplete with an explicit error (no silent pass, no silent fallback to Claude); disabling the opt-in restores ordinary checking in a new session.

**Recovering Phase 81 originals (PLANCHK-03)**
- **D-08:** Git does **not** contain original plans 81-01..81-09 (only 81-10/81-11 from 2026-10-19 onward; `.planning/` is excluded via `.git/info/exclude`). Search the **Time Machine backups (MaguffyNAS destination) read-only**; copy candidate files into the scratch area only. Never modify the backup or reset the active checkout. Record snapshot provenance and SHA-256 of every input.
- **D-09:** The "original" cutoff is **evidence-based**: pin the time of the first manual Codex findings from timestamps (commits, session logs, Codex output files). A snapshot qualifies only if it predates that point and all nine plans plus contemporaneous context/research/patterns/validation docs are present and mutually consistent. Anything less is labelled partial, not original.
- **D-10:** If exact originals are unrecoverable: record the true comparison as **unavailable**, then run a **separately labelled reconstructed benchmark** (rebuilt from session logs and the revision record). It is never presented as the original and its results are reported as weaker evidence.
- **D-11:** Adjudication: a **fresh Claude session** that never saw either reviewer's run scores the frozen outputs against the withheld answer key, with reproduction evidence per verdict, and checks false positives as carefully as hits. The owner spot-checks a plain-language summary plus any disputed calls (owner is not asked to read code).

**Adoption criteria (locked before any runs)**
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

**Records, PR shape and budget**
- **D-16:** Phase 84 records **stay local** — they are not pushed and get no PR of their own (honours "no docs-only PRs"). Phase-local artifacts live in the git-excluded phase directory. Tracked planning files touched by normal BM workflow (STATE.md/ROADMAP.md) ride along with the next substantive phase PR in the usual way; do not open a PR for them.
- **D-17:** Matched runs: **2 fresh runs per checker for the blind first pass, 1 per checker for the revision round.** Every run is reported with its spread; no cherry-picking, repeats disclosed.
- **D-18:** Ceiling: **15 minutes wall-clock per checker run**, and the whole phase stays within the owner's ChatGPT subscription (no paid API overage). A run hitting the limit is recorded as incomplete, not a pass.

### Claude's Discretion
- Exact scratch directory name/layout and packet assembly mechanics.
- Exact timestamp sources used to pin the cutoff (must be cited).
- Hook implementation details within the blueprint's constraints.

### Deferred Ideas (OUT OF SCOPE)
- Activating any Codex plan-checker integration in Triggarr — requires separate owner approval after this phase's report.
- Running the blind comparison on another phase (e.g. 82/83) — considered and not chosen; would be a scope change.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLANCHK-01 | Verify and record whether the installed Claude Code runtime supports an `agent.spawn` hook that changes only `bm:bm-plan-checker`'s model through model-gateway (fields, model selection, permissions, resume); any needed runtime update is proposed separately, never applied silently. | §"Runtime support for `agent.spawn`" below gives a direct, binary-level answer for 2.1.281 (the hook event, its field schema, model-field handling, and permission-pin behavior are all present and inspectable today) plus the official-docs confirmation and version context, so D-01/D-02's verification step has concrete evidence to work from rather than starting blind. |
| PLANCHK-02 | If supported, scaffold a scratch-project pilot that routes only the plan checker, proves the routed backend from gateway metadata, and exercises the required checks with fail-closed behavior; nothing activated in Triggarr without approval. | §"model-gateway 0.51.2: routing mechanics" and §"Why the hook route is likely necessary (not `model_overrides`)" explain exactly which lever can carry a gateway ID onto the `bm:bm-plan-checker` identity and which cannot, the exact JSONL schema to use as gateway-metadata proof, and the request-worker's non-silent failure codes. §"BM 5.0.3 plan-checker invocation" confirms every BM-side checker spawn (initial, revision loop, post-bounce) is a fresh `Agent()` call, so the hook fires on all of them and there is no live "resume" path to separately pilot. |
| PLANCHK-03 | Run the blind comparison on the original Phase 81 plans, or record it unavailable with reasons, with hashed/frozen inputs and a withheld answer key. | §"Recovering the original Phase 81 plans" gives a file-by-file, git-verified account of which of the nine original plans can and cannot be recovered without Time Machine, corrected/sharpened timestamp evidence for D-09's cutoff, and documents the concrete environment blocker (no Full Disk Access) that currently prevents the Time Machine side of D-08 from running at all. |
</phase_requirements>

## Summary

This phase asks two independent technical questions and the research answers both with much harder evidence than the blueprint had when it was written (2026-10-18, against BM 4.9.1 and Claude Code 2.1.281). First: **does the installed Claude Code 2.1.281 binary actually contain the `agent.spawn` mod hook, and can a hook on it change only one named subagent's model?** Direct string inspection of the installed binary (`~/.local/share/claude/versions/2.1.281`) shows the full implementation already present — the event name, its handler, the exact set of fields a hook is forbidden to rewrite (`tool_use_id, name, fork, parentModel, permissionMode, parentAgentId, provider`), and an explicit carve-out that `model` is *not* in that pinned set and is only type-checked (`typeof model === "string"`), not validated against an enum. Current official docs (code.claude.com, fetched this session) confirm the same contract in prose and add the piece the blueprint was missing: "If an installed mod sets a model in its `agent.spawn` hook, Claude Code uses that model in place of the per-invocation parameter," and that the hook does **not** fire again on a `SendMessage` resume. Second: **can BM 5.0.3's own config do this without a hook?** No — model-gateway's own documentation states plainly that the `Agent`/`Task` tool's `model` parameter is a fixed host enum (`sonnet`/`opus`/`haiku`/`fable`) and "a gateway id passed there is refused," which rules out BM's native `model_overrides` config key (confirmed present and documented in BM 5.0.3, a genuine difference from the 4.9.1 blueprint) as a shortcut: BM's `plan-phase.md` step 10 always passes an explicit `model="{checker_model}"` argument to `Agent(subagent_type="bm:bm-plan-checker", ...)`, at every initial check, every revision-loop iteration, and every post-bounce recheck — never omitting it, never resuming the subagent. That makes the `agent.spawn` hook the only documented, supported lever capable of overriding that value post-validation for this exact agent identity; the custom-agent-frontmatter fallback (D-03) is a different, real, model-gateway-confirmed pattern, but it requires the *invoker* to omit the model argument, which BM's shipped workflow does not do for `bm:bm-plan-checker`.

On the Phase 81 recovery side (PLANCHK-03), direct git forensics on this repository are more precise than CONTEXT.md's D-08 summary: plans 81-01 through 81-07 never entered git on any branch (including the `backup/phase-81-pre-scrub` branch), full stop — only Time Machine or the untouched local filesystem can supply them. Plans 81-08 and 81-09 as committed on 2026-10-19 22:34:01 are themselves post-gap-closure replacement content, not the true originals those slots held before that resequencing. The filesystem mtimes of the *never-tracked* files (81-01..81-07 `PLAN.md`, plus `81-CONTEXT.md`/`81-RESEARCH.md`/`81-PATTERNS.md`/`81-VALIDATION.md`) all fall in a tight Oct-18 window and were never touched by the 2026-10-21 git-history rewrite (which only touches tracked files) — a reasonably strong, non-cryptographic signal that most of the originals may still be sitting on disk, untouched, right now. Time Machine itself is currently **unreachable** from this session: `tmutil` and even plain `ls` on the mounted backup volumes both fail with "Operation not permitted" / "requires Full Disk Access" — a hard environment gate that must be resolved by the owner before D-08's backup search can proceed at all.

**Primary recommendation:** Investigate the `agent.spawn` hook first and treat it as very likely to work end-to-end for the narrow model-only case (the binary evidence strongly supports it); do not spend pilot time on BM's `model_overrides` config key as a substitute, and do not plan a "resume" test case for the hook (BM's checker loop never resumes). For PLANCHK-03, hash and provisionally treat the current on-disk, never-committed phase-81 files as candidate originals immediately (no Time Machine needed for that step), then use Time Machine, if and when Full Disk Access is granted, only to fill the 81-08/81-09 gap and to cross-verify the mtime-based candidates.

## Architectural Responsibility Map

This phase has no browser/API/database tiers — it investigates the agent-orchestration stack itself. The table below adapts the standard tier framework to that stack so the planner can sanity-check which layer owns which behavior.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Subagent model selection & override | Claude Code core (mods runtime, `agent.spawn` event) | model-gateway (backend resolution of the chosen id) | The mods runtime decides *what model string* a spawn uses; model-gateway decides *what backend* a Claude-prefixed id resolves to. A hook belongs in the first tier. |
| Per-agent model config (`model_overrides`, `models`, `model_profile`) | BM orchestrator (config resolution in `config-query.ts`) | Claude Code core (enum validation of the resulting invocation argument) | BM resolves a string; Claude Code's `Agent` tool still gates what that string may be at invocation time. BM cannot bypass that gate from config alone. |
| Gateway backend dispatch & model catalog | model-gateway shim/proxy (`request-worker.js`, `runtime.js`) | Codex backend (ChatGPT subscription login via `claude-code-proxy`) | The shim owns routing/logging/failure semantics; the actual model execution is a separate backend process outside this repo's or BM's control. |
| Plan-checker verification logic & instructions | BM agent definition (`agents/bm-plan-checker.md`) | — | Unchanged regardless of which model executes it — the hook/fallback changes *which model*, never the agent's instructions, tools, or structured-output contract. |
| Evidence/provenance recording for the pilot | Scratch pilot harness (outside the Triggarr repo, D-06) | Local filesystem (git-excluded phase directory, D-16) | Isolation is the point: the harness and its `.claude` settings must not be reachable from a Triggarr session. |
| Phase-81 original-artifact recovery | Time Machine / NAS backup (network destination) | Local git history + local filesystem mtimes (secondary, incomplete for 81-01..07) | Git is proven empty for most of the originals; the network backup is the only complete source, but is currently inaccessible from this environment (see Environment Availability). |

## Standard Stack

Not applicable in the conventional sense — this phase installs no new libraries. The "stack" is the already-installed tooling inspected below, each independently version-verified in this session:

| Component | Installed Version | Verified By |
|-----------|-------------------|-------------|
| Claude Code CLI | 2.1.281 (`~/.local/bin/claude` → `~/.local/share/claude/versions/2.1.281`) | `claude --version`; binary string inspection |
| Claude Code CLI, latest on npm | 2.1.310 (one newer than the 2.1.309 CONTEXT.md recorded at discussion time) | `npm view @anthropic-ai/claude-code version` / `versions --json` [VERIFIED: npm registry] |
| BM (Buildomator / GSD plugin) | 5.0.3 | `.claude-plugin/plugin.json` in the installed cache |
| model-gateway plugin | 0.51.2 | `.claude-plugin` cache path `eigenwise-toolshed/model-gateway/0.51.2/` |
| Codex CLI | 0.153.4 | `codex --version` |
| Node.js | v25.9.0 | `node --version` |
| git | 2.55.0 | `git --version` |
| Python | 3.14.5 | `python3 --version` |
| uv | 0.12.17 | `uv --version` |
| jq | 1.7.1 | `jq --version` |

No installation, upgrade, or package addition is proposed by this research. If the planner decides to build a reusable matched-run harness script (see "Matched-run mechanics" below), it needs only Python's standard library (`subprocess`, `json`, `hashlib`, `pathlib`) — no new third-party dependency.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages. The scratch pilot and any matched-run harness rely exclusively on already-installed CLIs (`claude`, `codex`, `git`, `jq`) and Python's standard library. If a future revision of the plan introduces a new dependency (for either the harness script or the scratch pilot's `.claude` configuration), run the Package Legitimacy Gate protocol before approving it — do not skip the gate just because this research found none needed today.

## Architecture Patterns

### Runtime support for `agent.spawn` (PLANCHK-01, D-01)

**Direct binary evidence (installed Claude Code 2.1.281), [VERIFIED: local binary inspection]:**

String-extracting the installed binary (`strings -a ~/.local/share/claude/versions/2.1.281`) surfaces the live, in-use implementation, not placeholder text:

```
var Be = [...,"process.spawn","settings.read","env.get","env.set"];
var KIt = [...Be, "tool.call","tool.check", ..., "agent.offer","agent.spawn",
           "prompt.submit", ..., "command.run","command.describe",
           "config.set","config.describe", ...];
```
`agent.spawn` is a first-class entry in the full mods event list — not experimental, not behind a feature flag. The only gate is `xp("agent.spawn")`, which just checks "does any loaded plugin have a hook registered for this event" (`xp = (o,e,s) => (s??loadedModules).some(r => r.hooks(o) && ...)`) — i.e., it is a no-op cost-saving check, not a kill switch.

The field-level contract:
```
var trn = ["tool_use_id","name","fork","parentModel","permissionMode","parentAgentId","provider"];
var As  = ["parentAgentId","provider"];
var El = {
  event: "agent.spawn",
  restoreArgument: (e,t) => G(As, e, t),           // force-restores parentAgentId/provider even if a hook tried to change them
  checkArgument(e,t) {
    return Mt({ keys: trn, passed: e, received: t,
      explanation: `the identity of the spawn and its parent is pinned; a rewrite keeps ${trn.join(", ")}` }) ?? Rs(e,t);
  },
  check: P((e) => At(e, "{ model }", (t) => typeof t.model === "string"))
};
```
Read literally: **`model` is explicitly absent from `trn`, the "pinned identity" list a hook cannot touch.** The only validation on a hook-returned `model` is `typeof t.model === "string"` — no enum check, no allowlist. Everything else identity-related (`tool_use_id`, `name`, `fork`, `parentModel`, `permissionMode`, `parentAgentId`, `provider`) is locked; **`permissionMode` being pinned means a narrow model-only hook cannot be abused to also escalate permissions** — directly relevant to the owner's safety posture.

The rewrite-logging path (`qIo`) confirms the same thing from the other direction:
```
_ = [...fields].filter(F => !pinned.has(F) && F!=="model" && passed[F]!==received[F]);
if (_.length>0) log(`agent.spawn ${subagentType}: ${_.join(", ")} rewritten by a hook`);
if (received.model !== passed.model) log(`agent.spawn ${subagentType}: model ${passed.model??"(inherit)"} -> ${received.model??"(inherit)"} by a hook`);
```
`model` gets its own dedicated log line, separate from the generic "fields rewritten" warning — the binary was built with "a hook changes only the model" as an anticipated, named case.

Resume/eviction/concurrency semantics also appear in the binary: a 10-minute wait-for-answer timeout (`VTe=10`, `"no answer within 10 minutes"`), an eviction concept (`"the subagent's record was evicted before its answer was read"`), and a subagent nesting depth cap (`"Subagent nesting limit reached (depth N)"`). None of these interact with the model field.

**Current official docs (fetched this session), [CITED: code.claude.com]:**

- `agent.spawn` — "A subagent or an agent team teammate is about to start... A hook can return `next({ ...e, model })` to choose its model, or `{ deny: reason }`."
- "If an installed mod sets a model in its `agent.spawn` hook, Claude Code uses that model **in place of the per-invocation parameter**." (From "Choose a model," precedence order effective v2.1.251+.)
- **Resume:** "When Claude resumes a subagent with the `SendMessage` tool, your `agent.spawn` hook doesn't run again. To refuse the `SendMessage` calls that resume a subagent, match that tool in a `tool.call` hook." — this is the one documented edge case D-01/D-07 asked about, and it turns out not to matter for this phase (see next section).
- Permission semantics for the *mods* system generally: hooks run under a 10-second own-execution budget per event; `agent.spawn` has no exit-code-based permission model (unlike the older "classic" hook system) — it is a plain async function that returns `next(e)`, `{ deny }`, or a partial-field object.
- The mods reference page is versioned "as of v2.1.290" for the CLI, but gives **no version-gate annotation on `agent.spawn`/`agent.offer`** themselves, unlike several newer mods features it does gate (`e.agentId`/`e.ceiling` on `tool.check` need v2.1.290+, `e.isReadOnly` needs v2.1.304+, etc.). The absence of a version floor on `agent.spawn` is circumstantial but consistent with the binary evidence that it already exists, functioning, in 2.1.281.

**Conclusion for D-01:** Treat `agent.spawn` hook support on the *installed* 2.1.281 as **verified present** with HIGH confidence from binary inspection, corroborated by current docs describing the identical contract. This is a materially stronger starting position than the blueprint had (which explicitly said hook availability "on that installed version were **not established**"). D-02's conditional runtime update is likely unnecessary for hook *availability* — though the planner should still record the live npm-latest version (2.1.310 as of this research) and decide whether to update for unrelated reasons (bug fixes, the `re-entry`/`rewritten` `next.error.cause` diagnostics that need v2.1.292/v2.1.300+, etc.). No actual hook was registered or exercised in this research session — that is pilot work, not investigation work, and remains to be executed per D-07.

### BM 5.0.3 plan-checker invocation (exact mechanics BM uses)

`~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/plan-phase.md`, step 10 (`## 10. Spawn bm-plan-checker Agent`):

```
Agent(
  prompt=checker_prompt,
  subagent_type="bm:bm-plan-checker",
  model="{checker_model}",
  description="Verify Phase {phase} plans"
)
```

`subagent_type` is the literal, exact string `"bm:bm-plan-checker"` — this is what a hook matcher must match (CONTEXT.md D-01's wording is confirmed correct).

Every place BM re-invokes the checker is a **fresh `Agent()` call with the same literal arguments**, never a `SendMessage` resume:
- Step 10 — initial check.
- Step 12 ("Revision Loop (Max 3 Iterations)") — after the planner revises, "spawn checker again (step 10)" — same `Agent()` call, same `subagent_type`, same `model="{checker_model}"`.
- Step 12.5 ("Plan Bounce") sub-step 5 — "Re-run plan checker on bounced plans: Spawn bm-plan-checker (same as step 10) on all modified plans."

**This directly resolves D-07's "resume path" exercise: there is no resume path to test.** Every one of BM's checker invocations is a brand-new `agent.spawn` event, so a narrowly-matched hook fires reliably on all of them (initial, every revision iteration, and the post-bounce recheck) without needing to handle the documented `SendMessage`-resume exemption at all. Do not plan pilot time around simulating a resumed checker session — it does not reflect how BM actually drives this agent.

`checker_model` itself resolves through BM's `resolve-model` query (`sdk/src/query/config-query.ts`): per-agent `model_overrides` first, then phase-type `models` map, then the active `model_profile` table, then runtime default. Under this repo's current `.planning/config.json` (`model_profile: "balanced"`, no `model_overrides`, no `runtime` key), `bm-plan-checker`'s catalog entry (`golden: sonnet, balanced: sonnet, budget: haiku, routingTier: light`) resolves to the `claude-sonnet-5-5` alias — i.e., **the ordinary checker today actually runs on Sonnet, not Opus.** This is the real baseline the "ordinary BM checker" side of the matched comparison (D-17) will use unless the planner deliberately changes `model_profile` for the exercise.

### Why the hook route is likely necessary (not `model_overrides`)

BM 5.0.3 ships a genuine, documented, per-agent model override config key — a real difference from the 4.9.1 blueprint inspected:

```json
{
  "model_profile": "balanced",
  "model_overrides": { "bm-executor": "opus", "bm-planner": "haiku" }
}
```
(`references/model-profiles.md`; dynamic key pattern `^model_overrides\.[a-zA-Z0-9_-]+$` in `sdk/src/query/config-schema.ts`.) It is tempting to assume setting `model_overrides["bm-plan-checker"] = "claude-gpt-6-astra[1m]"` is a simpler substitute for a mod hook. **It is not**, per model-gateway's own documentation ([CITED: installed `skills/model-gateway/SKILL.md`]):

> "Claude models keep working normally at the same time (passthrough path). That does not mean a subagent invocation can mix in a gateway id freely: the `Agent` tool's own `model` parameter is a **fixed host enum** (`sonnet`/`opus`/`haiku`/`fable`), independent of gateway or plugin state, and **a gateway id passed there is refused.**"

Whatever BM's config resolution computes still ends up as the literal `model=` argument to `Agent(subagent_type="bm:bm-plan-checker", model=<value>, ...)` (confirmed above) — an argument Claude Code's own tool-level validation enum-checks *regardless of where the string came from*. BM's config can pick a different alias (`"opus"` instead of `"sonnet"`) but cannot hand the Agent tool a gateway id directly.

model-gateway's *own* documented, supported pattern for routing a named subagent to a concrete gateway id is different, and matches CONTEXT.md D-03's fallback almost exactly:

```markdown
---
name: luna-reviewer
description: Reviews code changes using the GPT-5.6 Luna gateway model.
model: claude-gpt-5.6-luna[1m]
tools: Read, Grep, Glob
---
Review the diff for correctness and report findings.
```
"Save that as `.claude/agents/luna-reviewer.md`... Invoke with `subagent_type: "luna-reviewer"` and **no `model` argument**... This frontmatter contract and Model Gateway's routing for a concrete id are confirmed; an end-to-end custom-agent spawn through this path **has not been verified here**."

The catch: BM's `plan-phase.md` hardcodes `model="{checker_model}"` on every checker spawn (shown above) — it never omits the model argument for this agent. So the frontmatter fallback cannot be exercised through BM's real workflow without either forking BM (explicitly out of scope — "do not patch... the installed plugin cache") or building a **separate, hand-maintained invocation path outside `/bm:plan-phase`** that calls a differently-named agent with no model argument, which is exactly what D-03's wording ("a maintained dispatch integration that omits the invocation model argument") describes. Understand D-03's fallback as a tool for the **scratch-pilot comparison exercises only** (frozen Phase 81 snapshots, run outside BM's live workflow) — not as something that could ever be wired into Triggarr's actual `/bm:plan-phase`, which is consistent with this phase's activation boundary anyway.

**This chain of evidence (hook field contract + gateway's own enum-refusal statement + BM's hardcoded invocation argument) is the single most important finding for planning D-01 through D-07: the `agent.spawn` hook is not just the *preferred* mechanism, it is architecturally the *only* documented way to get a gateway-routed Codex model onto the literal `bm:bm-plan-checker` identity as BM actually invokes it.**

### model-gateway 0.51.2: routing mechanics

[CITED/VERIFIED: installed `lib/runtime.js`, `lib/request-worker.js`, `skills/model-gateway/SKILL.md`]

**Live catalog at inspection time** (`lib/runtime.js`, `MODEL_WINDOW_POLICY`, recheck at pilot time — D-04 requires this):

| Picker alias | Backend | Window |
|---|---|---|
| `claude-gpt-5.6-sol[1m]` | Codex | 920,012 (measured) |
| `claude-gpt-5.6-terra[1m]` | Codex | 920,012 (measured) |
| `claude-gpt-5.6-luna[1m]` | Codex | 920,012 (measured) |
| `claude-gpt-6-astra[1m]` | Codex | 920,012 (measured) — newest-named row; the SKILL.md explicitly warns `claude-code-proxy` 0.1.14–0.1.35 can *silently omit* Astra from the live catalog even while `doctor` reports a structural PASS, so "listed in code" is not the same as "actually being served" — confirm the serving proxy version is ≥0.1.36 at pilot time, not just that the id appears in `runtime.js`. |
| `claude-grok-4.5[1m]` | Grok | 500,000 (measured) |

**Request-route logging** (`request-worker.js`, `requestRouteLog`), exactly the "gateway metadata correlated to the checker invocation" D-14 requires:

```js
// ~/.claude/model-gateway/logs/request-routes.jsonl, one JSON object per line
{
  at: "<ISO timestamp>",
  backend: "codex",                 // or "grok" / "anthropic"
  model: "<concrete backend id, e.g. gpt-5.6-sol>",
  path: "<request path>",
  via: "<routing marker, e.g. 'dispatch-unbound'>",
  effort: "<reasoning effort, if present>",
  sessionId: "<Claude Code session id, from x-claude-code-session-id>",
  agentId: "<subagent id, from x-claude-code-agent-id>",
  parentAgentId: "<parent agent id, if any>",
  markersLength: <int>
}
```
This is enabled by default (disable with `CODEX_GATEWAY_REQUEST_LOG=0`). The pilot's proof-of-routing step is: capture the checker subagent's `agentId` (available via Claude Code's own telemetry — the `subagent.spawn` / `claude_code.subagent.spawn` OTel span carries `agent_id`, and `/tasks` shows the running subagent's id and model), then grep `request-routes.jsonl` for a matching `agentId` with `backend: "codex"` and the expected `model`. **A model label shown in `/tasks` or the picker is not this proof — the JSONL correlation by `agentId` is.**

**Non-silent failure codes**, directly relevant to D-07's "no silent pass, no silent fallback":
```js
if (upstreamBlocked) return 'upstream-blocked';       // OpenAI/auth rejection, does not expire
if (upstreamUnavailable) return 'upstream-unavailable'; // last Codex call failed in the past 60s
```
`doctor` surfaces both distinctly; neither is a silent pass. What is **not yet verified** (per model-gateway's own doc and not re-verified in this read-only session, since doing so would require sending a request) is what Claude Code itself does when the gateway returns one of these — whether the subagent's turn surfaces a visible error (expected, default behavior with no `--fallback-model` configured) or whether some other BM/Claude Code layer retries silently. This remains a pilot-time verification (D-07), not something this research could close out without sending a live request.

### Scratch-pilot hook skeleton (mods file layout)

[CITED: code.claude.com/docs/en/plugins/mods/reference]

```
~/scratch/planchk-pilot/
└── .claude/
    └── plugins/
        └── planchk-router/            # or --plugin-dir pointed straight at this
            ├── .claude-plugin/plugin.json
            └── hooks/
                ├── hooks.json          # { "modules": ["./register.js"] }
                └── register.js
```
```js
// register.js
export function register(on) {
  on('agent.spawn', { subagentType: 'bm:bm-plan-checker' }, async ($, e, next) => {
    return next({ ...e, model: 'claude-gpt-6-astra[1m]' }); // recheck live catalog at pilot time (D-04)
  });
}
```
The matcher syntax from the hooks reference ("A matcher containing only letters, digits, `_`, `-`, spaces, `,` and `|` is compared as an exact string") applies to `classic.*` settings-hooks matchers; the mods `on(event, matcher, hook)` form filters on the event's own fields (here, `subagentType`) as documented under "Filter which events a hook handles" — confirm the exact matcher key name (`subagentType` vs `agentType`) against `claude plugin validate` output at pilot time, since the hooks-docs page uses `agent_type` for the *classic* `SubagentStart`/`SubagentStop` matchers while the mods `agent.spawn` event's own field names come from the binary's `qIo`/`El` code (`n.subagentType`) — these are two different systems with similar-looking field names and must not be conflated when writing the actual hook.

Per `--plugin-dir`'s documented behavior, this loads for one session and reloads on save — convenient for pilot iteration without touching Triggarr's own plugin cache or settings, satisfying D-06.

### Anti-Patterns to Avoid
- **Assuming `model_overrides` in BM config is a hook substitute:** model-gateway's own docs state the Agent tool refuses a gateway id at the invocation layer regardless of config source. Confirmed above; do not pilot this as a primary route.
- **Planning a "resume" test case for the plan-checker hook:** BM never resumes `bm:bm-plan-checker`; every recheck is a fresh `Agent()` spawn. The documented resume exemption is real but irrelevant to this agent's actual call pattern.
- **Conflating BM's `runtime`/`model_profile_overrides.codex.*` multi-host-CLI feature with per-subagent gateway routing:** see "Common Pitfalls" below — these are unrelated BM features that happen to share the word "codex."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Enforcing a wall-clock ceiling on a `claude -p` session (D-18, 15 min) | A custom timeout wrapper from scratch | The same pattern already in this repo's `tests/codex_review_run.py` (Phase 83): Python's `subprocess` timeout, no external `timeout` binary needed, timeout recorded as a distinct exit code | Already built, tested, and documented (`docs/codex-adversarial-review-contract.md`) in this exact repo for an analogous problem (bounding a Codex CLI run). Claude Code 2.1.281 itself has no `--max-turns`/timeout flag (confirmed via `claude --help`); external wrapping is required either way. |
| Parsing `request-routes.jsonl` for the gateway-metadata proof | A bespoke parser | `jq` (already installed, 1.7.1) or Python's stdlib `json`, one object per line | It is already line-delimited single-line JSON; no custom format to reverse-engineer. |
| A cross-AI orchestrator to route BM through Codex generally | Any new scheduler/dispatcher | The existing `agent.spawn` hook (narrow, single-agent) or, if that fails, the existing custom-agent-frontmatter pattern | REQUIREMENTS.md's Out of Scope table and the blueprint both explicitly prohibit a new orchestrator; both viable routes here are already-supported Claude Code/model-gateway mechanisms. |
| Verifying Phase 81 timestamp provenance from scratch with a new tool | A bespoke log-correlation script | `git log --all --diff-filter=A -- <path>`, `stat -f "%Sm"`, and the existing `~/.codex/sessions/2026/10/` rollout files | All three sources are already queryable with stock tools; no tooling gap exists for this specific forensic task (demonstrated in this research session). |

**Key insight:** Every mechanism this phase needs — hook-based model override, gateway request logging, subprocess timeout enforcement, git/filesystem forensics — already exists in either the installed Claude Code/model-gateway/BM stack or this repository's own Phase 83 tooling. The investigation's job is to *prove* these mechanisms compose correctly for this specific narrow case, not to build new infrastructure.

## Recovering the original Phase 81 plans (PLANCHK-03, D-08/D-09)

### Git-verified state (HIGH confidence — direct `git log`/`git ls-files` inspection, this session)

| Plan | Ever in git (any branch, incl. `backup/phase-81-pre-scrub`)? | Current content's provenance |
|------|---|---|
| 81-01 through 81-07 `PLAN.md` | **Never.** Zero commits on any ref, confirmed via `git log --all --diff-filter=A -- "*81-0N-PLAN.md"` for N=1..7 and via full tree listing of `backup/phase-81-pre-scrub` (identical file set to current `main`). | Only ever existed on the local filesystem (or Time Machine). |
| 81-08, 81-09 `PLAN.md` | First appear 2026-10-19 22:34:01 -0400, in the **same commit** that adds 81-10/81-11 ("`docs(81): add gap-closure plans 81-10/81-11 for v5 grab identity and resequence 81-08/09`"). | This is **post-gap-closure replacement content for those slots**, not the pre-resequence originals. What the original 81-08/81-09 plans contained before the resequencing is unknown from git; last edit to the current 81-08/09 content is 2026-10-20 17:51:01, still ~2.5 hours before the deep-review session below. |
| 81-10 through 81-13 `PLAN.md` | New plans created 2026-10-19 22:34:01 through 2026-10-20 17:51:01, entirely absent from the "original nine" framing. | Out of scope for "original nine" recovery; relevant only to the later revision-review round if the planner wants a "revised plans" snapshot. |
| `81-CONTEXT.md`, `81-RESEARCH.md`, `81-PATTERNS.md`, `81-VALIDATION.md`, `81-DISCUSSION-LOG.md` | **Never tracked at all** — only `81-LIVE-MATRIX.md` among the non-PLAN/SUMMARY docs is in git. | Local filesystem (or Time Machine) only. |

**Corrected framing vs. CONTEXT.md D-08:** D-08 says "only 81-10/81-11 from 2026-10-19 onward" are in git — this research found that framing slightly imprecise: 81-08 and 81-09 *also* first appear in git on that same date/commit, but as **replacement** content, not originals. For planning purposes, treat git as containing **zero usable originals** for any of the nine original plan slots.

### Filesystem mtime evidence (MEDIUM confidence — not cryptographic, but internally consistent)

All never-tracked phase-81 files carry mtimes in a tight window on **2026-10-18** (15:29–18:46), and critically, **these mtimes were never disturbed by the 2026-10-21 git-history rewrite** (STATE.md's "Published-history note") — because that rewrite only touches *tracked* files, and a filter-branch/checkout operation on tracked files (81-04..07 `SUMMARY.md`, 81-08/09 `PLAN.md`+`SUMMARY.md`) visibly bumped **those** files' mtimes to a uniform `2026-10-21 14:28:10`. The untracked files sitting right next to them kept their original Oct-18 timestamps:

```
2026-10-18 15:29:45  81-DISCUSSION-LOG.md
2026-10-18 15:57:34  81-PATTERNS.md
2026-10-18 16:15:16  81-07-PLAN.md
2026-10-18 16:27:49  81-02-PLAN.md
2026-10-18 16:37:43  81-01-PLAN.md
2026-10-18 16:37:52  81-RESEARCH.md
2026-10-18 16:40:10  81-04-PLAN.md
2026-10-18 16:40:56  81-05-PLAN.md
2026-10-18 16:41:19  81-06-PLAN.md
2026-10-18 16:59:50  81-VALIDATION.md
2026-10-18 17:14:02  81-03-PLAN.md / 81-CONTEXT.md
2026-10-18 17:37:03  81-01-SUMMARY.md
2026-10-18 17:51:59  81-02-SUMMARY.md
2026-10-18 18:45:58  81-03-SUMMARY.md
---  (contrast: tracked files, touched by the Oct-21 rewrite checkout)  ---
2026-10-21 14:28:10  81-04-SUMMARY.md, 81-05-SUMMARY.md, 81-06-SUMMARY.md, 81-07-SUMMARY.md,
                     81-08-PLAN.md, 81-08-SUMMARY.md, 81-09-PLAN.md, 81-09-SUMMARY.md
```

**This is an actionable, low-cost finding for the planner: plans 81-01 through 81-07 and the four contemporaneous docs may already be sitting on disk, unmodified, right now — no Time Machine access required to get a first candidate.** SHA-256 baselines were computed in this session as a documented starting point (recompute and re-verify at execution time, since this research made no claim of exclusive access to the file during the gap):

```
dfeb54c5937136e7143574ab4d0b14feab0f80d106e215010e571377ba557fb2  81-01-PLAN.md
096a065550f1643f756b3d6b7f1cb0212dbee85952ad537199de02cd3f7f2b14  81-02-PLAN.md
3b3a54a61df4d2d0e91b9fe1c8e250ca7d1680280f1f34f7755dbac495fc0bdc  81-03-PLAN.md
3d2321350a2da83e9904081f8ee9f71de3fca6616485b700143c840be2ae5360  81-04-PLAN.md
5b071d71b5e0d09c8416e3abfed022691f3614f131c3fffad95d3b40f8d77f5d  81-05-PLAN.md
d7165eed6935e5e1efe94648fc79c39b4a20de66482940b7a7457d520c59e2b7  81-06-PLAN.md
b04fc2574c4a28cb099ce12e2afdea8cada2466c05068831e3ab443e432d24a4  81-07-PLAN.md
```

Caveat (do not overstate this evidence): mtime is not forgery-proof and this is not proof the content hasn't been edited in a way that preserved the mtime (e.g. some editors/tools can). It is, however, the best non-Time-Machine evidence available, and it is internally consistent with the git rewrite's footprint, which is a meaningful cross-check a pure "trust the mtime" claim would lack.

**Gap that genuinely requires Time Machine:** the true pre-resequence 81-08 and 81-09 content. Nothing on the local filesystem or in git preserves it — it was overwritten in place by the gap-closure revision. Only a Time Machine snapshot from before 2026-10-19 22:34:01 can supply it, if the destination retained one.

### Pinning "the first manual Codex findings" (D-09) — triangulated timestamp evidence

Three independent sources converge tightly around the evening of **2026-10-20**:

1. **Commit timestamps** (git, HIGH confidence):
   - `2026-10-20 20:21:24 -0400` — "`docs(phase-81): record Phase 81 closeout — 13/13 plans executed, incomplete per D-13`" (hash `1915a7d` / pre-rewrite `a2b8c1c`)
   - `2026-10-20 20:54:37 -0400` — "`docs(81): record deep-review pass 1 revision position and defer bugs-005 lifecycle`" (`06519aa` / `d14b71e`)
   - `2026-10-20 21:13:20 -0400` — "`docs(81): record deep-review pass 2 follow-up position`" (`3e19e48` / `9a1d423`)
   - `2026-10-20 21:30:02 -0400` — "`docs: record deferred Codex plan-checker routing investigation`" (`c2fb07a` / `363060e`) — this is the commit that records the blueprint's PLANCHK section itself, despite the blueprint document's own header saying "Recorded 2026-10-18." Flag this date mismatch explicitly; it was not resolved in this session and does not block planning, but the planner should not assume the blueprint's self-dated "2026-10-18" is the actual git-committed date of that section.
   - `2026-10-20 21:57:02 -0400` — "`docs(81): close SONARRV5-02 after the 81-14 live probe`" (`91b7992` / `b498475`)
2. **Codex CLI session log** (`~/.codex/sessions/2026/10/20/`, filename/mtime only, content not read — MEDIUM confidence, corroborating): a rollout session file named `rollout-2026-10-20T20-19-46-01a15bd4-0e22-7450-8da3-0b87eabfce83.jsonl` starts at **20:19:46**, 98 seconds before the "Phase 81 closeout" commit and comfortably inside the window of the "deep-review pass 1/2" commits that follow. This is the session most likely to be the actual manual Codex deep-review referenced by the blueprint.
3. **Claude session transcript mtime** (`~/.claude/projects/-Users-julianamacbook-triggarr/e21279f7-603c-4394-8fa8-e1b0cb0adc62.jsonl`, filename/mtime only — MEDIUM confidence, corroborating): last-written at **2026-10-20 21:28**, squarely inside the same window.

**Recommendation:** use **2026-10-19 22:34:01 -0400** (the gap-closure/resequence commit, the single latest *known-safe* moment — nothing after it is verified clean) as the conservative hard cutoff for anything the planner cannot individually verify, and treat the **2026-10-20 20:19:46–21:57:02** window as the actual review period if finer-grained dating of a specific file is needed. Everything checked above (81-01..07 PLAN.md, the four contemporaneous docs, and the git-committed 81-08 through 81-13 content) has a verified last-modification point before 20:19:46 on Oct 20, satisfying D-09's "predates first manual Codex findings" test under either cutoff choice.

### Time Machine access — BLOCKED in this environment (report honestly, do not guess around it)

```
$ tmutil destinationinfo
Kind: Network, URL: smb://Time%20Machine%20User@MaguffyNAS.../Time Machine Juliana MacBook Air   -- succeeds, confirms the destination CONTEXT.md names
$ tmutil latestbackup / tmutil listbackups
tmutil: listbackups requires Full Disk Access privileges.
$ ls "/Volumes/Backups of Juliana's MacBook Air"      (and " 1", " 2")
ls: Permission denied / Operation not permitted
```
The network Time Machine destination is confirmed configured and reachable (`destinationinfo` succeeds), and three backup volumes are already mounted under `/Volumes/` — but **every attempt to enumerate or browse their contents fails with a macOS Full Disk Access (TCC) permission error**, for both the privileged `tmutil` API and a plain `ls` on the mounted volume. This is not a transient error; it is the standard macOS protection for Time Machine backup contents, and it blocks this read-only research session completely regardless of any Phase 84-specific sandboxing.

Local APFS snapshots (`diskutil apfs listSnapshots /`) show only an OS-update snapshot — no local Time Machine snapshot exists for the Oct 10–19 window; the network destination is the only possible source.

**This must be resolved by the owner before D-08's backup search can execute, and it is not something a plan can work around:** either (a) grant Full Disk Access to whichever application/process will run the actual `tmutil`/backup-browsing commands at execution time, or (b) have the owner run the listing/copy commands themselves (outside this agent's permission boundary) and hand off the recovered files. Flag this explicitly as a blocking environment dependency in the plan rather than assuming it will resolve itself.

## Matched-run mechanics (D-05, D-17, D-18)

- **No native per-session timeout or `--max-turns` flag exists in Claude Code 2.1.281** (confirmed absent via `claude --help` — grep for "max-turn"/"timeout" returns nothing). D-18's 15-minute ceiling must be enforced externally, exactly as Phase 83's `tests/codex_review_run.py` already does for the (unrelated) Codex-CLI review contract: wrap the `claude -p ...` invocation in a `subprocess` call with a Python-level timeout, record a timeout as a distinct status rather than silently truncating output.
- **Reasoning effort:** `claude --effort <low|medium|high|xhigh|max>` is a documented session-level flag (seen in `claude --help`). This is the mechanism for D-05's "both run at highest reasoning effort" — do **not** rely on BM's native `runtimeTierDefaults.codex` tier defaults for this, because `bm-plan-checker`'s catalog tier is `sonnet`, and `model-catalog.json`'s codex-runtime default for the `sonnet` tier is `"gpt-5.3-codex"` at `"reasoning_effort": "medium"` — not the highest available. Explicitly pass `--effort xhigh` or `max` on both the ordinary and the Codex-routed matched runs rather than trusting any tier default to already be "highest."
- **Non-interactive, scripted sessions:** `claude -p` (`--print`) with `--output-format json` returns a single structured result object (includes model used, and typically duration/turn-count/cost fields in Claude Code's standard `--print --output-format json` result shape — reconfirm the exact field names against the installed version at pilot time rather than assuming the trained-knowledge schema is current). `--permission-mode` and `--settings <file>` let the pilot point a scripted session at the scratch project's isolated `.claude` directory without touching any global state. `--max-budget-usd` exists as a cost rail for the *Claude-side* API spend but has no bearing on Codex/ChatGPT-subscription spend, which model-gateway bills separately — D-18's "stays within the owner's ChatGPT subscription" needs to be checked via model-gateway's own usage signals (`doctor`'s `upstream-blocked`/`upstream-unavailable` state, the per-session high-water file under `~/.claude/model-gateway/request-body/`), not via `--max-budget-usd`.
- **Blind adjudicator session (D-11):** a fresh, isolated `claude -p` (or interactive) session with no prior context, given only the frozen outputs + withheld answer key — straightforward with `--settings`/`--add-dir` to scope exactly what it can read, no special mechanism needed beyond careful prompt/file scoping.

## Records staying local (D-16)

This repository already has the exact precedent to follow: `.git/info/exclude` excludes `.planning/` broadly (confirmed: `git check-ignore -v` on a never-tracked phase-81 file resolves to this exclude rule), and prior phases (81, 83) selectively `git add -f` only the specific files meant to ride into a future phase PR (e.g., 81's `SUMMARY.md`/`PLAN.md` files, 83's evidence files). For Phase 84, per D-16, the default (do nothing) already satisfies "stay local" — the phase directory `84-codex-plan-checker-investigation/` is excluded the same way, and no `git add -f` should be run against its contents unless a specific file is deliberately being carried forward (which D-16 says should not happen for this phase's own artifacts). The scratch pilot itself lives entirely outside the repo (D-06), so it needs no gitignore handling at all.

## Common Pitfalls

### Pitfall 1: Treating BM's `runtime: "codex"` config feature as the per-subagent routing mechanism
**What goes wrong:** BM 5.0.3 has a native `config.runtime` + `config.model_profile_overrides.<runtime>.<tier>` catalog (confirmed in `sdk/shared/model-catalog.json`, includes a full `codex` runtime entry with `gpt-5.4`/`gpt-5.3-codex`/`gpt-5.4-mini` tiers and reasoning-effort defaults). It is easy to assume this is "BM's native Codex routing" and try to use it for PLANCHK.
**Why it happens:** Both features use the word "codex" and live in the same config-resolution code path (`resolveModel` in `config-query.ts`).
**How to avoid:** `config.runtime` changes which *host CLI* BM assumes it is running under (Claude Code CLI vs. Codex CLI vs. Gemini CLI vs. Qwen CLI, for cross-tool compatibility) — it is a global, all-agents setting, not a per-agent, within-a-Claude-Code-session override, and it is unrelated to model-gateway's per-subagent routing. Setting it would affect every BM agent's model resolution at once, directly violating D-14's "every other agent's model... remains unchanged."
**Warning signs:** Any plan task that proposes setting `.planning/config.json`'s top-level `runtime` key for this investigation is out of scope and should be flagged.

### Pitfall 2: Treating gateway catalog presence as proof of routing
**What goes wrong:** Seeing `claude-gpt-6-astra[1m]` in `/model` or in `runtime.js`'s policy table and concluding the checker actually ran on it.
**Why it happens:** The picker/catalog list is populated from a static policy table and a discovery cache that can be stale (model-gateway's own doc: a stale shim can pass `doctor`'s structural check while a specific model id is actually missing from the serving proxy).
**How to avoid:** Require the `request-routes.jsonl` `agentId`-correlated entry (see "model-gateway 0.51.2: routing mechanics") as the actual proof, per D-04/D-14.
**Warning signs:** Any report of "routing confirmed" that cites only `/model`, `/tasks`, or a code label without a matching JSONL line.

### Pitfall 3: Assuming BM's `model_overrides` is a hook-free shortcut
**What goes wrong:** Spending pilot time trying `model_overrides["bm-plan-checker"] = "<gateway id>"` as a simpler alternative to building a hook, then being confused when the Agent tool refuses it.
**Why it happens:** `model_overrides` is real, documented, and does accept "full IDs" for *Claude* model ids — the refusal is specific to non-enum (gateway) ids, which is easy to miss on first read.
**How to avoid:** This research has already confirmed the refusal from model-gateway's own documentation; treat it as closed and go straight to the hook (or the frontmatter fallback) rather than re-discovering this during the pilot.

### Pitfall 4: Planning a "resume" test case for the plan-checker hook
**What goes wrong:** D-07 lists "resume path" among the pilot exercises, and the current official hooks docs do describe a real resume exemption (`SendMessage` doesn't re-fire `agent.spawn`) — easy to over-invest pilot design effort simulating this.
**Why it happens:** The exemption is real and documented, just not applicable to how BM drives this specific agent.
**How to avoid:** This research confirmed from BM's own `plan-phase.md` that every checker invocation (initial, revision loop, post-bounce) is a fresh `Agent()` call, never a resume. Note this explicitly in the pilot's exercise list as "N/A — BM's checker loop has no resume path" rather than omitting it silently (D-07's own bar: don't report something as passing that wasn't actually exercised, and don't report an inapplicable case as a gap either).

### Pitfall 5: Assuming Time Machine is the only possible source for the Phase 81 originals
**What goes wrong:** Blocking all of D-08/D-09 on getting Full Disk Access, when most of the originals may already be recoverable from the current, never-committed local filesystem state.
**Why it happens:** CONTEXT.md's D-08 framing emphasizes Time Machine as the recovery path, and it's the only path for 81-08/81-09's true originals — but it is not the only path for 81-01 through 81-07 and the contemporaneous docs, as this research's mtime/git-forensics cross-check showed.
**How to avoid:** Hash and provisionally use the current on-disk files for 81-01..07 + context/research/patterns/validation immediately; reserve the Time Machine effort (and the owner's Full Disk Access grant) specifically for recovering the true pre-resequence 81-08/81-09 content, which is the one genuine gap.

### Pitfall 6: Forgetting ignored files "will not arrive through Git alone" when assembling the blind packet
**What goes wrong:** Assembling the reviewer packet by checking out a git ref and assuming it's complete.
**Why it happens:** Most of the phase-81 planning docs are untracked; a git checkout of any ref will silently omit them with no error.
**How to avoid:** The blueprint itself already warns of this ("Ensure referenced local files are actually in the packet; ignored files will not arrive through Git alone") — treat the packet-assembly step as an explicit filesystem copy from the frozen/recovered source, never a `git archive`/`git checkout`.

## Code Examples

### Correlating a gateway-routed subagent to its model-gateway log entry
```bash
# After the pilot checker subagent completes, get its agent id from Claude Code's
# own /tasks output or OTel span, then:
jq -c --arg aid "<agent_id>" 'select(.agentId == $aid)' \
  ~/.claude/model-gateway/logs/request-routes.jsonl
# Expect: {"backend":"codex","model":"gpt-6-astra", ... ,"agentId":"<agent_id>", ...}
```

### Enforcing the 15-minute ceiling on a matched run (pattern reused from `tests/codex_review_run.py`)
```python
import subprocess, time

start = time.monotonic()
try:
    result = subprocess.run(
        ["claude", "-p", "--settings", str(settings_path), "--effort", "xhigh",
         "--output-format", "json", prompt],
        capture_output=True, text=True, timeout=900,  # 15 min, D-18
    )
    status = "completed" if result.returncode == 0 else "failed"
except subprocess.TimeoutExpired:
    status = "incomplete_timeout"
duration_s = time.monotonic() - start
```

## State of the Art

| Old Approach (blueprint, BM 4.9.1, 2026-10-18) | Current Approach (BM 5.0.3, this research) | When Changed | Impact |
|---|---|---|---|
| "Hook availability and gateway routing on [2.1.281] were **not established**" | Binary inspection confirms the `agent.spawn` hook's model-field contract is fully present and functioning on 2.1.281 | This research session (no version change — same binary, deeper inspection) | D-01's verification step starts from strong positive evidence rather than a blank slate; D-02's runtime-update decision is now a separate question from hook availability. |
| BM 4.9.1: no per-agent `model_overrides`/`runtime`/`model_profile_overrides` catalog documented in the blueprint | BM 5.0.3 ships all three, documented in `references/model-profiles.md` and enforced in `config-schema.ts` | Between BM 4.9.1 and 5.0.3 (exact version not pinned in changelog during this pass) | New-looking native config that could be mistaken for a routing shortcut — see Pitfall 1/3; does not actually change the hook-necessity conclusion. |

**Deprecated/outdated:** None of the blueprint's conclusions are deprecated — they are *sharpened*: where the blueprint said "not established," this research says "established, with the specific field-level contract," and where the blueprint said BM's invocation "model resolver accepts per-agent overrides, but that alone does not establish that Claude's invocation accepts a gateway model ID," this research confirms explicitly (from model-gateway's own docs) that it does **not** accept one, closing that open question.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `claude-gpt-6-astra[1m]` is still "the strongest Codex model the gateway offers" at actual pilot execution time | Architecture Patterns / model-gateway 0.51.2 | D-04 already requires rechecking the live catalog; if the catalog has changed (new model, Astra silently missing from an outdated proxy), the pilot would route to the wrong or an unavailable model. Low risk since D-04 explicitly gates on a recheck. |
| A2 | The mods `agent.spawn` matcher field is named `subagentType` (from binary code `n.subagentType`) rather than `agentType` (the name the *classic* `SubagentStart`/`SubagentStop` hooks docs use) | Architecture Patterns / Scratch-pilot hook skeleton | If wrong, the hook's matcher silently never fires (likely fails open to "no match," not a crash) and the pilot would wrongly conclude the hook doesn't work. Mitigate by running `claude plugin validate` on the draft hook before the real pilot run, as the mods reference itself recommends. |
| A3 | Claude Code's standard `--print --output-format json` result object includes duration/turn-count/cost-shaped fields usable for D-17/D-18 reporting, matching the general shape from training knowledge | Matched-run mechanics | If the exact field names differ on 2.1.281, the harness script would need a quick schema check (`claude -p "test" --output-format json \| jq .` ) before relying on specific field names in a report template — low risk, cheap to verify at execution time. |
| A4 | The Codex CLI session `rollout-2026-10-20T20-19-46-...jsonl` and the Claude session `e21279f7...jsonl` (mtime Oct 20 21:28) are actually the sessions that performed the manual Codex deep review referenced by the blueprint, rather than unrelated concurrent work | Recovering the original Phase 81 plans / timestamp triangulation | If wrong, the recommended cutoff window could be slightly mis-centered — though the recommended *conservative* cutoff (2026-10-19 22:34:01, the gap-closure commit) does not depend on this assumption at all, only the narrower "actual review window" estimate does. |

## Open Questions

1. **Does Claude Code's `agent.spawn` hook's model override interact correctly with model-gateway's per-request header-based session/agent correlation end-to-end?** (RESOLVED at the code-inspection level — both mechanisms are confirmed to exist independently and their field contracts are compatible — but no live request has been sent in this read-only research session.)
   - What we know: the hook sets `model` on the spawn event; model-gateway resolves any Claude-prefixed alias including gateway ids; the gateway logs correlate by `x-claude-code-agent-id`/`x-claude-code-session-id` headers that Claude Code itself sends.
   - What's unclear: whether Claude Code actually attaches those two headers to a request whose model came from a hook override specifically (vs. a normal invocation-argument model) — both code paths were inspected, neither showed special-casing that would suppress the headers, but this was not live-verified.
   - Recommendation: the pilot's very first exercise (an initial check against a trivial valid plan) doubles as this verification — if the `agentId`-correlated log entry appears with `backend: "codex"`, the question is closed with live evidence; do not treat this research's code-level inspection alone as sufficient proof for D-14's adoption bar.

2. **What exactly did the pre-resequence 81-08/81-09 plans contain, and is their loss material to the "original nine" comparison?**
   - What we know: they existed (Phase 81 had nine original plans per CONTEXT.md D-08's own framing), were overwritten in place by gap-closure content on 2026-10-19 22:34:01, and are absent from git and from the current filesystem.
   - What's unclear: whether Time Machine (once accessible) actually retained a pre-22:34:01 snapshot of that day, or whether the backup cadence missed that narrow window entirely.
   - Recommendation: attempt Time Machine recovery for just these two files once Full Disk Access is resolved; if genuinely unrecoverable, record per D-10 that the true 7-of-9 comparison is the best available (stronger evidence than a fully reconstructed 9-of-9 benchmark) and consider whether a 7-plan comparison still meaningfully exercises D-12's adoption bar, or whether it needs explicit reduced-scope framing in the final report.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Claude Code CLI | Hook pilot, matched runs | ✓ | 2.1.281 installed / 2.1.310 latest on npm | D-02's owner-approved update path if a later-version-only feature turns out to be needed |
| model-gateway plugin | Gateway routing, request logs | ✓ (installed, not started/stopped in this session) | 0.51.2 | — |
| Codex CLI | Unrelated to PLANCHK directly (used by the separate Phase 83 Codex-review contract); present for reference | ✓ | 0.153.4 | — |
| BM plugin | Checker invocation mechanics | ✓ | 5.0.3 | — |
| Time Machine (MaguffyNAS network destination) | D-08 original-plan recovery (81-08/81-09 gap specifically) | **✗ — destination configured and mounted, but unreadable** (`tmutil`/`ls` both fail with Full Disk Access / Operation-not-permitted errors) | — | Owner must either grant Full Disk Access to the tool that will browse the backup, or personally run the listing/copy and hand off recovered files; until resolved, record 81-08/81-09 originals as unavailable per D-10 and proceed with the 7-of-9 mtime-verified set |
| Full Disk Access (macOS TCC) for this execution context | Any `tmutil` or direct Time Machine volume browsing | ✗ | — | See above |

**Missing dependencies with no fallback:**
- Full Disk Access / Time Machine volume read access — genuinely blocks any read of backup contents from this environment; the fallback listed above (owner grants access or performs the read personally) is an owner action, not a technical substitute.

**Missing dependencies with fallback:**
- None of the others qualify as missing — all core CLIs needed for the hook pilot and matched-run harness are already installed and version-confirmed.

## Validation Architecture

`workflow.nyquist_validation` is absent from `.planning/config.json` → treated as enabled per the standing rule. This phase has no Triggarr application code, so "tests" here are evidence-record checks (file/field existence, hash/log correlation), not pytest assertions against product code.

**TDD-eligibility note (config has `workflow.tdd_mode: true`):** No task in this phase touches Triggarr's own source tree, so no task is TDD-eligible under the project's normal meaning (a failing `pytest` test written before the fix). If the planner chooses to commit a reusable matched-run harness script *inside* this repository (e.g., under `scripts/` or `tests/`, rather than keeping it entirely in the external scratch directory per D-06), that script becomes ordinary Triggarr-repo Python and should then follow the project's TDD/ruff conventions like any other new script — this is a discretionary decision point for the plan, not something this research resolves.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None applicable to this phase's own deliverables (evidence records + external scratch pilot); Triggarr's existing `pytest`/`uv run pytest tests/ -x -q` is unaffected and untouched |
| Config file | N/A |
| Quick run command | N/A (see per-requirement evidence checks below) |
| Full suite command | N/A |

### Phase Requirements → Evidence Map
| Req ID | Behavior | Evidence Type | Check | Artifact Exists? |
|--------|----------|----------|-------------------|-------------|
| PLANCHK-01 | Runtime hook support verified and recorded, with a positive or explicit-negative result, never assumed | Evidence record (this RESEARCH.md + a future pilot log) | `grep -q "agent.spawn" <evidence-file>` and the record states one of {verified-present, verified-absent, update-required} explicitly, with the binary/doc citations this research already gathered | ✅ (this document); pilot-time live confirmation — Wave 0 gap below |
| PLANCHK-02 | Scratch pilot routes only the checker, proves routing from gateway metadata, exercises required checks, fails closed | Evidence record (JSONL correlation + pilot transcript) | `jq 'select(.agentId == $aid and .backend == "codex")' request-routes.jsonl` returns ≥1 line; a deliberately-broken-gateway negative run records an explicit incomplete/error status, not a silent pass | ❌ — pilot not yet run (Wave 0 gap) |
| PLANCHK-03 | Blind comparison runs on recovered/hashed originals, or is recorded unavailable with reasons | Evidence record (hash manifest + adjudicator transcript, or an explicit "unavailable" statement) | `sha256sum` manifest exists and matches the files used; OR an explicit "comparison unavailable, reason: X" statement is present — either satisfies the requirement, a silent gap does not | ❌ — recovery/hashing partially done in this research (7-of-9 candidate hashes above); full manifest + Time Machine resolution still pending (Wave 0 gap) |

### Sampling Rate
- **Per investigation step:** record evidence immediately (hash, log line, or explicit unavailable-statement) before moving to the next step — do not batch evidence collection to the end.
- **Phase gate:** before `/bm:verify-work`, confirm every one of the four ROADMAP success criteria has either a positive evidence record or an explicit deferred/unavailable statement with a reason (criterion 4's own requirement).

### Wave 0 Gaps
- [ ] Register and validate the scratch-pilot `agent.spawn` hook (`claude plugin validate`) — no automated check exists yet because the hook itself doesn't exist yet; this is the pilot's first concrete task.
- [ ] A small harness script (or documented manual procedure) to run a `claude -p` session against the scratch project, capture `--output-format json`, and correlate the resulting `agentId` against `request-routes.jsonl` — reuse the pattern in `tests/codex_review_run.py` rather than designing from scratch.
- [ ] Resolve Full Disk Access (owner action) before attempting the Time Machine side of D-08.
- [ ] Decide and record (per D-09) the exact cutoff timestamp the plan will use, citing the specific commit/session evidence from this research rather than re-deriving it.

## Project Constraints (from CLAUDE.md)

**From `/Users/julianamacbook/triggarr/CLAUDE.md` (project, checked in):**
- Python 3.11+, ruff (`E,F,I,UP,B,SIM`), line length 120, `SecretStr` discipline, Loguru-only logging through the redacting sink, atomic write-then-rename, `pytest-asyncio` auto mode — **applies only if** the planner chooses to commit a harness script inside the Triggarr repo (see Validation Architecture's TDD note); does not apply to anything kept in the external scratch directory per D-06.
- `/deep-review` offer before pushing to main or tagging a release — not triggered by this phase (D-16: no push, no PR).
- Review-classification/Codex-pairing workflow (REVIEW-01..08, the paired-review blueprint) — explicitly distinct from this phase's PLANCHK investigation per CONTEXT.md's canonical refs ("do not conflate"); `/bm:review --codex` and the codex-adversarial-review-contract.md pattern are a *different* Codex integration (post-implementation code review) from what this phase investigates (plan-checker model routing). Do not merge the two in planning.
- One-PR-per-phase, no docs-only PRs — consistent with D-16 (no PR at all for this phase's own records).
- Planning file format (`docs/PLANNING-FORMAT.md`) — applies to any STATE.md/ROADMAP.md edits this phase's execution makes.

**From the user's global `~/.claude/CLAUDE.md`:**
- Security (absolute): never log sensitive data, never hardcode secrets — directly relevant to this phase's hard constraints (never print the model-gateway control-token, Codex `auth.json`, or any secret config key; this research read only non-secret fields and code, consistent with this rule).
- Resource cleanup on every path (context managers, `try/finally`) — relevant if a harness script is written (e.g., the Codex contract's own worktree-cleanup pattern, which already models this correctly).
- "My approval is not code review" / "Technical decisions are yours to own" — relevant to how the plan should present the hook-vs-fallback decision and the adoption criteria results to the owner: frame tradeoffs in user-impact/risk/time terms, not as a request to adjudicate implementation details.

## Sources

### Primary (HIGH confidence)
- Installed Claude Code 2.1.281 binary (`~/.local/share/claude/versions/2.1.281`) — direct `strings` inspection of the `agent.spawn` event implementation, field-pinning logic, and logging.
- https://code.claude.com/docs/en/plugins/mods/reference (fetched this session) — mods event table, `agent.spawn`/`agent.offer` contract, limits, file layout.
- https://code.claude.com/docs/en/sub-agents#choose-a-model (fetched this session) — model resolution precedence, hook-override behavior, resume semantics.
- https://code.claude.com/docs/en/hooks (fetched this session) — confirms mods events are documented elsewhere; classic-hook permission/resume semantics for contrast.
- Installed BM 5.0.3 (`~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/`): `workflows/plan-phase.md` (checker invocation, revision loop, bounce), `agents/bm-plan-checker.md`, `sdk/src/query/config-query.ts`, `sdk/src/model-catalog.ts`, `sdk/shared/model-catalog.json`, `sdk/src/query/config-schema.ts`, `references/model-profiles.md`, `references/model-profile-resolution.md`.
- Installed model-gateway 0.51.2 (`~/.claude/plugins/cache/eigenwise-toolshed/model-gateway/0.51.2/`): `skills/model-gateway/SKILL.md`, `lib/runtime.js`, `lib/request-worker.js`.
- This repository's own `git log`/`git ls-files`/`git show` output (direct inspection) for Phase 81 provenance and timestamp triangulation.
- `docs/codex-adversarial-review-contract.md` (local) — reusable timeout/evidence pattern.
- `.planning/config.json`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (local).

### Secondary (MEDIUM confidence)
- `npm view @anthropic-ai/claude-code version`/`versions --json` — confirms latest published version only (2.1.310), not functional claims. [VERIFIED: npm registry]
- Filesystem `mtime` evidence for untracked Phase-81 files — internally consistent but not cryptographically provable.
- Codex CLI session filename/mtime (`~/.codex/sessions/2026/10/20/rollout-2026-10-20T20-19-46-...jsonl`) and Claude session transcript mtime — corroborating, not confirmed by content.

### Tertiary (LOW confidence)
- None relied upon — all claims in this document trace to a primary or secondary source above.

## Metadata

**Confidence breakdown:**
- `agent.spawn` hook mechanics / BM invocation semantics / model-gateway routing & enum-refusal: HIGH — cross-verified across installed binary, installed plugin source, and current official docs, all agreeing.
- Phase-81 git-recoverability: HIGH (direct repository inspection, deterministic).
- Phase-81 filesystem-mtime "likely original" claim: MEDIUM (consistent but not cryptographic).
- Time Machine snapshot availability for the Oct 10–19 window: UNKNOWN/BLOCKED — the destination exists but its contents could not be enumerated in this session at all.

**Research date:** 2026-10-23
**Valid until:** Short shelf life recommended — 7 days for the live model-gateway catalog (D-04 already requires a recheck) and the npm-latest Claude Code version; the hook-mechanics findings (binary-level) are stable until the installed Claude Code version changes.
