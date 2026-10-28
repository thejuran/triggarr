# Quick Task 261026-s2v: Activate the Codex-routed plan checker for Triggarr only - Context

**Gathered:** 2026-10-26
**Status:** Ready for planning

<domain>
## Task Boundary

Activate the Phase 84 Codex-routed plan checker for Triggarr only: a narrowly scoped
`agent.spawn` hook that rewrites only `bm:bm-plan-checker`'s model to a model-gateway Codex
model, plus the early-access `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` environment flag, with
fail-closed behavior. Source of truth: `.planning/phases/84-codex-plan-checker-investigation/84-CLOSEOUT.md`
§ "Activation boundary" → "What the activation change will need to carry over".

</domain>

<decisions>
## Implementation Decisions

### Locked by the owner in Phase 84 (84-CLOSEOUT.md, 2026-10-26)
- Scope: Triggarr only. Other projects keep the ordinary BM checker.
- On failure: stop and report. An unavailable or incomplete checker run stays visibly
  incomplete with its error; the owner decides whether to retry or fall back; never a silent
  switch to a Claude model (preserve 84-PILOT-EVIDENCE.md N1-N4 behavior exactly).
- Review: BM code review plus the paired read-only Codex pass (Phase 83 policy).

### Placement (owner, 2026-10-26)
- Hook plugin source is COMMITTED in the repo, so it gets a reviewable diff.
- The switch that turns it on (plugin enablement and `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`)
  lives ONLY in the owner's gitignored `.claude/settings.local.json` (gitignored via the global
  git ignore), NOT in the shared `.claude/settings.json`. Clones of the public repo must be
  unaffected.
- Document how to re-enable on a new machine (short note next to the plugin).

### Live proof (owner, 2026-10-26)
- End with ONE live smoke run: a real `bm:bm-plan-checker` spawn on a small throwaway plan,
  using the persistent activation itself (not a `--plugin-dir` sideload). Confirm via gateway
  route log that the checker went to the Codex backend and the orchestrating session stayed on
  Anthropic. Bounded at 900s. The throwaway fixture lives outside the repo (scratch), not in Triggarr.

### Claude's Discretion
- Drop the pilot-only per-spawn `PLANCHK_SPAWN_LOG` logging unless a minimal signal is needed.
- Re-check the routed model id (`claude-gpt-6-astra[1m]`) against the live gateway catalog at
  activation time; if the strongest Codex model changed, stop and report rather than silently
  picking a different one.
- Exact mechanism for project-scoped plugin registration (local marketplace + enabledPlugins,
  or equivalent) and whether settings `env` is honored for the hooks-module gate: research.

</decisions>

<specifics>
## Specific Ideas

- Scratch reference plugin: `~/scratch/planchk-pilot/plugins/planchk-router/` (adapt, don't copy).
- Pilot loaded it via `--plugin-dir`; persistent activation needs a settings-based route.
- The gateway was reported as not starting at session start (EADDRINUSE on 127.0.0.1:18764) -
  check `model-gateway doctor` before the smoke run.

</specifics>

<canonical_refs>
## Canonical References

- .planning/phases/84-codex-plan-checker-investigation/84-CLOSEOUT.md (Activation boundary)
- .planning/phases/84-codex-plan-checker-investigation/84-RUNTIME-VERDICT.md
- .planning/phases/84-codex-plan-checker-investigation/84-PILOT-EVIDENCE.md (N1-N4 fail-closed)
- docs/review-classification-policy.md, docs/codex-adversarial-review-contract.md

</canonical_refs>
