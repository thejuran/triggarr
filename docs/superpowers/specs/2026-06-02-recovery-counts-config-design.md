# Design Spec — Recovery, Counts & Config Parity

**Date:** 2026-06-02
**Status:** Approved (brainstorming) — ready for `/gsd:new-milestone`
**Source backlog items:** Phase 999.1 (UI password recovery), Phase 999.2 (count-only refresh)
**Project:** Triggarr — Python 3.11+ automation daemon (FastAPI + htmx + Tailwind CSS v4), triggers searches in Radarr/Sonarr/Lidarr on a schedule. Latest shipped: v2.9.

---

## 1. Summary

One milestone, **three disjoint feature tracks**, each independently phaseable (matches the v2.9 disjoint-track precedent), closed by a shared docs + walkthrough step. No code is shared between tracks, so GSD can phase them independently.

| Track | Feature | Primary files | Risk |
|-------|---------|---------------|------|
| **A** | UI password recovery (filesystem-token reset) | `triggarr/auth.py`, `triggarr/web/routes.py`, `triggarr/web/middleware.py`, new templates, tests | **High** (auth surface) |
| **B** | Count-only refresh (dry-run, no search) | `triggarr/search/engine.py`, `triggarr/search/scheduler.py`, `triggarr/web/routes.py`, `triggarr/templates/partials/app_card.html`, tests | Medium (hot-path refactor) |
| **C** | DEBT-06: expose graceful-shutdown drain timeout in settings UI | `triggarr/models/config.py`, `triggarr/templates/settings.html`, `triggarr/web/routes.py`, `triggarr/search/scheduler.py`, tests | Low (mirrors existing knobs) |

**Documentation deliverable (cross-track):** correct the stale deferred table in planning state — **DEBT-07 (request timeout), DEBT-08 (page size), DEBT-03 (search-history cap) are already shipped** (present in `settings.html` and written by the settings POST handler). Only DEBT-06 was genuinely unexposed.

### Why these three together

Track A and Track B are the two parked backlog items the user asked to ship. Track C is a small, self-contained rider discovered during context exploration: re-checking the deferred list against live code revealed DEBT-07/08/03 already done and DEBT-06 as the single cheap, settings-surface-aligned item left. Folding it in brings the settings UI to full config parity and lets us correct the stale record.

### Out of scope (deliberately excluded)

UI-01/02/03 (pixel-exact visual verification — needs human, behind first-run setup, not launch-visible), PERF-01/02/03, SCALE-01/02, AUDIT-01, OBS-01 (substantial v2-scoped features, not riders), and the `--color-triggarr-primaryDark` duplicate-token cosmetic cleanup (unrelated). These stay parked.

---

## 2. Track A — UI Password Recovery

### 2.1 Problem

Triggarr is single-user with built-in auth (v2.6): bcrypt `password_hash`, signed session cookies, `session_secret`. A locked-out user currently must hand-edit `triggarr.toml` (clear `username`/`password_hash`) and re-run `/setup`. A real user got locked out by typing a plaintext value into the bcrypt `password_hash` field — a silent failure, since `bcrypt.checkpw` against a non-hash always rejects. We need a self-service recovery flow that never requires hand-editing the TOML.

### 2.2 Trust model

With no email and a single user, "recovery" proves **host/filesystem access**, not identity. The mechanism: Triggarr mints a CSPRNG token and writes it to two places only a host operator can read — the application log and a file in the config volume. Possession of that token *is* the authorization.

This adds **no new network attack surface**: a remote attacker who can hit the reset endpoints still cannot read the token (it is never returned in any HTTP response), and the endpoints are rate-limited.

### 2.3 Flow

1. **Login page** gains a "Forgot password?" link, visible only when auth is configured (`not auth.needs_setup`). (When `needs_setup` is true there is no password to recover — the user is already routed to `/setup`.)
2. **Request token** — `POST /reset/request`:
   - Mint a CSPRNG token (`secrets.token_urlsafe(32)`).
   - Store in-memory: `app.state.reset_token = (token, expiry_monotonic)` with a **15-minute TTL** (`time.monotonic() + 900`). Minting overwrites any prior token (invalidating it).
   - Write the token to **(a)** the Loguru log at `warning` level (operator-visible via `docker logs`) and **(b)** a file in the config volume at `<config_dir>/reset-token.txt`, mode `0600`, written atomically (temp-then-rename, mirroring `_atomic_toml_write`).
   - Return a neutral confirmation page ("If recovery is available, a reset token has been written to the application logs and the config volume. Check `docker logs` or `/config/reset-token.txt`.") — the token value is **never** in the HTTP response.
