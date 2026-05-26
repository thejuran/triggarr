# Plan 66-05: SEC-01 part 2 — Nonce-based CSP — SUMMARY

**Date:** 2026-05-26
**Plan:** 66-05-PLAN.md
**Requirement:** SEC-01 (part 2 of 2; part 1 was plan 66-04)
**Type:** execute (autonomous: false — final checkpoint requires browser smoke)
**Wave:** 3
**Status:** Implementation complete; awaiting Task 5 human-verify checkpoint

## What Shipped

Completed the SEC-01 migration:

1. `SecurityHeadersMiddleware.dispatch` generates a per-request CSP nonce via `secrets.token_urlsafe(16)`, stores it on `request.state.csp_nonce` BEFORE `call_next`, and composes `script-src 'self' 'nonce-{nonce}'` (dropping `'unsafe-inline'`).
2. `triggarr/web/routes.py` adds the sync `_csp_nonce_processor(request)` context processor that surfaces the nonce to Jinja templates as `{{ csp_nonce }}`. Wired via `Jinja2Templates(env=..., context_processors=[_csp_nonce_processor])` — not `templates.env.globals` (anti-pattern: globals are process-wide, breaking the per-request contract).
3. The 4 inline `<script>` blocks (base.html, dashboard.html, setup.html, settings.html) carry `nonce="{{ csp_nonce }}"`.
4. **Codex M0 fix (Task 1.5):** `remove_instance` returns `HX-Redirect` for HTMX callers — forces a full browser navigation so the new CSP nonce activates. Without this, the HTMX body-swap of the fresh settings page would inherit the OLD document's CSP policy, silently blocking the new `<script nonce="NEW">` tags.
5. Tests cover: directive-level CSP assertions, per-request nonce uniqueness, header/body nonce parity, HX-Redirect contract, 303 backwards compat for non-HTMX callers, and a defense-in-depth invariant (only ONE `hx-target="body"` exists in templates).

## Tasks Completed

| Task | Type | Outcome |
|------|------|---------|
| 1. Pre-flight gates | execute | All 3 gates passed (zero inline handlers from 66-04; SEC-03 from 66-02; CSP still had unsafe-inline pre-state). |
| 1.5. HX-Redirect on `remove_instance` (codex M0) | execute | New routes.py code path + 3 new tests (hx-redirect, 303-compat, body-swap-invariant). |
| 2. Wire nonce middleware + context_processor + tag 4 templates | execute | middleware.py + routes.py + 4 templates all updated. `'unsafe-inline'` GONE from script-src; style-src retained per D-04. |
| 3. Update CSP test + add parity + uniqueness tests | execute | test_security_headers_csp_present rewritten with directive-level checks; new test_csp_nonce_changes_per_request + test_csp_nonce_matches_html_script_tag. |
| 4. Final source-grep sweep | execute | All 13 acceptance-criteria greps pass. |
| **5. Human-verify browser smoke check** | **checkpoint** | **PENDING — requires browser DevTools session.** |

## Files Changed

| File | +/- |
|------|-----|
| `triggarr/web/middleware.py` | +5 −5 |
| `triggarr/web/routes.py` | +21 −1 |
| `triggarr/templates/base.html` | +1 −1 |
| `triggarr/templates/dashboard.html` | +1 −1 |
| `triggarr/templates/setup.html` | +1 −1 |
| `triggarr/templates/settings.html` | +1 −1 |
| `tests/test_middleware.py` | +44 −9 |
| `tests/test_web.py` | +94 −1 |

## Test Results

- Full suite — 934 passed (+5 new tests over 929 Wave 1+2 baseline)
- `uv run ruff check triggarr/ tests/` — All checks passed
- All 13 source-grep acceptance criteria from PLAN.md verified.

## Key Architecture

| Concern | Solution |
|---------|----------|
| Where the nonce is generated | `SecurityHeadersMiddleware.dispatch` as the FIRST statement (Pitfall 7 — must precede `call_next` so the template render can read it). |
| How the nonce reaches templates | `request.state.csp_nonce` → sync `_csp_nonce_processor(request)` context_processor → `{{ csp_nonce }}` in Jinja. |
| Why context_processor, not Jinja globals | Globals are process-wide; nonce must be per-request. Anti-pattern guard: `grep -c "templates.env.globals\['csp_nonce'\]" triggarr/web/routes.py` returns 0. |
| Why sync `def` not `async def` | FastAPI/Starlette does not support async context_processors (Pitfall 8). |
| Why the empty-string default | `getattr(request.state, "csp_nonce", "")` protects error-page renders where the middleware did not run; `<script nonce="">` would be inert, which is the correct fail-closed behavior. |
| HTMX + CSP nonce lifetime (codex M0) | `remove_instance` returns `HX-Redirect` for HTMX callers. Forces full browser navigation, refreshes the CSP header, activates the new nonce. Only ONE handler in Triggarr triggers `hx-target="body"`; the defense-in-depth invariant test ensures no future handler can silently break this contract. |

## Codex Adversarial Findings Addressed

- **M0 / HIGH (HTMX body-swap CSP nonce lifetime):** Task 1.5 — `remove_instance` returns `HX-Redirect` for HTMX. Plus 3 new tests including a body-swap-invariant grep that fails CI if any future handler reintroduces the pattern.

## Decisions Covered

- D-01 (drop `'unsafe-inline'` from script-src) ✓
- D-02 (`secrets.token_urlsafe(16)` + `request.state.csp_nonce` + Jinja global via context_processor) ✓
- D-03 (all 4 inline scripts get nonce) ✓
- D-04 (style-src retains `'unsafe-inline'`) ✓
- D-05 (revised — verified zero inline event handlers via 66-04 Task 1 pre-flight gate) ✓

## Awaiting Task 5: Browser Smoke Check

This plan is `autonomous: false` because TestClient does not enforce CSP at runtime. The only honest acceptance is a real browser opening the four pages with DevTools Console open and confirming zero CSP-violation entries. See plan 66-05 Task 5 for the detailed checklist, including the **codex M0 HTMX body-swap check** (remove an instance and confirm the post-navigation auth-method dropdown warning still fires).
