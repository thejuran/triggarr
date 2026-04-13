---
phase: 48
slug: foundations-navigation-chrome
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-13
---

# Phase 48 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| repo -> runtime static | woff2 files shipped in Docker image served by FastAPI StaticFiles mount | Static font binaries (no execution semantics) |
| browser -> static/css | Compiled output.css loaded by base.html via `request.url_for` | CSS stylesheet (presentation only) |
| request object -> Jinja template | `request.url.path` and `request.url_for(...).path` used for class selection | Server-known path strings |
| test process -> filesystem | Test reads output.css from repo tree | Committed repo artifacts only |
| test process -> in-memory app | TestClient issues GET against locally-constructed app | No network egress |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-48-01 | Tampering | Vendored Geist Mono woff2 files | mitigate | Downloaded from official Vercel/Geist release tag; 2 files, both <512KB | closed |
| T-48-02 | Information Disclosure | Relative URL in @font-face | accept | Repo-relative path, no cross-origin request | closed |
| T-48-03 | Denial of Service | Large font file inflating page weight | mitigate | Latin subset only, `font-display: swap` prevents FOIT | closed |
| T-48-04 | Tampering | CSS content from design mockup | accept | Static literals from internal design artifact, no third-party CSS | closed |
| T-48-05 | Spoofing | Font-face src URL | accept | Repo-controlled relative path, Same-Origin Policy | closed |
| T-48-06 | Injection (XSS) | `current_path` comparison in base.html | accept | Framework-normalized path in `{% if %}` comparison, Jinja2 autoescape | closed |
| T-48-07 | Injection (XSS) | `update_info.latest_version` in nav | accept | Server-side semver validation, autoescape, no new data flow | closed |
| T-48-08 | CSRF Bypass | Nav template changes | accept | GET-only template changes, OriginCheckMiddleware untouched | closed |
| T-48-09 | Tampering | Sticky nav z-30 vs modal z-50 | accept | Correct z-index layering preserved | closed |
| T-48-10 | Information Disclosure | dot-pulse span in update chip | accept | Pure visual element, guarded by `update_available` conditional | closed |
| T-48-11 | Information Disclosure | Test asserts on output.css | accept | Committed repo artifacts only, no secrets | closed |
| T-48-12 | Denial of Service | Test reads full output.css | accept | <200KB file, trivial memory cost | closed |
| T-48-13 | Tampering | Monkeypatch _update_info | mitigate | `try/finally` blocks restore state in both update-info tests | closed |
| T-48-14 | Injection | TestClient GETs fixed routes | accept | Fixed paths, no user input | closed |
| T-48-15 | Spoofing | Mocked update_info fake URL | accept | Rendered as string only, never fetched | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-48-02 | Relative font path, no user data, Same-Origin Policy | gsd-security-auditor | 2026-04-13 |
| AR-02 | T-48-04 | Static CSS from internal design artifact | gsd-security-auditor | 2026-04-13 |
| AR-03 | T-48-05 | Repo-controlled relative path | gsd-security-auditor | 2026-04-13 |
| AR-04 | T-48-06 | Framework path in boolean comparison, autoescape | gsd-security-auditor | 2026-04-13 |
| AR-05 | T-48-07 | Semver-validated server value, autoescape | gsd-security-auditor | 2026-04-13 |
| AR-06 | T-48-08 | GET-only changes, CSRF middleware untouched | gsd-security-auditor | 2026-04-13 |
| AR-07 | T-48-09 | z-30 nav < z-50 modal, correct layering | gsd-security-auditor | 2026-04-13 |
| AR-08 | T-48-10 | Visual element only, no data exposure | gsd-security-auditor | 2026-04-13 |
| AR-09 | T-48-11 | Committed files only, no elevated privileges | gsd-security-auditor | 2026-04-13 |
| AR-10 | T-48-12 | Trivial file size, no resource concern | gsd-security-auditor | 2026-04-13 |
| AR-11 | T-48-14 | Fixed routes, no injection surface | gsd-security-auditor | 2026-04-13 |
| AR-12 | T-48-15 | String assertion only, never fetched | gsd-security-auditor | 2026-04-13 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-13 | 15 | 15 | 0 | gsd-security-auditor (sonnet) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-13
