---
phase: 60
slug: foundation-header
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 60 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 60-01-01 | 01 | 1 | FONT-01 | — | N/A | visual | Browser check: body text is system sans-serif | N/A | ⬜ pending |
| 60-01-02 | 01 | 1 | FONT-02 | — | N/A | visual | Browser check: Geist Mono only on designated elements | N/A | ⬜ pending |
| 60-02-01 | 02 | 1 | HDR-01 | — | N/A | visual | Browser check: increased header padding, Phosphor icons | N/A | ⬜ pending |
| 60-02-02 | 02 | 1 | HDR-02 | — | N/A | visual | Browser check: nav links center-aligned, gap-6 spacing | N/A | ⬜ pending |
| 60-02-03 | 02 | 1 | HDR-03 | — | N/A | visual | Browser check: logout pipe divider, sign-out icon | N/A | ⬜ pending |
| 60-02-04 | 02 | 1 | HDR-04 | — | N/A | visual | Browser check: connection status pill with pulsing dot | N/A | ⬜ pending |
| 60-02-05 | 02 | 1 | HDR-05 | — | N/A | visual | Browser check: favicon/icon left of logo text | N/A | ⬜ pending |
| 60-02-06 | 02 | 1 | HDR-06 | — | CSRF POST form preserved | visual | Browser check: logout still uses POST form | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. This phase is primarily visual/template changes verified by browser inspection.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Body text renders in system sans-serif | FONT-01 | Font rendering is visual | Inspect body text in browser DevTools, verify `font-family` |
| Geist Mono only on designated elements | FONT-02 | Font scope is visual | Check version badge, log viewer, schedule rows have `font-geist-mono` |
| Header padding and Phosphor icons | HDR-01, HDR-02 | Layout is visual | Compare header against UI-SPEC mockup |
| Nav alignment and spacing | HDR-03 | CSS layout is visual | Verify `gap-6` and center alignment in DevTools |
| Logout pipe divider | HDR-04 | Visual separator | Check pipe character and sign-out icon appear |
| Connection status pill | HDR-05 | Live status indicator | Verify green dot pulses, text reads "Connection Stable" |
| Favicon/app icon | HDR-06 | Visual asset | Check icon renders left of "Triggarr" text |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
