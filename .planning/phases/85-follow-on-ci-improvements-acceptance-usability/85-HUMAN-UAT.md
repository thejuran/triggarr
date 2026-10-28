---
status: partial
phase: 85-follow-on-ci-improvements-acceptance-usability
source: [85-VERIFICATION.md]
started: 2026-10-27T22:31:35Z
updated: 2026-10-27T22:31:35Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. P1 — Open the phase PR and record the real CI run on the exact head: every required job's conclusion (test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint, CI ready), plus added PR wall-clock time vs. the ~5-minute target.
expected: All required jobs succeed on GitHub's real amd64 runners (not the arm64 substitution used in local verification); os-scan and actionlint both run and pass; added time stays near budget.
result: [pending]

### 2. P2 — Download the CI coverage artifact for the reviewed/accepted head and run `coverage-provenance.cjs check --expected-head <head>`; confirm vibe-check's test-sufficiency lane discovers coverage.xml.
expected: Check passes; vibe-check locates and uses the artifact (CIMAINT-06).
result: [pending]

### 3. P3 — First main-push Release run after merge: confirm the `release` job's actual permissions (packages: write, contents: read, actions: read — no contents: write) and that `:main`/`:dev` publish successfully to ghcr.io under the narrowed permission.
expected: Publish succeeds with no contents:write grant on the release job (CIMAINT-07).
result: [pending]

### 4. P4 — First scheduled/triggered Dependabot run against the new `.github/dependabot.yml` (uv, github-actions, docker ecosystems).
expected: Grouped PRs (or 'no updates available') per ecosystem, no auto-merge, each PR reviewed under the interim untrusted-head rule (CIMAINT-02).
result: [pending]

### 5. P5 — Next release's CHANGELOG entry states Python wheel/sdist are no longer attached as release assets (D-14/CIMAINT-05).
expected: CHANGELOG wording matches the owner-recorded decision.
result: [pending]

### 6. P6 — CIMAINT-01/CIMAINT-04 negative demonstration on the phase PR (85-18 recipes): push the prepared patch with owner go-ahead, confirm the docker-job lockfile-mismatch failure and the actionlint failure on GitHub, then revert and re-review the restored head.
expected: Both failures reproduce on GitHub exactly as locally reproduced in this verification (docker 'version mismatch: idna lock 3.15 image 3.4'; actionlint 'property "missing" is not defined in object type {} [expression]'); CI ready fails; no Release run. Restore push reverts cleanly, fresh CI/BM/Codex review follows on the restored head.
result: [pending]

### 7. Paired Codex adversarial review on the final head, by PR URL after push (per owner decision 2026-10-27).
expected: Codex review completes (status.json complete, base-status.json complete for changed grader files) or, if it stays INCOMPLETE/PENDING after one retry, the owner records an approved fallback per `codex-fallback.cjs`.
result: [pending]

### 8. Acceptance register schema migration: run `review-register.cjs migrate --kind dispositions --apply` and `--kind blockers --apply` against the live repository variables (still schema 1) only after owner go-ahead, then exercise `acceptance-readiness.cjs` against the real phase PR head.
expected: Migration succeeds; readiness check reports the D-12 checklist correctly for the real PR; a second concurrent PR's register entry is shown not to erase or satisfy this PR's (ACCEPT-02).
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps
