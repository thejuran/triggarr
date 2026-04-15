---
phase: 59
slug: security-hardening-address-shield-findings-shield-001-throug
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 59 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `pyproject.toml` |
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
| 59-01-01 | 01 | 1 | D-07,D-08,D-09 | SHIELD-001 | CSP header present with correct directives | unit | `uv run pytest tests/ -x -q -k csp` | ❌ W0 | ⬜ pending |
| 59-01-02 | 01 | 1 | D-04,D-05,D-06 | SHIELD-002 | API key not in settings template context | unit | `uv run pytest tests/ -x -q -k api_key` | ❌ W0 | ⬜ pending |
| 59-01-03 | 01 | 1 | D-01,D-02,D-03 | SHIELD-003 | Rate limiter blocks after 10 attempts | unit | `uv run pytest tests/ -x -q -k rate_limit` | ❌ W0 | ⬜ pending |
| 59-01-04 | 01 | 1 | D-10 | SHIELD-007 | IPv4-mapped IPv6 blocked | unit | `uv run pytest tests/ -x -q -k ssrf` | ❌ W0 | ⬜ pending |
| 59-01-05 | 01 | 1 | D-11,D-12 | SHIELD-005,011 | No user input in log messages | unit | `uv run pytest tests/ -x -q -k log` | ❌ W0 | ⬜ pending |
| 59-01-06 | 01 | 1 | D-13 | SHIELD-004 | Gitleaks ignores test fixtures | integration | `gitleaks detect --no-banner` | ❌ W0 | ⬜ pending |
| 59-01-07 | 01 | 1 | D-14 | SHIELD-009 | Auth-disabled warning periodic | unit | `uv run pytest tests/ -x -q -k disabled_warn` | ❌ W0 | ⬜ pending |
| 59-01-08 | 01 | 1 | D-15 | SHIELD-010 | Security comment in parse_changelog | grep | `grep -q 'Security boundary' triggarr/web/routes.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New test functions for rate limiter, CSP header, API key masking, IPv6 SSRF, log sanitization
- [ ] Update `tests/conftest.py` — adapt `_disabled_warned` reset for timestamp-based periodic warning
- [ ] `.gitleaksignore` file for test fixture false positives

*Existing pytest infrastructure covers framework needs — no new test framework installation required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Login page shows rate limit error | D-02 | Visual rendering of error message | Trigger 10+ failed logins, verify error banner renders |
| Settings page masks API key | D-05 | Visual template rendering | Load settings page, verify key is masked |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
