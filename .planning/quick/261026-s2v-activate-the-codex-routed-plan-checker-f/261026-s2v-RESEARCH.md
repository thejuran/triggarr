# Quick Task 261026-s2v: Activate the Codex-routed plan checker (Triggarr only) - Research

**Researched:** 2026-10-26 (all commands run this session on Claude Code 2.1.281; experiments in `~/scratch/planchk-activation/` with isolated `CLAUDE_CONFIG_DIR`s; Triggarr repo and `~/.claude/settings.json` untouched; sha256 of `~/.claude/settings.json`, `~/.claude/plugins/known_marketplaces.json`, `~/.claude/plugins/installed_plugins.json` re-checked OK after all experiments)
**Domain:** Claude Code plugin registration, settings scopes, hooks-module gate, model-gateway
**Confidence:** HIGH (every core claim reproduced live)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Scope: Triggarr only. Other projects keep the ordinary BM checker.
- On failure: stop and report. An unavailable or incomplete checker run stays visibly incomplete with its error; the owner decides whether to retry or fall back; never a silent switch to a Claude model (preserve 84-PILOT-EVIDENCE.md N1-N4 behavior exactly).
- Review: BM code review plus the paired read-only Codex pass (Phase 83 policy).
- Hook plugin source is COMMITTED in the repo, so it gets a reviewable diff.
- The switch that turns it on (plugin enablement and `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`) lives ONLY in the owner's gitignored `.claude/settings.local.json`, NOT in the shared `.claude/settings.json`. Clones of the public repo must be unaffected.
- Document how to re-enable on a new machine (short note next to the plugin).
- End with ONE live smoke run: a real `bm:bm-plan-checker` spawn on a small throwaway plan, using the persistent activation itself (not a `--plugin-dir` sideload). Confirm via gateway route log that the checker went to the Codex backend and the orchestrating session stayed on Anthropic. Bounded at 900s. The throwaway fixture lives outside the repo (scratch), not in Triggarr.

### Claude's Discretion
- Drop the pilot-only per-spawn `PLANCHK_SPAWN_LOG` logging unless a minimal signal is needed.
- Re-check the routed model id (`claude-gpt-6-astra[1m]`) against the live gateway catalog at activation time; if the strongest Codex model changed, stop and report.
- Exact mechanism for project-scoped plugin registration and whether settings `env` is honored for the hooks-module gate: research (answered below).

### Deferred Ideas (OUT OF SCOPE)
- None listed.
</user_constraints>

## Summary

1. **Registration:** use a directory-type local marketplace committed in the repo, registered with `claude plugin marketplace add <dir> --scope local` + `claude plugin install planchk-router@<mkt> --scope local`. Both commands write ONLY `extraKnownMarketplaces` + `enabledPlugins` into `.claude/settings.local.json`; `.claude/settings.json` and `~/.claude/settings.json` are untouched. They DO also write two user-global *registry* files (`~/.claude/plugins/known_marketplaces.json`, `installed_plugins.json` with `scope: local, projectPath: <triggarr>`). Behavior stays Triggarr-only (plugin shows `Status: ✘ disabled` from another directory), but the marketplace name is listed globally. Hand-writing the settings keys alone does NOT work.
2. **Env gate:** `"env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}` in `settings.local.json` IS honored for the hooks-module gate (debug log: `hooks module planchk-router@triggarr-local loaded ... events: agent.spawn`). No shell/direnv fallback needed.
3. **Gateway:** healthy. The EADDRINUSE is benign: an already-running shim (PID 43955, serving 0.51.2) owns :18764 and the SessionStart `ensure` tried to start a second one. Nothing stopped/restarted. `claude-gpt-6-astra[1m]` still present, still the newest Codex row, evidence date 2026-09-05; catalog unchanged (21 models).
4. **Fail-closed gap found:** N1-N4 hold for the hook shape, but there is a fifth, untested case: if the hooks module does not load (flag missing, e.g. settings.local.json lost on a new machine, or a Claude Code update changes the gate), the checker silently runs on the BM-resolved Claude model. That violates "never a silent switch". A classic `PreToolUse` guard in the same plugin closes it (proven live, below).
5. **Smoke run:** must run with cwd = Triggarr root (activation is bound to that directory), fixture under scratch via absolute paths + `--add-dir`, no `--plugin-dir`, flag explicitly unset in the shell.

