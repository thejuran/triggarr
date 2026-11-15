# Requirements: Triggarr v2.14 Reliability

**Defined:** 2026-11-15
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Sources:** the Reliability scope agreed in ROADMAP.md (2026-10-18), the owner's scope and fold-in decisions of 2026-11-15, and the v2.14 research in `.planning/research/` (SUMMARY.md, 2026-11-15).

**Standing rules for the whole milestone:**
- No new runtime dependency. Keep the single-process architecture and SQLite.
- No generic retry framework, no blanket I/O or offloading rewrite, and no claim of exactly-once delivery.
- Each fix lands with a regression test that fails on the unfixed code. A cleanup fix must show the resource was actually closed, not only that the error still surfaces.
- Check the current implementation before planning each carried-forward fix (the database cursor-lifetime concern from 999.13 was not found by research; re-check it briefly at phase planning and record the result).
- Existing invariants hold: API keys never exposed, sanitized logging, cycle grades, the consecutive-failure counter counting Failed only, schema migrations forward-only, identity isolation by stable instance ID.

## v1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### State & Config Consistency

- [ ] **CONSIST-01**: When removing an instance fails to save the settings file, the user still sees the instance, and its settings, schedule and connection keep working as before the attempt.
- [ ] **CONSIST-02**: When removing an instance fails to save, the user sees an error that says the instance was not removed, with no internal details.
- [ ] **CONSIST-03**: When the saved state file holds valid JSON that is not an object (`[]`, `42`, `null`), Triggarr starts with default state and logs a warning, instead of crashing.

### Resource Lifecycle

- [ ] **LIFE-01**: When startup fails partway, Triggarr closes the database and every connection it had already opened, and the process exits promptly rather than hanging.
- [ ] **LIFE-02**: When one *arr connection fails to close at shutdown, the remaining connections and the database are still closed, and the failure is logged sanitized.
- [ ] **LIFE-03**: After a failed startup, the scheduler is not left running.

### Search-Command Delivery

- [ ] **DELIV-01**: A search command whose request may have reached the *arr app (the response timed out or the connection dropped after sending) is not sent again automatically.
- [ ] **DELIV-02**: A search command that provably never left Triggarr (the connection could not be established) is still retried, and read requests keep their existing retry.
- [ ] **DELIV-03**: A search command with unknown delivery is recorded as "unconfirmed", distinct from accepted and failed, in the cycle result and in search history.
- [ ] **DELIV-04**: Unconfirmed commands never grade a cycle Failed and never add to the consecutive-failure counter; a cycle containing any unconfirmed command grades Partial at worst (owner decision 2026-11-15).
- [ ] **DELIV-05**: The user can see on the instance card how many commands in the last cycle were unconfirmed.
- [ ] **DELIV-06**: An item whose search command was unconfirmed counts as attempted for queue ordering, so it is not searched again ahead of items never tried.
- [ ] **DELIV-07**: The documentation states the remaining delivery limits plainly: a duplicate search is made unlikely, not impossible, and an unconfirmed command may or may not have run.

### Upgrade Backups

- [ ] **BKUP-01**: Pre-upgrade database backups are bounded: the original backup taken before the first upgrade attempt is always kept, plus at most the 3 most recent later ones.
- [ ] **BKUP-02**: Pruning never removes the original backup or the one just written, orders backups by the timestamp in their names, and a pruning failure is logged without blocking startup.

### Removed-Instance Searches

- [ ] **RMINST-01**: When a Sonarr instance is removed, its still-pending searches get the final outcome "Instance removed" (owner decision 2026-11-15); they are kept in History, and are distinct from the existing "Legacy" label.
- [ ] **RMINST-02**: "Instance removed" searches no longer count toward the pending-search limit and are never checked or credited again.
- [ ] **RMINST-03**: A new instance added under the same name never selects, displays as its own in-progress work, or receives credit for the removed instance's searches.
- [ ] **RMINST-04**: Pending searches already orphaned by a removal before this release are brought to the same "Instance removed" outcome at upgrade or startup.

### Telemetry

- [ ] **TELEM-01**: With `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint set in the container environment, Triggarr starts and serves requests; an automated test pins this.
- [ ] **TELEM-02**: The documentation states that telemetry export is unsupported and that nothing is exported.

### Recovery Demonstration

- [ ] **SMOKE-01**: The built-image check in CI demonstrates recovery after a restart with a non-object state file: the container comes back healthy.
- [ ] **SMOKE-02**: The built-image check in CI demonstrates that repeated failed upgrade attempts leave a bounded number of backups, with the original still present.
- [ ] **SMOKE-03**: Each recovery demonstration injects a real fault and fails when the corresponding fix is absent.

## v2 Requirements

Deferred. Tracked but not in the current roadmap.

### Search-Command Delivery

- **FUT-14**: After an unconfirmed search command, Triggarr asks the *arr app whether the command arrived and resolves the result to accepted or failed (owner deferred 2026-11-15).

### Removed-Instance Searches

- **FUT-15**: Radarr and Lidarr pending searches of a removed instance get the same "Instance removed" lifecycle, if investigation shows they are affected (this milestone covers Sonarr, where the gap was found).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Exactly-once search delivery | Cannot be guaranteed over HTTP without server support; claiming it would be dishonest |
| Generic or configurable retry framework | Agreed scope boundary; one narrow rule (retry only what never left) is enough |
| Automatically re-sending an unconfirmed command later | Reintroduces the duplicate search this milestone removes |
| Blanket blocking-I/O or offloading rewrite | 999.13 was narrowed on 2026-10-18 to demonstrated lifecycle defects only |
| Scheduled or user-facing database backup feature | Only the existing pre-upgrade backup needs a bound |
| Deleting a removed instance's search history | Owner chose to keep the record and mark it "Instance removed" |
| Telemetry export support | Not a product goal; documented as unsupported |
| Dashboard cards re-rendering every 5 seconds (click swallowed) | Not folded in (owner, 2026-11-15); stays in backlog/MAINTENANCE.md |

## Traceability

Which phases cover which requirements. Filled in during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 0
- Unmapped: 24 ⚠️ (roadmap not yet written)

---
*Requirements defined: 2026-11-15*
*Last updated: 2026-11-15 after initial definition*
