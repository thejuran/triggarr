---
id: S01
parent: M002
milestone: M002
provides:
  - CI-gated release for both dev and tag paths via unified workflow_run trigger
requires: []
affects: []
key_files:
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
key_decisions:
  - Unified workflow_run for both release paths (removed direct push:tags trigger)
  - SHA-pinned all third-party actions in release workflow
  - Tightened branches filter to semver pattern v[0-9]*.[0-9]*.[0-9]*
  - Removed :main tag from tag releases (only pushed on dev path now)
patterns_established:
  - Shell injection prevention via env vars for user-controlled inputs in run: blocks
  - --target on gh release create to pin release to exact commit SHA
observability_surfaces:
  - GitHub Actions workflow run logs
drill_down_paths: []
duration: 20m
verification_result: passed
completed_at: 2026-04-06
---

# S01: Gate All Releases on CI

**Both dev and tag release paths now require CI to pass before publishing, with SHA-pinned actions and shell injection prevention.**

## What Happened

Added `tags: ['v*']` to ci.yml so CI runs on tag pushes. Rewrote release.yml to use `workflow_run` exclusively for both dev (main) and official (tag) paths, eliminating the direct `push: tags` trigger that bypassed CI. Applied all 7 deep review findings: SHA-pinned actions, shell injection fix via env var, `--target` on gh release create, tightened branches filter to semver pattern, inline expressions instead of env context in with: blocks, and guarded `:main` Docker tag to only push on dev path.

## Verification

- YAML syntax validated for both workflow files
- 468 tests passing, no regressions
- Logical review of tag matrix: main→`:main`+`:dev`, tag→`:latest`+`:v*`
- Deep review findings all addressed

## Deviations

None — single-task slice executed as planned, plus deep review hardening.

## Known Limitations

- Full operational verification requires a real push to GitHub (workflow_run behavior can only be confirmed in Actions UI)

## Follow-ups

- Consider SHA-pinning ci.yml actions as well (not in scope for this milestone)

## Files Created/Modified

- `.github/workflows/ci.yml` — added `tags: ['v*']` to push trigger
- `.github/workflows/release.yml` — unified workflow_run, SHA-pinned actions, hardened shell/tag handling

## Forward Intelligence

### What the next slice should know
- No next slice — single-slice milestone

### What's fragile
- `workflow_run` branches filter uses glob pattern `v[0-9]*.[0-9]*.[0-9]*` — if tag naming convention changes, this needs updating

### Authoritative diagnostics
- GitHub Actions tab → workflow runs for "Release" — shows trigger source and tag matrix

### What assumptions changed
- None — approach worked as designed
