---
phase: 72-password-reset-backend-token-lifecycle
plan: "02"
subsystem: auth/reset
tags: [auth, password-reset, token-mint, rate-limit, atomic-write, tdd]
dependency_graph:
  requires:
    - generate_reset_token() in triggarr/auth.py (Plan 01)
    - RESET_REQUEST_RATE_LIMIT_SECONDS in triggarr/web/routes.py (Plan 01)
    - app.state.reset_token / app.state.last_reset_time init (Plan 01)
    - /reset middleware exemption (Plan 01)
    - tests/test_reset.py RED suite (Plan 01)
  provides:
    - _write_reset_token_file() private helper in triggarr/web/routes.py
    - GET /reset/request → reset_request_page handler in triggarr/web/routes.py
    - POST /reset/request → reset_request_post handler in triggarr/web/routes.py
  affects:
    - tests/test_reset.py (10 request/mint tests go GREEN)
tech_stack:
  added:
    - tempfile (stdlib — mkstemp for atomic token-file write)
  patterns:
    - os.fchmod(fd, 0o600) on temp fd BEFORE os.replace (M1 pre-rename chmod)
    - search_now optimistic+locked rate-limit pattern (D-14/D-15)
    - H1 live-token no-op guard (supersession only on expired/absent tokens)
    - D-17 log-before-file ordering (warning log first so file-write failure is non-fatal)
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
decisions:
  - "D-02: token value IS in the single mint warning log line (deliberate operator-only recovery channel); token NEVER in any HTTP response"
  - "D-17: warning log line emitted BEFORE file write; OSError in file write is non-fatal (in-memory token is authority)"
  - "M1: os.fchmod(fd, 0o600) on the open temp fd before os.replace — no post-rename chmod window"
  - "H1: live-token no-op guard inside search_lock before mint decision; timestamp update still happens (rate-limit stamp set before H1 check)"
  - "File write dispatched via run_in_executor after lock release — does not hold search_lock during I/O"
metrics:
  duration: ~20 minutes
  completed: 2026-06-03
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 1
---

# Phase 72 Plan 02: Reset-Request/Mint Path — GREEN Implementation Summary

**One-liner:** Reset-request path implemented — CSPRNG mint with optimistic+locked rate-limit, H1 live-token no-op guard, M1 pre-rename 0600 chmod, and D-17 log-before-file ordering; all 10 request/mint tests go GREEN.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | GREEN: reset_request_page, reset_request_post, _write_reset_token_file | 050c9c9 | triggarr/web/routes.py |

---

## What Was Built

### Task 1 — GREEN Implementation (050c9c9)

**triggarr/web/routes.py:** Three additions:

**`import tempfile`** — added to stdlib imports (alongside os/asyncio/secrets/time). `generate_reset_token` added to the auth import block.

**`_write_reset_token_file(path: Path, token: str) -> None`** — private synchronous helper, dispatched via run_in_executor:
- Mirrors `_atomic_toml_write` (config.py:95-163): `tempfile.mkstemp(dir=path.parent)` → `os.fchmod(fd, 0o600)` (M1) → `f.write(token)` → `f.flush()` → `os.fsync` → `os.replace` → dir fsync
- M1 deviation: `os.fchmod(fd, 0o600)` is called on the OPEN temp fd BEFORE `os.replace` — the renamed file is already 0600 with no post-rename chmod window or crash-path
- OSError before rename: `logger.error("{path} - {exc}")` — NEVER the token value (Pitfall 1); unlinks temp; does NOT re-raise (D-17 non-fatal)
- OSError after rename (dir fsync): `logger.warning("{path} - {exc}")` — proceed (file is there)
- `finally: os.close(dir_fd)` — always releases dir fd

**`reset_request_page` (GET /reset/request)** — thin handler returning `reset.html` with `step="request"`. No auth required (M2 exemption from Plan 01 covers this path).

