# Upgrading past Sonarr attribution (database schema v10, v2.12)

The Sonarr attribution correction changes `triggarr.db`'s schema to version 10
and writes a stable ID into every instance in `triggarr.toml`. Unlike the
earlier v2.12 changes in [Rollback and re-upgrade: Honest Cycle
Outcomes](rollback-honest-cycle-outcomes.md), this one cannot be undone by
switching images.

## Before upgrading

- The config directory (`/config` in Docker) must be writable. On the first
  start after upgrading, Triggarr adds an `id` to each instance in
  `triggarr.toml`. If it cannot write the file, it logs
  "Could not save instance ids to ... the config directory must be writable"
  and does not start. Read-only config mounts and single-file bind mounts of
  `triggarr.toml` are not supported.
- Stop the container and copy `/config/triggarr.db` (with any
  `triggarr.db-wal` and `triggarr.db-shm` beside it), `triggarr.toml` and
  `state.json` somewhere outside `/config`. Triggarr also writes
  `triggarr.v9-backup` itself before migrating.

## Supported: forward-only

Once a Triggarr build with schema v10 has started against your database,
the supported way to recover from a problem is to deploy a newer fixed
build, not an older one. Keep the database, `triggarr.toml` and
`state.json` as they are.

## Do not roll back by changing the image only

Do not start a pre-v10 image (v2.12 builds without the attribution
correction, v2.11.x or earlier) against a database that has reached
schema v10. The older code does not recognize the new schema and does not
stop, and:

- every lifetime counter it credits is added twice, because its insert no
  longer matches the existing per-instance row and its update then changes
  both rows;
- the searches it records carry no stable ID, so after a later re-upgrade
  the Sonarr tracker never picks them up again;
- because the attribution cutover is already recorded, rows written during
  the rollback are treated as corrected data even though the old,
  uncorrected attribution produced them.

## Emergency only: restoring the pre-upgrade database

Use this only when forward recovery is not possible. It has not been
rehearsed, and it loses data.

1. Stop the container.
2. Move `triggarr.db`, `triggarr.db-wal` and `triggarr.db-shm` out of
   `/config` and keep them.
3. Copy `triggarr.v9-backup` to `/config/triggarr.db`. This is the database
   as it was immediately before the first upgrade attempt.
4. Keep the current `state.json` and `triggarr.toml`.
5. Start the older image.

What this loses or changes:

- **History and counters since the upgrade.** Every search-history row,
  lifetime counter increment, grab-ownership record and the attribution
  cutover written since the upgrade are gone. Counters return to their
  pre-upgrade values. The longer the upgrade has been running, the more is
  lost.
- **Tracking for recent searches.** Searches the *arr apps accepted since
  the upgrade no longer have pending rows, so any grabs they produced are
  never credited or shown.
- **No search replay, as long as `state.json` is kept.** This change does
  not alter `state.json`. Restoring the pre-upgrade `state.json` as well
  would make Triggarr send search commands again for items the *arr apps
  already accepted.
- **Instance IDs.** The older version ignores the `id` values in
  `triggarr.toml`, but saving settings in its web UI removes them. A later
  upgrade then assigns new IDs and associates existing rows by instance name.
- **Re-upgrading.** The next upgrade migrates the restored database to v10
  again and records a new cutover. Everything up to that point, including
  rows written while rolled back, is then treated as pre-correction data
  and disclosed as such.
