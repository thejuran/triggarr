---
status: secured
phase: 52-recent-activity-rail
threats_total: 5
threats_closed: 5
threats_open: 0
asvs_level: 1
audited: 2026-04-13
---

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-52-01 | Tampering | activity_rail.html entry.name | mitigate | CLOSED | `autoescape=True` at routes.py:50; all user-data fields use `{{ }}` with no `|safe` or `{% autoescape false %}` |
| T-52-02 | Tampering | SVG outcome icons | accept | CLOSED | Hardcoded SVG strings in conditional blocks, no user data in SVG markup |
| T-52-03 | Info Disclosure | relative_time_filter | accept | CLOSED | Filter receives only timestamp strings from search_history table; no secrets |
| T-52-04 | Tampering | base.html sidebar block | accept | CLOSED | Block defaults empty; only dashboard overrides with static partial include |
| T-52-05 | DoS | flex layout on all pages | accept | CLOSED | Single flex child equivalent to block flow; no client-controllable layout |

## Accepted Risks

- **T-52-02:** SVG icons hardcoded in template — no injection vector
- **T-52-03:** Timestamp-only data path — no secret exposure
- **T-52-04:** Server-controlled template inclusion — no user influence
- **T-52-05:** Trivial layout change — no performance impact

## Audit Trail

### 2026-04-13 — Initial Audit

| Metric | Count |
|--------|-------|
| Threats found | 5 |
| Closed | 5 |
| Open | 0 |
