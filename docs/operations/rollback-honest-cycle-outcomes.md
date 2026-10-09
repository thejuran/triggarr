# Rollback and re-upgrade: Honest Cycle Outcomes (v2.12)

This is the generic docker-compose procedure for rolling back a Triggarr
deployment past the "Honest Cycle Outcomes" change (the per-instance grade,
split timestamps, and grade-driven failure counter), and for safely
upgrading again afterward. It applies to any docker-compose deployment;
substitute your own compose file path and service name where shown.

## What changed in state.json

Three new or re-scoped fields live per instance inside `/config/state.json`.
`triggarr.db`'s schema is unchanged -- nothing here touches search history or
the pending-tracking table.

- `last_cycle` (new) -- a dict (or `null` before the instance's first cycle
  under this version) holding the cycle's grade (Success / Partial / Failed /
  Nothing needed searching), accepted/failed counts, and the finish time.
- `last_successful_search` (new) -- an ISO timestamp, written only when the
  cycle got at least one search command accepted by the *arr app. `null`
  until that happens.
- `last_success` (existing field, new meaning) -- no longer written by the
  engine. It stays frozen at whatever value it held before the upgrade, and
  is shown only as "Last success (legacy)" until the instance's first new
  cycle completes.

## Before upgrading

1. Record the currently running image tag:
   ```bash
   docker compose images triggarr
   ```
2. Stop the writer. Triggarr's scheduler is the only process that writes
   `state.json` and `triggarr.db`; stopping it honors `stop_grace_period`, so
   an in-flight search cycle finishes draining before the container exits:
   ```bash
   docker compose stop triggarr
   ```
3. Back up the config volume. Locate the host path mounted at `/config` in
   your compose file's `volumes:` section, then copy the three files into a
   timestamped backup directory:
   ```bash
   mkdir -p backup-pre-upgrade-$(date -u +%Y%m%dT%H%MZ)
   cp -p /path/to/config/state.json /path/to/config/triggarr.db /path/to/config/triggarr.toml \
     backup-pre-upgrade-$(date -u +%Y%m%dT%H%MZ)/
   ```
4. Pull and start the new image:
   ```bash
   docker compose pull triggarr
   docker compose up -d triggarr
   ```

## Rolling back to v2.11.1

1. Stop the writer:
   ```bash
   docker compose stop triggarr
   ```
2. Snapshot the current (post-upgrade) `state.json` and `triggarr.db` into a
   new timestamped directory, the same way as the pre-upgrade backup above.
   The rollback keeps running on these current files -- it does not touch
   the pre-upgrade backup.
3. Pin the image. Edit the `triggarr` service in your compose file:
   ```yaml
   services:
     triggarr:
       image: ghcr.io/thejuran/triggarr:v2.11.1
   ```
4. Start it back up and confirm it came up clean:
   ```bash
   docker compose up -d triggarr
   docker compose logs --tail 50 triggarr
   ```
   Expect the scheduler to start with no state-load error, and the dashboard
   to load with every instance card present.

## Do not restore the pre-upgrade state.json or triggarr.db

Restoring the pre-upgrade backup from step 3 of "Before upgrading" is almost
never correct, and never safe to do casually.

`state.json` also holds `missing_searched` / `cutoff_searched` (the
per-instance searched-item logs) and the `*_pass` counters -- the bookkeeping
that lets Triggarr dispatch each item exactly once per pass. Restoring the
pre-upgrade file rewinds that bookkeeping, so the running version re-sends
search commands for items the *arr app already accepted since the upgrade --
a replay. Restoring `triggarr.db` drops the search-history and
pending-tracking rows recorded for those same accepted commands, breaking
closed-loop grab tracking for them.

Restore a backup only if the current file is genuinely unreadable (corrupt
JSON, failed SQLite open), and only after accepting that a replay of
recently-accepted searches is the tradeoff. Never restore either file as a
routine part of a rollback or re-upgrade.

## What v2.11.1 does with the new fields

Verified directly against the v2.11.1 source: its state-loading merge does
`{**_default_instance_state(), **instance_data}` per instance and pops only
the long-retired `missing_cursor` / `cutoff_cursor` keys. Any other unknown
key -- including `last_cycle` and `last_successful_search` -- passes through
untouched on every load and save.

- `last_cycle` and `last_successful_search` are carried through unchanged.
  v2.11.1 never reads or writes them.
- The "Last OK" row (v2.11.1's label for this value) shows the frozen
  pre-upgrade `last_success` until v2.11.1's own first cycle stamps it again
  with its original connection-only meaning.
- The consecutive-failure counter is in-memory only and restarts at 0 on
  container start, regardless of which version is running.

## Upgrading again after a rollback

1. Repeat the stop-and-snapshot steps from "Rolling back to v2.11.1" (stop
   the writer, snapshot the current files).
2. Set the image back to the newer tag, then pull and start it (the same
   `docker compose pull triggarr && docker compose up -d triggarr` form used
   above).
3. Until the first new cycle finishes (at most one search interval), the
   card shows the pre-rollback `last_cycle` grade with its true age (e.g.
   "3d ago"). "Last checked" turns amber if that age exceeds 2x the
   instance's search interval.
   "Last successful search" shows the `last_successful_search` value from
   before the rollback -- it never falls back to the connection-only
   `last_success` stamps v2.11.1 wrote while it was running, because the new
   code only shows `last_success` under the legacy label, and that label
   requires `last_cycle` to be `null`. The legacy label does not reappear
   once `last_cycle` exists.
4. Optional clean slate. If the stale pre-rollback grade would be confusing
   rather than informative, you can clear it with the container stopped:
   ```bash
   docker compose stop triggarr
   jq '(.radarr, .sonarr, .lidarr)[]?.last_cycle = null
       | (.radarr, .sonarr, .lidarr)[]?.last_successful_search = null' \
     /path/to/config/state.json > /path/to/config/state.json.tmp \
     && mv /path/to/config/state.json.tmp /path/to/config/state.json
   docker compose up -d triggarr
   ```
   Skip this step if `jq` is not available -- it is optional, not required
   for a correct upgrade. Afterward the card shows "Not run yet" plus
   "Last success (legacy): `<the v2.11.1 value>`", which correctly labels a
   connection-only time rather than a confirmed search.

   Never apply this kind of edit to `missing_searched`, `cutoff_searched`, or
   any `*_pass` field -- those are the searched-item bookkeeping described
   above, and editing them has the same replay risk as restoring a backup.