**Primary recommendation:** commit `.claude/plugins/` marketplace + `planchk-router` (module hook + PreToolUse guard + README), register at `--scope local`, add the env key to settings.local.json, smoke-run from Triggarr root.

## Finding 1: Persistent, Triggarr-only registration

Evidence (`CLAUDE_CONFIG_DIR=~/scratch/planchk-activation/cfg`, cwd = scratch git repo):

```
$ claude plugin marketplace add ./tools/claude-marketplace --scope local
✔ Successfully added marketplace: triggarr-local (declared in local settings)
$ claude plugin install planchk-router@triggarr-local --scope local
✔ Successfully installed plugin: planchk-router@triggarr-local (scope: local)
```
Resulting `.claude/settings.local.json` (complete content written):
```json
{"extraKnownMarketplaces": {"triggarr-local": {"source": {"source": "directory",
   "path": "/abs/path/to/tools/claude-marketplace"}}},
 "enabledPlugins": {"planchk-router@triggarr-local": true}}
```
Also written in the config dir: `plugins/known_marketplaces.json` (marketplace entry) and `plugins/installed_plugins.json` (`"scope": "local", "projectPath": "<project root>"`). In real use these are `~/.claude/plugins/*.json`: **user-global registry, not settings**. `claude plugin list` from another directory: `planchk-router@triggarr-local ... Status: ✘ disabled`; `claude plugin marketplace list` there still shows `triggarr-local`. [VERIFIED: live CLI]

- `--scope` defaults to `user` for both commands (`claude plugin marketplace add --help`: "user (default), project, or local"; install `-s` default "user"). **Always pass `--scope local`**; omitting it writes `~/.claude/settings.json`. [VERIFIED: --help]
- **Settings-only does not work:** fresh config dir + only the three keys hand-written in settings.local.json -> debug: `installPluginsForHeadless: no marketplaces declared` / `Plugin planchk-router@triggarr-local not found in any marketplace, skipping`. The CLI commands are required (this is also the new-machine re-enable recipe). [VERIFIED: live debug log]
- **Files read in place:** debug `Read hooks.json for plugin planchk-router (enabled=true): <source path>/hooks/hooks.json`; docs: directory marketplace with relative-path source "reads the plugin's files directly ... edits take effect at the next session start or `/reload-plugins`" [CITED: code.claude.com/docs/en/plugin-marketplaces]. Committed-source edits apply without reinstall/version bump (a cache dir is created but not used for the files).
- Existing in-repo pattern: `.claude/plugins/turingmind/` is already committed. Recommend `.claude/plugins/.claude-plugin/marketplace.json` (name e.g. `triggarr-local`, single entry `"source": "./planchk-router"`) + `.claude/plugins/planchk-router/`. Do not list turingmind. `.dockerignore`/Dockerfile only `COPY triggarr/ pyproject.toml CHANGELOG.md entrypoint.sh`, so nothing ships in the image. Run `claude plugin validate` on both the marketplace dir and plugin dir (passes; add `owner`, marketplace `description`, plugin `author` to silence warnings).
- Merge, don't overwrite: Triggarr's settings.local.json already holds `permissions` and `enabledMcpjsonServers` (model-gateway doctor also names it as its default write target). The CLI merges; add `env` with a JSON merge, never a rewrite.
- settings.local.json is ignored here via `~/.config/git/ignore:1:**/.claude/settings.local.json`; docs say Claude Code adds that line itself the first time *it* writes the file in a repo that doesn't ignore it, so the CLI path is safe on a new machine. [CITED: code.claude.com/docs/en/settings]
- Worktrees: docs say a worktree session uses the main checkout's local file, so BM executor worktrees under `.claude/worktrees/` inherit the activation. [CITED: code.claude.com/docs/en/settings]
- Backup first: `cp ~/.claude/plugins/{known_marketplaces,installed_plugins}.json` to `.bak-pre-planchk` (follows the existing `.bak-pre-*` pattern there).

Owner-visible tradeoff (minor): the marketplace *name* appears in the global registry; the *behavior* is Triggarr-only. No settings-file-based route avoids the registry write. Alternative with zero global writes is a shell alias (`--plugin-dir` + env); it is not settings-based and the owner ruled out sideloading for the smoke proof.

## Finding 2: settings.local.json `env` is honored by the hooks-module gate

