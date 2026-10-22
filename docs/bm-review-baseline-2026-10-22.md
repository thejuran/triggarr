# BM review baseline — REVIEW-01 gate

Recorded: 2026-10-22. Status: gate pending owner approval.

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
