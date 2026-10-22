# BM review baseline — REVIEW-01 gate

Recorded: 2026-10-22. Status: approved by owner on 2026-10-22; not yet applied.

No plugin installation, update, or settings change is performed by this document.

## Baseline

| Item | Value | Source command |
|---|---|---|
| BM installed version | `4.9.1` (directory `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/`) | `cat ~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/.claude-plugin/plugin.json` (`"version": "4.9.1"`); `ls ~/.claude/plugins/cache/gsd-plugin/bm/` |
| Claude Code version | `2.1.281 (Claude Code)` | `claude --version` |
| Codex CLI version | `codex-cli 0.153.4` | `codex --version` |
| codex plugin version | `1.0.4` (directory `~/.claude/plugins/cache/openai-codex/codex/1.0.4/`) | `ls ~/.claude/plugins/cache/openai-codex/codex/` |
| node version | `v25.9.0` | `node --version` |
| gh version | `gh version 2.86.0 (2026-01-21)` | `gh --version` (first line) |
| gh authenticated account | `thejuran` | `gh api user --jq .login` |
| Current branch | `paired-review` | `git branch --show-current` |
| HEAD full SHA | `63e061b85b9680541647ec5f741773e774bd7461` | `git rev-parse HEAD` |
| Saved config copy | `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-config-before.json` | `cp .planning/config.json .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-config-before.json` |
| Saved config sha256 | `b7d92c364b56ac73da1f5d2c6b0d1731d10e0268bec0487af3caa69a6f89ebbb` | `shasum -a 256 .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-config-before.json` |

### Full current `.planning/config.json` contents

```json
{
  "mode": "yolo",
  "parallelization": true,
  "commit_docs": true,
  "model_profile": "balanced",
  "workflow": {
    "research": true,
    "plan_check": true,
    "verifier": true,
    "code_review": false,
    "_auto_chain_active": false,
    "tdd_mode": true
  },
  "granularity": "standard",
  "resolve_model_ids": true
}
```

## Current BM review behavior (installed 4.9.1)

Re-read directly from the installed workflow files (not copied from `83-RESEARCH.md` or the blueprint).

| Path | Auto-runs review? | Condition | File / step responsible |
|---|---|---|---|
| **phase execution** | Yes | Runs once, after all plans/waves of the phase have completed (step `code_review_gate` sits after `execute_waves` → `aggregate_results` → the partial-wave check confirms no incomplete plans remain). Skipped with message `"Code review skipped (workflow.code_review=false)"` if `workflow.code_review` resolves to `"false"`; otherwise invokes `Skill(skill="gsd-code-review", args="${PHASE_NUMBER}")`. Marked `required="true"` and advisory-only — a review error never blocks execution. | `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/execute-phase.md`, step `code_review_gate` (line 1214) |
| **quick task** | Only in full mode | `quick.md` Step 6.25 ("Code review (auto)") is skipped entirely if `$FULL_MODE` is false. `$FULL_MODE` is only set by `--full`, or by passing all of `--discuss --research --validate` together. Same config gate (`workflow.code_review`) as phase execution; same skip message. | `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/quick.md`, Step 6.25 (line 862) |
| **explicit `/bm:code-review`** | Yes, on explicit invocation | User-invoked command; not gated behind `$FULL_MODE`. Runs the `gsd-code-review` skill directly against the named phase. | `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/code-review.md` |
| **review after fixes** | Yes, via `/bm:code-review <N> --fix --auto` | The `--auto` iteration loop (capped at `MAX_ITERATIONS=3`) re-invokes the `gsd-code-review` skill at the same depth recorded in the original `REVIEW.md` frontmatter (falls back to full-phase scope if no `files_reviewed_list` was recorded), then re-fixes until clean or the cap is reached. **Each iteration backs up the prior `REVIEW.md`/`REVIEW-FIX.md` to `*.iterN.md` before overwriting** — the final `REVIEW.md` and `REVIEW-FIX.md` are each the single latest-state file, not iteration-by-iteration copies. `REVIEW-FIX.md` is committed once, at the end of the workflow, not per iteration. | `~/.claude/plugins/cache/gsd-plugin/bm/4.9.1/workflows/code-review-fix.md`, step `auto_iteration_loop` (line 232) |

