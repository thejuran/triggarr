# Phase 87: Settings & State-File Safety - Context

**Gathered:** 2026-11-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Two fixes, both inside existing behavior (CONSIST-01, CONSIST-02, CONSIST-03):

1. Removing an instance can't corrupt live settings when the settings file fails to save. On a failed save the instance keeps its settings, schedule and live connection exactly as before the attempt, and the user sees an error stating the instance was not removed, with no internal detail.
2. A saved state file holding valid JSON that is not an object (`[]`, `42`, `null`, `"a string"`) makes Triggarr start with default state and log a warning, instead of crashing.

Not in this phase: what happens to a removed instance's pending searches (Phase 90), startup/shutdown resource cleanup (Phase 89), the built-image recovery demonstration (Phase 92), and any change to how Save Settings or Add Instance report their own failures.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (milestone standing rules, not re-asked)
- **D-01:** No new runtime dependency. Each fix lands with a regression test that fails on the unfixed code.
- **D-02:** The removal fix follows the order `save_settings` and `add_instance` already use: build the post-removal configuration without touching live settings, write it to disk, and only after the write succeeds change live settings, the scheduler job, the client registry, the state entry and the tag cache.
- **D-03:** The regression test for a failed removal asserts the full postcondition, not only the response: the instance is still in live settings, its scheduler job is still present, and its client is still registered (research PITFALLS.md, Pitfall 4).

### Removal-failed message
- **D-04:** The error appears on the row of the instance the user tried to remove, without a page reload. Unsaved edits elsewhere on the Settings page must survive a failed removal.
- **D-05:** Message text: "'<name>' was not removed: the settings file could not be saved. Nothing was changed. Check the Triggarr log for details." It names the general cause only: no file paths, no system error text, no exception names. The instance name is escaped.
- **D-06:** The message stays until the user's next action on that instance (trying Remove again replaces it) or a page reload. No timer and no close control.
- **D-07:** The technical reason is recorded as one error-level log entry naming the app, the instance and the system reason, with secrets redacted by the existing log sink.

### Reset state file handling
- **D-08:** When a state file is reset to defaults, the bad file is set aside next to the original first. Exactly one set-aside copy is kept; a later occurrence replaces it, so it can never accumulate.
- **D-09:** The same set-aside treatment applies to both kinds of broken state file: the new wrong-shape case and the existing truncated/unparseable case. One recovery behavior to understand and test.
- **D-10:** The warning states what happened and what it costs: it names the file, the kind of data found versus expected (e.g. a list where an object was expected), that queue progress and last-run times were reset to defaults, and that search history is unaffected. It never includes the file's contents.
- **D-11:** If setting the bad file aside fails (for example an unreadable file or a read-only volume), startup still continues with default state and the failure is logged. Recovery must never be blocked by the copy step.
- **D-12:** State files that are an object at the top but wrong inside are left as they are. Planning confirms with a quick check that those cases already recover without crashing, and changes nothing there.

### Neighbouring save paths
- **D-13:** Planning checks the other settings-changing routes (password, API key, sign-in mode and any other writer of the settings file) for the same mutate-before-write order and records the result in the phase. Anything unsafe is written into `.planning/backlog/MAINTENANCE.md` with the evidence and is NOT fixed in this phase.
- **D-14:** The friendly error is delivered for removal only. The phase adds a note to `.planning/backlog/MAINTENANCE.md` that a failed Save Settings still shows a raw server-error page and a failed Add Instance gives no useful message, pointing at the UI Redesign milestone's "Settings sections and one save" item as the natural home.

