# Phase 72: Password Reset Backend & Token Lifecycle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 72-password-reset-backend-token-lifecycle
**Areas discussed:** (gray-area menu presented; user declined to select — design spec trusted as-is)

---

## Discussion flow

The design spec `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §2 + §7 already locked every blocking decision for Track A / Phase 72 ("§7 Open questions / deferrals: None blocking. All design decisions resolved"). Codebase scouting confirmed all referenced patterns exist exactly as the spec describes (`change_password`, `search_now` rate-limit, `_atomic_toml_write`, `EXEMPT_PREFIXES`, the `generate_*` auth helpers).

A gray-area selection menu was presented offering four optional discussion topics:

| Option | Description | Selected |
|--------|-------------|----------|
| Rate-limit scope & response | per-IP vs global key; confirm window; throttle response shape | |
| Token-file lifecycle edge cases | partial-mint, stale-file-at-startup, deletion-failure-on-success | |
| Confirm-failure UX contract | response shape/status codes feeding Phase 73's UI | |
| Auto-login & redirect mechanics | cookie attributes + 303 redirect vs login-with-flash | |

**User's choice:** Declined the gray-area menu; on follow-up chose **"Write CONTEXT.md from spec now"** — trust the spec + scouted codebase patterns as-is, no further questioning.

**Notes:** Because the spec is exhaustive for this track, the four menu topics were resolved as Claude's-discretion calls grounded in the existing codebase patterns rather than re-asked. See the discretion resolutions below.

---

## Claude's Discretion (resolved, not asked)

- **Rate-limit scope (D-14/D-15):** Chose the global `app.state.last_reset_time` monotonic-key pattern from `search_now` (the pattern the spec explicitly names) over login's per-IP `_check_rate_limit`. Rationale: reset limits guard log/file flooding + token-guessing throughput, matching `search_now`'s threat shape; login's per-IP limiter targets distributed credential brute-force. Windows: request ~60s, confirm a few/min; `429` on throttle; optimistic-then-locked double-check on confirm (it holds `search_lock`).
- **Token-file edge cases (D-16..D-19):** Atomic temp-then-rename mirroring `_atomic_toml_write` + `0o600`; log-line-first ordering so a file-write failure still leaves the token recoverable from logs; stale file at startup is harmless (in-memory token is the authority) — no boot-time cleanup added; deletion-failure-on-success warns rather than blocks (reset already committed, leftover token already consumed).
- **Confirm-failure response shape (D-20):** HTML page re-render with an `errors: dict[str,str]` field-error contract mirroring `change_password`'s `security_password.html` pattern (not JSON), so Phase 73's server-rendered htmx UI reuses the same context keys. Generic `error` for token failures (no leak), per-field `errors` for password failures.
- **Auto-login & redirect (D-13):** Cookie attributes mirror `login_post`/`change_password` exactly (`COOKIE_MAX_AGE`, `httponly`, `samesite=lax`, `secure=is_secure_request`); 303 redirect to dashboard; user lands logged in (no second login step).

## Deferred Ideas

- "Forgot password?" link + styled request/confirm reset pages → Phase 73 (RCOV-01).
- Count-only refresh → Phase 74 (Track B). Drain-timeout knob + deferred-record correction → Phase 75 (Track C).
- No scope creep surfaced — discussion stayed within the Track A backend boundary.
