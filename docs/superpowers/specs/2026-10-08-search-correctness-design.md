# v2.12 — Search Correctness & Trustworthy Feedback (Design)

**Date:** 2026-10-08
**Status:** Approved in brainstorming (sections 1–2 with owner clarifications)
**Target release:** v2.12.0 (public release; `release_intent: true`)
**Phase numbering:** continues from v2.11's Phase 76 → Phases 77–81 (flat `.planning/phases/<N>-<slug>/` layout)

## 1. Purpose

Triggarr's core value is to reliably trigger searches for the right media and report honestly what happened. An external review found four places where that promise silently breaks:

1. Tag-scoped searches widen to the whole library when a tag can't be resolved.
2. Sonarr grab attribution ignores the season and re-credits the same grab, so effectiveness stats are wrong.
3. A season eligible for both the missing and upgrade queues receives two identical SeasonSearch commands per cycle.
4. "Last success" is stamped even when every search command failed, which also resets the consecutive-failure counter.

This milestone fixes those four, plus three backlog items on the same theme:
- **999.3:** the reset token is visible in the in-app log viewer, an account-takeover path.
- **999.6:** API keys can leak into logs.
- **999.5:** one malformed *arr record can wedge a whole cycle.

## 2. Scope

**In scope:** findings #1–#4 and backlog items 999.3, 999.5, 999.6, plus a bounded Sonarr v5 compatibility task in Phase 81 (added 2026-10-12).

**Out of scope** (2026-10-17 backlog triage supersedes the earlier blanket deferral to a next hardening milestone):
- Retained fixes are organized in ROADMAP.md under the future Reliability and Authentication Safety & Responsiveness milestones (2026-10-18). Maintenance rules and closed decisions live in `.planning/backlog/`; none expands v2.12.
- new features
- Lidarr/Radarr attribution changes (the season bug is Sonarr-specific)
- recomputing historical stats
- changing the HTTP client's automatic single retry of POST requests. A timeout after the server already accepted a command can still produce a duplicate command. This is assigned to the future Reliability milestone; implementation remains outside v2.12.

## 3. Locked definitions

### 3.1 Cycle outcome grades

"Accepted" means the *arr API accepted the search command. Whether a grab follows is a separate tracking result and never affects the cycle grade.

A queue is **active** when its configured search count is > 0. Inactive queues are ignored for grading.

A queue is **evaluated** when its eligible items were fetched, filtered (including tag scope) and processed without malformed data preventing evaluation.

| Grade | Condition |
|---|---|
| **Success** | Every active queue was evaluated, ≥1 command was attempted, and every attempted command was accepted. |
| **Nothing needed searching** | Every active queue was evaluated successfully and none had eligible work. |
| **Partial** | ≥1 command was accepted, AND (another command failed, OR an active queue could not be evaluated, OR malformed records prevented complete evaluation). |
| **Failed** | No command was accepted, AND (≥1 attempted command failed, OR any active queue could not be evaluated, OR the cycle could not fetch/evaluate anything). |

Consequences:
- A blocked queue (e.g. an unresolved tag) plus an empty queue is **Failed**, never "Nothing needed searching". The app could not establish that nothing needed searching.
- Malformed search-side records are counted separately from failed commands but degrade the grade: some accepted → Partial; none accepted and evaluation incomplete → Failed.
- Malformed *tracking* events affect tracking diagnostics only, never the search-cycle grade.
- **Persistence failures never change command outcomes.** If a command is accepted but its history insert fails:
  - the command still counts as accepted
  - **last successful search** updates
  - a separate **persistence warning** is shown on the card
  - it is never classified as a failed command, and the search is never retried because logging failed

### 3.2 Timestamps

- **Last successful search:** updated only when ≥1 command was accepted.
- **Last checked:** updated whenever a cycle finishes, including Failed and empty cycles.
- **Legacy value:** the pre-upgrade `last_success` is preserved and displayed as **"Last success (legacy)"** until the instance's first new cycle completes. It is never relabelled as a confirmed successful search.
- **Connection health** (`connected`) stays a separate signal from the cycle grade.

### 3.3 Consecutive-failure counter (SAFETY-03)

