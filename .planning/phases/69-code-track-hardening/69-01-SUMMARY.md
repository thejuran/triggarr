---
phase: 69-code-track-hardening
plan: 01
subsystem: repo-hygiene
tags: [gitignore, gitleaks, secret-scan, tooling]
dependency_graph:
  requires: [68-code-track-hostile-reader-discovery]
  provides: [clean-gitleaks-scan, orchestrator-json-gitignored]
  affects: [.gitignore, .gitleaksignore]
tech_stack:
  added: []
  patterns: [gitleaks-8.x-fingerprints]
key_files:
  created: []
  modified:
    - .gitignore
    - .gitleaksignore
decisions:
  - "D-07: .gitleaksignore fingerprint per-commit brittleness accepted as maintenance cost of keeping allowlist in .gitleaksignore (not gitleaks.toml)"
  - "D-08: fingerprints generated from live gitleaks run at executor time, not hand-fabricated or copied from research snapshot"
  - "D-09: .orchestrator.json added to GSD/tooling transients block in .gitignore"
  - "D-10: audit-and-close sweep ran; zero untracked-but-not-ignored runtime artifacts, zero accidentally-tracked editor/tooling cruft"
metrics:
  duration: 10m
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 69 Plan 01: Repo Hygiene — .gitignore + .gitleaksignore Hardening Summary

## One-Liner

Closed two launch-visible repo-hygiene gaps: `.orchestrator.json` git-ignored and `.gitleaksignore` converted from four bare-path entries (rejected by gitleaks 8.30.x) to 23 commit-SHA fingerprints, producing a clean gitleaks exit-0 scan with no "Invalid entry" warnings.

## What Was Built

Two tooling/repo-metadata file changes with zero application-behavior impact:

**Task 1 — .gitignore (CHARD-01 / P68-FI-004):**
Appended `.orchestrator.json` to the existing "GSD / tooling transients" block. No sibling orchestrator runtime artifacts (`.orchestrator.lock` etc.) exist in the working tree, so no speculative patterns were added. The file was previously untracked-but-not-ignored; a `git add -A` could have committed GSD orchestrator runtime state into the public repo. Now `git check-ignore .orchestrator.json` returns `.orchestrator.json`.

**Task 2 — .gitleaksignore (CHARD-04 / P68-FI-001):**
Replaced 4 bare-path entries (`tests/test_auth_middleware.py` etc.) — which gitleaks 8.30.x rejects with "Invalid .gitleaksignore entry" warnings — with 23 gitleaks-8.x fingerprints in `commitSHA:filepath:rule:line` format. Fingerprints were generated from a live `gitleaks git .` run at executor time (not copied from the research snapshot) against 1,025 commits. All 23 hits are `generic-api-key` false positives: test fixtures and doc/planning prose containing example API key strings. After writing, gitleaks exits 0 with `INF no leaks found` and zero "Invalid entry" warnings.

## Audit-and-Close Sweep Output (D-10)

**`git status --porcelain | grep '^??'` output (untracked files):**
```
(empty — no untracked-but-not-ignored files in the worktree)
```

**`git ls-files | grep -E '\.(DS_Store|swp|code-workspace|swo)$'` output:**
```
(empty — PASS: no editor/tooling cruft accidentally tracked)
```

Both sweep outputs are clean. CHARD-01's "no untracked transient or accidentally-tracked artifact remains" is verified, not assumed.

## gitleaks Fingerprint Details

**Final fingerprint count written:** 23

**Coverage:** All 23 `generic-api-key` hits across 1,025 commits of history. Hits span:
- Test files: `test_auth_middleware.py`, `test_auth_routes.py`, `test_config.py`, `test_logging.py`
- Planning docs: `.planning/codebase/TESTING.md`, `.planning/phases/58-*/`, `.planning/PROJECT.md`, `.planning/phases/46-*/`
- GSD artifacts: `.gsd/milestones/M001/slices/S05-S06/`, `.gsd/exec/7953456f-*.stdout`
- Security report: `reports/security-2026-04-15.md` (two commits)
- Plugin doc: `.claude/plugins/turingmind/agents/security.md`

All confirmed false positives (example/dummy API key strings in non-production code); triaged in Phase 68 findings.

**Note on original 4-file allowlist:** Two of the original entries (`test_auth_integration.py`, `test_auth_config.py`) had ZERO actual hits in the scan and were correctly omitted from the fingerprint set.

**Maintenance note (D-07 accepted cost):** gitleaks fingerprints are per-commit, not per-file. A future commit that introduces a `generic-api-key` regex match in ANY file will produce a NEW fingerprint that is NOT pre-suppressed. The allowlist must be refreshed (re-run `gitleaks git . --report-format json`, re-extract `Fingerprint` fields, rewrite `.gitleaksignore`) after any commit that touches test fixtures or planning docs containing API key strings. This is the accepted maintenance cost of keeping the allowlist in `.gitleaksignore` rather than switching to a `gitleaks.toml` path/rule allowlist (D-07 LOCKED).

## Verification Results

**Task 1:**
- `git check-ignore .orchestrator.json` → `.orchestrator.json` (PASS)
- `git status --porcelain | grep ".orchestrator.json"` → (empty, PASS)
- `git ls-files | grep -E '\.(DS_Store|swp|code-workspace|swo)$'` → (empty, PASS)

**Task 2:**
- `gitleaks git . --no-banner --redact` exits 0 (PASS)
- Output: `INF no leaks found` (PASS)
- Zero "Invalid .gitleaksignore entry" warnings (PASS)
- All 23 non-comment lines match `^[0-9a-f]{40}:.+:[a-z0-9-]+:[0-9]+$` (PASS)

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add .orchestrator.json to .gitignore (CHARD-01) | 1162039 | .gitignore |
| 2 | Rewrite .gitleaksignore as gitleaks-8.x fingerprints (CHARD-04) | b034122 | .gitleaksignore |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — both changes reduce security surface (prevent accidental commit of runtime state; restore functional secret-scan posture). No new trust boundaries introduced.

## Self-Check: PASSED

- `.gitignore` modified: confirmed (`git show 1162039 --stat` shows 1 file changed)
- `.gitleaksignore` modified: confirmed (`git show b034122 --stat` shows 1 file changed)
- Commits 1162039 and b034122 both present in git log
- gitleaks exit 0 verified live at executor time