### Half-finished cleanup
- **D-15:** Once the settings file is saved, the removal is real. If a later tidy-up step fails (for example closing the instance's connection), the user still sees the normal successful removal and nothing extra is shown.
- **D-16:** Every remaining tidy-up step still runs when one fails, and each failure is logged with secrets redacted. One failed step must not leave the scheduler job, client, state entry or tag-cache entry of a removed instance behind.

### Claude's Discretion
- How the row-level message is delivered (htmx does not swap error responses by default; the Remove button currently targets the whole body). Any mechanism is acceptable if it meets D-04 to D-06, keeps the existing success path (HX-Redirect for htmx, 303 otherwise) and does not reintroduce the stale-CSP-nonce problem that the HX-Redirect was added to avoid.
- What a direct, non-htmx POST to the removal route returns on a failed save: a non-2xx response carrying the same plain wording, no internal detail.
- HTTP status code for the failed-save response, styling of the message (existing red text conventions in `settings.html`), and accessibility attributes.
- The set-aside file's name and permissions (keep them at least as restrictive as the state file's).
- Exact wording of the D-10 warning and the D-07/D-16 log entries, within the no-contents and redaction rules.
- Which other non-object roots get explicit tests beyond `[]`, `42`, `null` (a string and a boolean are suggested).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` §"Phase 87: Settings & State-File Safety" — goal and the three success criteria
- `.planning/REQUIREMENTS.md` — CONSIST-01, CONSIST-02, CONSIST-03 and the "Standing rules for the whole milestone" block
- `.planning/PROJECT.md` — Active requirements for state/config consistency (999.9) and the known-debt note on `test_state_wrong_structure_list_crashes`

### Research for this milestone
- `.planning/research/SUMMARY.md` — confirmed defect status (items 1 and 2), build-order rationale, "Phase 1: Settings & state-file safety"
- `.planning/research/PITFALLS.md` §"Pitfall 4" — the removal ordering defect, the correct sibling pattern, the full-postcondition test
- `.planning/research/PITFALLS.md` §"Pitfall 5" — the non-object state root crash, the single entry-point guard, the test to flip

### Project rules
- `CLAUDE.md` — SecretStr discipline, loguru with the redacting sink, atomic write-then-rename, review workflow (one PR per phase, paired Codex pass)
- `docs/PLANNING-FORMAT.md` — required before editing STATE.md, ROADMAP.md or REQUIREMENTS.md
- `.planning/backlog/MAINTENANCE.md` — where D-13 and D-14 notes are written

### Downstream phases that build on this one
- `.planning/ROADMAP.md` §"Phase 90" — reuses this phase's corrected removal route
- `.planning/ROADMAP.md` §"Phase 92" — restarts the built image with a non-object state file; the D-08 set-aside step must work inside the container

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/web/routes.py` `add_instance` (around lines 882-934) and `save_settings` (write region around lines 715-731): the correct validate → write → update-live-state order to mirror.
- `triggarr/config.py` `_atomic_toml_write` and `_settings_to_dict`: the existing atomic settings writer and serializer; no new writer is needed.
- `tests/test_web.py` `test_save_settings_propagates_write_failure` (around line 856): the existing way to force a settings-write failure (`patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError(...))`).
- `tests/test_web.py` `multi_instance_app` fixture and the `test_remove_instance_*` tests (around lines 1478-1535, 2834): existing removal coverage to extend and keep passing.
- `tests/test_state.py` `test_state_wrong_structure_list_crashes` (around line 407): documents today's crash; its docstring says to flip it to assert recovery. `test_state_corrupt_warning_names_reason_without_contents` sets the no-contents convention for warnings.
- `triggarr/state.py` `_default_state()`: the default state returned on recovery.

### Established Patterns
- `remove_instance` (`triggarr/web/routes.py` around lines 937-995) is the outlier: it deletes from the live settings dict before the write, so a failed write leaves settings, the scheduler job and the client disagreeing.
- `load_state` (`triggarr/state.py` around lines 210-245) catches only `json.JSONDecodeError` and `OSError`; a non-object root crashes later in `_is_v22_state_format`. Research recommends one `isinstance(data, dict)` guard at the `load_state` entry point rather than guards inside the helpers.
- Corrupt-state warnings name the reason but never echo file content (`exc.doc` is never logged).
- Settings mutations take `request.app.state.search_lock`; the stale client is closed after the lock is released.
- Successful htmx removal returns `HX-Redirect` rather than a body swap, because a body swap would inherit the old CSP nonce (SEC-01).
- The Settings page has no error surface today, and htmx ignores error responses by default, so a failed removal currently shows the user nothing.
- Route error responses elsewhere are short plain-text `HTMLResponse` bodies with a 4xx status and `html.escape` on any user-supplied name.

### Integration Points
- `triggarr/templates/settings.html` instance row (`<details>` / `<summary>` with the Remove button, around lines 159-172): where the D-04 message appears.
- `triggarr/search/scheduler.py` around line 481: the single caller of `load_state` at startup.
- The scheduler job id format `"{app_name}_{instance_name}_search"`, the `{app_name}_clients` dicts, `triggarr_state` and `tag_cache` on `app.state`: the live state that must be untouched after a failed save and fully cleaned after a successful one.

</code_context>

<specifics>
## Specific Ideas

- The exact user-facing sentence in D-05 was chosen by the owner; use it as written (with the real instance name).
- The owner's priority for the message placement is that a failed removal does not cost the user their other unsaved edits on the page.
- The set-aside copy exists for diagnosis: so the owner or Claude can see afterwards what corrupted the state file.

</specifics>

<deferred>
## Deferred Ideas

- Friendly error for a failed Save Settings (currently a raw server-error page) and a failed Add Instance (no useful message): recorded in `.planning/backlog/MAINTENANCE.md` by this phase (D-14); natural home is the UI Redesign milestone's Settings work.
- Fixing any other settings route found to mutate live state before writing: recorded with evidence in `.planning/backlog/MAINTENANCE.md` by this phase (D-13), not fixed here.
- Logging a warning when an inner part of an otherwise well-formed state file is reset (D-12 leaves this as is).
- A visible on-page notice when post-save cleanup did not fully finish (not chosen; D-15).

</deferred>

---

*Phase: 87-Settings & State-File Safety*
*Context gathered: 2026-11-15*
