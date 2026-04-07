# M002: Uniform CI & Release — Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

## Project Description

Triggarr's CI/CD pipeline has two release paths: dev (on main push) and official (on tag push). The dev path is properly gated by CI, but the tag path bypasses tests entirely.

## Why This Milestone

The tag push release path (`v*`) triggers release.yml directly without waiting for CI to pass. A broken commit could be released as `latest` and pushed to GHCR. The decision register (2026-04-06 #1) established: "Public: dev on main → official on tag; All: push :main tag". The `:main` tag fix is already shipped (`5a3b543`), but the CI gate on the tag path is still missing.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Push a `v*` tag and know that CI (tests + lint + docker build) must pass before the release is published
- Pull `ghcr.io/thejuran/triggarr:main` and always get a CI-verified image regardless of release path

### Entry point / environment

- Entry point: GitHub Actions workflows (`.github/workflows/ci.yml`, `.github/workflows/release.yml`)
- Environment: CI (GitHub Actions)
- Live dependencies involved: GHCR (ghcr.io), GitHub Releases

## Completion Class

- Contract complete means: workflow files are syntactically correct and logically gate releases on CI
- Integration complete means: a real tag push triggers CI first, then release (verified via Actions UI or dry-run)
- Operational complete means: both release paths produce correct tags on GHCR

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- The release workflow for tag pushes cannot publish without CI passing
- Both dev and tag release paths still produce the correct Docker tags (dev: `main`+`dev`, tag: `main`+`latest`+`v*`)
- The GitHub Release + Python package steps still run only on tag pushes

## Risks and Unknowns

- `workflow_run` chaining for tags may not work the same as for branches — GitHub Actions docs need verification

## Existing Codebase / Prior Art

- `.github/workflows/ci.yml` — current CI pipeline (test, lint, docker build)
- `.github/workflows/release.yml` — current release pipeline with two trigger paths

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- Decision #1 (2026-04-06): release strategy by visibility — this milestone completes its implementation

## Scope

### In Scope

- Gate tag release path on CI passing
- Ensure both release paths produce correct Docker tags
- Keep GitHub Release + Python package creation on tag path only

### Out of Scope / Non-Goals

- Changing the CI test suite itself
- Adding new release artifacts
- Changing the Docker build process

## Technical Constraints

- Must use GitHub Actions native features (workflow_run, needs, etc.)
- Cannot require manual intervention for releases
- Must not break the existing dev release path

## Integration Points

- GHCR (ghcr.io/thejuran/triggarr) — Docker image registry
- GitHub Releases — release artifacts

## Open Questions

- Best approach: extend CI to also trigger on tags and use `workflow_run` for all releases, or add CI steps inline to release.yml for the tag path?
