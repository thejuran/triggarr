---
phase: 73-password-reset-ui
plan: "01"
subsystem: auth-ui
tags: [auth, password-reset, templates, jinja2, tdd]
dependency_graph:
  requires: [72-password-reset-backend]
  provides: [RCOV-01]
  affects: [triggarr/web/routes.py, triggarr/templates/login.html, triggarr/templates/reset.html]
tech_stack:
  added: []
  patterns:
    - "Defensive Jinja2 guard: {% if needs_setup is defined and not needs_setup %} (fails closed)"
    - "TDD RED/GREEN per task (test commits precede feat commits)"
    - "Message-state branching in request step ({% if message %} ... {% else %} ...form... {% endif %})"
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/templates/login.html
    - triggarr/templates/reset.html
    - tests/test_reset.py
decisions:
  - "Defensive guard is 'needs_setup is defined and not needs_setup' (not bare 'not needs_setup') so any future render path that omits the key fails closed"
  - "GET /reset/confirm handler mirrors reset_request_page exactly; no middleware.py change needed (exempt via startswith('/reset/'))"
  - "Back-to-login placed after step branches (before closing </div>) so it renders on both request and confirm steps"
  - "Message-state branch replaces the submit form entirely when message is present; neutral {{ message }} text + onward link are the only rendered elements"
metrics:
  duration: "293s (~5 minutes)"
  completed: "2026-06-03"
  tasks_completed: 3
  files_changed: 4
---

# Phase 73 Plan 01: Password Reset UI Summary

Delivered the browser-facing surface of the filesystem-token password recovery flow: conditional "Forgot password?" link on all three login.html render sites (GET, invalid-credentials POST, 429 rate-limit POST), new GET /reset/confirm route, neutral request-confirmation message with onward confirm link (for both first-mint and H1 live-token no-op paths), and "Back to login" cross-navigation on both reset steps.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests: GET /reset/confirm reachability and exemption non-widening | 19cf801 | tests/test_reset.py |
| 1 (GREEN) | Add needs_setup to all 3 login.html contexts; register GET /reset/confirm | c67c7cd | triggarr/web/routes.py |
| 2 (RED) | Failing tests: forgot-password link, message-state, Back-to-login | 0f5f5fc | tests/test_reset.py |
| 2 (GREEN) | Template: forgot-password link, message-state, onward link, Back-to-login | 5020197 | triggarr/templates/login.html, triggarr/templates/reset.html |
| 3 | Green gate: full reset suite + ruff clean (verification only, no code) | (green-gate) | — |

## Verification Results

- `uv run pytest tests/test_reset.py -x -q`: **29 passed** (Phase 72 + Phase 73 tests)
- `uv run ruff check triggarr/ tests/`: **All checks passed**
- `git diff triggarr/web/middleware.py`: **empty** (no exemption change)
- `grep -c 'needs_setup' triggarr/web/routes.py`: 8 occurrences (3 context dicts + existing uses)
- Defensive guard confirmed: `{% if needs_setup is defined and not needs_setup %}` in login.html
- `reset_confirm_page` registered at routes.py:1647 (GET /reset/confirm)
- "Back to login" present in reset.html at line 71
- Token grep in reset.html: only appears in label text, input field name, and instructional prose — never as a rendered `{{ token }}` variable

## Key Decisions

1. **Defensive guard form**: Used `{% if needs_setup is defined and not needs_setup %}` rather than bare `{% if not needs_setup %}`. This fails closed — any future render path that omits the `needs_setup` key from context will hide the link instead of showing it. All three login.html render sites (login_page GET, login_post 429, login_post invalid-credentials) pass `needs_setup=auth.needs_setup` reusing the existing `auth` local in scope at each site.

2. **No middleware.py change**: GET /reset/confirm is exempt via the existing `path.startswith("/reset/")` predicate in AuthMiddleware.dispatch (line 118). EXEMPT_PREFIXES stays exactly `("/health", "/static", "/login", "/setup")` — `/reset` was NOT added. The /resetXYZ regression test asserts the auth boundary (302→/login for a browser request), not the routing outcome, so a bypass cannot masquerade as a passing 404.

3. **Message-state branching**: The `{% if message %} ... {% else %} ...form... {% endif %}` structure inside the request step hides the "Request Reset Token" submit button entirely when a confirmation message is present. The onward link to `reset_confirm_page` appears only in the message branch. Never references a `token` variable — only `{{ message }}`.

4. **Context-boundary token-absence**: Test (iii) in `test_request_confirmation_message_state` reads the routes.py source and asserts both message-branch context dicts contain exactly `{"step", "message"}` with no token-valued key. This pins the invariant at the TemplateResponse context boundary, not just the rendered body/headers.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functionality is fully wired.

## Threat Surface Scan

No new network endpoints or auth paths beyond those specified in the plan's threat model.

- T-73-01 (token leak): Mitigated — `reset.html` references only `{{ message }}` in the message branch; `grep -n "token" reset.html` shows only label text and input field, never a `{{ token }}` variable. Context-boundary test proves both message-branch dicts in `reset_request_post` have no token key.
- T-73-02 (exemption widening): Mitigated — `git diff triggarr/web/middleware.py` is empty; `test_reset_confirm_route_did_not_widen_exemption` asserts 302→/login for /resetXYZ (not 404, not 200).
- T-73-03 (link leak on POST re-render during setup): Mitigated — defensive guard at all three render sites; `test_forgot_password_link_absent_during_setup_rate_limit` seeds 10 failures to force the 429 path and asserts the link is absent.

## TDD Gate Compliance

Both tasks followed RED → GREEN:
- Task 1: `test(73-01)` commit 19cf801 (RED) precedes `feat(73-01)` commit c67c7cd (GREEN)
- Task 2: `test(73-01)` commit 0f5f5fc (RED) precedes `feat(73-01)` commit 5020197 (GREEN)

## Self-Check

Files verified:
- triggarr/web/routes.py: modified (needs_setup at 3 sites + reset_confirm_page)
- triggarr/templates/login.html: modified (defensive forgot-password link)
- triggarr/templates/reset.html: modified (message-state + Back-to-login)
- tests/test_reset.py: modified (7 new Phase 73 tests: 2 Task 1 + 5 Task 2)
- triggarr/web/middleware.py: NOT modified (verified via git diff)
