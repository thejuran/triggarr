---
phase: 66-security-hardening
verified: 2026-05-26T00:00:00Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
---

# Phase 66: Security Hardening — Verification Report

**Phase Goal:** The application's HTTP attack surface is narrowed: inline scripts are gone, credential-containing URLs are rejected at save time, and session and Basic auth handling are defensively validated.
**Verified:** 2026-05-26
**Status:** PASSED
**Re-verification:** No — initial verification.
**Verifier:** Claude (gsd-verifier) — goal-backward analysis against `main @ 3474da9`.

---

## Goal Assessment (4 ROADMAP Success Criteria)

| # | Success Criterion | Status | File:Line Evidence |
|---|---|---|---|
| 1 | CSP `script-src` no longer contains `'unsafe-inline'`; all inline `<script>` blocks use a per-response nonce | IMPLEMENTED | `triggarr/web/middleware.py:43-44,50-57` (nonce gen + `'nonce-{nonce}'`); `templates/base.html:116`, `dashboard.html:48`, `setup.html:70`, `settings.html:253` (all 4 inline scripts carry `nonce="{{ csp_nonce }}"`) |
| 2 | *arr URL with `apikey=` is rejected with clear validation error before config write | IMPLEMENTED | `triggarr/models/config.py:65-89` (`@field_validator("url")` with `key.lower().startswith("apikey")` + exact D-08 message at L87) |
| 3 | Basic auth header with null bytes / control chars is rejected with 401 + WARNING; decode failure also logged at WARNING | IMPLEMENTED | `triggarr/web/middleware.py:25-27` (`_has_control_chars` helper); `:175` (`validate=True` strict b64); `:177-186` (control-char branch + 401); `:179` and `:205` (two `basic_auth_rejected` WARNING sites for `control_char` and `decode_failure`) |
| 4 | On startup, session_secret < 32 chars logs WARNING naming problem + remediation | IMPLEMENTED | `triggarr/startup.py:49-71` (`_warn_if_session_secret_short` helper, modeled on `check_localhost_urls`); `:215` (wired into `startup()` main flow at step 4.7, between `check_localhost_urls` and `validate_connections`) |

**Score: 4/4 success criteria fully implemented.**

---

## Detailed Truth-by-Truth Verification

### SC-1: CSP nonce migration

| Check | Evidence | Status |
|---|---|---|
| `grep -c "script-src 'self' 'unsafe-inline'" triggarr/web/middleware.py` returns 0 | Result: `0` | VERIFIED |
| `grep -c "'nonce-{nonce}'" triggarr/web/middleware.py` returns 1 | Result: `1` | VERIFIED |
| Zero inline event-handler attributes in any template | `grep -rEn 'on(click\|change\|submit\|load\|blur\|focus\|keydown\|keyup\|input)=' triggarr/templates/` returns nothing (exit 1) | VERIFIED |
| All 4 inline `<script>` blocks have `nonce="{{ csp_nonce }}"` | base.html:116, dashboard.html:48, setup.html:70, settings.html:253 — all four match | VERIFIED |
| No inline `<script>` block without a nonce exists in templates | Negative grep returns no results | VERIFIED |
| `data-action=` markers replace migrated handlers in partials | `security_apikey.html`: 5 markers; `log_viewer.html`: 3 markers | VERIFIED |
| `_csp_nonce_processor` wired via `Jinja2Templates(env=..., context_processors=[_csp_nonce_processor])` not `templates.env.globals` (per-request safety) | `routes.py:66-80` | VERIFIED |
| Empty-string default protects error-page renders | `getattr(request.state, "csp_nonce", "")` at `routes.py:77` | VERIFIED |
| Playwright browser smoke check confirmed real-browser CSP enforcement, 0 violations | Documented in 66-05-SUMMARY.md §"Task 5 — Browser Smoke Check Results" | VERIFIED (human-verified) |

### SC-2: SEC-02 URL validation

