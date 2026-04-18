---
phase: 61
slug: stat-cards-app-cards
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-15
verified: 2026-04-18
---

# Phase 61 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_stats_health.py tests/test_app_cards.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~2 seconds (phase suites), ~18 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 61-01-01 | 01 | 1 | STAT-01 | N/A | unit (HTML assert) | `uv run pytest tests/test_stats_health.py -k "test_grab_rate_hero_card_layout or test_stat_card_label_typography" -q` | ✅ green |
| 61-01-02 | 01 | 1 | STAT-02 | N/A | unit (HTML assert) | `uv run pytest tests/test_stats_health.py -k "test_per_app_bars_with_colors or test_mini_bars_horizontal_layout" -q` | ✅ green |
| 61-01-03 | 01 | 1 | STAT-03 | N/A | unit (HTML assert) | `uv run pytest tests/test_stats_health.py -k "test_stat_cards_have_phosphor_icons or test_grab_rate_has_phosphor_icon" -q` | ✅ green |
| 61-01-04 | 01 | 1 | STAT-04 | N/A | unit (HTML assert) | `uv run pytest tests/test_stats_health.py -k "test_stat_card_subtitles or test_health_strip_has_colored_dots" -q` | ✅ green |
| 61-02-01 | 02 | 1 | CARD-01 | N/A | unit (HTML assert) | `uv run pytest tests/test_app_cards.py -k "test_app_card_radarr_border_color or test_app_card_unreachable_border_color" -q` | ✅ green |
| 61-02-02 | 02 | 1 | CARD-02 | N/A | unit (HTML assert) | `uv run pytest tests/test_app_cards.py -k "test_card_header_border_bottom or test_connected_pill_has_border or test_connected_pill_unified_shape" -q` | ✅ green |
| 61-02-03 | 02 | 1 | CARD-03 | N/A | unit (HTML assert) | `uv run pytest tests/test_app_cards.py::test_recessed_subcards -q` | ✅ green |
| 61-02-04 | 02 | 1 | CARD-04 | N/A | unit (HTML assert) | `uv run pytest tests/test_app_cards.py -k "test_search_button_app_colored_hover or test_connected_card_search_now_button or test_footer_section_background" -q` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Coverage:** 8/8 requirement tasks green. 12 tests in `tests/test_stats_health.py` + 26 tests in `tests/test_app_cards.py` = 38 total, all pass.

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. Both `tests/test_stats_health.py` and `tests/test_app_cards.py` were updated in-phase with new assertions for the scaled stat cards, recessed sub-cards, colored borders, and app-colored hover states.*

---

## Manual-Only Verifications

All P61 requirements have at least one automated test asserting target Tailwind classes, Phosphor icon presence, Jinja2 conditional output, and htmx attributes. Visual fidelity to the artifact is best confirmed in a live browser but is not required for Nyquist compliance — class presence is the programmatic invariant.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pixel-level hero number sizing | STAT-01 | Computed font rendering | Inspect stat card hero values in DevTools; confirm computed font-size renders at 32px |
| Mini bar proportional widths | STAT-02 | Inline `style="width: X%"` calculation | With real Radarr at ~75% grab rate, observe bar fill width in DOM and browser |
| Hover accent rendering | CARD-04 | Hover pseudo-class | Hover over Search Now button on each app type (radarr/sonarr/lidarr); confirm text color shifts to app accent |

All manual items are **redundant** with automated class-presence tests — they verify visual rendering and interactive states, not structural correctness.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — all COVERED)
- [x] No watch-mode flags
- [x] Feedback latency < 10s (phase suites run in <1s each)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-18

---

## Validation Audit 2026-04-18

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tests mapped | 38 across 8 requirements |
| Requirements COVERED | 8/8 (STAT-01..04, CARD-01..04) |
| Requirements PARTIAL | 0 |
| Requirements MISSING | 0 |

**Status change:** `nyquist_compliant: false` → `true`. Original draft pre-classified all requirements as "visual / Browser check" with N/A automated commands. Phase 61 execution expanded `tests/test_stats_health.py` and `tests/test_app_cards.py` with assertions for every STAT/CARD requirement. This audit refreshes the Per-Task Verification Map to reference the real tests. **No new test generation required.**
