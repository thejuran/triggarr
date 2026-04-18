---
phase: 60
slug: foundation-header
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-15
verified: 2026-04-18
---

# Phase 60 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_header_redesign.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds (phase suite), ~18 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

Note: HDR-06 was deferred during Phase 60 execution (D-05) and reassigned to Phase 63. It is NOT a Phase 60 validation target.

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 60-01-01 | 01 | 1 | FONT-01 | N/A | unit (HTML assert) | `uv run pytest tests/test_header_redesign.py::test_body_has_font_sans_class -q` | ✅ green |
| 60-01-02 | 01 | 1 | FONT-02 | N/A | unit (HTML assert) | `uv run pytest tests/test_header_redesign.py::test_version_badge_uses_font_geist_mono -q` | ✅ green |
| 60-02-01 | 02 | 1 | HDR-01 | N/A | unit (HTML assert) | `uv run pytest tests/test_header_redesign.py::test_header_has_py4_padding -q` | ✅ green |
| 60-02-02 | 02 | 1 | HDR-02 | N/A | unit (HTML assert) | `uv run pytest tests/test_header_redesign.py -k "test_nav_has_phosphor_icons or test_nav_links_use_text_15px" -q` | ✅ green |
| 60-02-03 | 02 | 1 | HDR-03 | N/A | unit (HTML assert) | `uv run pytest tests/test_header_redesign.py -k "test_nav_center_aligned_absolute or test_header_has_w64_zones" -q` | ✅ green |
| 60-02-04 | 02 | 1 | HDR-04 | CSRF POST form preserved | unit (HTML assert) | `uv run pytest tests/test_header_redesign.py -k "test_logout_has_css_pipe_divider or test_logout_has_sign_out_icon or test_logout_is_post_form or test_logout_hover_red" -q` | ✅ green |
| 60-03-01 | 03 | 1 | HDR-05 | N/A | unit (route + htmx wiring) | `uv run pytest tests/test_header_redesign.py -k "test_connection_pill_partial_endpoint or test_connection_pill_disconnected_state or test_connection_pill_loaded_via_htmx_in_header" -q` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Coverage:** 7/7 requirement tasks green. All 20 tests in `tests/test_header_redesign.py` pass.

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. `tests/test_header_redesign.py` was added as part of Plan 60-03 and provides 20 DOM-assertion tests across all P60 requirements (excluding deferred HDR-06 which is covered by Phase 63).*

---

## Manual-Only Verifications

All P60 requirements have at least one automated test asserting the presence of target Tailwind classes, Phosphor icon classes, htmx attributes, and template structure. Visual fidelity to the AIDesigner artifact is best confirmed in a live browser, but is not required for Nyquist compliance — class presence is the programmatic invariant.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser-rendered font appearance | FONT-01, FONT-02 | Visual font rendering | Inspect body text and version badge in DevTools; confirm computed `font-family` resolves to system sans-serif / Geist Mono respectively |
| Pixel-level header layout match | HDR-01, HDR-02, HDR-03 | Visual fidelity to artifact | Compare header against `.aidesigner/runs/.../design.html` |
| Connection pill live behavior | HDR-05 | Requires live instance state | Run dashboard with at least one Radarr/Sonarr instance configured; observe green dot pulsing and 30s refresh |

All manual items are **redundant** with automated DOM assertions — they verify visual rendering, not structural correctness.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — all COVERED)
- [x] No watch-mode flags
- [x] Feedback latency < 5s (phase suite runs in <1s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-18

---

## Validation Audit 2026-04-18

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tests mapped | 20 across 7 requirements |
| Requirements COVERED | 7/7 (FONT-01, FONT-02, HDR-01..HDR-05) |
| Requirements PARTIAL | 0 |
| Requirements MISSING | 0 |

**Status change:** `nyquist_compliant: false` → `true`. The original draft VALIDATION.md was written before execution and pre-classified all requirements as "visual / Browser check" with N/A automated commands. Phase 60 execution subsequently added `tests/test_header_redesign.py` (20 tests) which provides full automated coverage. This audit refreshes the Per-Task Verification Map to reference the real tests. **No new test generation required.**

HDR-06 was intentionally removed from this map — it was deferred in D-05 and reassigned to Phase 63.
