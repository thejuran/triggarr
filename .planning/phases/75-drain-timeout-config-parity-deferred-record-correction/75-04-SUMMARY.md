---
phase: 75-drain-timeout-config-parity-deferred-record-correction
plan: "04"
subsystem: docs
tags: [docs, record-correction, changelog, readme]
dependency_graph:
  requires: ["75-02", "75-03"]
  provides: [corrected-deferred-record, readme-drain-docs, changelog-v2.10]
  affects: [".planning/STATE.md", "README.md", "CHANGELOG.md"]
tech_stack:
  added: []
  patterns: [in-app-changelog-section]
key_files:
  created: []
  modified:
    - .planning/STATE.md
    - README.md
    - CHANGELOG.md
decisions:
  - "D-07: DEBT-07/08/03 rows in STATE.md marked as shipped (already-shipped config fields config.py:128-130 + settings inputs); DEBT-06 row marked as shipped in Phase 75 (CFG-03/CFG-04)"
  - "D-08: README prose paragraph added after the existing stop_grace_period guidance; existing stop_grace_period / systemd / env-var docs preserved intact"
  - "D-09: CHANGELOG.md v2.10.0 section added above v2.9.0 covering all three milestone tracks; uses ## vX.Y.Z (YYYY-MM-DD) format the in-app parser requires"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-04"
  tasks_completed: 2
  files_changed: 3
---

# Phase 75 Plan 04: Deferred-Record Correction & Documentation Summary

Corrected the stale deferred record and documented the shipped drain-timeout knob across three DOCS-01 surfaces: STATE.md deferred table, README drain docs, and CHANGELOG.md v2.10 section.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Correct STATE.md deferred-record table (D-07) | 83f5afe | .planning/STATE.md |
| 2 | Extend README drain docs + add v2.10 CHANGELOG section (D-08, D-09) | 154f8c8 | README.md, CHANGELOG.md |

## What Was Built

**D-07 (STATE.md deferred table):** Updated the two DEBT rows at STATE.md:107-108 to reflect shipped reality. DEBT-07/08/03 (request timeout / page size / search-history cap) changed from "already shipped — DOCS-01 corrects record in Phase 75" to "shipped — config fields config.py:128-130 + settings inputs; DOCS-01 corrected the record in Phase 75". DEBT-06 changed from "in scope — Phase 75 (CFG-03/CFG-04)" to "shipped — Phase 75 (CFG-03/CFG-04); general.shutdown_drain_timeout config field + settings input + env-override precedence". The genuinely-deferred rows (UI-01/02/03, PERF-01/02/03, SCALE-01/02, AUDIT-01, OBS-01, v2.9-audit follow-ups, primaryDark token) are unchanged.

**D-08 (README.md):** Added a new paragraph after the existing stop_grace_period prose at README.md:95 documenting that the drain timeout is now a persisted config field (`general.shutdown_drain_timeout`, settable in the Settings UI, default 60 s, minimum 1 s) and that `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` overrides the configured value when set (config default, env overrides precedence per D-06). All existing drain guidance preserved: `stop_grace_period: 90s` comment at README.md:86, prose at README.md:95, and systemd comment at README.md:143.

**D-09 (CHANGELOG.md):** Added `## v2.10.0 (2026-06-04)` section at the top of CHANGELOG.md (above v2.9.0) covering all three milestone tracks in bulleted feature format: password recovery (Track A, Phases 72-73), per-card count refresh (Track B, Phase 74), and configurable shutdown drain timeout (Track C, Phase 75). Uses the `## vX.Y.Z (YYYY-MM-DD)` header format that `read_changelog()` parses for the in-app changelog modal.

## Verification

```
grep -n "DEBT-06\|DEBT-07/08/03" .planning/STATE.md
→ line 107: shipped (record corrected) ...
→ line 108: shipped in v2.10 ...

grep -n "shutdown_drain_timeout\|TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT" README.md
→ lines 86, 95, 97, 143 — all present; new content at 97

grep -n "## v2.10" CHANGELOG.md
→ line 3: ## v2.10.0 (2026-06-04)

uv run pytest tests/ -x -q  →  1067 passed (baseline unchanged)
uv run ruff check triggarr/ tests/  →  All checks passed!
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. Docs-only plan. The CHANGELOG.md content is maintainer-authored, rendered through the existing read_changelog() path whose escaping is unchanged (T-75-11 accepted in plan threat model). No token, secret, hash, or PII appears in any edited document (T-75-12 accepted).

## Self-Check: PASSED

- .planning/STATE.md: corrected rows present (grep confirmed)
- README.md: shutdown_drain_timeout paragraph present (grep confirmed)
- CHANGELOG.md: ## v2.10.0 section present (grep confirmed)
- Task commits: 83f5afe (STATE.md), 154f8c8 (README + CHANGELOG)
- 1067 tests passing, ruff clean
