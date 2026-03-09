# Fetcharr

Python automation daemon that triggers searches in Radarr and Sonarr on a schedule.
FastAPI + htmx + Tailwind CSS v4 dark UI. Docker-first deployment to ghcr.io/thejuran/fetcharr.

## Development Commands

```bash
uv sync --extra dev                    # install dependencies
uv run pytest tests/ -x -q             # run tests
uv run ruff check fetcharr/ tests/     # lint
uv run tailwindcss -i fetcharr/static/css/input.css -o fetcharr/static/css/output.css --watch  # dev CSS
docker build -t fetcharr:local .       # local Docker build
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
