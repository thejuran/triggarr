# planchk-router

Triggarr-only Claude Code plugin. Routes a `bm:bm-plan-checker` subagent spawn to a
model-gateway Codex model, so the plan checker runs on Codex while the orchestrating
session stays on Anthropic. Every other subagent type, and every other project, is
unaffected.

## How it works

- `hooks/register.js` is an `agent.spawn` module hook that rewrites only the `model`
  field on a `bm:bm-plan-checker` spawn. It has no `try`/`catch` around the rewrite:
  an unavailable model, unreachable gateway, timeout, or incomplete output must
  surface as a visible error, never a silent fallback to a Claude model.
- `hooks/guard.mjs` is a classic `PreToolUse` hook (matcher `Agent|Task`) that blocks
  (exit 2) a `bm:bm-plan-checker` spawn whenever the module-hook gate is off. Classic
  hooks load even when the modules gate does not, so this closes the gap where the
  plugin is installed but the rewrite silently never runs.

## The switch (where activation actually lives)

The plugin source here is committed and reviewable, but it does nothing by itself.
Two things turn it on, and both live ONLY in this machine's gitignored
`.claude/settings.local.json` — never in the shared `.claude/settings.json`:

1. The plugin is registered at `--scope local` (writes `extraKnownMarketplaces` +
   `enabledPlugins` into `settings.local.json`).
2. `"env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}` is merged into the same file
   (early-access gate for the hooks module system).

Clones of the public repo are unaffected: without both of the above, the plugin is
present but inert.

## Re-enable on a new machine

Do not copy `.claude/settings.local.json` between machines — it holds an absolute
path to this plugin. Back up the existing file first, then from the Triggarr repo
root:

```bash
claude plugin marketplace add ./.claude/plugins --scope local
claude plugin install planchk-router@triggarr-local --scope local
```

Then merge (do not overwrite) `"env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}`
into `.claude/settings.local.json`. Never omit `--scope local` — omitting it writes
the user-global settings file instead of this project's local one.

Confirm the module loaded:

```bash
claude --debug hooks -p "Reply OK"
```

...then grep the newest `~/.claude/debug/<session-id>.txt` for
`hooks module planchk-router@triggarr-local loaded`. Re-run this check after every
Claude Code update — the hooks-module gate is a server-side rollout flag plus this
env override, and either side of that could change.

That load-line check only proves `register.js` (the module hook) still loads — it
says nothing about whether `guard.mjs` (the classic hook) still blocks when the
module gate is off. Re-run the negative (fail-closed) check too, after every update,
without editing `.claude/settings.local.json`. From the Triggarr root, force the flag
off for one disposable session with a command-line settings override (command-line
settings take precedence over `settings.local.json`; verified live 2026-10-26), so the
real local registration is what gets tested:

```bash
cd /path/to/triggarr
claude --debug hooks --settings '{"env":{"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS":"0"}}' \
  -p "<prompt that spawns a bm:bm-plan-checker agent>"
```

The `--debug hooks` log for that session should say hooks modules are not turned on
(the router did not load). Alternative, outside Triggarr: from a throwaway directory
with no `.claude/` of its own, sideload the plugin directory itself (not its
marketplace parent) with the flag unset:

```bash
cd /path/to/some/throwaway/dir
env -u CLAUDE_CODE_ENABLE_FUNCTION_HOOKS claude --plugin-dir /path/to/triggarr/.claude/plugins/planchk-router \
  -p "<prompt that spawns a bm:bm-plan-checker agent>"
```

Confirm the spawn is refused: the session output (the Agent call's hook error) or
the `--debug hooks` log contains `planchk-router: refusing bm:bm-plan-checker spawn`,
and no checker model appears in the session's model usage. The `claude -p` process
itself still exits 0; the refusal is reported inside the session, not as an exit code. If that message does not appear, the guard has stopped firing
and the plugin can no longer fail closed — stop and investigate before relying on it
again.

## Disable / remove

- Disable the plugin — `claude plugin disable planchk-router@triggarr-local --scope
  local`. This turns OFF both `register.js` and `guard.mjs`: nothing intercepts the
  spawn anymore, so `bm:bm-plan-checker` runs unrouted on the ordinary Claude model
  it would always use. This is the deliberate "off switch" (opt out of Codex
  routing), not a fail-closed state — it does not block anything.
- Remove or revert ONLY the `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` env key while the
  plugin stays enabled — this is different from disabling the plugin. `register.js`
  stops loading (module hooks need the flag), but `guard.mjs` is a classic hook and
  still loads regardless, so it still fires and blocks (exit 2) every
  `bm:bm-plan-checker` spawn with a visible refusal instead of letting it run
  unrouted. This is the actual fail-closed path.
- Full removal (also uninstalls): `claude plugin marketplace remove triggarr-local`.

## After a real checker run

On a failed or incomplete Codex-routed checker run, BM's plan-checker flow offers
Accept / Retry / Stop. Do NOT pick "Accept verification" for a Codex-routed
failure — that treats an unchecked plan as passed.

After a real (non-failed) run, confirm the routing actually happened: grep
`~/.claude/model-gateway/logs/request-routes.jsonl` for that session's codex lines.
This is a residual control for the case where the plugin loads but the rewrite
itself silently fails for some other reason.

## Known limitations (carried forward, unresolved)

- The full BM review loop is only partially validated: routing and the post-bounce
  recheck are proven, but a full revision/recheck cycle was never exercised.
- A 15-minute (900s) timeout was seen on a large, real-world-sized input — the
  Codex route's completeness under large inputs is not proven, only its correctness
  and fail-closed behavior when it does complete.
- Effort equivalence between the ordinary and Codex-routed checker is unknown —
  requesting maximum effort does not establish comparable computational effort
  between the two systems.
- The model-gateway proxy's own billing/API-key internals are unverified, not ruled
  out, though its behavior is consistent with subscription-only billing.
- The guard matches on the PreToolUse tool names `Agent`/`Task` and the
  `tool_input.subagent_type` field (RESEARCH.md Assumptions Log, A2 — verified only
  on the Claude Code version active at activation time). If a future Claude Code
  update renames either the tool or the field at the same time it changes the
  hooks-module gate, the guard would silently `exit(0)` on every spawn and
  `bm:bm-plan-checker` would run unrouted on a Claude model with no visible error —
  which is exactly why the negative recheck above has to be re-run after every
  update, not just the module-loaded line.
