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

## Buildomator + Greptile pilot

See [the activation checklist](docs/buildomator-greptile-pilot.md). This is a staged
migration; keep the existing review process until the checklist is complete.
Use feature branches and PRs. Buildomator's review hook is advisory, and a Greptile
review does not replace running tests or product acceptance. After fixes, require
fresh checks and review of the current commit. Do not weaken CI, suppress findings,
or push directly to main to make a task appear complete.

## Deferred review-workflow proposal — after v2.12

At v2.12 closeout or before starting the next milestone, read
[the BM + Greptile + Codex blueprint](docs/bm-greptile-codex-blueprint.md)
and present the rollout for owner confirmation. It is a proposal for the next
workflow, not an active instruction to change this milestone. Continue the
current BM + Greptile + manual vibe-check process and protected owner acceptance.
Do not update BM, enable new review settings, or retire vibe-check for this
proposal during v2.12. See `.planning/backlog/MAINTENANCE.md` → Operator planning follow-up.

At the same post-v2.12 checkpoint, read [the CI reference-baseline plan](docs/ci-reference-baseline-plan.md). Present it alongside the review blueprint; it does not activate the proposed CI changes during the current milestone. The separately authorized CLI approval procedure below is active now.

## Active owner approval through Claude CLI

Follow [owner CLI acceptance](docs/owner-cli-acceptance.md). Claude may submit the
owner's explicit approval of the exact PR head commit to GitHub's existing
`review-acceptance` environment. Present the full SHA, PR, run/attempt, and evidence;
recheck them before submission. Never infer approval, approve autonomously, reuse
it after a commit/run change, or bypass a gate. This is approval transport only:
current reviews, CI, dispositions, owner acceptance, and merge/release rules stay
unchanged. This standing permission does not approve any pending PR.
