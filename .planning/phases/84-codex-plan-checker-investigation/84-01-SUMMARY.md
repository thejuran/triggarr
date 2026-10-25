---
phase: 84-codex-plan-checker-investigation
plan: "01"
subsystem: investigation
tags: [claude-code, mods, agent-spawn, model-gateway, codex, bm-plan-checker, gpt-6-astra]

# Dependency graph
requires: []
provides:
  - "Isolation baseline (sha256 of Triggarr/global settings + plugin list) for Phase 84 closeout to prove nothing was activated in Triggarr"
  - "Live, evidence-backed verdict for PLANCHK-01: the installed Claude Code 2.1.281 runtime's agent.spawn hook can route only bm:bm-plan-checker to a model-gateway Codex model, proven from gateway request-log metadata and a clean before/after control"
  - "Discovery that an installed/sideloaded mod's hooks module requires the undocumented, early-access CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 environment flag to load at all on 2.1.281"
  - "Scratch pilot plugin (planchk-router) and a synthetic toy GSD project fixture at ~/scratch/planchk-pilot, outside the repo, for Plan 02 onward to reuse"
  - "Route decision for Plan 02: hook (the fallback custom-agent-frontmatter route, D-03, is not needed)"
affects: [84-02, 84-03, 84-04, 84-05, 84-06, 84-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "agent.spawn mods hook scoped to one exact subagent_type via the subagentType matcher, rewriting only the model field"
    - "process-group-kill subprocess timeout (reused from tests/codex_review_run.py) to bound a claude -p smoke run to 900s"

key-files:
  created:
    - .planning/phases/84-codex-plan-checker-investigation/84-ISOLATION-BASELINE.txt (local only, git-excluded, never committed per D-16)
    - .planning/phases/84-codex-plan-checker-investigation/84-RUNTIME-VERDICT.md (local only, git-excluded, never committed per D-16)
    - /Users/julianamacbook/scratch/planchk-pilot/plugins/planchk-router/.claude-plugin/plugin.json
    - /Users/julianamacbook/scratch/planchk-pilot/plugins/planchk-router/hooks/hooks.json
    - /Users/julianamacbook/scratch/planchk-pilot/plugins/planchk-router/hooks/register.js
    - /Users/julianamacbook/scratch/planchk-pilot/toy/ (synthetic one-phase GSD project fixture, own throwaway git repo)
    - /Users/julianamacbook/scratch/planchk-pilot/runs/smoke/ (driver prompt, run_smoke.py harness, two full attempt transcripts, route-log extracts, comparison notes)
  modified: []

key-decisions:
  - "Routed model: claude-gpt-6-astra[1m] (newest Codex row in the live catalog; serving claude-code-proxy 0.1.40 >= the 0.1.36 floor for Astra; doctor shows it measured, not unmeasured)"
  - "agent.spawn hooks require CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 for installed/sideloaded plugins on Claude Code 2.1.281 -- undocumented on the two fetched docs pages, discovered via claude --debug hooks; this flag must be carried into any later use of this route"
  - "Route for Plan 02: hook (D-03 fallback not built)"
  - "D-02 update gate not triggered -- installed runtime verified-present, no global Claude Code update proposed or applied"

requirements-completed: [PLANCHK-01]

duration: 23min
completed: 2026-10-25
---

# Phase 84 Plan 01: Runtime Verification & Live Routing Proof Summary

**Live-proved the `agent.spawn` hook routes only `bm:bm-plan-checker` to Codex's `gpt-6-astra` via model-gateway on the installed Claude Code 2.1.281 -- gated behind an undocumented early-access flag the binary/docs evidence alone did not reveal.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-10-25T15:46:57Z
- **Completed:** 2026-10-25T16:09:42Z
- **Tasks:** 3 (Task 1 auto, Task 2 auto, Task 3 checkpoint:decision -- skip condition met, not presented)
- **Files modified:** 0 tracked Triggarr files (all deliverables are git-excluded evidence records or scratch-pilot files outside the repo, per D-16/D-06); 1 new tracked file (this SUMMARY.md)

## Accomplishments
- Recorded a byte-level isolation baseline (sha256 of 6 settings/config files + plugin list + a "no matches" planchk grep) before building anything, and re-verified all 6 hashes unchanged and the grep still empty after the pilot ran.
- Re-verified (not copied) the `agent.spawn` hook's binary-level contract on the installed 2.1.281 CLI: the pinned-identity field set (`tool_use_id`, `permissionMode`, `parentAgentId`, `parentModel`, etc.) a hook cannot rewrite, and the one check on a hook-returned `model` (non-empty string, no enum) -- plus fetched docs confirming the model-precedence and `SendMessage`-resume-exemption contract, and confirmed from BM 5.0.3's own `plan-phase.md` that the checker is never resumed (resume exemption is N/A, not a tested pass).
- Chose the routed model live from `model-gateway doctor` (serving proxy 0.1.40, Astra measured) rather than trusting catalog presence alone: `claude-gpt-6-astra[1m]`.
- Built the scratch-only `planchk-router` mods plugin (one `agent.spawn` hook, matched to exactly `bm:bm-plan-checker`, changing only `model`) and a synthetic toy GSD project fixture, entirely outside the repo.
- Ran a real BM step-10 checker invocation twice against the toy fixture: once without, once with the hook's dependency satisfied, producing a clean before/after control that isolates the one variable (the missing `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` flag) that made the hook's model rewrite take effect.
- Proved the routing from gateway metadata (`request-routes.jsonl`): the checker's 15 calls all showed `backend: codex, model: gpt-6-astra, effort: xhigh`, cleanly bracketed by the main session's own `backend: anthropic, model: claude-opus-5-5` calls before and after, corroborated independently by Claude Code's own stderr diagnostic naming `agent:custom:bm:bm-plan-checker` next to the routed model.
- Recorded the Verdict (`verified-present`) and Route (`hook`) in `84-RUNTIME-VERDICT.md`, and evaluated Task 3's D-02 skip condition: met, so the update-gate checkpoint was not presented to the owner -- `D-02 update gate: not triggered` was appended and the plan finished without a global Claude Code update.

## Task Commits

No task-level code commits in Triggarr: every file this plan's Tasks 1-3 create or modify is either a git-excluded phase-dir evidence record (`84-ISOLATION-BASELINE.txt`, `84-RUNTIME-VERDICT.md`, never committed per D-16) or lives entirely outside the repo under `~/scratch/planchk-pilot/` (D-06). Only this SUMMARY.md is committed, force-added per the plan's own `<output>` instruction.

**Plan metadata:** (hash recorded after this commit below)

## Files Created/Modified
- `.planning/phases/84-codex-plan-checker-investigation/84-ISOLATION-BASELINE.txt` — pre-pilot sha256 baseline of 6 settings/config files + plugin list + planchk-grep result (local only, never committed)
- `.planning/phases/84-codex-plan-checker-investigation/84-RUNTIME-VERDICT.md` — full PLANCHK-01 evidence record: installed versions, binary/docs evidence, live proof (both attempts), Verdict, Route, D-02 gate outcome (local only, never committed)
- `/Users/julianamacbook/scratch/planchk-pilot/plugins/planchk-router/` — the scratch-only `agent.spawn` hook plugin
- `/Users/julianamacbook/scratch/planchk-pilot/toy/` — synthetic one-phase GSD project fixture (own git repo)
- `/Users/julianamacbook/scratch/planchk-pilot/runs/smoke/` — driver prompt, timeout-bounded runner, two full `claude -p` transcripts, route-log extracts, plugin-validate output, comparison notes
- `.planning/phases/84-codex-plan-checker-investigation/84-01-SUMMARY.md` — this file (only file this plan commits)

## Decisions Made
- Routed model chosen live (`claude-gpt-6-astra[1m]`) per D-04, not from catalog presence alone — confirmed via the serving proxy version and `doctor`'s measured/unmeasured distinction.
- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is required for an installed/sideloaded mod's hooks module to load at all on 2.1.281; this is now a hard prerequisite for Plan 02 onward and for any eventual Triggarr activation, carried forward explicitly rather than assumed.
- Route for Plan 02: hook. The D-03 fallback (custom-agent-frontmatter) is not built, since the hook route is proven live.
- D-02 update gate: not triggered — the installed runtime is verified-present, so no global Claude Code version change was proposed or applied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `--permission-mode default` is not a valid value on the installed CLI**
- **Found during:** Task 2, Step C (live smoke run flag assembly)
- **Issue:** The plan's action text specifies `--permission-mode default`; the installed CLI's actual enum is `acceptEdits | auto | bypassPermissions | manual | dontAsk | plan` — no `default` value exists, so the literal flag would fail at CLI startup.
- **Fix:** Used `--permission-mode bypassPermissions` for the scratch `claude -p` sessions only (an isolated, read-only-against-a-toy-fixture pilot in `~/scratch/planchk-pilot/`, never touching Triggarr). This lets the one-shot, non-interactive run actually execute the Read/Bash/Agent tool calls it needs without hanging on an unanswerable permission prompt.
- **Cost if wrong:** If this were the wrong permission posture for a real (non-pilot) run, a hook or subagent could write/execute unexpectedly; here the blast radius is the disposable toy fixture and the pilot's own scratch directory only, and the pinned-identity contract (Task 1 binary evidence) still prevents the hook itself from touching `permissionMode`.
- **Files modified:** none (flag choice only, inside `runs/smoke/run_smoke.py`, which itself is scratch-only).
- **Commit:** N/A (scratch file, not committed).

**2. [Rule 3 - Blocking] Installed mod hooks silently did not load on attempt 1**
- **Found during:** Task 2, Step C (first live smoke run)
- **Issue:** The hook never fired; the checker ran on the literal, unrewritten `model="sonnet"` argument. `claude --debug hooks` revealed the root cause: an early-access flag, `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, gates whether an installed/sideloaded mod's hooks module loads at all on 2.1.281 — undocumented on either docs page fetched in Task 1, and not caught by `claude plugin validate` (which only checks the manifest/matcher statically).
- **Fix:** Set `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` in the `claude -p` subprocess's own environment for attempt 2 only (never in any Triggarr or global settings file). Attempt 2 then routed cleanly.
- **Cost if wrong:** If this flag were mistakenly treated as unnecessary going forward, Plan 02 onward would silently repeat attempt 1's failure mode (hook loaded, matcher correct, but never actually executes) and could misreport the route as broken when it is simply unconfigured.
- **Files modified:** `/Users/julianamacbook/scratch/planchk-pilot/runs/smoke/run_smoke.py` (scratch only, not committed).
- **Commit:** N/A (scratch file, not committed).

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues preventing the live-proof task from completing). Neither touches Triggarr, both are scoped to the scratch pilot, and the second is the central, load-bearing finding of this plan rather than a minor correction.
**Impact on plan:** Both auto-fixes were necessary to get an honest live result at all; without them, the pilot would have incorrectly concluded the hook was non-functional.

## Assumption Drift (advisory)

**1. `agentId`-based gateway-log correlation was assumed usable; it was not observable at all in this gateway version/path.**
- **Found during:** Task 2, Step D (verdict write-up)
- **Planned:** `84-RESEARCH.md`'s "Code Examples" and Task 2's own `<acceptance_criteria>` describe correlating the checker's gateway-route lines by matching `agentId` (`jq -c --arg aid "<agent_id>" 'select(.agentId == $aid)'`), with the stated rule "a model label alone is not proof."
- **Actual:** Every line `request-routes.jsonl` wrote in both attempts carried `agentId: null` — for the main session's own calls *and* for the checker's codex-backed calls alike. The literal plan acceptance check (`select(.agentId!=null) | .backend` == "codex", `select(.agentId==null) | .backend` == "anthropic") does not hold in this environment, because `agentId` never gets set on either side of that partition here.
- **Why:** likely a gateway-version/config-specific gap in whether `x-claude-code-agent-id` is forwarded/logged for this dispatch path; not investigated further since it was out of this task's scope to debug model-gateway internals.
- **Cost if wrong:** If a later plan assumes `agentId` correlation is available and gates on it strictly, it will wrongly read every run (including a correctly-routed one) as unproven. The substitute evidence used here — session-id scoping, an otherwise-exclusive model/backend partition, tight time-bracketing against the subagent's own lifecycle timestamps, and an independent `stderr` diagnostic line naming the exact subagent identity next to the routed model — is solid but is a different correlation mechanism than the plan assumed, and should be carried forward explicitly in Plan 02's matched-run harness rather than re-discovered.

## Issues Encountered
None beyond the two auto-fixed deviations above, both resolved within this plan.

## User Setup Required

None — no external service configuration required. (If this route is ever proposed for real activation in Triggarr, that is a separate, later owner approval per the phase's activation boundary; this plan does not request it.)

## Next Phase Readiness
- Plan 02 can proceed on the `hook` route with the scratch plugin and toy fixture already built, and should carry `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` forward explicitly in its own harness.
- The isolation baseline is in place for Phase 84's eventual closeout check (re-hash the same 6 files + re-run the planchk grep).
- No blockers for Plan 02. The open Time Machine / Full Disk Access gap (PLANCHK-03, Plan 03) is unrelated to this plan's scope.

---
*Phase: 84-codex-plan-checker-investigation*
*Completed: 2026-10-25*