Confirmed separately (same installed 4.9.1 files): `/bm:review --codex` (`workflows/review.md`) pipes `.planning/PROJECT.md`, the phase's `ROADMAP.md` section, plans, and `REQUIREMENTS.md` to `codex exec --skip-git-repo-check -`, producing a **plan** review (`REVIEWS.md`, consumed by `/bm:plan-phase --reviews`). It has no code-review mode and is not an alternative path to the four rows above.

## Target assessment: BM v5.0.3

No newer release exists: `gh release list -R buildomator/buildomator -L 5` shows `v5.0.3  Latest  v5.0.3  2026-10-22T15:59:02Z` as the newest entry (next newest: `v5.0.2`, `v5.0.1`, `v5.0.0`, `v4.9.3`). D-01's proposed target is confirmed current as of this assessment.

Tag `v5.0.3` is an annotated tag; `gh api repos/buildomator/buildomator/git/ref/tags/v5.0.3` resolves to tag object `37602d2d17b7177c35357734fa7ed813e1a877e7`, which `gh api repos/buildomator/buildomator/git/tags/37602d2d17b7177c35357734fa7ed813e1a877e7` resolves to **commit `e499a62e67748294fb3ab091ce7f7ef773bb4a3c`** (message: "Buildomator 5.0.3: remove vendored Claude Code skill source, add a divergence-as-root-cause discipline to the debugger and code fixer."). Every quote and path below was fetched read-only from this tag/commit via `gh api repos/buildomator/buildomator/contents/<path>?ref=v5.0.3` (`Accept: application/vnd.github.raw`) into the session scratchpad — never into this repository — not copied from `83-RESEARCH.md` or the blueprint.

### (a) Auto-run review per path — unchanged from installed 4.9.1

- **Phase execution:** `dist/bm/workflows/execute-phase.md` step `code_review_gate` (line 1241) — byte-identical text to the installed 4.9.1 file: "This step is REQUIRED and must not be skipped... If `CODE_REVIEW_ENABLED` is `"false"`: display... and proceed to next step." The step sits after `execute_waves` → `aggregate_results` → the partial-wave completeness check, so it fires once, only after all of a phase's plans have finished — not per wave, not per plan.
- **Quick task:** `dist/bm/workflows/quick.md` Step 6.25 "Code review (auto)" (line 890) — "Skip this step entirely if `$FULL_MODE` is false." Unchanged: still requires `--full` (or all of `--discuss --research --validate` together).
- **Explicit `/bm:code-review`:** `dist/bm/workflows/code-review.md`, invoked directly by the user via the `code-review` SKILL.md dispatch layer; same config gate, same `resolve_depth`/`compute_file_scope` steps as below.
- **Review after fixes:** `dist/bm/workflows/code-review-fix.md`, step `auto_iteration_loop` (line 232) — `MAX_ITERATIONS=3` (line 241), loop uses `-lt` so "Total fix passes = MAX_ITERATIONS" (line 239), `.iterN.md` backup-before-overwrite on both `REVIEW.md` and `REVIEW-FIX.md` (lines 270-275), unchanged from 4.9.1.

### (b) Depth handling (REVIEW-05)

Config key `workflow.code_review_depth`. `dist/bm/workflows/code-review.md` step `resolve_depth` (lines 102-116): priority is `--depth` flag > `workflow.code_review_depth` config > default `"standard"` (`REVIEW_DEPTH="${CONFIG_DEPTH:-standard}"`). The verbatim >50-file downgrade text (lines 313-320), identical to 4.9.1:

```
Warning: ${#REVIEW_FILES[@]} files is a large review scope.
Consider using --files to narrow scope, or --depth=quick for a faster pass.
Switching from deep to standard depth for large file count.
```

