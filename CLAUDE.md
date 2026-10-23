# Triggarr

Python automation daemon that triggers searches in Radarr and Sonarr on a schedule.
FastAPI + htmx + Tailwind CSS v4 dark UI. Docker-first deployment to ghcr.io/thejuran/triggarr.

## Development Commands

```bash
uv sync --extra dev                    # install dependencies
uv run pytest tests/ -x -q             # run tests
uv run ruff check triggarr/ tests/     # lint
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch  # dev CSS
docker build -t triggarr:local .       # local Docker build
```

## Code Conventions

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys -- call `.get_secret_value()` only at HTTP client init
- Loguru for logging with custom redacting sink (never print/logging module)
- Atomic file writes (write-then-rename) for config and state
- pytest-asyncio with asyncio_mode=auto

## Deep Code Review Convention

Before pushing to main or creating a release tag, offer `/deep-review` to the user.
The deep review checks:

1. **Security:** No API keys in logs, responses, or HTML. SecretStr discipline maintained.
2. **Correctness:** All tests pass (`pytest tests/ -x`). No ruff violations.
3. **Resilience:** Error handling follows established patterns (httpx.HTTPError + pydantic.ValidationError catches). No bare `except:`.
4. **Docker:** Dockerfile builds successfully. No secrets baked into image layers.
5. **Config:** Pydantic validation before any config write. TOML comments preserved in defaults.

> Before pushing, I recommend running /deep-review to check for security, correctness,
> and resilience issues. Shall I proceed?

The `/deep-review` offer before pushing to main or creating a release tag is separate
from per-checkpoint review; per-PR review follows the classification policy below.

## Review workflow

- Classify every PR by content per [the review-classification policy](docs/review-classification-policy.md)
  and record the classification against the exact head (classify upward when in doubt).
- After every BM code-review run -- phase execution, quick task, explicit `/bm:code-review`,
  or review after fixes -- Claude automatically runs the independent Codex pass per
  [the Codex adversarial review contract](docs/codex-adversarial-review-contract.md):
  read-only (`--sandbox read-only`), on the exact checkpoint commit, the fixed template
  only, one retry on failure and then INCOMPLETE/PENDING with the owner asked to choose.
- Missing, failed, skipped, stale, or wrong-commit Codex evidence is never reported as
  clean. `/bm:review --codex` is a **plan** review and never counts as this independent
  code review (D-05).
- Record every checkpoint per [the review checkpoint record](docs/review-checkpoint-record.md):
  one PR comment per head SHA, a RISK-01 note, and an explicit vibe-check recommendation
  with the owner's recorded decision whenever risk is high.
- Quick tasks only run BM's own review (and therefore the paired Codex pass) in full
  mode: pass `--full` to `/bm:quick`, or review does not run at all.
- Phase-execution review fires once, after all of a phase's plans have completed, not
  per wave or per plan: pair the Codex pass once that single review has run, not earlier.
- Quick-task review depth is hardcoded to `quick` regardless of `workflow.code_review_depth`:
  record this as the actual depth and never relabel it with the configured depth.

Use feature branches and one PR per phase; no docs-only PRs, ever. Buildomator's review
hook is advisory, and a Greptile review does not replace running tests or product
acceptance. After fixes, require fresh checks and review of the current commit.
Do not weaken CI, suppress findings, or push directly to main to make a task appear
complete. Batch pushes and hold docs-only commits until the next substantive push.
See [the activation checklist](docs/buildomator-greptile-pilot.md) for the full
protections.

This standing instruction authorizes only running the read-only Codex review; it
approves no PR and waives no review.

## Planning file format

Before creating or updating `.planning/STATE.md`, `.planning/ROADMAP.md`, or
`.planning/REQUIREMENTS.md`, BM and other agents must read and follow
[the Roadmaps planning format](docs/PLANNING-FORMAT.md), including its checklist
after planning updates. `STATE.md` records current project status; `ROADMAP.md`
records the plan. Keep their milestone and phase status consistent, update
`last_updated` whenever editing `STATE.md`, and do not mark an in-review phase
finished. Use the prescribed sections for agreed future milestones so the
Roadmaps page can display them.

Preserve unrelated in-flight planning edits. This format requirement does not
authorize changing milestone scope, completion status, or the active review and
acceptance workflow. If the Roadmaps page cannot be checked, report that
limitation rather than claiming its display was verified.

## Review-workflow rollout (v2.13)

[The BM + Greptile + Codex blueprint](docs/bm-greptile-codex-blueprint.md) is being
implemented across Phases 83-86 of this milestone (v2.13). Routine vibe-check stays
in force until the owner decides otherwise in Phase 86 (PILOT-03). Greptile is optional
since 2026-10-22 (owner decision): it runs while free credits last, paid credits are
not bought, and it is not a required check.

[The CI reference-baseline plan](docs/ci-reference-baseline-plan.md) is implemented
across Phases 82 and 85. See `.planning/backlog/MAINTENANCE.md` → Operator planning
follow-up.

## Active owner approval through Claude CLI

Follow [owner CLI acceptance](docs/owner-cli-acceptance.md). Claude may submit the
owner's explicit approval of the exact PR head commit to GitHub's existing
`review-acceptance` environment. Present the full SHA, PR, run/attempt, and evidence;
recheck them before submission. Never infer approval, approve autonomously, reuse
it after a commit/run change, or bypass a gate. This is approval transport only:
current reviews, CI, dispositions, owner acceptance, and merge/release rules stay
unchanged. This standing permission does not approve any pending PR.
