---
phase: 47
slug: test-hardening-state-search-edge-cases
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-09
---

# Phase 47 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Filesystem -> App | Config files (TOML, JSON, SQLite) read from disk may be corrupt or malicious | Config values, state data, DB schema |
| *arr API -> search engine | Mocked in tests; real boundary is API responses with unexpected data | Tag lists, wanted items, library counts |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-47-01 | Tampering | triggarr.toml | accept | Test-only phase: verifies existing behavior (exception propagation). No production code changes. | closed |
| T-47-02 | Tampering | state.json | accept | Existing recovery logic (json.JSONDecodeError catch -> defaults) already handles this. Tests verify it. | closed |
| T-47-03 | Denial of Service | SQLite DB | accept | Corrupt DB prevents startup -- acceptable for a single-user daemon. Tests document the behavior. | closed |
| T-47-04 | Information Disclosure | Tag resolution failure | accept | Fail-open by design: if tag can't be resolved, search all items rather than skip. Tests verify this existing behavior. | closed |
| T-47-05 | Denial of Service | Empty queue processing | accept | Empty queues are normal operation. Tests verify no unnecessary work done. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-47-01 | T-47-01 | Test-only phase — no production code changes. Tests verify existing TOML validation propagates correctly. | Claude | 2026-04-09 |
| AR-47-02 | T-47-02 | Existing recovery logic handles corrupt state.json. Tests verify and document the behavior. | Claude | 2026-04-09 |
| AR-47-03 | T-47-03 | Single-user daemon; corrupt DB causing startup failure is acceptable. Tests document the behavior. | Claude | 2026-04-09 |
| AR-47-04 | T-47-04 | Fail-open search on tag resolution failure is by design — better to search too much than miss items. | Claude | 2026-04-09 |
| AR-47-05 | T-47-05 | Empty queues are normal operation, zero-search is the correct response. | Claude | 2026-04-09 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-09 | 5 | 5 | 0 | Claude (gsd-secure-phase) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-09