(the third line only prints when `REVIEW_DEPTH` was `deep`).

**Quick-task depth is hardcoded, not config-driven.** `dist/bm/workflows/quick.md` line 929 writes `Depth: quick` literally into the reviewer `Agent()` prompt. It never calls `code-review.md`'s `resolve_depth` step and never reads `workflow.code_review_depth` at all — see Surprise 2 below.

### (c) Fix loop

`/bm:code-review <N> --fix --auto`: `MAX_ITERATIONS=3` (`code-review-fix.md` line 241); each iteration backs up `REVIEW.md`/`REVIEW-FIX.md` to `*.iterN.md` before overwriting (lines 270-275); "REVIEW.md and REVIEW-FIX.md are each overwritten per iteration (latest state). ONE final version of each, not per-iteration copies" (line 363); `REVIEW-FIX.md` is committed once, after all iterations (line 364). Unchanged from 4.9.1.

### (d) External reviewer invocation from code review — confirmed no

`dist/bm/workflows/review.md` and its dispatch layer `dist/bm/skills/review/SKILL.md` ("Request cross-AI peer review of phase plans from external AI CLIs") pipe `.planning/PROJECT.md`, the phase's `ROADMAP.md` section, the phase's plans, and `REQUIREMENTS.md` to `codex exec --skip-git-repo-check -` (review.md line 208) to produce `REVIEWS.md`, consumed only by `/bm:plan-phase --reviews`. This reviews phase **plans**, never committed code. `dist/bm/workflows/code-review.md` has no Codex, Gemini, or any external-CLI option anywhere in its text. **D-05 holds at v5.0.3**, confirmed directly from the tag's own files (not inferred from the CHANGELOG).

### (e) Specialist/craft-skill lanes — exact supported surface, and the gap

The installed catalog `dist/bm/sdk/shared/craft-skill-catalog.json` holds **13 entries** at v5.0.3 (grew from 2 at v4.9.2 to 8 at v4.9.3 to 13 at v5.0.0's Superpowers addition, per `CHANGELOG.md`'s `[4.9.2]`/`[4.9.3]`/`[5.0.0]` entries). The one entry targeting `bm-code-reviewer` is `code-reviewer` (domain `code-quality`, trust tier `A`, license MIT, source `https://github.com/Jeffallan/claude-skills` pinned at commit `1be15d80...`).

The supported CLI surface is exactly five `bm-sdk query craft-skill.*` subcommands, confirmed by reading `dist/bm/sdk/dist/query/craft-skill.js` (lines 468-518): `craft-skill.list`, `craft-skill.assess`, `craft-skill.match`, `craft-skill.insert`, `craft-skill.release`. **There is no sixth "enable all" or "enable every lane" command.** `craft-skill.insert` (line 496-508 / `dist/bm/bin/lib/craft-skill-insert.cjs` line 189 usage string: `craft-skill insert <id> --agent <type> --location <where> [--sticky] [--approved]`) takes exactly one catalog `id`, one `--agent <type>`, and one `--location <checkout>` per call — it is scoped to a single skill × a single agent, never a bulk operation.

Per `dist/bm/references/craft-skill-propose-on-fit.md` (the authoritative behavior description), the intended mechanism is per-task and trigger-matched: `craft-skill.match "<scope text>"` shortlists candidates deterministically, a model judges relevance only, then either an interactive accept (`Accept (ephemeral, this task only)` / `Accept sticky (persist for <agent>)` / `Skip`) or — only in autonomous mode — an auto-insert gated on `verdict === 'allow'` AND relevance AND a resolved checkout. `code-review` is one of the nine wired surfaces: confirmed directly in `dist/bm/workflows/code-review.md` step `spawn_reviewer` (lines 459-495), which runs `craft-skill.match` against the review scope before the reviewer spawns, substitutes `bm-code-reviewer` for `bm-executor` in the accept/insert/log lines, and releases the inserted skill after the reviewer returns (success or failure path alike).

