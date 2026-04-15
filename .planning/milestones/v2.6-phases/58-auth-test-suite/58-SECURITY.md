---
phase: 58
slug: auth-test-suite
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-15
---

# Phase 58 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| test -> middleware | Tests exercise auth enforcement via TestClient; no real network | Session cookies, API keys, HTTP headers |
| test -> routes | Tests exercise route handlers via TestClient with real templates | Form data (credentials), cookies, redirect URLs |
| test -> full app stack | Integration tests exercise complete middleware + routes + auth helpers chain | Multi-step flows with config writes, credential creation |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-58-01 | Spoofing | Session cookie | mitigate | Tests verify wrong-secret (D-07) and expired cookies rejected at middleware level | closed |
| T-58-02 | Tampering | API key header | mitigate | Tests verify empty, whitespace, and invalid API keys return 401 JSON | closed |
| T-58-03 | Information Disclosure | Open redirect | mitigate | `_safe_next_url()` sanitizes `?next=` param; tests verify external and protocol-relative URLs rejected | closed |
| T-58-04 | Elevation of Privilege | Disabled mode bypass | accept | Intentional config choice; `_disabled_warned` flag + `logger.warning` in middleware; test verifies warning fires | closed |
| T-58-05 | Spoofing | Setup -> login flow | mitigate | Integration test verifies credentials created during setup actually work for login (7-step E2E flow) | closed |
| T-58-06 | Elevation of Privilege | API key after setup | mitigate | Integration test verifies API key from saved TOML config authenticates requests immediately | closed |
| T-58-07 | Spoofing | Password change session | accept | Old session works after password change by design (session_secret unchanged); test confirms behavior | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-58-01 | T-58-04 | Disabled auth mode is an intentional configuration choice for trusted networks. Warning log ensures visibility. | Phase 58 threat model | 2026-04-15 |
| AR-58-02 | T-58-07 | Password change does not rotate session_secret — existing sessions remain valid. This is by design to avoid mass session invalidation. | Phase 58 threat model | 2026-04-15 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-15 | 7 | 7 | 0 | gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-15
