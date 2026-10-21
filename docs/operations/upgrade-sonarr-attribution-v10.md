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
  its own backup (`triggarr.vN-backup`, see below) before migrating.

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
rehearsed, and it loses data. Complete steps 1–3 before touching the live
database; if any step fails, stop and follow "If any step fails" below.

1. **Find the real pre-upgrade backup.** Do not assume a file name. On its
   first start, the upgrade logged `Database backed up to <path>`, and the
   file is named after the schema version the database had before the
   upgrade: `triggarr.v9-backup` when upgrading from v2.7 through v2.11.x,
   and a lower number (for example `triggarr.v8-backup` from v2.5.x) from
   older releases. If an earlier attempt had already made one, the upgrade
   kept it and also wrote
   `triggarr.vN-backup-<timestamp>`; the file without a timestamp is the
   earliest, taken before any attempt. A brand-new database has no backup.
   The copy you saved yourself under "Before upgrading" is the other
   candidate.
2. **Check that backup, on a copy, before using it.** Copy it outside
   `/config` and, with the `sqlite3` tool, confirm that
   `PRAGMA integrity_check;` prints `ok` and that
   `SELECT version FROM schema_version;` prints the pre-upgrade version (the
   number in the backup's name, such as 9 for `triggarr.v9-backup`). Never
   continue with a version of 10 or more: that is not a pre-upgrade
   database.
3. **Choose a compatible image.** Use the image you ran before the
   upgrade. Its schema version must be at least the backup's version, and
   it must be a build without the attribution correction (v2.11.x or
   earlier). An image older than the backup's schema version does not
   recognize it and does not stop.
4. Stop the container.
5. Move `triggarr.db`, `triggarr.db-wal` and `triggarr.db-shm` out of
   `/config` and keep them.
6. Copy the checked backup to `/config/triggarr.db`, and confirm the copy
   matches it byte for byte (for example, with `sha256sum` on both).
7. Keep the current `state.json` and `triggarr.toml`.
8. Start the image from step 3, and only if every step above succeeded.

If any step fails — no backup can be found, a check does not print the
expected result, no compatible image is available, or a copy or move fails
— do not start Triggarr with any image. Leave the container stopped, put
the files from step 5 back into `/config` unchanged, and recover forward
with a fixed newer build instead. Starting an older image against a missing
or partly restored database creates a new, empty one; starting it against
the v10 database causes the problems listed under "Do not roll back by
changing the image only".

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