| Check | Evidence | Status |
|---|---|---|
| `@field_validator("url")` exists on `InstanceConfig` | `models/config.py:65-89` | VERIFIED |
| Uses `key.lower().startswith("apikey")` (codex M2 — catches URL-encoded variants) | `models/config.py:86` | VERIFIED |
| Exact D-08 message text matches | `models/config.py:87`: `"URL must not contain an apikey= query parameter. Use the API Key field instead."` | VERIFIED |
| Validator runs at model construction, before `_atomic_toml_write` / `search_lock` | Pydantic semantics: `@field_validator` runs at `InstanceConfig(**form_data)` construction, which happens before `async with search_lock` in `routes.py` | VERIFIED |
| `parse_qsl(keep_blank_values=True)` so `?apikey=` (empty value) is rejected | `models/config.py:85` | VERIFIED |
| Test exercises 8 reject cases (including URL-encoded `apikey%3D...`) | `tests/test_config.py:250-268` — 8 parametrized cases all PASS | VERIFIED |
| Test exercises 6 accept cases for legitimate non-apikey queries (subpath, base, token) | `tests/test_config.py:271-286` — 6 parametrized cases all PASS | VERIFIED |
| Behavioral spot-check: `InstanceConfig(url='http://radarr:7878?apikey=leak', ...)` raises `ValidationError` containing `apikey=` | Confirmed via `uv run python -c "..."` | PASS |

### SC-3: SEC-03 Basic auth hardening

| Check | Evidence | Status |
|---|---|---|
| `_has_control_chars(s)` helper at module scope covers 0x00..0x1F + 0x7F | `middleware.py:25-27` (`any(ord(c) < 0x20 or ord(c) == 0x7F for c in s)`) | VERIFIED |
| `base64.b64decode(authorization[6:], validate=True)` (codex M3 strict decode) | `middleware.py:175` | VERIFIED |
| Control-char check on both username AND password before `compare_digest` | `middleware.py:177` (`_has_control_chars(username) or _has_control_chars(password)`) | VERIFIED |
| Two `logger.warning("basic_auth_rejected reason={reason} client_ip={ip}", ...)` call sites | `middleware.py:179` (`reason="control_char"`) and `:205` (`reason="decode_failure"`) | VERIFIED |
| 401 with `WWW-Authenticate: Basic realm="Triggarr"` on rejection | `middleware.py:183-186` and `:209-212` | VERIFIED |
| PII minimization — no `{username}`, `{password}`, `{decoded}`, `{authorization}` placeholders in any log format string | Grep returns 0 matches | VERIFIED |
| `client_ip` derived with `None` guard (`request.client.host if request.client else "unknown"` — Pitfall 2) | `middleware.py:172` | VERIFIED |
| Tests cover null-byte, control-char (U+0010), DEL (U+007F), decode failure, AND non-ASCII regression guard | `tests/test_auth_middleware.py:334, 364, 389, 414, 441` — all 5 PASS | VERIFIED |
| Behavioral spot-check: `_has_control_chars` returns True for `\x00` and `\x7F`, False for non-ASCII (`hellöü`) | Confirmed via inline Python | PASS |

### SC-4: SEC-04 session_secret startup warning

