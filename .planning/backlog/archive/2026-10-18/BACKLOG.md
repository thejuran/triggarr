# Backlog before milestone organization

Archived 2026-10-18. Historical snapshot only; statuses may be stale. Active work is defined in [ROADMAP.md](../../../ROADMAP.md). Retired entries are not pending work.


**Triage approved 2026-10-17.** Finish v2.12 first. Retained items below are unscheduled follow-ups, not a commitment to another broad hardening milestone. Retired means **won't do under current scope**; do not repeatedly carry it forward or create plans without the stated reopening evidence. Original 999.x findings came from the 2026-06-26 deep review; recheck current code before implementation.

### 999.4 — Keep: password hashing off the event loop

Move synchronous bcrypt work in async authentication/setup/reset paths off the shared event loop, preserving authentication and rate-limit behavior. Verify unrelated requests and scheduled work can progress during hashing. No auth redesign or new settings.

### 999.9 — Keep: state and config consistency

- Make instance removal write validated replacement settings before swapping live state; a failed write must preserve settings, scheduler jobs and clients.
- Guard non-object state JSON (`[]`, `42`, `null`) so loading follows the documented recovery path instead of raising on dictionary access.
- Require focused failure-path regression tests.

### 999.10 — Narrow: evidence-backed auth boundary review

Review cookie-authenticated mutations with missing Origin/Referer, auth-exempt path matching, trusted-proxy/rate-limit behavior, and cookie/CSP behavior in supported deployments. Reproduce each alleged defect and record its actual prerequisites before choosing a fix; older proposed remedies are not approved requirements. Keep API-key/Basic clients and supported reverse-proxy setups working. Do not automatically add auth modes, cookie settings, a CSP rewrite, or treat an HX-Request header alone as proof of CSRF protection.

### 999.13 — Narrow: startup/shutdown resource cleanup

Keep concrete failure-path work: ensure database/client resources opened during partial startup are closed, and failure closing one client does not prevent closing remaining resources or the DB. Verify with injected initialization/close failures. Fix cursor lifetime defects locally if confirmed. Drop the blanket async-I/O/offloading rewrite; reopen performance work only for measured stalls. This does not retire 999.4's known CPU-blocking auth work.

### POST-retry semantics — Keep: ambiguous command acceptance

An automatic POST retry after a response timeout can duplicate a command already accepted upstream. Establish explicit retry behavior for search commands, distinguish confirmed acceptance from unknown delivery, and test response-loss scenarios. Keep safe read retries; do not broaden into a generic retry framework. This remains outside v2.12's one-engine-dispatch guarantee.

### Maintenance rules — no standalone implementation phase

- **999.8 — atomic writes:** Retire consolidation of all writers/public APIs as a project. Preserve atomic replacement, appropriate secret-file permissions, cleanup and durability. Fix only demonstrated defects with focused tests. The current TOML writer uses `mkstemp`; omitting a later `chmod` does not by itself demonstrate world-readable output.
- **999.11 — URL validation compatibility:** When a future validation change rejects a previously supported configuration, ship a migration/recovery path and regression test with that change. Do not prebuild a generic migration system or weaken existing validation. No standalone task until such a change is proposed.

### Retired — won't do under current scope

| Item | Decision / reason | Reopen only when |
|------|-------------------|------------------|
| 999.7 — client registry and module reorganization | Retired as standalone architecture work; three supported apps do not justify a new abstraction project. | A new integration or demonstrated dispatch inconsistency requires it. |
| 999.12 — changelog renderer rewrite | Retired; all three text insertion points are escaped, the security boundary is documented, and 19 changelog tests passed during the 2026-10-17 review. Preserve those protections. | A reproducible escaping defect or new untrusted content path appears. |
| PERF-01/02 — per-endpoint timeout/page-size overrides | Retired; global settings already cover normal operation. | An observed endpoint-specific problem cannot be solved with existing settings. |
| PERF-03 — state streaming/compression | Retired; no measured state-size or memory problem. | Profiling demonstrates a material bottleneck. |
| SCALE-01 — more than five instances per app | Retired; no current deployment requirement. | An actual deployment needs more than five instances of one app. |
| SCALE-02 — archival/PostgreSQL | Retired; SQLite and bounded history fit a single-process utility. | A concrete retention or scale requirement exceeds SQLite/current retention. |
| AUDIT-01 — config audit log | Retired; limited value in the current single-user model. | A real operational accountability requirement emerges. |
| OBS-01 — scheduler dashboard | Retired; existing cards and cycle outcomes cover core operational feedback. | A recurring diagnostic need cannot be answered by existing status/history/logs. |
| UI-01/02/03 — pixel-exact verification | Retired as pixel-exact requirements; retain ordinary login, setup and security-settings usability checks. | A functional usability or accessibility regression is observed. |
| Unused `--color-triggarr-primaryDark` token | Retired as tracked work; optional cleanup while editing that stylesheet. | It causes an actual styling defect. |

### Promoted / historical — removed from active backlog

| Original item | Owning milestone/phase | Status |
|---------------|------------------------|--------|
| 999.1 — password recovery | v2.10, Phases 72–73; [archive](../../../milestones/v2.10-ROADMAP.md) | Shipped; no duplicate backlog task. |
| 999.2 — count-only refresh | v2.10, Phase 74; [archive](../../../milestones/v2.10-ROADMAP.md) | Shipped; no duplicate backlog task. |
| 999.3 — reset-token viewer exposure | v2.12, [Phase 77](../../../ROADMAP.md#phase-77-secret--reset-token-log-hygiene) | Implementation complete; milestone NAS UAT remains pending. |
| 999.6 — log secret-redaction gaps | v2.12, [Phase 77](../../../ROADMAP.md#phase-77-secret--reset-token-log-hygiene) | Implementation complete; no duplicate backlog task. |
| 999.5 — malformed upstream records | v2.12, [Phase 80](../../../ROADMAP.md#phase-80-cycle-robustness--sonarr-season-dedup) | Pending in Phase 80, not retired or complete. |

### Other small follow-ups

Existing screenshot/CI maintenance in `TODO.md` is unchanged by this triage. The older v2.9 follow-up (URL-validation duplication, Retry-Connection button behavior, bug-report version options) remains unscheduled and must be revalidated before work; it is not part of a new hardening program.
