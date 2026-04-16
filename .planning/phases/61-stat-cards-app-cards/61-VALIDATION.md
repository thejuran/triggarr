---
phase: 61
slug: stat-cards-app-cards
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 61 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 61-01-01 | 01 | 1 | STAT-01 | — | N/A | visual | Browser check: stat cards use text-[32px]/text-[36px] hero numbers | N/A | ⬜ pending |
| 61-01-02 | 01 | 1 | STAT-02 | — | N/A | visual | Browser check: colored Phosphor icons per app type | N/A | ⬜ pending |
| 61-01-03 | 01 | 1 | STAT-03 | — | N/A | visual | Browser check: Grab Rate card has per-app mini progress bars | N/A | ⬜ pending |
| 61-01-04 | 01 | 1 | STAT-04 | — | N/A | visual | Browser check: p-5 padding on stat cards | N/A | ⬜ pending |
| 61-02-01 | 02 | 1 | CARD-01 | — | N/A | visual | Browser check: colored left border per app type | N/A | ⬜ pending |
| 61-02-02 | 02 | 1 | CARD-02 | — | N/A | visual | Browser check: title + connection pill with bottom border | N/A | ⬜ pending |
| 61-02-03 | 02 | 1 | CARD-03 | — | N/A | visual | Browser check: recessed sub-cards for missing/cutoff stats | N/A | ⬜ pending |
| 61-02-04 | 02 | 1 | CARD-04 | — | N/A | visual | Browser check: Search Now button hover accent | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Stat card hero number sizing | STAT-01 | Visual CSS styling — no automated DOM assertion framework | Inspect stat cards in browser, verify text-[32px]/text-[36px] classes |
| Colored Phosphor icons | STAT-02 | Icon color is visual | Inspect icons, verify app-type color mapping |
| Mini progress bars on Grab Rate | STAT-03 | Visual component | Check Grab Rate card for orange/blue mini bars |
| App card colored left border | CARD-01 | Visual CSS border | Inspect app cards for border-l color per app type |
| App card header/body sections | CARD-02 | Layout structure is visual | Verify title + pill above border-b separator |
| Recessed sub-cards | CARD-03 | Visual nesting | Check missing/cutoff stats in recessed containers |
| Search Now hover accent | CARD-04 | Hover state is interactive | Hover over Search Now button, verify app-colored accent |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