3. **Confirm reset** — `POST /reset/confirm` with `token`, `new_password`, `confirm_password`:
   - Validate token: present, not expired, `secrets.compare_digest` match. On failure → generic error ("Invalid or expired reset token"), no detail leak.
   - Validate passwords: non-empty, match, within bcrypt 72-byte limit (reuse `hash_password`'s `ValueError`).
   - On success (under `search_lock`, mirroring `change_password`):
     - `new_hash = hash_password(new_password)`.
     - **Rotate `session_secret`** (`generate_session_secret()`) — invalidates all existing sessions (same rationale as `change_password`).
     - Build updated `AuthConfig` via `model_copy`, atomic TOML write, `chmod 0600`, reload settings, `_sync_auth_state`, refresh redaction secrets + logging.
     - **Delete the token file**, clear `app.state.reset_token`.
     - Auto-login: set a fresh session cookie under the new secret (cookie attributes mirror `login_post`/`change_password`).
     - Redirect to dashboard.

### 2.4 Security discipline

- **Rate-limit both endpoints**, reusing the `search_now` monotonic-timestamp pattern (`app.state.last_search_time`-style keyed dict, e.g. `app.state.last_reset_time`):
  - `/reset/request`: ~1 per 60s — prevents log/file flooding.
  - `/reset/confirm`: a few attempts per minute — defense-in-depth on the CSPRNG token.
- Token compared with `secrets.compare_digest` (constant-time).
- Token value appears exactly once, at mint, in the operator-only log + file. Never logged at confirm time, never in any response body.
- Token file: atomic write (temp-then-rename), mode `0600`, **deleted on successful reset** and rewritten (replacing prior) on each new mint.
- `password_hash` / `session_secret` stay `SecretStr`; `collect_secrets` already feeds the redacting sink — refresh it after reset.
- **Middleware exemption:** add `/reset` to `EXEMPT_PREFIXES` in `triggarr/web/middleware.py` (currently `("/health", "/static", "/login", "/setup")`) — a locked-out user cannot authenticate, so the reset routes must be reachable unauthenticated, exactly like `/login` and `/setup`.

### 2.5 Why in-memory token (not persisted)

A container restart invalidating a pending token is acceptable — the user simply clicks "Forgot password?" again. This keeps **zero new persistent auth-state**: nothing extra in the TOML, no hashed-token-compare-on-boot path, no cleanup obligation beyond the transient `reset-token.txt` (itself deleted on use).

### 2.6 Components & boundaries

- `triggarr/auth.py` — add `generate_reset_token() -> str` (thin `secrets.token_urlsafe` wrapper) for symmetry with the existing `generate_*` helpers. Token *storage/validation* lives in the route layer (it is request/app-state-scoped), not in `auth.py`.
- `triggarr/web/routes.py` — `reset_request_page` (GET form), `reset_request_post` (POST mint), `reset_confirm_post` (POST apply). Reuse `_atomic_toml_write`, `_settings_to_dict`, `hash_password`, `generate_session_secret`, `sign_session`, `_sync_auth_state`, `collect_secrets`, `setup_logging`.
- New templates: a "Forgot password?" affordance on `login.html`, and a reset page (request + confirm forms) styled to match `login.html`/`setup.html`.
- `triggarr/web/middleware.py` — add `/reset` to `EXEMPT_PREFIXES`.

### 2.7 Tests

- Token: mint returns urlsafe token; stored with correct TTL; expiry rejects after 15 min (monotonic-clock injectable or via direct state manipulation); single-use (consumed on success); new mint invalidates prior.
- Confirm: wrong/expired token → generic error, no state change; password mismatch / empty / >72 bytes → field errors; success rotates `session_secret`, writes hash, deletes token file, auto-logs-in (cookie set).
- Session rotation: a cookie signed with the pre-reset secret fails `validate_session` after reset.
- Rate-limit: second `/reset/request` within 60s throttled; rapid `/reset/confirm` attempts throttled.
- Middleware: `/reset/*` reachable unauthenticated; still no other route exposed.
- Redaction: token value does not survive into any HTTP response; `reset-token.txt` is mode 0600 and removed after success.

---

## 3. Track B — Count-Only Refresh

### 3.1 Problem

Counting and searching are a single inseparable pass. Each `run_*_cycle` in `engine.py` fetches the full missing/cutoff lists (the source of accurate counts), then immediately slices a batch off the cursor and searches it. After a bulk quality-profile change a user wants the **true post-change counts** without launching a search wave or advancing the cursor. The expensive part (querying *arr) already exists; this is the existing cycle with the search loop short-circuited.

### 3.2 Engine seam extraction

Each `run_*_cycle` currently does:

```
fetch missing/cutoff
  → cache raw counts (missing_count, cutoff_count, total_items)
  → set connection health (connected=True, unreachable_since=None)
  → resolve tags
  → filter (monitored / tag / unreleased) + compute eligible/searchable counts
  → [ slice batch + search loop + advance cursor ]      ← search-only block
  → stamp last_run / last_success
```

**Extract the shared prefix** (everything up to and including filter + eligible-count caching, plus the connection-health update) into a per-app helper:

- `refresh_radarr_counts(...)`, `refresh_sonarr_counts(...)`, `refresh_lidarr_counts(...)` — or a shared core parameterised by app-specific filter/tag callbacks. (Planner's choice; the per-app form is acceptable given the existing per-app cycle functions, provided filtering logic is not duplicated in a way that can drift — prefer factoring the shared filter sequence.)

The helper does: **fetch → cache raw counts → set connection health → resolve tags → filter → cache eligible/searchable counts**, and returns (on fetch failure: set `connected=False`, `unreachable_since`, return — same as the cycle's current abort branch).

Then:

- `run_*_cycle` calls the helper, then performs the **slice + search loop + cursor advance + `last_run`/`last_success` stamp** (behavior unchanged — guaranteed by the existing cycle tests, which must stay green).
- The **count-only path** calls **only** the helper and stops.

**Cursor guarantee:** because slicing lives *exclusively* in the cycle function (never in the helper), the count-only path **cannot** advance the cursor. This is a structural guarantee, not a `count_only` flag the hot loop must reason about. (The design note's pitfall (a) — never advance the cursor — is satisfied by construction.)

### 3.3 State semantics on the count path

A count-only refresh genuinely fetches from *arr, so it shares *some* bookkeeping but not all:

| State | Count-only path | Rationale |
|-------|-----------------|-----------|
| `connected`, `unreachable_since` | ✅ updated | It genuinely probed reachability. |
| `missing_count` / `cutoff_count` / eligible / searchable counts | ✅ updated | This is the whole point. |
| `last_run` / `last_success` | ❌ untouched | These mean "last *search*", and no search ran. |
| SAFETY-03 failure counter (`app.state.search_failures`) | ❌ untouched | That counter governs *scheduled-search* escalation; a manual count probe must not reset or trip it. |

A fetch failure during count-only flips the card to `connected=False` (via the helper's health update) but does **not** escalate the scheduler.

### 3.4 Surface

- **Endpoint:** `POST /api/refresh-counts/{app}/{instance}` — structurally identical to `search_now`: same `search_lock` acquisition, same rate-limit pattern (`SEARCH_RATE_LIMIT_SECONDS`-style, can share or use a sibling constant), same `_build_app_context` → `partials/app_card.html` response — **minus** the search and the failure-counter/`last_run` updates. Validates `app_name in APP_TYPES`, instance enabled, name length, exactly like `search_now`. This is a **documented, stable API surface** (the scripting path the backlog note asked for).
- **UI:** a **"Refresh counts"** button on `app_card.html` next to "Search Now", htmx-posting to the endpoint and swapping the returned card partial. Mirror the "Search Now" in-flight/disabled affordance (the v2.9 walkthrough already hardened that button's in-flight state).

### 3.5 Tests

- Helper returns correct raw + eligible/searchable counts for Radarr/Sonarr/Lidarr fixtures.
- Helper **never advances the cursor** (assert cursor unchanged before/after).
- Count path does **not** stamp `last_run`/`last_success` and does **not** touch `app.state.search_failures`.
- Count path **does** update `connected`/`unreachable_since` (success and failure cases).
- Endpoint parity: rate-limit, lock, app/instance validation, 200 + card on success, error handling mirrors `search_now`.
- Existing cycle tests stay green (the refactor is behavior-preserving for the search path).

---

## 4. Track C — DEBT-06: Drain-Timeout Settings Knob

### 4.1 Problem

The graceful-shutdown drain timeout is currently read only from `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` at scheduler import time (`_read_shutdown_drain_timeout`, default 60.0s, clamped `>=1.0`). It is not a config field and not exposed in the settings UI — the one genuinely-unexposed config knob, while DEBT-07/08/03 are already settings-UI knobs.

### 4.2 Design

- Add to `GeneralConfig` (`triggarr/models/config.py`):
  `shutdown_drain_timeout: float = Field(default=60.0, ge=1.0)` — bounded to defend against a typo disabling the drain (same defensive intent as `max_consecutive_failures`'s bounds).
- Add a numeric input to `triggarr/templates/settings.html` mirroring the existing `max_consecutive_failures` / `request_timeout` inputs, with help text documenting the env-override precedence.
- Wire it through the settings POST handler in `routes.py` (`safe_*` parse + persist alongside the other `general.*` fields).

### 4.3 Precedence (the one real decision)

**Config field is the default; the env var overrides it when set** (12-factor: an explicit env override beats a persisted file). The scheduler reads the configured value, then applies `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` if present, keeping the `>=1.0` clamp. This **preserves the documented env knob** for ops who already set it (no silent behavior change for existing deployments) and adds the UI path for everyone else.

Implementation note: the drain timeout is currently a module-level constant read at import. To honor a config value it must be read from `settings` at scheduler-construction/shutdown time rather than import time — refactor `_read_shutdown_drain_timeout` to take the configured default and apply the env override on top, called where `settings` is available (lifespan/scheduler setup). Document precedence in the field help text and release notes.

### 4.4 Tests

- Config field: default 60.0; rejects `<1.0` (validation); accepts valid floats.
- Precedence: env var set → env wins over config; env unset → config value used; clamp `>=1.0` applied to both sources.
- Settings round-trip: value persists through the settings POST handler and reloads.

---

## 5. Cross-Track Close

- **Docs:** README / settings docs updated for the new drain-timeout knob and the password-recovery flow (operator instructions: where to read the reset token). In-app changelog entry. Correct the stale deferred table (DEBT-07/08/03 shipped; DEBT-06 now shipped).
- **Walkthrough (milestone-end, on deployed NAS build):** exercise (A) forgot-password → read token from logs/volume → reset → auto-login; (B) "Refresh counts" updates counts without launching a search or advancing the cursor; (C) drain-timeout knob saves and round-trips in settings.
- **Verification floor:** all existing tests stay green (965 baseline), ruff clean, Docker build succeeds, SecretStr discipline maintained (no token/hash/secret in any response or non-redacted log).

## 6. Testing Strategy (summary)

pytest-asyncio (`asyncio_mode=auto`), following existing patterns. Per-track coverage as enumerated in §2.7, §3.5, §4.4. Security-sensitive Track A gets the most adversarial coverage (token lifecycle, rate-limit, redaction, session rotation).

## 7. Open questions / deferrals

None blocking. All design decisions resolved in brainstorming:
- Recovery trust model: filesystem-token. ✅
- Token lifecycle: in-memory, 15-min TTL, single-use, restart-invalidated. ✅
- Abuse defense: rate-limit both endpoints. ✅
- Engine seam: extract fetch+count+filter helper (no `count_only` flag). ✅
- Refresh surface: button + documented API endpoint, mirror `search_now`. ✅
- Count-path state: health yes, `last_run`/failure-counter no. ✅
- Milestone shape: three independent tracks. ✅
- DEBT-06 precedence: config default, env overrides. ✅
