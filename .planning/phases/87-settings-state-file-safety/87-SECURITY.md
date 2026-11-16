---
phase: 87
slug: settings-state-file-safety
status: verified
threats_open: 0
asvs_level: 1
created: 2026-11-15
---

# Phase 87 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser -> POST /api/instance/remove/{app}/{instance} | instance_name is user-controlled path input (length-capped at 64, must exist in settings) | instance name, HX-Request header |
| concurrent requests -> shared app.state.settings | settings-changing requests (`remove_instance`, `add_instance`, `save_settings`) can interleave around `search_lock` | in-memory Settings object, TOML file |
| route -> filesystem (triggarr.toml) | write can fail with OSError carrying paths and system text | config path, exception text |
| route -> log sink | exception text and instance names reach logs | app/instance names, exception type/message, config path (never API keys/SecretStr) |
| filesystem (state.json) -> load_state | file contents are untrusted (could be corrupted, non-UTF-8, wrong shape, or tampered) | raw JSON bytes |
| load_state -> filesystem (set-aside copy) | new `state.json.corrupt` file written in the config directory | file bytes, permission bits |
| server response -> browser DOM | the removal-failure body is inserted by htmx `innerHTML` into a row-local slot | escaped instance name only |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-87-01 | Information Disclosure | `remove_instance` failure response | mitigate | `_removal_failed_response` (routes.py:961-979) builds the body only from the fixed D-05 sentence and `html.escape(instance_name)`; never includes `exc`, path, or exception type | closed |
| T-87-02 | Tampering (reflected markup) | `remove_instance` failure response | mitigate | `html.escape(instance_name)` at routes.py:974; `test_remove_instance_write_failure_escapes_name` (tests/test_web.py:1983) asserts escaped output, no raw `<b>` | closed |
| T-87-03 | Tampering (state integrity) | `remove_instance` ordering | mitigate | Settings read inside `search_lock` (routes.py:1002), write before swap (`_atomic_toml_write` at 1075, swap at 1125); `test_remove_instance_write_failure_keeps_live_state` (tests/test_web.py:1555) | closed |
| T-87-03b | Tampering (lost update / resurrected instance) | `remove_instance` concurrency | mitigate | Existence re-check inside the lock (routes.py:1005); `test_remove_instance_concurrent_removals_both_persist` (tests/test_web.py:1585) and `test_remove_instance_concurrent_same_instance_second_is_not_found` (tests/test_web.py:1633) both pass at HEAD | closed |
| T-87-04 | Information Disclosure | new `logger.error` lines | mitigate | All new log calls (routes.py:1031-1038, 1109-1117, 1135-1141, 1163-1169) carry only app/instance names, path, and exception type/message -- never SecretStr values; routed through the existing redacting sink (`triggarr/logging.py::create_redacting_sink`) | closed |
| T-87-04b | Repudiation (missing/duplicated audit trail) | writer + route logging | mitigate | `log_failure: bool = True` keyword on `_atomic_toml_write` (triggarr/config.py:129, suppressing both the OSError and the "(unexpected error)" branch at lines 175 and 189); `log_failure=False` passed only at routes.py:1075; every other caller logs as before; `test_remove_instance_real_write_failure_logs_one_error` and `test_atomic_toml_write_logs_os_replace_failure` (unmodified) both pass | closed |
| T-87-05 | Denial of Service | post-save cleanup | mitigate | Scheduler-removal (routes.py:1131-1141) and client-close (routes.py:1160-1169) each isolated in their own `try/except Exception`; `test_remove_instance_scheduler_failure_still_completes` and `test_remove_instance_close_failure_still_succeeds` (tests/test_web.py:2469, 2507) pass | closed |
| T-87-06 | Spoofing (CSP nonce reuse) | htmx failure path | accept | Superseded in effect by T-87-08's mitigation (no body/html swap remains at all); documented below in Accepted Risks Log per the register's original disposition | closed (accepted) |
| T-87-07 | Tampering (XSS via innerHTML swap) | `span.remove-error` swap | mitigate | Body is plain text, `html.escape`d by `_removal_failed_response`; `triggarr/templates/settings.html` applies no `\| safe` to the slot; `test_remove_instance_write_failure_escapes_name` covers it | closed |
| T-87-08 | Spoofing (stale CSP nonce) | Remove button target change | mitigate | `hx-target="next .remove-error" hx-swap="innerHTML"` (settings.html:167) replaces the old `hx-target="body"`; `test_no_new_body_swap_html_targets` (tests/test_web.py:2587) asserts zero `hx-target="body"/"html"` occurrences in `triggarr/templates/`, confirmed passing | closed |
| T-87-09 | Information Disclosure | MAINTENANCE.md entries | mitigate | `.planning/backlog/MAINTENANCE.md` "Small follow-ups" entries cite only code locations (file:line) and behavior; no secrets, no raw file contents (verified by reading the current file) | closed |
| T-87-10 | Denial of Service (lost edits) | full-page swap on failure | mitigate | Failure swaps only the row-local `.remove-error` slot (settings.html:172); other form fields are not re-rendered; `test_settings_remove_button_targets_row_error_slot` (tests/test_web.py:2542) covers the wiring | closed |
| T-87-10b | Tampering (lost update) | `add_instance` / `save_settings` pre-lock snapshot | accept | See detailed disposition note below. Partially superseded by post-plan fixes; residual risk documented in MAINTENANCE.md | closed (accepted) |
| T-87-11 | Denial of Service | `load_state` startup crash | mitigate | `if not isinstance(data, dict):` guard at state.py:334, before `_is_v22_state_format`; `test_state_wrong_structure_list_recovers` and `test_state_non_object_root_recovers` (tests/test_state.py:409, 423) pass for `[]`, `42`, `null`, a string, `true`, `1.5` | closed |
| T-87-12 | Information Disclosure | D-10 warning | mitigate | Warning built from path, `_describe_json_kind` output, and exception type/message only (state.py:211-226, 274-280); never `exc.doc` or parsed values; `test_state_non_object_warning_names_kind_without_contents` asserts a sentinel value is absent | closed |
| T-87-13 | Information Disclosure | `state.json.corrupt` permissions | mitigate | `shutil.copy2` preserves source mode (state.py:250); `test_state_set_aside_permissions_not_wider` (tests/test_state.py:507) sets source to `0o640` (distinct from mkstemp's `0o600`) and asserts the copy matches exactly | closed |
| T-87-14 | Tampering (symlink write-through) | set-aside destination | mitigate | `mkstemp` in the same directory then `os.replace` onto the fixed name (state.py:248-251); replaces rather than follows an existing symlink | closed |
| T-87-15 | Denial of Service (disk growth) | repeated corruption | mitigate | One fixed destination name (`state.json.corrupt`), overwritten each time; `test_state_set_aside_keeps_exactly_one_copy` | closed |
| T-87-16 | Denial of Service | copy failure blocking startup | mitigate | `try/except OSError` around mkstemp/copy2/replace (state.py:247-271), fd closed immediately after mkstemp, guarded `finally` cleanup; `test_state_set_aside_failure_still_recovers` parametrized over all three failure points, passing | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Detailed disposition note: T-87-10b

The register's original disposition was **accept**, with the plan's mitigation plan reading: "Recorded in MAINTENANCE.md with evidence for owner decision; outside this phase's scope (D-13 deferral rule); single-user admin UI makes concurrent settings changes rare."

Verified against HEAD (commit `de305eac`), the code has moved substantially past that original "accept" baseline through four post-planning review/fix rounds, but a residual gap remains and is documented, not silently fixed in full:

- **`add_instance`** (routes.py:901-958): fixed in review-fix round 2 (commit `bef326b9`). The settings read, duplicate/limit checks, build and validation all moved inside `search_lock` (routes.py:925-950). `test_add_instance_during_removal_write_does_not_resurrect_removed` (tests/test_web.py:1665) proves the removed instance stays removed. **This side of T-87-10b is now mitigated, not merely accepted.**
- **`save_settings`, general-only form case** (routes.py:725-869): fixed in the deep-review pass (commit `7a92e735`). `current_settings = request.app.state.settings` now reads inside the lock (routes.py:739) via `_settings_from_form`, so a general-only Save queued behind a removal's write no longer resurrects the removed instance. `test_general_settings_save_during_removal_write_does_not_resurrect_removed` (tests/test_web.py:1755, confirmed present) covers this. **This side is also now mitigated.**
- **`save_settings`, full-form case (STILL OPEN, accepted)**: a Save whose form carries fields for only some of an app's instances treats the form as the complete instance list -- an instance named in the form but no longer in settings is recreated with a new id (a stale tab, or an overlap where the form still names a just-removed instance). This is unchanged by any fix round and is explicitly recorded as open in `.planning/backlog/MAINTENANCE.md` ("Settings read before search_lock in add_instance and save_settings", updated 2026-11-15, with three dated sub-updates tracing the add_instance fix, the general-only fix, and a further correction (SA-01, iteration 5) that in production the merge may instead *keep* a form-omitted instance rather than delete it -- a reviewer observation not yet independently re-verified or ruled on by the owner). Three options (A/B/C) are recorded for an owner decision; none is scheduled.

**Disposition held as `accept` for the residual case**, matching the register: the remaining risk is a single-user admin UI, requires either a stale browser tab or a narrow overlap window, and is fully documented with file:line evidence and owner-facing options in MAINTENANCE.md. This satisfies the CLOSED bar for an `accept` disposition (documented in the Accepted Risks Log below), while the two originally-accepted sub-cases that have in fact been mitigated are noted as such for accuracy.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-87-01 | T-87-06 | Original plan-time rationale: the removal failure path swaps plain text into a row slot, not a page body, so no CSP nonce is at risk; success path keeps `HX-Redirect` unchanged (SEC-01). Superseded in practice by T-87-08's full mitigation (zero body/html swap targets remain in any template, pinned by `test_no_new_body_swap_html_targets`). | Phase 87 plan (87-01-PLAN.md) | 2026-11-15 |
| AR-87-02 | T-87-10b | Residual risk after post-planning fixes: a Save whose form omits or only partially lists instances can still recreate a just-removed instance with a new id (stale tab, or a narrow overlap window for full-form saves specifically -- the general-only and add_instance cases are now mitigated in code). Single-user admin UI; narrow window; fully documented with routes.py file:line evidence and three owner-facing design options (A/B/C) in `.planning/backlog/MAINTENANCE.md` under "Settings read before search_lock in add_instance and save_settings" (updated through the 2026-11-15 deep-review sub-entries). Not fixed in Phase 87; owner decision pending. | Phase 87 plan + fix-round owner decisions | 2026-11-15 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-15 | 19 | 19 | 0 | Claude (bm-security-auditor) |

**Verification performed (not taken on documentation alone):**
- `uv run pytest tests/test_web.py -k "remove_instance or body_swap or remove_button" -q` -- 31 passed
- `uv run pytest tests/test_config.py -k "atomic_toml_write" -q` -- 8 passed
- `uv run pytest tests/test_state.py -q` -- 54 passed
- `uv run pytest tests/test_web.py -k "real_write_failure_logs_one_error or write_never_starts or refused_thread_start" -q` -- 6 passed
- `uv run python tests/audit_lock_coverage.py` -- covered: 8 / 8, uncovered: 0
- `uv run ruff check triggarr/ tests/` -- All checks passed
- Direct source read of `triggarr/web/routes.py` (`_settings_from_form`, `save_settings`, `add_instance`, `_removal_failed_response`, `remove_instance`), `triggarr/config.py` (`_atomic_toml_write`), `triggarr/state.py` (`_recover_from_bad_state_file`, `load_state`), `triggarr/logging.py` (redacting sink), and `triggarr/templates/settings.html` (Remove button, `.remove-error` slot) at HEAD `de305eac`, not inferred from SUMMARY/REVIEW prose alone
- Cross-checked `.planning/backlog/MAINTENANCE.md`'s Phase 87 entries (D-13 audit, D-14 follow-up, UTF-8 finding, pre-lock snapshot finding and its three dated sub-updates) against current `routes.py` line numbers and behavior

**Scope note:** this audit verifies the 19 threats declared in the 87-01/87-02/87-03 plan registers against the code as it stands after four post-planning review/fix rounds (round 1 through the deep-review pass at `7a92e735`/`e90f8cef`). It does not re-scan for new vulnerabilities beyond the declared register. Separate, non-blocking items surfaced by those review rounds (e.g. SA-01 directory-handle-close-after-replace, SA-03 unreadable-state-file overwrite-on-next-save, the late-write-after-refused-thread-start mechanism in `save_settings`/`add_instance`/auth routes, Codex F001 cancellation handling) are tracked in MAINTENANCE.md as their own backlog items, outside this phase's declared threat register, and are not scored here.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-15
