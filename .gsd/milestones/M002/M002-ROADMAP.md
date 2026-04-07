# M002: Uniform CI & Release

**Vision:** All release paths (dev and official) are gated by CI, producing correct Docker tags on GHCR with zero manual intervention.

## Success Criteria

- Tag pushes trigger CI first; release only proceeds if CI passes
- Dev path (main push) still produces `main` + `dev` Docker tags
- Tag path (v* push) still produces `main` + `latest` + `v*` Docker tags
- GitHub Release + Python package still created only on tag pushes
- No duplicate or wasted CI runs

## Key Risks / Unknowns

- `workflow_run` with tag events — GitHub docs say `workflow_run` only triggers on default branch workflows; tag-triggered CI may not chain via `workflow_run`

## Proof Strategy

- workflow_run tag behavior → retire in S01 by reading GitHub docs and designing around any limitation

## Verification Classes

- Contract verification: workflow YAML syntax validation, logical review of trigger/condition matrix
- Integration verification: push to repo and verify Actions behavior (or dry-run analysis)
- Operational verification: both release paths produce correct GHCR tags
- UAT / human verification: user confirms Actions runs look correct after a push

## Milestone Definition of Done

This milestone is complete only when all are true:

- Release workflow cannot publish without CI passing, on both paths
- Docker tags are correct for both dev and tag releases
- GitHub Release + package steps preserved for tag-only
- Workflows pushed to main and verified

## Requirement Coverage

- Covers: Decision #1 (2026-04-06) — uniform release strategy
- Partially covers: none
- Leaves for later: none
- Orphan risks: none

## Slices

- [x] **S01: Gate All Releases on CI** `risk:medium` `depends:[]`
  > After this: Both dev and tag release paths require CI to pass before publishing. Proven by workflow file review and push verification.

## Boundary Map

### S01

Produces:
- Updated `ci.yml` that also triggers on `v*` tags
- Updated `release.yml` that uses `workflow_run` for both paths (or equivalent CI gate)
- Correct tag matrix for both release paths

Consumes:
- nothing (single slice)