| Run (same scratch project, isolated config, shell var unset) | Debug log line |
|---|---|
| No flag anywhere | `installed plugins' hooks modules not loaded: rollout flag (tengu_plugin_hooks_modules) is off ...` / `hooks module planchk-router@triggarr-local not loaded: ... (early access: set CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 in its environment to load them)` |
| `"env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}` in settings.local.json | `hooks module planchk-router@triggarr-local loaded (worker, environment 1, tier user); events: agent.spawn` |

[VERIFIED: `claude --debug hooks -p`, log at `$CLAUDE_CONFIG_DIR/debug/<sid>.txt`; debug output goes to that file, not to stderr]. The same env value also reached classic hook subprocesses (a SessionStart check `test "$CLAUDE_CODE_ENABLE_FUNCTION_HOOKS" = 1 || echo ...` stayed silent with settings env set, and printed its warning without it). No shell/direnv/wrapper fallback needed. Consistent with 84-PILOT-EVIDENCE N2: settings `env` wins over inherited process env.

Note: the gate is a server-side rollout flag (`tengu_plugin_hooks_modules`) plus this env override. A future Claude Code version could change either (auto-updater is disabled globally, so changes only arrive with a manual update). Re-run the `--debug hooks` check after any Claude Code update.

## Finding 3: Gateway status and routed model (re-checked live)

`node ~/.claude/model-gateway/model-gateway.js doctor` (abridged, quoted):
```
version: claude-code-proxy 0.1.40
codex auth: authenticated
proxy (claude-code-proxy) on :18765: answering /v1/models
shim (model router) on :18764: running (serving 0.51.2)
Codex readiness: ready
catalog: 21 models ... (writtenBy: 0.51.2)
gpt-6-astra | claude-gpt-6-astra[1m] | 920012 | ... | 2026-09-05
live shim model ids: PASS (match the installed policy)
lifecycle exit evidence: observed supervisor PID 8030; exit code 1; signal none
```
`guardian.log`: `shim supervisor cannot bind 127.0.0.1:18764: EADDRINUSE; PID 43955 owns 127.0.0.1:18764`. `lsof -iTCP:18764 -sTCP:LISTEN` -> `node 43955`. So the session-start failure was the SessionStart `ensure` trying to start a duplicate supervisor while the existing shim kept serving. **Nothing was stopped or restarted.** No action needed for this task (if the owner wants a clean log, `model-gateway.js stop && ensure` is the documented fix, but that briefly interrupts all sessions).

Codex rows are identical to 84-RUNTIME-VERDICT (gpt-5.2 ... gpt-6-astra/-fast); `gpt-6-astra` is still the newest-named row with a measured date. **No stop-and-report trigger.** `models` lists `"id": "claude-gpt-6-astra[1m]"`. Route log `~/.claude/model-gateway/logs/request-routes.jsonl` fields: `at, backend, model, path, sessionId` (+`effort` on codex lines); no `agentId` (same as Phase 84).

## Finding 4: Fail-closed

**Hook shape keeps N1-N4.** The module must be exactly `on('agent.spawn', { subagentType: 'bm:bm-plan-checker' }, async ($, e, next) => next({ ...e, model: 'claude-gpt-6-astra[1m]' }))`: no try/catch around `next`, no conditional model, no Claude id anywhere in the file. N1 (unknown model -> explicit HTTP 400), N2 (gateway down -> ECONNREFUSED), N3 (timeout) all come from the runtime/gateway, not from hook code, so they carry over unchanged. N4 (no structured header) is handled by BM itself: plan-phase.md step 11a fires on "neither `## VERIFICATION PASSED` nor `## ISSUES FOUND`" and offers the owner Accept / Retry / Stop. That is an owner choice, not a silent pass. But "Accept verification" treats a failed Codex run as PASSED, so the planner should tell the owner never to pick it for a Codex-routed failure. `PLANCHK_SPAWN_LOG` can be dropped; routing proof comes from the route log + `result.modelUsage`.

**Gap: hooks module not loaded = silent Claude fallback.** With the plugin enabled but the module gate off, Phase 84 attempt 1 already showed the checker running on `claude-sonnet-5[1m]` with no error. This activation adds new ways for that to happen: settings.local.json edited/lost, new machine, Claude Code update. **Recommended fix (technical decision): add a classic `PreToolUse` guard in the same plugin.** Classic hooks load even when the modules gate is off (debug: `Registered 1 hooks from 3 plugins` alongside `hooks module ... not loaded`). Proven live with the real config and the plugin sideloaded (sideload used only for this experiment):

