# S01: Gate All Releases on CI

**Goal:** Both dev (main push) and official (tag push) release paths require CI to pass before publishing Docker images.
**Demo:** Workflow files show unified CI-gated release with correct tag matrix. Verified by YAML review and actionlint.

## Must-Haves

- CI triggers on tag pushes (`v*`) in addition to main + PRs
- Release uses `workflow_run` exclusively (no direct `push: tags` trigger)
- Dev path (main): pushes `main` + `dev` Docker tags
- Official path (tag): pushes `main` + `latest` + `v*` Docker tags
- GitHub Release + Python package still tag-only
- PR CI completions do NOT trigger releases

## Proof Level

- This slice proves: operational
- Real runtime required: yes (push to GitHub to verify Actions behavior)
- Human/UAT required: yes (confirm Actions UI shows correct behavior)

## Verification

- `actionlint .github/workflows/ci.yml .github/workflows/release.yml` (if available, or manual YAML review)
- Review tag matrix logic: dev path → `main`+`dev`, tag path → `main`+`latest`+`v*`
- Confirm `if` condition excludes PR-triggered CI completions
- Confirm checkout uses `workflow_run.head_sha` for both paths
- Confirm GitHub Release step uses `workflow_run.head_branch` for tag name

## Observability / Diagnostics

- Runtime signals: GitHub Actions workflow run logs
- Inspection surfaces: Actions tab in GitHub repo
- Failure visibility: workflow_run conclusion check in `if` condition
- Redaction constraints: none (no secrets in workflow logic)

## Integration Closure

- Upstream surfaces consumed: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- New wiring introduced in this slice: `workflow_run` for tag path replaces direct `push: tags` trigger
- What remains before the milestone is truly usable end-to-end: push to main and verify in Actions UI

## Tasks

- [x] **T01: Update CI and Release workflows** `est:20m`
  - Why: Tag pushes currently bypass CI entirely; need to gate all releases on test/lint/docker passing
  - Files: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
  - Do:
    1. In `ci.yml`: add `tags: ['v*']` to the `push` trigger alongside `branches: [main]`
    2. In `release.yml`: remove the `push: tags: ['v*']` trigger entirely
    3. In `release.yml`: remove `branches: [main]` from `workflow_run` (needed so tag-triggered CI also fires release)
    4. Update the job `if` condition to: `workflow_run.conclusion == 'success'` AND (`head_branch == 'main'` OR `startsWith(head_branch, 'v')`)
    5. Replace all `github.event_name == 'push'` / `startsWith(github.ref, 'refs/tags/v')` checks with `startsWith(github.event.workflow_run.head_branch, 'v')`
    6. Replace `github.event_name == 'workflow_run'` (dev detection) with `github.event.workflow_run.head_branch == 'main'`
    7. Update Docker metadata tags to use the new conditions
    8. Update `gh release create` to use `github.event.workflow_run.head_branch` as tag name
    9. Ensure checkout ref remains `github.event.workflow_run.head_sha`
  - Verify: Review YAML for correctness; confirm tag matrix produces expected tags for each path
  - Done when: Both workflow files are updated and internally consistent

## Files Likely Touched

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