Critically, every insert — proposed per-task or called directly — requires a **local checkout of the skill's third-party source at its exact pinned commit**: `--location` must be a directory containing a `SKILL.md` whose frontmatter `name` matches the catalog's `skill_name`, with the checkout's git `HEAD` equal to `pinned_commit` (`craft-skill-insert.cjs` line 292 refuses on a pin mismatch). Buildomator's own changelog states the catalog "holds metadata and pinned commits only, never skill bodies... Buildomator never fetches or runs" the source (`CHANGELOG.md` `[4.9.2]`) — a human must separately clone each catalog entry's repository and check out its pinned commit before any insert can succeed. `craft-skill.insert` also refuses outright on a `block` verdict (`craft-skill-insert.cjs` line 200) and requires an explicit `--approved` flag the first time a given `id`/`pinned_commit` pair is inserted (line 206) — there is no default-approved path.

**Conclusion: v5.0.3 has no supported key, flag, or command that means "every specialist/craft-skill lane, turned on."** The real surface is per-skill, per-agent, checkout-gated, and explicitly approval-gated. Per D-03's "never invent a key, a lane without a supported key is reported, not faked" — reported here, not approximated. See Surprise 1 below for the proposed adjustment.

## Model change bundled with the version

Confirmed directly from `CHANGELOG.md` at the v5.0.3 tag. The `[5.0.1] - 2026-10-20 (Sonnet and Haiku tiers move to 5.5)` entry states:

> The `sonnet` tier is now Claude Sonnet 5.5 (`claude-sonnet-5-5`) and the `haiku` tier is now Claude Haiku 5.5 (`claude-haiku-5-5`) across the four Claude-compatible runtimes (claude, opencode, copilot, hermes). Sonnet 5.5 costs the same as Sonnet 5 ($2 and $10 per MTok). Haiku 5.5 is far cheaper than Haiku 4.5 (from $0.10 and $0.50 per MTok, against $1 and $5) and moves from a 200K to a 1M context window, so the light-tier agents get a newer model at a large cost reduction.

This is **accepted as part of the version change per D-02, not pinned, and not a separate settings change.** A related change in the immediately preceding `[5.0.0] - 2026-10-20` entry: the `opus` tier also moved to Claude Opus 5.5 (`claude-opus-5-5`) in that release — noted here for completeness since it affects the same Claude-compatible runtimes and the same version-change window, though D-02 only names the sonnet/haiku move explicitly.

**Later pilot comparisons (Phase 86) must note that BM's sonnet-, haiku-, and opus-tier agents all changed model at the same time this gate's review settings changed** — any before/after comparison of review quality, findings, or cost between the pre-gate and post-gate workflow cannot attribute the difference to the settings change alone.

## Proposed settings (for owner approval)

| Setting | Current | Proposed | Source in v5.0.3 |
|---|---|---|---|
| `workflow.code_review` | `false` | `true` | `dist/bm/workflows/settings.md` line 48 ("`workflow.code_review` — enable /bm:code-review and /bm:code-review --fix commands"); gates all four review paths (`execute-phase.md` line 1246, `quick.md` line 896, `code-review.md`, `code-review-fix.md`) |
| `workflow.code_review_depth` | (absent — resolves to `standard`) | `standard` (explicit) | `dist/bm/workflows/code-review.md` lines 102-116, step `resolve_depth` (default `"standard"` if config value absent). Does **not** reach the quick-task path — see (b)/Surprise 2: that path hardcodes `quick` regardless of this setting. |
| *(craft-skill / specialist lane — "every lane on")* | n/a | **not proposed — no supported key exists** | `dist/bm/sdk/dist/query/craft-skill.js` (5 single-skill subcommands, no bulk "enable" operation); `dist/bm/references/craft-skill-propose-on-fit.md` (per-task, checkout-gated, approval-gated design); `dist/bm/sdk/shared/craft-skill-catalog.json` (13 entries, 1 targets `bm-code-reviewer`) |
| `mode` | `"yolo"` | unchanged | — |
| `parallelization` | `true` | unchanged | — |
| `commit_docs` | `true` | unchanged | — |
| `model_profile` | `"balanced"` | unchanged | — |
| `workflow.research` | `true` | unchanged | — |
| `workflow.plan_check` | `true` | unchanged | — |
| `workflow.verifier` | `true` | unchanged | — |
| `workflow._auto_chain_active` | `false` | unchanged | — |
| `workflow.tdd_mode` | `true` | unchanged | — |
| `granularity` | `"standard"` | unchanged | — |
| `resolve_model_ids` | `true` | unchanged | — |

