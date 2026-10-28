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
result: pass (2026-10-28) — CI run 40751931306 attempt 1 on head 5a97e1f98982b47672ba108e357a024e0f2a44e2: test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint, CI ready all success; wall clock ~5 min (19:10:43Z→19:16:33Z), os-scan 18 s, actionlint 11 s.

### 2. P2 — Download the CI coverage artifact for the reviewed/accepted head and run `coverage-provenance.cjs check --expected-head <head>`; confirm vibe-check's test-sufficiency lane discovers coverage.xml.
expected: Check passes; vibe-check locates and uses the artifact (CIMAINT-06).
result: pass (2026-10-28) — coverage-40751931306-1 artifact: `coverage-provenance.cjs check --expected-head 5a97e1f… --expected-run-id 40751931306` → "Coverage evidence matches head 5a97e1f98982b47672ba108e357a024e0f2a44e2".

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
result: deferred (owner decision 2026-10-28) — run after merge on a throwaway draft PR from main (85-18 recipes), so PR #36's accepted head 5a97e1f does not move.

### 7. Paired Codex adversarial review on the final head, by PR URL after push (per owner decision 2026-10-27).
expected: Codex review completes (status.json complete, base-status.json complete for changed grader files) or, if it stays INCOMPLETE/PENDING after one retry, the owner records an approved fallback per `codex-fallback.cjs`.
result: INCOMPLETE/PENDING with owner-approved fallback — Codex by PR URL a1/a2 on 5a97e1f both incomplete (diff size); vibe-check full-PR deep review approved as fallback (`codex/5a97e1f98982-fallback.json`, validated); checkpoint issuecomment-6478764430.

### 8. Acceptance register schema migration: run `review-register.cjs migrate --kind dispositions --apply` and `--kind blockers --apply` against the live repository variables (still schema 1) only after owner go-ahead, then exercise `acceptance-readiness.cjs` against the real phase PR head.
expected: Migration succeeds; readiness check reports the D-12 checklist correctly for the real PR; a second concurrent PR's register entry is shown not to erase or satisfy this PR's (ACCEPT-02).
result: pass (2026-10-28, owner go-ahead) — both variables migrated and verified to schema 2 (schema-1 kept under archived_schema1); empty slices written and verified for 36:5a97e1f…; `acceptance-readiness.cjs --pr 36 … --fallback …` → "Ready to request approval".

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps
