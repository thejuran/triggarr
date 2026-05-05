# Deferred Backlog Audit

Generated: 2026-05-03
Updated: 2026-05-05 during M001/S02/T03

This file surfaces carry-forward work found in the legacy GSD v1 artifacts and adjacent project notes. The existing root-level GSD files remain historical; new execution should be planned under `.gsd/milestones/M###/`.

## Carry forward now

### 1. Update check interval 24h → 6h

- Source: `.gsd/QUEUE.md`; confirmed by `git stash list` / `git stash show --stat stash@{0}` during the transition audit.
- Status: queued and apparently already implemented in `stash@{0}`.
- Files in stash: `triggarr/search/scheduler.py`, `triggarr/update_check.py`.
- Rationale in queue: Sonarr/Radarr use 6h; Tautulli uses 12h.
- Recommendation: treat as a small ready slice. Apply only after review, then verify with tests/lint before completing.

## Resolved / retired during M001

### Config-directory portability

- Former source: `TODO.md`.
- Status: retired from active backlog.
- Why retired: current code and tests derive `triggarr.toml`, `state.json`, and `triggarr.db` from an absolute `TRIGGARR_CONFIG_DIR`, while keeping `/config` as the Docker-compatible default when the variable is unset.
- Follow-up: do not re-plan this from legacy notes unless new evidence shows a regression in the current config-dir contract.

## Deferred unless user demand appears

### DEFER-01 — Cross-instance search deduplication

- Source: `.gsd/REQUIREMENTS.md`, `.gsd/QUEUE.md`, `.gsd/STATE.md`
- Status: deferred / someday-maybe.
- Problem: overlapping libraries across multiple instances may search the same item independently.
- Proposed direction: record external IDs and timestamps; skip if another same-app instance recently searched the same TMDB/TVDB/foreignAlbumId.
- Complexity: medium-high because schedules are independent, Sonarr searches at season level, and external ID availability needs confirmation.
- Recommendation: do not schedule by default. Promote only if users report wasted searches or duplicate grabs.

### DEFER-02 — Dynamic instance hot-add

- Source: `.gsd/REQUIREMENTS.md`
- Status: deferred.
- Problem: adding instances may require restart in some paths.
- Current mitigation: config reload on settings save handles most practical cases.
- Recommendation: keep deferred unless the UI/admin loop shows real friction.

## Keep out of scope

These are explicitly anti-features in `.gsd/REQUIREMENTS.md` and should not be carried forward as backlog without an explicit product decision:

- `OOS-01` — Auto-discover *arr instances. Reason: network scanning / SSRF risk.
- `OOS-02` — Tag management from Triggarr. Reason: write operations expand attack surface; Triggarr should stay read + search only.
- `OOS-03` — Tag-based exclusion. Reason: inverse tag logic is more confusing than include-only filtering.

## Stash notes

- `stash@{0}` matches the queued update-check interval change and looks actionable.
- Older stashes contain historical GSD/planning state or pre-rename `fetcharr` work. Do not apply them blindly; inspect individually only if recovering old work is explicitly needed.

## Audit conclusion

No active blockers were found in legacy GSD state. The only active carry-forward candidate identified here is the 6h update-check interval from `stash@{0}`; the former configurable config-directory TODO is retired because current code already implements the portable path contract.