- Flag unset -> Agent call blocked, orchestrator printed: `PreToolUse:Agent hook error: [...guard.mjs]: planchk-router: refusing bm:bm-plan-checker spawn - CLAUDE_CODE_ENABLE_FUNCTION_HOOKS is not 1, so the Codex route would silently not apply. Stop and report.`; `modelUsage` = `['claude-opus-5-5[1m]']` only (checker never ran).
- Flag set -> guard passed, checker replied `PONG`; `modelUsage` = `['claude-opus-5-5[1m]', 'claude-gpt-6-astra[1m]']`; route log for SID `e6575860-...`: 2x `backend:codex, model:gpt-6-astra, effort:xhigh`, then `backend:anthropic, model:claude-opus-5-5`.

Guard as tested (`hooks/hooks.json` = `{"modules":["./register.js"],"hooks":{"PreToolUse":[{"matcher":"Agent|Task","hooks":[{"type":"command","command":"node \"${CLAUDE_PLUGIN_ROOT}/hooks/guard.mjs\""}]}]}}`; `claude plugin validate` passes):
```js
// guard.mjs: exit 2 (block) only for bm:bm-plan-checker when the module gate env is off
let raw = '';
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  let input;
  try { input = JSON.parse(raw); } catch { process.exit(0); }
  const t = input && input.tool_input;
  if (!t || t.subagent_type !== 'bm:bm-plan-checker') process.exit(0);
  if (process.env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS === '1') process.exit(0);
  process.stderr.write('planchk-router: refusing bm:bm-plan-checker spawn - CLAUDE_CODE_ENABLE_FUNCTION_HOOKS is not 1 ... Stop and report.\n');
  process.exit(2);
});
```
Planner should decide whether unparseable stdin should block (exit 2) rather than pass; blocking is stricter. Limitation: the guard checks the env flag, not whether the module actually loaded. A module crash, or a future gate change that ignores the env var, would still fall back silently. Residual control: after each real checker run, confirm codex lines in the route log (see Finding 5); re-run the `--debug hooks` check after Claude Code updates. Nothing else in the hook needs changing.

## Finding 5: Smoke-run recipe (do not run during research)

The activation is bound to the Triggarr directory (settings.local.json + installed_plugins `projectPath`), so a session started in a scratch dir would NOT have it. The session must start in the Triggarr root and point at a scratch fixture by absolute path.

