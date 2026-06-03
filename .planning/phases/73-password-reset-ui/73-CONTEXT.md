# Phase 73: Password Reset UI - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

The browser-facing surface of the filesystem-token password recovery flow. Deliver RCOV-01 — the "Forgot password?" link on the login page (shown only when auth is already configured) — and finalize the styled request/confirm reset pages so a locked-out user can discover and complete recovery entirely from the browser, with pages that look and behave like `login.html`/`setup.html`.

**In scope:**
- The conditional "Forgot password?" affordance on `login.html` (visible only when `not needs_setup`), wired to `GET /reset/request`.
- Rendering the neutral request-confirmation state (the backend already passes a `message` context that `reset.html` does not yet render).
- A new `GET /reset/confirm` route so the confirm step (enter token + new password) is reachable directly from the request-confirmation's onward link — today the confirm step is only re-rendered on POST failure.
- Finalizing/verifying the confirm-page inline field errors (empty / mismatch / over-72-byte) and the top-level token-error banner.
- "Back to login" cross-navigation on both reset steps.

**Out of scope:**
- All backend behavior from Phase 72 — token mint/store/validate, session rotation, atomic write, rate-limiting, middleware exemption, the `error`/`errors`/`message` context contracts (LOCKED, do not change). Phase 73 consumes those contracts; it does not alter route logic, only adds the GET-confirm presentation route and the templates/markup.
- Count-only refresh (Track B / Phase 74), drain-timeout knob (Track C / Phase 75).
</domain>

<decisions>
## Implementation Decisions

### "Forgot password?" placement (RCOV-01)
- **D-01:** A centered, muted-text "Forgot password?" link sits **below the Sign In button** on `login.html`, separated by a small top margin (keeps the form fields visually grouped; recovery affordance is clearly secondary). It links to `GET /reset/request` (the `reset_request_page` route).
- **D-01a:** The link renders **only when `not needs_setup`** — absent during first-run setup. **`login.html` is rendered from THREE sites**, none of which currently pass `needs_setup`: `login_page` (routes.py:1256, the GET), and `login_post` on the rate-limit re-render (routes.py:1334) and the invalid-credentials re-render (routes.py:1373). Because Jinja treats an undefined variable as falsy, a bare `{% if not needs_setup %}` guard would render the link on any render path that omits the key — including a failed POST `/login` **during first-run setup**, leaking the link before auth is configured. Therefore: pass `needs_setup` (from `request.app.state.settings.auth.needs_setup`) into **every** `login.html` TemplateResponse context (all three sites) AND make the template guard defensive — `{% if needs_setup is defined and not needs_setup %}` — so a future render path that forgets the key fails closed (link hidden), not open. This is presentation plumbing, not auth logic.

### Request-confirmation state
- **D-02:** When the neutral `message` context is present (successful mint OR the H1 live-token no-op — both paths pass the same `message`), the request step **replaces the "Request Reset Token" button** with the neutral confirmation text plus an **onward affordance ("Enter reset token")** linking to the confirm step. The operator reads their logs, then clicks onward — no dead end.
- **D-02a:** The onward affordance requires a **new `GET /reset/confirm` route** that renders `reset.html` with `step: "confirm"` (and is reachable unauthenticated). **Exemption mechanism (corrected):** Phase 72 does NOT add `/reset` to `EXEMPT_PREFIXES` — `EXEMPT_PREFIXES` is exactly `("/health", "/static", "/login", "/setup")` (middleware.py:25). The reset exemption is an **exact-or-`/reset/` predicate** in the middleware dispatch (middleware.py:118: `path == "/reset" or path.startswith("/reset/")`), deliberately tightened so a hypothetical `/resetXYZ` route stays gated (a bare `startswith("/reset")` would over-expose it). `GET /reset/confirm` matches `startswith("/reset/")`, so it inherits the exemption automatically — **no middleware change, and DO NOT widen the exemption** (do not add `/reset` to `EXEMPT_PREFIXES`; `git diff middleware.py` must stay empty). Today only `GET /reset/request` + the two POSTs exist; the confirm step is otherwise only reachable by a failing POST. Mirror `reset_request_page` (routes.py:1635) for the handler shape. A `/resetXYZ`-stays-gated assertion is a blocking verification item.
- **D-02b:** The token value is NEVER placed in the `message` or any template context (Phase 72 D-02 / Pitfall 5) — the confirmation only points the operator at `docker logs` / `reset-token.txt`. Phase 73 must not surface the token anywhere in markup.

### Confirm-page errors & token field
- **D-03:** Token failures (bad / expired / used / superseded) stay in the **top-level centered generic `error` banner** ("Invalid or expired reset token"), matching the locked Phase 72 D-06/D-20 contract — **no backend change**. The token error is page-level (about the whole reset attempt), not a field-validation error.
- **D-03a:** Password-field failures stay **inline per-field** via the `errors` dict, keyed `new_password` / `confirm_password`. All three roadmap-named cases are ALREADY produced by the Phase 72 backend (routes.py:1791-1830) and rendered by the existing `reset.html` shell: empty → `new_password: "New password is required"`; mismatch → `confirm_password: "Passwords do not match"`; over-72-byte → `new_password: "Password must be 72 characters or fewer"`. Phase 73 finalizes/verifies this styling; it does not add new error plumbing.

### Cross-navigation
- **D-04:** A muted **"Back to login"** link at the bottom of **both** reset steps (request and confirm), linking to `GET /login` (`login_page`). The request→confirm onward link is covered by D-02. This is a small new affordance — `login.html`/`setup.html` do not currently cross-link — but it gives a user who lands on reset (or changes their mind) a clear way back.

