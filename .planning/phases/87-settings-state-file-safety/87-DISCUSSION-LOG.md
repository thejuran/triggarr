# Phase 87: Settings & State-File Safety - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-15
**Phase:** 87-Settings & State-File Safety
**Areas discussed:** Removal-failed message, Reset state file handling, Neighbouring save paths, Half-finished cleanup

---

## Removal-failed message

### Placement

| Option | Description | Selected |
|--------|-------------|----------|
| On the instance row | Red message on the instance, no page reload; other unsaved edits stay intact | ✓ |
| Banner at top of page | Page reloads with a red banner; unsaved edits elsewhere are lost | |
| You decide | Claude picks during planning | |

### Wording

| Option | Description | Selected |
|--------|-------------|----------|
| Plain + cause + next step | "'<name>' was not removed: the settings file could not be saved. Nothing was changed. Check the Triggarr log for details." | ✓ |
| Plain only | "'<name>' was not removed. Nothing was changed." | |
| You decide | Claude writes the wording | |

### Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Until next action or reload | No timer; stays until retry, save or reload | ✓ |
| Dismissible with an X | Stays until closed | |
| Fades after a few seconds | Disappears on its own | |

### Log detail

| Option | Description | Selected |
|--------|-------------|----------|
| Error entry in the log | One error-level line naming the instance and system reason, secrets redacted | ✓ |
| Warning entry in the log | Same content at warning level | |
| You decide | Claude matches other save failures | |

**User's choice:** all four recommended options.
**Notes:** Context given to the owner: the Settings page has no error area today and htmx ignores error responses, so a failed removal currently shows nothing.

---

## Reset state file handling

### Bad file

| Option | Description | Selected |
|--------|-------------|----------|
| Keep one copy aside | Bad file set aside next to the original; one copy, replaced on recurrence | ✓ |
| Overwrite it | Same as the existing truncated-file case; nothing kept | |
| You decide | Claude picks during planning | |

### Consistency with the existing truncated-file case

| Option | Description | Selected |
|--------|-------------|----------|
| Same treatment for both | One recovery behavior for both kinds of broken file | ✓ |
| Only the new case | Leave the truncated-file behavior unchanged | |

### Warning content

| Option | Description | Selected |
|--------|-------------|----------|
| What + consequence | File, wrong kind of data, what was reset, search history unaffected; never contents | ✓ |
| What only | File and wrong kind of data only | |
| You decide | Claude writes it | |

### Inner-shape cases

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as is | Requirement covers the top-level shape only; planning confirms inner cases already recover | ✓ |
| Add a warning there too | Also warn when an inner part is reset | |

**User's choice:** all four recommended options.
**Notes:** At the area check the owner accepted Claude's call that a failed set-aside never blocks startup and is logged.

---

## Neighbouring save paths

### Other routes with the same unsafe order

| Option | Description | Selected |
|--------|-------------|----------|
| Record it, fix later | Planning checks and records; unsafe findings go to the maintenance backlog with evidence | ✓ |
| Fix it in this phase | Fix every route found, each with its own test | |
| Stop and ask me | Pause and decide case by case | |

### Other failure messages (Save Settings, Add Instance)

| Option | Description | Selected |
|--------|-------------|----------|
| Removal only, note the rest | Deliver the removal message; note Save and Add in the maintenance backlog, pointing at UI Redesign | ✓ |
| Removal only, no note | Leave the others unrecorded | |

**User's choice:** both recommended options.

---

## Half-finished cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Success; problem logged | Instance is gone as normal; all remaining tidy-up steps still run; each failure logged | ✓ |
| Success with a notice | Also show that cleanup did not fully finish | |
| You decide | Claude picks during planning | |

**User's choice:** Success; problem logged.

---

## Claude's Discretion

- Delivery mechanism for the row-level message (within the CSP-nonce and existing success-path constraints)
- Response for a direct non-htmx POST on a failed save; HTTP status; styling and accessibility
- Set-aside file name and permissions
- Exact log wording within the no-contents and redaction rules
- Which additional non-object roots get explicit tests

## Deferred Ideas

- Friendly errors for failed Save Settings and Add Instance (maintenance backlog; UI Redesign)
- Fixing any other settings route found unsafe (maintenance backlog, with evidence)
- Warning when an inner part of a well-formed state file is reset
- On-page notice when post-save cleanup did not fully finish
