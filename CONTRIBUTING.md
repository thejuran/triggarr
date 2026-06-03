# Contributing to Triggarr

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Getting Started

1. Fork the repo and clone your fork
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Install dependencies: `uv sync --extra dev`

## Development Commands

```bash
uv sync --extra dev                    # install dependencies
uv run pytest tests/ -x -q             # run tests
uv run ruff check triggarr/ tests/     # lint
TAILWINDCSS_VERSION=v4.2.2 uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch  # dev CSS (must match Dockerfile TAILWINDCSS_VERSION)
docker build -t triggarr:local .       # local Docker build
```

## Before Opening a PR

1. All tests pass: `uv run pytest tests/ -x -q`
2. No lint errors: `uv run ruff check triggarr/ tests/`
3. Docker builds: `docker build -t triggarr:local .`

## Commit Conventions

Use conventional commit prefixes:

- `feat:` -- new feature
- `fix:` -- bug fix
- `docs:` -- documentation only
- `test:` -- adding or updating tests
- `refactor:` -- code change that neither fixes a bug nor adds a feature

## Pull Requests

1. Push your branch and open a PR against `main`
2. Fill out the PR template checklist
3. CI must pass before merge

## Reporting Issues

Use the GitHub issue templates for bug reports and feature requests.