**`reset_request_post` (POST /reset/request)** — full implementation:
1. Optimistic rate-limit check before lock (`last_reset_time["request"]`, `RESET_REQUEST_RATE_LIMIT_SECONDS=60`) → 429
2. `async with search_lock:` — re-check rate-limit (double-check pattern, mirrors DRSEC-03) → 429; set `last_reset_time["request"] = now`
3. H1 live-token guard (inside lock): read `stored = app.state.reset_token`; if `stored is not None and time.monotonic() < stored[1]` → return neutral confirmation immediately (no mint, no TTL reset, no file write)
4. Mint path (only when no live token): `token = generate_reset_token()`, `app.state.reset_token = (token, time.monotonic() + 900)`, then `logger.warning("... {token}", token=token)` — the deliberate operator-only recovery channel (D-02 + RESEARCH #4; intentionally NOT in collect_secrets/redacting sink)
5. Lock released before file write
6. `await run_in_executor(None, _write_reset_token_file, token_path, token)` — non-blocking I/O after lock
7. Return neutral `TemplateResponse` with `step="request"` and `message=<neutral copy>` — context NEVER contains token (Pitfall 5)

**Key ordering invariant (D-17):** warning log line with token is emitted INSIDE the lock, before lock release and before file write. A file-write failure still leaves the token recoverable from the log.

---

## Deviations from Plan

None — plan executed exactly as written.

The only ruff fix required: the original implementation used a `try/except Exception: pass` guard around the `run_in_executor` call (SIM105 violation). This was simplified to a direct `await` — `_write_reset_token_file` already handles OSError internally and does not re-raise (D-17), so the outer guard was redundant.

Tracked as: `[Rule 3 - Blocking] ruff SIM105: replaced try/except/pass with direct await` — inline fix, no behavioral change.

---

## Verification Results

```
uv run ruff check triggarr/web/routes.py    # All checks passed
uv run pytest tests/test_reset.py::test_request_mints_token \
  tests/test_reset.py::test_token_file_written_0600 \
  tests/test_reset.py::test_token_not_in_response \
  tests/test_reset.py::test_token_in_mint_log \
  tests/test_reset.py::test_token_ttl_stored_correctly \
  tests/test_reset.py::test_new_mint_supersedes_prior \
  tests/test_reset.py::test_live_token_request_is_noop \
  tests/test_reset.py::test_request_rate_limited \
  tests/test_reset.py::test_reset_routes_unauthenticated \
  tests/test_reset.py::test_no_other_route_exposed -v    # 10 passed
uv run pytest tests/ --ignore=tests/test_reset.py -q    # 984 passed (baseline unchanged)
```

Redaction grep verified:
- `grep -nE "logger\.(error|warning)" triggarr/web/routes.py` — all file-write OSError log lines reference only `{path}` and `{exc}`, never `{token}`
- The intentional mint warning at the single `logger.warning("... {token}", ...)` call DOES include the token value (D-02 recovery channel confirmed)

Confirm-path tests still RED (Plan 03): `test_expired_token_rejected`, `test_token_single_use`, and all `test_confirm_*` / `test_pre_reset_*` / `test_new_cookie_*` / `test_password_*` / `test_token_file_deleted_*` / `test_confirm_rate_limited` — these hit POST /reset/confirm which is not yet implemented.

---

## Known Stubs

None introduced by this plan. The neutral confirmation message wording ("If recovery is available, a reset token has been written...") is intentionally minimal per CONTEXT.md note — Phase 73 owns the final styled copy. The contract (neutral, no token, points at log+file) is locked.

---

## Threat Flags

No new threat surface beyond what is covered in the plan's threat_model. All four STRIDE mitigations verified:
- T-72-redaction: token absent from all HTTP responses (test_token_not_in_response GREEN); present in mint warning log (test_token_in_mint_log GREEN); file-write error paths log only path+exc
- T-72-fileperm: os.fchmod(fd, 0o600) before os.replace (M1); test_token_file_written_0600 GREEN
- T-72-flood: 60s rate-limit with double-check; test_request_rate_limited GREEN
- T-72-supersede-dos: H1 live-token guard inside lock; test_live_token_request_is_noop GREEN

---

## TDD Gate Compliance

RED gate: tests were already committed RED in Plan 01 (commit 3b11314) — the RED gate was satisfied in Wave 1.
GREEN gate: implementation committed in this plan (commit 050c9c9) — feat(72-02) commit exists after the RED test commit. Gate sequence: test(72-01) → feat(72-02). COMPLIANT.

---

## Self-Check: PASSED

Files exist:
- triggarr/web/routes.py — FOUND (reset_request_page, reset_request_post, _write_reset_token_file)

Commits exist:
- 050c9c9 — FOUND (feat(72-02): implement reset_request_page, reset_request_post, _write_reset_token_file)