1. Fixture: `cp -R ~/scratch/planchk-pilot/toy ~/scratch/planchk-activation/smoke-toy` (never modify the pilot copy). Adapt the pilot driver (`~/scratch/planchk-pilot/runs/smoke/driver.txt`) into `~/scratch/planchk-activation/smoke-driver.txt`: replace every relative `.planning/...` path in both the read step and the `<files_to_read>` block with absolute `~/scratch/planchk-activation/smoke-toy/.planning/...` paths. Keep the exact single `Agent(subagent_type="bm:bm-plan-checker", model="sonnet", description="Verify Phase 1 plans", prompt=...)` call and the instruction to print the checker's result verbatim.
2. Pre-checks: `git -C ~/triggarr status --porcelain` (record); `model-gateway.js doctor` shows `Codex readiness: ready` and astra row; `cd ~/triggarr && env -u CLAUDE_CODE_ENABLE_FUNCTION_HOOKS claude --debug hooks -p "Reply OK"`, then grep `~/.claude/debug/<sid>.txt` for `hooks module planchk-router@triggarr-local loaded`.
3. Run (900s, process-group kill; reuse `~/scratch/planchk-pilot/runs/smoke/run_smoke.py`'s `start_new_session=True` + `os.killpg` pattern, copied into scratch-activation):
   `cd ~/triggarr && env -u CLAUDE_CODE_ENABLE_FUNCTION_HOOKS claude -p --session-id <uuid> --debug hooks --add-dir ~/scratch/planchk-activation/smoke-toy --permission-mode bypassPermissions --output-format stream-json --verbose < smoke-driver.txt`. No `--plugin-dir`, no `--settings`. Unsetting the flag in the shell proves the settings-based activation is what loaded it.
4. Pass criteria: result contains `## VERIFICATION PASSED` or `## ISSUES FOUND`; final `result.modelUsage` keys = main `claude-opus-5-5[1m]` + `claude-gpt-6-astra[1m]`, no `claude-sonnet-5`; `grep '"sessionId":"<uuid>"' ~/.claude/model-gateway/logs/request-routes.jsonl | jq -r '[.backend,.model]|@tsv' | sort | uniq -c` -> only `anthropic claude-opus-5-5` and `codex gpt-6-astra`, with the codex lines inside the subagent's start/end window from the stream; debug log has the `loaded` line; `git status --porcelain` unchanged afterwards.
5. Caveat: running from the Triggarr root means Triggarr's SessionStart hooks/CLAUDE.md load, and the checker may run read-only `bm-sdk` queries against Triggarr's `.planning/`. The driver must say not to read anything else. Classify any non-routing outcome as incomplete and report it; do not retry silently.

## Common Pitfalls
- **Forgetting `--scope local`** -> writes `~/.claude/settings.json` (forbidden). Verify `shasum` of it before/after.
- **Hand-writing settings keys only** -> plugin silently not found (Finding 1).
- **Overwriting settings.local.json** -> loses existing `permissions`/`enabledMcpjsonServers`.
- **Absolute marketplace path** in settings.local.json is machine-specific. Fine for a local file; the re-enable note must say to re-run the two CLI commands on a new machine, not copy the file.
- **Disable path:** `claude plugin disable planchk-router@triggarr-local --scope local` (or remove the env key; the guard then blocks checker spawns, so remove the plugin entirely to return to the ordinary checker). Full removal: `claude plugin marketplace remove triggarr-local` (also uninstalls).

## Environment Availability
| Dependency | Available | Version |
|---|---|---|
| Claude Code | yes | 2.1.281 (`~/.local/share/claude/versions/2.1.281`) |
| node (guard script) | yes | used live |
| model-gateway shim / proxy | yes, running | 0.51.2 / claude-code-proxy 0.1.40, Codex ready |
| No new packages installed | n/a | Package Legitimacy Audit: not applicable |

## Validation Architecture
No pytest surface (JS plugin, outside `triggarr/`). Validation = `claude plugin validate .claude/plugins` and `claude plugin validate .claude/plugins/planchk-router` (both must print `✔ Validation passed`), the `--debug hooks` load-line check, the guard negative check (flag unset -> spawn refused), and the Finding 5 smoke run. `uv run pytest tests/ -x -q` + `ruff` stay green (no Python touched).

## Security Domain
- No secrets involved; the guard prints only the env-flag state. Never print or log the gateway `control-token` or route-log contents beyond backend/model/sessionId.
- `permissionMode` is pinned by the runtime for agent.spawn rewrites (84-RUNTIME-VERDICT), so the module can't escalate permissions; the guard can only block (exit 2), never allow.
- Public clones are unaffected: nothing is enabled without settings.local.json plus the CLI registration.

## Assumptions Log
| # | Claim | Risk if wrong |
|---|---|---|
| A1 | Interactive (non `-p`) Triggarr sessions honor settings.local.json `env` the same way (tested only in `-p`; Triggarr folder is already trusted) | Module not loaded in interactive `/bm:plan-phase`; guard would then block visibly (fail-closed), not silently |
| A2 | Agent tool `tool_input.subagent_type` field name is stable (verified on 2.1.281 only) | Guard passes everything; covered by the post-run route-log check |

## Sources
- Live: `claude --help`/`plugin --help`/`marketplace add --help`/`install --help`, `claude plugin validate`, `claude --debug hooks -p` debug logs, `model-gateway.js doctor|status|models`, gateway `guardian.log`, `lsof`, route log.
- [CITED] https://code.claude.com/docs/en/settings (scopes, precedence, local-file git exclude, worktrees, `extraKnownMarketplaces` waits for trust)
- [CITED] https://code.claude.com/docs/en/plugin-marketplaces (directory marketplace, relative sources read in place)
- Phase 84: 84-CLOSEOUT.md (Activation boundary), 84-RUNTIME-VERDICT.md, 84-PILOT-EVIDENCE.md; BM `workflows/plan-phase.md` step 11a.

**Valid until:** next Claude Code or model-gateway update (re-run Findings 2-3 checks).