- Increments on **Failed**.
- Resets on **Success**, **Partial** and **Nothing needed searching**.
- The threshold and alert behavior are otherwise unchanged.

## 4. Phases

### Phase 77 — Secret & reset-token log hygiene (999.3, 999.6)

**Behavior**
- The reset token is redacted **before** insertion into the in-app log viewer buffer. Buffered entries stay redacted permanently, including after the token expires, is consumed or is replaced.
- Only the stderr log (`docker logs`, the authorized retrieval channel) carries the token.
- The token never appears in any HTTP response.
- Every path that logs an *arr HTTP exception routes it through the existing sanitizer (`_sanitize_exc`). This includes Sonarr `detect_api_version`, where legacy installs carry the apikey in the request URL, and the remaining 999.6 sites.

**Acceptance**
- Token absent from the viewer buffer and from `/partials/log-viewer` output.
- Token present in the stderr sink.
- The viewer stays redacted after the token is consumed, expires, or is replaced by a new token.
- An HTTP error whose URL contains an apikey is logged redacted on every covered path.

### Phase 78 — Honest cycle outcomes (#4)

**Behavior**
- The engine computes and persists a per-instance last-cycle record:
  - grade (§3.1)
  - accepted count
  - failed count
  - malformed/skipped count
  - unevaluated queues with reasons
  - finish time
- `last_success` is split into **last successful search** and **last checked** (§3.2). Saved state from older versions loads cleanly via the existing defaults-merge path.
- The scheduler's failure counter follows §3.3, derived from the grade, while connection health remains separate.
- **Dashboard card:** shows the last cycle as `<Grade> · <N> accepted, <M> failed · <relative time>` (e.g. "Partial · 4 accepted, 1 failed · 8m ago").
  - Amber for Partial, red for Failed.
  - An expandable detail lists the failure reasons. Messages are sanitized, with no secrets and no stack traces.
  - "Nothing needed searching" is shown as such, with last-checked time.

**Acceptance**
- Engine tests cover each grade for Radarr, Sonarr and Lidarr, including the inactive-queue and empty-cycle cases.
- Scheduler tests: Failed increments the counter; Success, Partial and Nothing-needed each reset it.
- Template tests render every grade plus the legacy timestamp label.

### Phase 79 — Tag-scoped searches stay in scope (#1)

**Behavior**
- When a queue has a tag configured and the tag cannot be resolved (the tag fetch failed, or the tag no longer exists), that queue is **skipped**: zero searches.
- The other queue still runs if its own scope resolves.
- A persistent card warning names the queue and the reason, and clears automatically once the tag resolves on a later cycle.
- A skipped queue counts as "could not be evaluated" for grading (§3.1).
- The old documented fallback (search all eligible items) is removed, and the README/docs are updated.

**Acceptance**
- For all three apps, a missing tag and a failed tag fetch each produce zero searches for the affected queue, a visible warning and the correct grade. This includes Failed when the other queue is empty.
- The warning clears when the tag resolves.

### Phase 80 — Cycle robustness + Sonarr season dedup (999.5, #3)

**Robustness behavior**
- A malformed *arr record no longer aborts the cycle. Covered cases:
  - null/missing nested `series`/`artist` data in `run_*_cycle`, mirroring the guard already in `refresh_*_counts`
  - a malformed or naive grab date in correlation
  - a non-string version in `detect_api_version`
- The bad item is skipped and logged, the rest of the cycle runs, and state persists.
- A failure inside any history insert, on either the failure path or the success path, is logged and does not abort the batch.
- An accepted command whose history insert fails stays accepted and raises the persistence warning (§3.1). It is never counted as failed and never retried.
- `tag_autocomplete` returns its documented empty-`<datalist>` fallback on `ValueError`/JSON errors instead of a 500.
- Skipped malformed items are reported in the cycle detail and graded per §3.1. They are not counted as failed commands.