Sources: `dist/bm/workflows/code-review.md`, `dist/bm/workflows/execute-phase.md`, `dist/bm/workflows/quick.md`, `dist/bm/workflows/code-review-fix.md`, `dist/bm/workflows/review.md`, `dist/bm/workflows/settings.md`, `dist/bm/workflows/settings-integrations.md`, `dist/bm/skills/review/SKILL.md`, `dist/bm/skills/code-review/SKILL.md`, `dist/bm/references/craft-skill-propose-on-fit.md`, `dist/bm/sdk/dist/query/craft-skill.js`, `dist/bm/sdk/shared/craft-skill-catalog.json`, `dist/bm/bin/lib/craft-skill-insert.cjs`, `CHANGELOG.md` — all fetched read-only at tag `v5.0.3`, commit `e499a62e67748294fb3ab091ce7f7ef773bb4a3c`.

## Surprises and proposed adjustments

**1. No supported "every craft-skill lane on" operation exists (D-03(b)).** The only supported surface is five single-skill/single-agent `bm-sdk query craft-skill.*` subcommands, each insert scoped to one catalog `id` × one `--agent` × one local `--location` checkout at the skill's exact pinned commit, refusing on a `block` verdict and requiring an explicit `--approved` flag. There is no boolean, no catalog-wide switch — note that 4.9.1's `agent_skills.<agent-type>` key (confirmed unchanged in v5.0.3's `settings-integrations.md`) injects arbitrary free-text skill *names* into an agent's spawn and has no relationship to the craft-skill catalog's trust/pin gate, so it cannot be used to approximate "every catalog lane on" either — and no CLI flag inserts more than one skill per call.
> **Proposed adjustment:** Do not approximate "every lane on" with a fabricated key. Of the 13 catalog entries, the only one in this phase's REVIEW-02..06 scope is `code-reviewer` (targets `bm-code-reviewer`, trust tier A, MIT, `github.com/Jeffallan/claude-skills@1be15d80`). Turning it on durably would require cloning that repository locally at the pinned commit and then running `bm-sdk query craft-skill.insert code-reviewer --agent bm-code-reviewer --location <checkout> --sticky --approved` once — a one-time manual action with its own supply-chain-review weight, not a config-diff line item. Recommend scoping this gate's settings approval to `workflow.code_review`/`workflow.code_review_depth` only, and treating craft-skill-lane adoption (if the owner still wants it) as its own, separately-scoped decision — noting that the propose-on-fit mechanism already fires automatically inside the code-review flow once `workflow.code_review=true` (it runs `craft-skill.match` before every reviewer spawn, per task), so no settings change is needed for the lane to be *offered* each time it is relevant. What has no supported "on" switch is making it always-already-inserted ahead of time.

**2. Quick-task review depth is hardcoded to `quick`, not config-driven (REVIEW-05).** `dist/bm/workflows/quick.md` line 929 writes `Depth: quick` literally into the reviewer agent's prompt; it never calls `code-review.md`'s `resolve_depth` step and never reads `workflow.code_review_depth`. So once this gate sets `workflow.code_review_depth=standard`, the quick-task path's *actual* review depth stays `quick` regardless — a real, confirmed mismatch, not a hypothetical.
> **Proposed adjustment:** No BM setting changes this. Record it plainly every time the quick-task path is demonstrated: REVIEW-05's "requested vs. actual depth" field reads requested `standard` (per `workflow.code_review_depth`), actual `quick` (hardcoded by `quick.md` line 929) — disclosed, not silently relabelled.

**3. `execute-phase`'s `code_review_gate` reviews a whole phase once, never per wave or per plan.** Unchanged from 4.9.1 (confirmed byte-identical step text at v5.0.3, `execute-phase.md` line 1241): the step sits after `execute_waves` → `aggregate_results` → the partial-wave completeness check, so it fires only once all of a phase's plans have finished.
> **Proposed adjustment:** Not a gap to fix — a scoping fact to carry into REVIEW-02's demonstration plan: the "phase execution" path can only be observed by letting a phase run to its last plan, not an intermediate one.

None of these three findings is D-04's own example surprise ("review doesn't run automatically on quick tasks") — that example does not reproduce at either version; quick-task review does auto-run, gated on `--full`. The depth-handling difference that *does* reproduce is narrower (Surprise 2) and is disclosed above rather than assumed away.

## Owner approval

**Date/time:** 2026-10-22 14:37 EDT (owner answered in the Claude Code CLI session).

**Clarification exchange, before the answer:** The checkpoint's context presented two bullets describing the auto-run triggers — "BM reviews code automatically when a phase finishes all its plans" and "`/bm:code-review` runs on demand, as it does today." The owner asked: "which one is it -- automatically or on demand?" The orchestrator answered: both are separate triggers enabled by the same setting (`workflow.code_review`), and corrected one point in the process — with `workflow.code_review=false` (today's setting), `/bm:code-review` currently exits with "Code review skipped" (BM 4.9.1 `workflows/code-review.md`, lines 90-95), so **today neither trigger runs**; turning the setting on enables both. The owner then answered the checkpoint.