| Check | Evidence | Status |
|---|---|---|
| `_warn_if_session_secret_short(settings: Settings) -> None` helper exists | `startup.py:49-71` | VERIFIED |
| Modeled on `check_localhost_urls` (sync, one-shot — NOT `_warn_if_auth_disabled` which doesn't exist) | Same shape as `check_localhost_urls` at `startup.py:25-46`; D-14 revision correctly cited | VERIFIED |
| Wired into `startup()` main flow at step 4.7, alongside `check_localhost_urls` | `startup.py:211-215` (`check_localhost_urls(settings)` at 4.6, then `_warn_if_session_secret_short(settings)` at 4.7) | VERIFIED |
| Trigger: `not needs_setup AND len(session_secret) < 32` (D-13) | `startup.py:65-67` | VERIFIED |
| Warning message names the problem AND the remediation; includes U+2192 (→) arrow | `startup.py:69-70`: `"auth.session_secret is shorter than 32 characters -- regenerate via Settings → Security or set a longer value in config.toml"` — U+2192 confirmed via `repr()` | VERIFIED |
| SecretStr discipline: `.get_secret_value()` used ONLY for `len()` (never logged) | `startup.py:67` — only invocation; D-07 honored | VERIFIED |
| Test `tests/test_startup.py::test_warn_if_session_secret_short` covers warn, no-warn-on-long, no-warn-on-needs_setup | Test at `test_startup.py:138`; included in 24-test `test_startup.py` PASS | VERIFIED |

**Minor stylistic note (non-blocking):** CONTEXT D-14 phrased the dash before "regenerate" as an em-dash (`—`); the source uses `--` consistent with `check_localhost_urls` and the rest of the codebase's logging style. Functionally identical and matches existing-pattern intent. The mandatory U+2192 arrow (in "Settings → Security") is preserved.

---

## Codex Adversarial Findings Resolution

| Finding | Severity | Status | Evidence |
|---|---|---|---|
| **M0** — HTMX body-swap CSP nonce lifetime: `remove_instance` HTMX response would let body-swap inherit old CSP nonce, silently breaking `<script nonce="NEW">` on freshly-loaded settings page | HIGH | RESOLVED | `routes.py:819-825` — HTMX callers get `HX-Redirect` (forces full navigation); non-HTMX get 303. Tests at `test_web.py:1298` (HX-Redirect) and `:1329` (body-swap defense-in-depth grep — only ONE `hx-target="body"` allowed in templates) both PASS |
| **M1** — Silent log-only UX on SEC-02 validation failure (user sees no field-level error, only stale form) | MED | ACCEPTED DEFERRAL | 66-01-SUMMARY.md explicitly documents this as accepted per D-08 deferral; current `routes.py:565-569` catches ValidationError, logs WARNING, 303-redirects. Future UX phase can layer field-level surfacing. |
| **M2** — URL-encoded variant `?apikey%3Dsecret` would bypass `key.lower() == "apikey"` because parse_qsl decodes the key to `apikey=secret` | MED | RESOLVED | `models/config.py:86` — `key.lower().startswith("apikey")` instead of `==`; tests at `test_config.py:259-260` exercise `?apikey%3Dsecret` and `?apikey%3D%73ecret` — both PASS |
| **M3** — `base64.b64decode("!!!!")` would silently return `b""` (non-strict decode), letting the `decode_failure` WARNING never fire for malformed payloads | MED | RESOLVED | `middleware.py:175` — `validate=True` parameter forces `binascii.Error` (a `ValueError` subclass) into the `except` branch; test `test_basic_auth_decode_failure_logs_warning` confirms WARNING is logged |

---

## Decision Coverage (D-01 through D-14)

```
$ gsd-sdk query check.decision-coverage-plan ".planning/phases/66-security-hardening" ".planning/phases/66-security-hardening/66-CONTEXT.md"
{
  "passed": true,
  "skipped": false,
  "total": 14,
  "covered": 14,
  "uncovered": [],
  "message": "All trackable CONTEXT.md decisions are covered by plans."
}
```

**14/14 locked decisions covered.** Includes the two 2026-05-26 revisions:
- **D-05 (revised):** Inline event-handler attributes migrated to `addEventListener` / `data-action` before unsafe-inline drop — verified at runtime by zero-match grep.
- **D-14 (revised):** `_warn_if_session_secret_short` correctly modeled on `check_localhost_urls` (not the nonexistent `_warn_if_auth_disabled`).

---

## Test Results

```
$ uv run pytest tests/ -x -q
............... [snip] ...............
934 passed, 27 warnings in 20.01s

$ uv run ruff check triggarr/ tests/
All checks passed!
```

- **Full suite:** 934 tests PASS (target was ≥934; baseline was 857 → +77 new tests across the phase as advertised in the verification protocol).
- **Lint:** Ruff clean.
- **Targeted SC verification runs:**
  - SEC-01 CSP/nonce/HX-Redirect tests: 5/5 PASS
  - SEC-02 URL validator tests: 14/14 parametrized PASS
  - SEC-03 Basic auth tests: 5/5 PASS
  - SEC-04 startup warning: 1/1 PASS (plus 24/24 `test_startup.py`)
- **Behavioral spot-checks:** SEC-02 validator raises with `apikey=` in message; `_has_control_chars` correctly distinguishes control chars from non-ASCII printables.

---

## Atomic Commit Trail

`git log --oneline 837fb45..HEAD` shows the per-plan, per-task commit cadence expected from a TDD execution:

```
3474da9 docs(66-05): close Task 5 browser smoke check (PASSED via Playwright)
00238e1 docs(66-05): SUMMARY for SEC-01 part 2 nonce wiring (pre-checkpoint)
a4f7447 test(66-05): update CSP test + add nonce header/body parity test (SEC-01 part 2, Task 3)
f7ee2b8 feat(66-05): wire CSP nonce middleware + drop unsafe-inline from script-src (SEC-01 part 2)
cc84aac fix(66-05): force full nav on HTMX remove_instance to refresh CSP nonce (codex M0)
3e93163 docs(66-04): SUMMARY for SEC-01 part 1 inline event handler migration
339e926 refactor(66-04): migrate partial inline handlers to data-action + add bindLogViewerControls
7fb7f3f refactor(66-04): migrate base/setup/settings inline event handlers to addEventListener
7a18e9e docs(66): SUMMARY.md for Wave 1 plans (66-01, 66-02, 66-03)
1be3169 refactor(66-03): split line 146 to satisfy E501
a148981 feat(66-03): add _warn_if_session_secret_short startup check (SEC-04)
1cc1a77 feat(66-02): reject control chars in Basic auth credentials + log decode failures
18d937c test(66-03): add failing tests for SEC-04 session_secret startup warning
73cec82 test(66-02): add failing tests for SEC-03 control-char rejection + decode warning
e5844c3 feat(66-01): reject apikey= in InstanceConfig.url (SEC-02)
37509bd test(66-01): add failing tests for SEC-02 apikey= URL validator
[...planning artifacts above this point...]
```

Clean test-then-feat TDD pattern across all 3 RED/GREEN tasks (66-01, 66-02, 66-03). 66-04 / 66-05 used `refactor` + `feat` + `test` per the migration-vs-feature distinction. The codex M0 fix is committed as `fix(66-05): force full nav on HTMX remove_instance`. No squashes, no amends to published commits.

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description (from REQUIREMENTS.md) | Status | Evidence |
|---|---|---|---|---|
| SEC-01 | 66-04, 66-05 | CSP `script-src` no longer includes `'unsafe-inline'`; inline scripts use per-response nonce | SATISFIED | SC-1 above; both inline-handler migration (66-04) and nonce wiring (66-05) shipped |
| SEC-02 | 66-01 | URL validation at config save rejects `apikey=` query parameter | SATISFIED | SC-2 above; validator + 8 reject + 6 accept tests |
| SEC-03 | 66-02 | Basic auth decoder rejects null bytes / control chars; decode failures logged at WARNING | SATISFIED | SC-3 above; 5 dedicated tests including non-ASCII regression guard |
| SEC-04 | 66-03 | Startup validation logs WARNING when session_secret < 32 chars | SATISFIED | SC-4 above; helper + 3-scenario test |

No orphaned requirements. All 4 SEC-* requirements declared in REQUIREMENTS.md as "Phase 66" are claimed by at least one plan and satisfied by code.

---

## Anti-Pattern Scan

No blockers found in phase-modified files. Reviewed:
- `triggarr/web/middleware.py` — clean; `_has_control_chars`, `request.client` None-guard, strict b64, two paired WARNING sites with PII-min format strings.
- `triggarr/models/config.py` — clean; validator placed BEFORE `at_least_one_search_count` (per Pydantic v2 semantics); narrow `startswith("apikey")` rule preserves legit subpath/query setups.
- `triggarr/startup.py` — clean; SecretStr `.get_secret_value()` used only inside `len()`, never in a log line; helper mirrors proven `check_localhost_urls` shape; `needs_setup` guard prevents first-run false positives.
- `triggarr/web/routes.py` — clean; `_csp_nonce_processor` is sync (correct for FastAPI/Starlette), `getattr(..., "csp_nonce", "")` provides fail-closed default for pre-middleware error renders, `Jinja2Templates(env=..., context_processors=[...])` avoids the process-wide `.env.globals` anti-pattern noted in 66-05-SUMMARY.
- 4 inline `<script>` blocks across templates — all properly nonced; partials use `data-action` markers + delegated listeners on parent elements that survive `hx-swap` cycles (security_apikey via `#apikey-section` parent; log_viewer via `bindLogViewerControls` rebind on `htmx:afterSwap`).
- No `TBD`, `FIXME`, or `XXX` debt markers introduced.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| SEC-02 validator raises ValidationError on apikey= URL | `python -c "InstanceConfig(url='...?apikey=leak', ...)"` | ValidationError raised with `apikey=` in message | PASS |
| `_has_control_chars` correctly classifies 0x00, 0x7F, non-ASCII | `python -c "_has_control_chars('\x00'), _has_control_chars('\x7f'), _has_control_chars('hellöü')"` | True, True, False | PASS |
| Full pytest suite passes after Phase 66 changes | `uv run pytest tests/ -x -q` | 934 passed | PASS |
| Ruff lint clean | `uv run ruff check triggarr/ tests/` | All checks passed | PASS |
| Decision coverage SDK check | `gsd-sdk query check.decision-coverage-plan ...` | passed=true, total=14, covered=14 | PASS |

---

## Anything Missed or Partially Done

**Honest review — nothing material is missing or partial:**

1. **D-08 UX surfacing (M1 codex finding) is explicitly deferred, not missed.** The user sees the form re-render with the stale URL value when they submit an `apikey=`-bearing URL. The validation error fires correctly, is logged at WARNING via the redacting loguru sink, and is caught at `routes.py:565-569` into a 303 redirect. The user does NOT see a field-level error message in the UI. This is documented as accepted deferral in 66-01-SUMMARY.md and CONTEXT D-08. A future UX phase can layer field-level error surfacing; the security-hardening goal (rejection before TOML write) is fully achieved.

2. **Em-dash vs double-dash in SEC-04 warning** — CONTEXT D-14 phrased the second separator as `—` (em-dash); the source uses `--`. The U+2192 arrow (`→`) requirement IS met. The em-dash vs double-dash is a minor stylistic detail consistent with existing `check_localhost_urls` style elsewhere in the codebase. Not material.

3. **`style-src 'unsafe-inline'` retained** — Explicitly out of scope per D-04 (deferred for future hardening); not a SEC-01 success-criterion violation.

4. **The manual browser CSP smoke check is a "human-verified" step** that was performed via Playwright MCP against a live Triggarr server and documented in 66-05-SUMMARY.md §"Task 5". The verifier did NOT re-run this — but `test_csp_nonce_changes_per_request` + `test_csp_nonce_matches_html_script_tag` + `test_security_headers_csp_present` provide programmatic coverage of the directive content and per-request nonce parity that does NOT depend on a real browser. The browser smoke proved CSP enforcement under a real Chromium engine — that proof is documented evidence, not a claim that needs re-running on every verification.

---

## Recommendation

**PHASE COMPLETE.**

All 4 ROADMAP success criteria are observably satisfied in the codebase:
- CSP `script-src 'self' 'nonce-{nonce}'` with zero `'unsafe-inline'` (verified by grep + 5 passing tests + Playwright browser smoke).
- `apikey=` URL rejection via Pydantic `@field_validator` running BEFORE the TOML write lock (verified by 8 parametrized reject tests including URL-encoded variants, exact D-08 message preserved).
- Basic auth null-byte / control-char rejection with paired WARNING logs and PII minimization (verified by 5 dedicated tests including non-ASCII regression guard, strict `validate=True` b64 decode).
- Startup `session_secret < 32` WARNING modeled on `check_localhost_urls` and wired into `startup()` at step 4.7 (verified by 3-scenario test).

All 4 codex adversarial findings (M0/M1/M2/M3) are addressed (M0 with new HX-Redirect path + 2 invariant tests; M1 explicitly accepted deferral; M2 with `startswith("apikey")` + tests; M3 with `validate=True` strict decode).

All 14 CONTEXT.md locked decisions are covered by plans (decision-coverage SDK passed). Full test suite passes 934/934 with ruff clean. Atomic per-plan/per-task commit trail with no force-pushes or amends.

Ready to proceed to Phase 67 (Observability & CSRF Test Coverage).

---

*Verified: 2026-05-26*
*Verifier: Claude (gsd-verifier)*
