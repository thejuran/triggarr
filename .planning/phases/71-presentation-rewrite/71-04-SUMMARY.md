---
phase: 71-presentation-rewrite
plan: "04"
subsystem: changelog
tags: [changelog, release-notes, documentation]
dependency_graph:
  requires: []
  provides: [v2.9.0-changelog-entry]
  affects: [in-app-changelog-viewer, CHANGELOG.md]
tech_stack:
  added: []
  patterns: [tautulli-changelog-model]
key_files:
  created: []
  modified:
    - CHANGELOG.md
decisions:
  - "D-11: CHANGELOG.md is the in-app changelog source — a single edit covers both release notes and in-app changelog"
  - "D-12: v2.9.0 entry lists user-facing changes only — SSRF config-load hardening, manual-search failure counter fix, docs overhaul"
metrics:
  duration: "5m"
  completed: "2026-06-02"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 71 Plan 04: v2.9.0 Changelog Entry Summary

**One-liner:** v2.9.0 changelog entry with Security (config-load URL validation), Fixes (manual-search failure counter), and Documentation (README + SECURITY.md overhaul) categories in strict parser format.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Insert v2.9.0 entry at top of CHANGELOG.md | 84510fe | CHANGELOG.md |

## What Was Built

A `## v2.9.0 (2026-06-02)` entry inserted as the first version block in `CHANGELOG.md`, above the existing `## v2.8.1` entry.

The entry contains:
- A one-sentence user-facing summary paragraph
- `* Security:` category: URL validation at config-load time (SSRF/cloud-metadata/link-local hardening, loopback permitted)
- `* Fixes:` category: manual-search failure counter now increments and resets on the same path as scheduled cycles
- `* Documentation:` category: full README rewrite (benefit-led intro, Quick Start, pip/systemd, tag-filtering fail-open) and SECURITY.md updated to reflect v2.8/v2.8.1 hardening + at-rest plaintext caveat

All category lines match the exact parser format (`* CategoryName:` with nothing after the colon). Two-space-indented bullet lines used throughout.

## Verification

- `parse_changelog(latest_only=True)` returns HTML containing `v2.9.0` — verified inline.
- `uv run pytest tests/test_changelog.py -x -q` — 19 passed in 0.02s.
- `## v2.9.0 (2026-06-02)` is the first `## v` entry (line 3), before `## v2.8.1` (line 20).
- All three category lines confirmed via `grep -E '^\* (Security|Fixes|Documentation):$'`.
- No mention of gitleaks, `.orchestrator.json`, or the fastapi/starlette dep bump (internal-only, excluded per D-12).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — docs-only content edit; changelog.py renders it read-only with HTML escaping already in place.

## Self-Check: PASSED

- CHANGELOG.md confirmed modified with `## v2.9.0 (2026-06-02)` at top
- Commit 84510fe confirmed in git log
- 19 parser unit tests passing