### Claude's Discretion (planner/executor latitude)
- Exact Tailwind utility classes / spacing for the link and confirmation block (match the existing muted-link and card idioms in `login.html`/`base-auth.html`; reuse `text-triggarr-muted`, the same input/button classes already in `reset.html`).
- Exact copy for the onward link ("Enter reset token" vs "I have my token") and the "Back to login" label.
- Whether the request-confirmation hides the request `<form>` entirely or swaps its button — as long as a successful request does not show a live "Request Reset Token" button alongside the confirmation (D-02).
- Whether to handle the message-present state by a template `{% if message %}` branch inside `step == "request"` or a distinct step value — template-internal, no contract impact.
- Test placement (extend the existing reset test suite from Phase 72 vs a UI-focused addition) — follow the established suite layout.
</decisions>

<specifics>
## Specific Ideas

- The reset pages already extend `base-auth.html` and reuse `login.html`'s card (`max-w-[420px]`, `bg-triggarr-card`, `border-triggarr-border`, `rounded-lg p-6`), the `triggarr-green` brand line, and identical input/button classes — Phase 72's shell is already close to login/setup parity. Phase 73 is finishing touches (message state, links, GET-confirm route, `needs_setup` wiring), not a redesign.
- Errors use `aria-live="polite"` already in the shell — preserve that on any new/changed error or message regions.
- Success has no dedicated UI: a valid confirm 303-redirects to the dashboard auto-logged-in (Phase 72 D-13). "Transition to the logged-in dashboard" (roadmap SC #3) is the backend redirect, not a Phase 73 page.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design spec (source of truth for this track)
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §2 — Track A design; §2.3 (flow / neutral-confirmation copy contract), §2.6 (component boundaries). RCOV-01 is the UI requirement this phase delivers.

### Phase 72 context (the locked backend contracts this UI consumes)
- `.planning/phases/72-password-reset-backend-token-lifecycle/72-CONTEXT.md` — D-02 (token never in any response/context), D-06/D-20 (generic `error` for token, per-field `errors` for password; HTML page not JSON), D-13 (confirm success → 303 dashboard auto-login). DO NOT re-decide these.

### Codebase patterns to mirror (read before planning)
- `triggarr/templates/login.html` — the card/branding/input/button idiom and the muted-link target style; add the conditional "Forgot password?" link here.
- `triggarr/templates/setup.html` — second styling anchor for parity.
- `triggarr/templates/base-auth.html` — the shared auth-page base (`{% block content %}`); reset/login/setup all extend it.
- `triggarr/templates/reset.html` — the Phase 72 shell to finalize: already has `step == "request"` / `step == "confirm"` branches, generic `error`, per-field `errors`; MISSING the `message` render and the cross-nav links.
- `triggarr/web/routes.py:1233` §`login_page` — add `needs_setup` to the `login.html` context (D-01a).
- `triggarr/web/routes.py:1635` §`reset_request_page` — handler shape to mirror for the new `GET /reset/confirm` (D-02a).
- `triggarr/web/routes.py:1644` §`reset_request_post` — already passes the neutral `message` context (the value Phase 73 must render); confirms the copy.
- `triggarr/web/middleware.py:25,115-118` — the reset exemption is an exact-or-`/reset/` predicate (`path == "/reset" or path.startswith("/reset/")`), NOT a `/reset` entry in `EXEMPT_PREFIXES` (which stays `("/health", "/static", "/login", "/setup")`). The new `GET /reset/confirm` matches `startswith("/reset/")` and inherits the exemption with NO middleware change; do not add `/reset` to `EXEMPT_PREFIXES` (that would over-expose `/resetXYZ`). Verify reachability AND that `/resetXYZ` stays gated, in tests.

### Project state
- `.planning/STATE.md` — v2.10 milestone shape; cross-cutting thread (Track A adds zero new network attack surface; the token must never reach any HTTP response/template).
- `.planning/codebase/CONVENTIONS.md` — template/Tailwind conventions, redacting-sink discipline.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/templates/reset.html` — the Phase 72 shell; finalize in place (add `message` render, onward link, "Back to login").
- `triggarr/templates/login.html` — muted-text and card idioms to copy for the "Forgot password?" link.
- `reset_request_page` (routes.py:1635) — exact handler shape for the new `GET /reset/confirm`.
- `login_page` (routes.py:1233) — the single route edit: add `needs_setup` to context.

### Established Patterns
- Server-rendered Jinja via `templates.TemplateResponse`; pages extend `base-auth.html`. CSP nonce is injected globally (`_csp_nonce_processor`, routes.py:84) — no inline scripts/styles needed here (pure markup + Tailwind classes).
- Error/message regions use `aria-live="polite"`.
- The token value must never appear in any template context (Phase 72 D-02) — Phase 73 renders only `error`, `errors`, and `message`, never a token.

### Integration Points
- `login.html` ← new conditional link; `login_page` route ← `needs_setup` context key (D-01a).
- New `GET /reset/confirm` route in `routes.py` registers with the existing router and inherits the `/reset` exempt prefix (D-02a) — confirm reachable-unauthenticated in tests.
- `reset.html` ← `message` render + onward link (request step) + "Back to login" (both steps).
- No new `app.state`, no new middleware, no backend logic changes beyond the GET-confirm route and the `needs_setup` context add.
</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within the Phase 73 UI boundary. Count-only refresh (Phase 74) and the drain-timeout/docs track (Phase 75) are separate, already-scoped phases.
</deferred>

---

*Phase: 73-password-reset-ui*
*Context gathered: 2026-06-03*