**Dedup behavior**
- Within one Sonarr cycle, each (series, season) receives at most **one engine dispatch** across both queues. The HTTP client's transport-level POST retry is outside this guarantee (§2).
- The missing queue claims a season **on attempt**: once the missing queue attempts it, the upgrade queue does not attempt it in the same cycle, even if the missing-queue command failed.
- The upgrade queue skips claimed seasons without consuming batch slots, so its batch fills with other eligible seasons.
- Exclusion preserves the season's existing position in the upgrade rotation (searched-log). It is neither marked as searched nor removed from prior history.
- **Pass definition (DEDUP-03, amended 2026-10-18 after the PR #28 review).** A claimed season counts as covered for the upgrade queue's pass, whatever the outcome of the missing-queue command (accepted, failed, or no response). An upgrade pass completes when the upgrade queue's batch is non-empty and every eligible upgrade season that is not claimed this cycle is in its searched-log. Claimed seasons are never inserted into the upgrade searched-log, and an empty batch never completes a pass. This amends v2.11 QUEUE-09 ("every currently-eligible item has been searched") for claimed seasons only; without it, a season claimed every cycle would block the upgrade pass for as long as the overlap lasts.

**Acceptance**
- One test per malformed-record case: the cycle completes, state persists, and the grade is correct.
- **Success-path insert failure:** an accepted command whose history insert fails is counted as accepted, updates last successful search, and shows the persistence warning. It is not retried.
- A season in both queues gets exactly one engine dispatch, including when that command fails.
- The upgrade batch is still filled to its limit from other seasons.
- The excluded season's upgrade searched-log entry is unchanged.
- The upgrade pass completes once every unclaimed upgrade season has been searched, for a successful, failed or unanswered missing-queue command and across partial batches; an entirely claimed upgrade batch dispatches nothing and completes no pass.

### Phase 81 — Correct Sonarr grab attribution (#2)

**Behavior**
- **Season matching.** A Sonarr grab credits a search only if it matches that search's series **and season** (`search_history.season_number` is already stored).
- **Source-scoped grab identity.** Credited grabs are keyed by (app, stable source-instance ID, grab ID) with a uniqueness constraint.
  - The stable source-instance ID is a permanent Triggarr-assigned instance ID. It is generated at instance creation, backfilled for existing instances on first load, persisted via the existing atomic config write, and unchanged by renames.
  - Different Sonarr servers issuing identical grab IDs never collide.
  - Renaming an instance never lets old grabs count again.
- **Atomic ownership.** The new ownership table records which search owns each grab. Ownership rows are committed in the same transaction as the outcome/stat updates.
- **Accumulation.** Later tracking checks include a search's previously owned grabs, so partial results accumulate to complete correctly.
- **Distinct episodes.** Results count distinct episodes; multiple grab events for the same episode count once.
- **Cutover.** Exactly one DB migration adds the ownership table and records a cutover marker. The marker is recorded once, only after the migration succeeds.
- **Pre-cutover searches.** Searches created before the cutover that are still pending keep their rows and existing counters but are **excluded** from corrected attribution, so grabs already counted under the old logic are not credited again.
  - These frozen legacy rows are **excluded from the active pending cap** (`PENDING_CAP_MULTIPLIER * max_rows`), so they can never block new history.
  - In history views they display as **"Legacy — tracking discontinued"**. Their stored outcomes are not rewritten.
- **Ownership retention.** Ownership records are independent of `search_history` rows. Pruning or deleting history never cascades to ownership records (no cascading foreign key or cleanup), so "each grab credited at most once, ever" holds after pruning. Ownership rows are small, one per credited grab, and this milestone does not prune them.
- **Stats note.** A persistent note beside Sonarr effectiveness stats reads: *"Attribution corrected on <date>. Earlier results may include misattributed or double-counted grabs."* Totals that include pre-cutover data are labelled *"Lifetime — includes historical estimates."*
- Existing history rows and counters are never modified or reset.

**Acceptance (regression tests)**
- The original reproduction: one Season 1 grab credits only the Season 1 search, exactly once, across two tracking checks.
- **Cross-instance collision:** identical grab IDs from two Sonarr instances are credited independently.
- **Rename:** renaming an instance does not re-credit old grabs.
- **Partial → complete:** a search accumulates owned grabs across checks; distinct-episode counting holds.
- **Restart persistence:** ownership survives a process restart; no re-credit afterward.
- **History pruning:** history pruning followed by another tracking check must not re-credit a grab whose owning search row was pruned.
- **Legacy pending cap:** pre-cutover pending rows don't count toward the pending cap; new searches insert even when legacy rows alone would exceed it; legacy rows render as "Legacy — tracking discontinued".
- **Pre-cutover pending searches:** excluded from corrected attribution, and their rows and counters are preserved.
- **Migration:** existing rows survive and the cutover is recorded exactly once.


### Phase 81 bounded task — Verify Sonarr v5 compatibility (added 2026-10-12)

This task verifies the existing integration against the Sonarr v5 beta; it is not an API rewrite or a new feature track.

**Behavior and scope**
- Correct application-version reporting: a valid v5 version must report v5 rather than falling through to v3. Keep application version separate from API route version. Cover v3/v4/v5 and malformed/non-string versions, reusing Phase 80's version-handling guard.
- Retain the current `/api/v3` endpoints and `X-Api-Key` authentication unless a reproducible compatibility failure requires a targeted change. Do not switch every endpoint to `/api/v5` based on the application version.
- Verify connection/status, tag lookup, paginated missing and cutoff lists (including `includeSeries`), library counts, `SeasonSearch` acceptance, and grab-history tracking against an isolated Sonarr v5 beta instance. Retain v4 regression coverage and run the same smoke flow against v4.
- Include alternate series orders, season packs, and multi-season releases in Phase 81 attribution fixtures. Use Sonarr-returned series/season/episode identities, never release-title parsing. Confirm distinct-episode counts and no cross-season attribution or repeat credit across tracking checks.
- Fix only demonstrated incompatibilities in these existing flows. Sonarr's new UI, OIDC, metadata management, and custom Wanted-filter features do not add Triggarr features to this milestone.

**Acceptance and evidence**
- Version tests prove v5 is reported correctly without implicitly changing API routes; malformed versions follow the sanitized fallback.
- Save sanitized representative v4/v5 response fixtures and regression tests for any compatibility fixes, including alternate-order and pack attribution cases.
- Record exact tested Sonarr versions/builds, test date, endpoint outcomes, and attribution results in the phase verification report. Use a disposable/test library with controlled download settings; do not upgrade the production NAS to perform this task.
- A live v5 smoke test is required before claiming v5 support. If a suitable beta instance or a required test scenario is unavailable, explicitly record it as unverified and keep the compatibility task open; passing mocks alone does not establish live compatibility.

**Research baseline (2026-10-12; recheck against the tested beta build)**
- Sonarr's v5 development tree still contains v3 missing, history, and command controllers. This supports testing the existing routes first, but is not a live compatibility guarantee: [v3 API source](https://github.com/Sonarr/Sonarr/tree/v5-develop/src/Sonarr.Api.V3).
- The local `SonarrClient.detect_api_version` currently returns v3 for versions not starting with `4`; the client already uses API-key authentication.

## 5. Ordering rationale

- 77 is first because it is isolated, small, and the highest-stakes fix.
- 78 defines the outcome model, and 79 depends on it.
- 80 touches the cycle loop (dedup and robustness share code), and it reports malformed counts into 78's model.
- Phase 81 attribution is independent of 79/80 and carries the only DB migration and config-schema addition (the stable instance ID). Its final v4/v5 compatibility task runs after Phase 80 so it verifies the completed robustness and dedup behavior.

## 6. Verification

- **Every phase:** `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/` must pass.
- **Sonarr compatibility:** complete the Phase 81 v4/v5 smoke matrix and record exact builds and any unverified scenarios before claiming v5 support.
- **Milestone end:** an NAS walkthrough of:
  - the card grades (Success, Partial, Failed, Nothing needed, legacy label)
  - the tag-unresolved warning
  - single season search for a dual-eligible season
  - the Sonarr stats cutover note
  - the log viewer with an active reset token

## 7. Constraints carried from the project

- SecretStr discipline: `.get_secret_value()` only at HTTP client init; no secrets in logs, responses or HTML.
- Loguru only, with the redacting sink.
- Atomic write-then-rename for config and state. Pydantic validation before any config write; TOML comments preserved.
- Error handling follows the established `httpx.HTTPError` + `pydantic.ValidationError` pattern, widened only where this spec says so.