**Owner's verbatim words:** "A"

This selected option `approve-as-proposed`, whose full text as presented was: "Approve as proposed: BM v5.0.3, `workflow.code_review=true`, `workflow.code_review_depth=standard`, nothing else changed, craft-skill lanes left as 'offered automatically' (not pre-installed). Trade-off: the Sonnet/Haiku/Opus model change rides along and must be noted in later comparisons."

**Approved exact version:** BM v5.0.3 (tag commit `e499a62e67748294fb3ab091ce7f7ef773bb4a3c`), per the Target assessment above. No newer release exists as of this assessment.

**Approved settings list (exact key = value lines, exactly two keys changed; every other `.planning/config.json` key is unchanged):**

```
workflow.code_review: false -> true
workflow.code_review_depth: unset -> "standard"
```

No other key in `.planning/config.json` changes. The craft-skill/specialist lane row from the Proposed settings table above is **not approved as a settings change** — consistent with the Surprises section's finding that v5.0.3 has no supported "every lane on" key, flag, or command (D-03(b), D-04). Craft-skill lanes are left as "offered automatically": the `code-review` workflow's existing `craft-skill.match` step already proposes the `code-reviewer` catalog entry per-task once `workflow.code_review=true`, with no durable pre-install and no settings-table line item.

**Adjustments to the proposal:** None beyond the craft-skill-lane scoping already reflected in the Proposed settings table (no fabricated key proposed; Option A approves the table exactly as written, including that row's "not proposed" disposition).

**Model-tier note (D-02):** The bundled v5.0.1 Sonnet/Haiku 5.5 (and v5.0.0 Opus 5.5) model-tier change rides along with this approval, as disclosed in "Model change bundled with the version" above. It is accepted as part of the version change, not pinned, and must be noted in later pilot comparisons (Phase 86) alongside the review-settings change.

**Approval transport: Claude CLI conversation; not inferred.**

This approval covers only the BM version and the two settings keys listed above. **It does not approve any pull request.** `.planning/config.json` is not modified by this record — the change is applied by Plan 05, which also runs `/bm:version` afterward to confirm the loaded version.
