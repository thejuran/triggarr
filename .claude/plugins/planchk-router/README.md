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

## Disable / remove

- Disable (guard then blocks every `bm:bm-plan-checker` spawn instead of letting it
  run unrouted): `claude plugin disable planchk-router@triggarr-local --scope local`.
  Removing only the `env` key has the same effect — the guard fails closed.
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
