# Phase 73: Password Reset UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 73-password-reset-ui
**Areas discussed:** "Forgot password?" placement, Request-confirmation state, Confirm-page errors & token field, Cross-navigation links

---

## "Forgot password?" placement (RCOV-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Below Sign In button | Centered muted-text link under the submit button, small margin. Standard convention; keeps fields grouped, affordance clearly secondary. | ✓ |
| Right-aligned under password field | Small link directly under the password input, right-aligned. Tighter coupling to the field, but inserts a row between fields and button. | |

**User's choice:** Below Sign In button (centered, muted).
**Notes:** Shown only when `not needs_setup`. `login_page` doesn't currently pass `needs_setup` into context — the route must add it (D-01a).

---

## Request-confirmation state

| Option | Description | Selected |
|--------|-------------|----------|
| Replace form with confirmation + link to confirm | Hide the request button when `message` present; show neutral confirmation + onward link to the confirm step. | ✓ |
| Show confirmation above, keep request button | Render message but leave the request button visible (re-request, rate-limited 60s). Busier. | |
| Confirmation only, no onward link | Just the message; operator manually navigates to confirm. No obvious next step. | |

**User's choice:** Replace form with confirmation + onward link to confirm step.
**Notes:** Surfaced that there is no `GET /reset/confirm` route today — the onward affordance requires adding one (D-02a). Token value must never reach the `message`/context (D-02b).

---

## Confirm-page errors & token field

| Option | Description | Selected |
|--------|-------------|----------|
| Keep token error in top banner | Token failures stay in the centered top `error` banner (matches Phase 72 D-06/D-20, no backend change). Password problems inline per-field. | ✓ |
| Move token error inline under token field | Show token error under the token input; requires backend to also pass it in the `errors` dict (touches Phase 72 code). | |

**User's choice:** Keep token error in top banner; password errors inline.
**Notes:** Verified all three password error cases (empty / mismatch / over-72-byte) are already produced by the Phase 72 backend (routes.py:1791-1830) and rendered by the existing shell — no new error plumbing (D-03a).

---

## Cross-navigation links

| Option | Description | Selected |
|--------|-------------|----------|
| "Back to login" on both reset steps | Muted "Back to login" link at the bottom of both request and confirm. | ✓ |
| "Back to login" only on the request step | Only the entry page links back; confirm step has no back link. | |
| No cross-nav links | Keep reset pages link-free like login/setup. | |

**User's choice:** "Back to login" on both steps.
**Notes:** Small new affordance (login/setup don't cross-link); request→confirm onward link handled by D-02.

---

## Claude's Discretion

- Exact Tailwind classes / spacing for the link and confirmation block (match existing muted-link and card idioms).
- Exact copy for the onward link and "Back to login" label.
- Whether the confirmation hides the `<form>` or swaps the button (as long as no live request button shows alongside the confirmation).
- Template-internal handling of the message-present state (`{% if message %}` branch vs distinct step value).
- Test placement (extend the Phase 72 reset suite vs a UI-focused addition).

## Deferred Ideas

None — discussion stayed within the Phase 73 UI boundary.
