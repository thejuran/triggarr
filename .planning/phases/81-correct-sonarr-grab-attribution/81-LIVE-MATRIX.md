# Phase 81 Live Acceptance Matrix: SONARRV5-02

Built by Plan 81-06 Task 1. No NAS, sandbox, or production action was taken to produce this file — every Live cell is a placeholder awaiting Plan 07/08 execution, gated by the owner authorization recorded in the Authorization section below.

## Rules

Quoted verbatim from `81-CONTEXT.md`:

- **D-10:** "The intended sequence is that the isolated v4 and v5 sandboxes verify Phase 81 before merge... Sandbox Triggarr must never point at production Sonarr. Read-only checks against production v4 are optional and only supplementary post-deployment observation, never Phase 81 acceptance evidence. Any production deployment needs explicit owner authorization."
- **D-12:** "Alternate series orders and multi-season packs need representative sanitized Sonarr-response fixtures plus real-client-path regression tests (Sonarr-returned series/season/episode identities, never release-title parsing). If they can't be produced live, record them as unverified-live. Fixtures are never presented as live evidence. The acceptance matrix keeps separate live and fixture columns."
- **D-13:** "Pre-merge live verification (D-10) is the intended sequence. As an exception, the implementation PR may merge... while compatibility evidence is still missing. In that case Phase 81 stays incomplete: each requirement is marked complete only when its own acceptance criteria are met, SONARRV5-02 stays open with each unverified scenario listed, Phase 81 stays unchecked in ROADMAP.md, and STATE.md matches. Full v5 support is never claimed."

**API reachability alone is not v5 support.** A successful connection, a 200 status, or an existing grab already sitting in sandbox history proves none of the scenarios below by itself — each row needs its own live evidence or stays `unverified-live`.

## Build identity

Recorded once per sandbox, before and after each live run. Empty until Plan 07/08 execute.

### v5 sandbox (`sonarr-v5` / `triggarr-test`, project `v5test`)

| Field | Before run | After run |
|---|---|---|
| Triggarr commit SHA (full) | `a139879794c621692593346f35b3c98700b9b222` | `a139879794c621692593346f35b3c98700b9b222` (unchanged — same container throughout) |
| Triggarr image tag | `triggarr:phase81-a139879794` | `triggarr:phase81-a139879794` |
| Triggarr image ID | `sha256:72e6b23f0697f3748844025ce9dcbc9dff63dbaf8d6852037e986a7859add219` | `sha256:72e6b23f0697f3748844025ce9dcbc9dff63dbaf8d6852037e986a7859add219` (unchanged) |
| Triggarr repo digest | n/a — local NAS build, never pushed to a registry (matches runbook guidance to avoid `@sha256` pins that WUD can't parse; image ID above is the authoritative identity) | n/a (same) |
| Container start time | `2026-10-19T22:06:35.036944811Z` | `2026-10-19T22:06:35.036944811Z` (unchanged — no restart, no WUD interruption during the run) |
| Sonarr version / branch | `5.0.0.2701` / `develop` (sonarr-v5 container; WUD auto-advanced it from the 2026-10-12 `5.0.0.2569` baseline — expected per the sandbox docs) | `5.0.0.2701` / `develop` (unchanged; sonarr-v5 `StartedAt` also unchanged at `2026-10-19T16:01:45Z` — no interruption) |
| Sonarr runtime fingerprint (.NET / SQLite) | `.NET 10.0.13` / `SQLite 3.53.4` | `.NET 10.0.13` / `SQLite 3.53.4` (unchanged) |
| Date | 2026-10-19 | 2026-10-19 |

Evidence: `v5test-results/81-5-fingerprint-after.txt`. All three sandbox containers' start times are identical before and after the controlled run — no WUD update or restart occurred, so nothing needed to be repeated.

Prior fingerprint on file (`v5test-results.md`, 2026-10-12, not re-verified for this phase): Sonarr `5.0.0.2569` / develop, .NET 10.0.12, SQLite 3.53.4, image ref `linuxserver/sonarr:develop`, image ID `sha256:64e1d669b88d…`, repo digest `linuxserver/sonarr@sha256:2c1e9317f330…008f53`. This is historical setup evidence, not a current fingerprint — WUD may have advanced the build since (confirmed above: it has).

**Deployment confirmed (2026-10-19, docker-only, passwordless):** `triggarr-test` now runs the exact Phase 81 commit, built on the NAS from `git archive HEAD` (never the Mac's arm64 build) in `/volume1/docker/v5test/build-phase81-a139879794`, tagged `triggarr:phase81-a139879794` with an `org.opencontainers.image.revision` label matching the commit SHA exactly. Only `/volume1/docker/v5test/docker-compose.yml`'s `triggarr-test` image line was changed (backup kept at `docker-compose.yml.bak-phase81-a139879794`); `sonarr-v5` and `seedsyncarr-test` container start times are unchanged from before the recreate, confirming only the one service was touched. Startup logs (sanitized, no keys) confirm: schema migration v9 → v10 ran ("add grab ownership, attribution cutover and stable-id association"), the attribution cutover was recorded (`pre-fix Sonarr data: False, instances: 1`), and the `v5test` Sonarr instance's configured URL is `http://sonarr-v5:8989` (read directly from the host-owned `triggarr.toml`, which is outside prod and contains no `sonarr:8989` reference). Evidence: `v5test-results/81-1-fingerprint-before.txt`.

**Deferred to Task 2 (assumption drift, advisory — see Task 1 execution note below):** the plan's Task 1 step 5 expected the startup log to already show "Detected API v5" at this point. The code only runs that detection for *enabled* Sonarr instances (`validate_connections` iterates `get_enabled_instances`), and the `v5test` instance must stay `enabled=false` until the owner's `SEARCHES=on` + Deluge-destination gates pass (owner decision, 2026-10-19: never enable schedule/monitoring before those gates pass). So the live "v5" detection log and the Settings "Test connection" result are confirmed in Task 2, after the owner's gates authorize enabling the instance — not a gap, just later in the sequence than the plan's prose assumed.

### v4 sandbox (not yet provisioned)

| Field | Before run | After run |
|---|---|---|
| Triggarr commit SHA (full) | _(empty — sandbox does not exist)_ | _(empty)_ |
| Triggarr image tag | _(empty)_ | _(empty)_ |
| Triggarr image ID | _(empty)_ | _(empty)_ |
| Triggarr repo digest | _(empty)_ | _(empty)_ |
| Container start time | _(empty)_ | _(empty)_ |
| Sonarr version / branch | _(empty)_ | _(empty)_ |
| Sonarr runtime fingerprint (.NET / SQLite) | _(empty)_ | _(empty)_ |
| Date | _(empty)_ | _(empty)_ |

**Note:** WUD (`dockercompose.v5test` trigger, 6-hourly digest watch) auto-updates the v5 sandbox's Sonarr and Triggarr test containers on its own schedule. Any run interrupted by a WUD update or an unplanned container restart must be repeated in full — a fingerprint captured before the interruption cannot be assumed to still match the container that finished the run.

### Plan 07 Task 1 execution note (2026-10-19)

Blocked before any sandbox change. `setup-sonarr-v5-test.sh`'s `ACTION=verify` / `ACTION=deluge-check` paths (and the script generally) start with `sudo -v` and use bare `sudo` throughout (config reads, `mkdir`/`chown`, embedded `python3` checks) — only `/usr/local/bin/docker` and `/usr/local/bin/docker-compose` are NOPASSWD on this NAS (per `CLAUDE.md`). Both `ssh nas '...'` and `ssh -t nas '...'` invocations of the script failed identically: `sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper` / `sudo: a password is required`. Confirmed with `sudo -n true` (fails) vs. `sudo -n -l` (succeeds, non-interactive — lists only the two NOPASSWD docker entries). No askpass helper is configured. This is a genuine interactive-credential requirement, not a script bug: the isolation/Deluge-destination gate cannot be produced by the automated executor in this session.

No NAS or sandbox state was changed: all reads were via already-world-readable/writable files or the passwordless `docker inspect` path. Confirmed `triggarr-test`'s current (pre-change) identity: image `ghcr.io/thejuran/triggarr:main`, image ID `sha256:91fa99eea2ef972bf94370c7bb0732d148f25abf3e0d3c887a5f05c711420197`, revision label `c914cbca16bb550fed5ab3dbd87a625d39ccca75` (not the Phase 81 build), started `2026-10-18T02:44:05Z`. The `v5test` Sonarr instance in `triggarr-test`'s config remains `enabled = false` (unchanged baseline). The Phase 81 build (`git rev-parse HEAD` = `9f7da49edf3983a4de318675f155e1b5f573f9ea`, clean tree confirmed against `triggarr tests Dockerfile pyproject.toml uv.lock`) was never built or deployed. No isolation or Deluge-destination gate was run, so every v5 Live cell in `## Matrix` stays `unverified-live` for this reason, not a failed check.

Task 2 did not run (depends on Task 1's gates). Per the plan's own Task 1 instruction ("If any gate fails: stop, restore the baseline... record the failure, and go to the Task 3 checkpoint"), this is reported as a blocking checkpoint rather than an owner-reviewable result.

### Plan 07 Task 1 continuation (2026-10-19, same date)

Owner decision: "You run the gates" — the owner runs every step needing interactive sudo (the isolation gate, Deluge-destination check, any sudo-requiring fingerprint) personally in their own terminal; the executor does everything that works password-free.

Completed without a password, in order:
1. Confirmed the Phase 81 build identity: `git rev-parse HEAD` = `a139879794c621692593346f35b3c98700b9b222` (branch `phase-81-sonarr-attribution`); `git status --porcelain -- triggarr tests Dockerfile pyproject.toml uv.lock` empty (clean).
2. Captured a pre-change fingerprint using `sudo /usr/local/bin/docker inspect`/`exec` only (NOPASSWD): all three sandbox containers' image refs/IDs/digests/start times, plus Sonarr's own `/api/v3` and `/api/v5` `system/status` (both reporting `5.0.0.2701`/`develop`, read via the sonarr-v5 container's own world-readable `/config/config.xml` API key, not the host-level file). Confirmed `triggarr-test` was still byte-for-byte the container recorded in the prior blocker note (same image ID, same start time) — no drift while blocked. Saved sanitized to `v5test-results/81-1-fingerprint-before.txt`.
3. Streamed `git archive --format=tar HEAD` over `ssh nas` into a fresh `/volume1/docker/v5test/build-phase81-a139879794` (world-writable dir, no sudo needed to create it) and built with `sudo /usr/local/bin/docker build --label org.opencontainers.image.revision=<sha> -t triggarr:phase81-a139879794 .` (NOPASSWD docker build). Image ID `sha256:72e6b23f0697f3748844025ce9dcbc9dff63dbaf8d6852037e986a7859add219`; revision label confirmed to match the SHA exactly.
4. Backed up `/volume1/docker/v5test/docker-compose.yml` (world-writable, owned by <nas-user>) to `docker-compose.yml.bak-phase81-a139879794`, changed only the `triggarr-test` service's `image:` line, and ran `sudo /usr/local/bin/docker compose -p v5test up -d triggarr-test` (NOPASSWD). Confirmed via `docker inspect`: `triggarr-test` now runs the new image/ID/revision; `sonarr-v5` and `seedsyncarr-test` start times unchanged (only the one service was recreated).
5. Read startup logs (NOPASSWD `docker logs`): schema migration v9 → v10 ran, attribution cutover recorded (`pre-fix Sonarr data: False, instances: 1`), banner shows `Sonarr/v5test: disabled` (instance still disabled, matching the required pre-gate baseline). No secrets appear in the captured logs.
6. Read the `v5test` instance's configured Sonarr URL directly from the host-owned (`<nas-user>:users`, mode 600) `/volume1/docker/v5test/triggarr/triggarr.toml` — no sudo or docker exec needed, since the SSH session already owns the file. Confirmed `url = "http://sonarr-v5:8989"` (never `sonarr:8989`), `enabled = false`, `search_missing_count`/`search_cutoff_count` both positive (so enabling later will pass the app's own validation). The raw file (contains the v5test Sonarr API key, Triggarr's own API key, and a bcrypt password hash) was read transiently and never written to any saved file — only these sanitized facts are recorded here.

Not done (owner's role, not yet run): `ACTION=verify SEARCHES=off` — the next required gate before anything that could enable searching. No controlled-test prep (monitoring a series, enabling the schedule) has happened or will happen before this gate's output is read and confirmed `ALL ISOLATION CHECKS PASSED`.

This is reported as a checkpoint (type human-action), not a blocker: everything password-free is done, and the next step is squarely the owner's per the 2026-10-19 decision.

### Gate 1 result: `SEARCHES=off` — PASSED (owner-run, 2026-10-19 17:40 ET)

Owner ran `ACTION=verify SEARCHES=off bash /tmp/setup-sonarr-v5-test.sh` interactively (their own sudo password). Output: 46 lines, ends `ALL ISOLATION CHECKS PASSED`, `isolation checks failed: 0`. Sanitized copy (no keys found by grep) saved to `v5test-results/81-2-verify-searches-off.txt`; NAS auto-saved copy `/volume1/docker/v5test/results/verify-20261019-174049.txt`.

Key facts from this run: Sonarr v5 is now `5.0.0.2701`/develop (WUD advanced it further since the Task 1 fingerprint captured minutes earlier at the same version); `triggarr-test` confirmed resolving `sonarr-v5` by name (not prod), v5 key rejected by prod (401); no prod cross-references in either direction; `sonarr-v5 RSS sync interval: 0 min`, indexers <private indexers> have their per-indexer RSS flag already on (harmless while the global interval is 0); **series: 2 (0 monitored)** — one more series exists than the 2026-10-12 record (`Hacks` only); `scheduled RSS grabbing: OFF`, matching `SEARCHES=off`.

### Runbook Step 4 ordering conflict — surfaced, not resolved unilaterally

The runbook's Step 4 text ("Set RSS Sync Interval back to 15, enable the triggarr-test schedule, and monitor the test series. **Then** run `ACTION=verify SEARCHES=on`...") assumes those three actions happen *before* the `SEARCHES=on` gate, because that gate's own pass condition requires them: `search_state()` in the script only checks Sonarr's global RSS Sync Interval and per-indexer RSS flags (prints, but does not gate on, monitored series count) — `scheduled = bool(rss) and bool(rss_idx)`; it fails with `SEARCHES=on expected, but RSS sync is off` unless the interval is already non-zero. Likewise `deluge_check()` fails (`NONE no torrents labelled tv-v5test yet`) unless a `tv-v5test`-labelled torrent already exists in Deluge — i.e. an actual grab, from Sonarr or from Triggarr, needs to have happened or still be seeding.

This directly conflicts with the owner's 2026-10-19 instruction: *"Never start any controlled search (schedule enable, series monitor, SeasonSearch) until the owner-run SEARCHES=on gate AND Deluge-destination check output ... show ALL ISOLATION CHECKS PASSED and DELUGE DESTINATIONS PASSED."* All three listed actions are exactly what Step 4 wants done first. No prep that would enable or fire a search was performed; this is reported as a checkpoint question rather than decided unilaterally. See the Task 1/2 checkpoint for the question and options put to the owner.

### Owner decision: "Executor sets RSS, I run 1 cmd" (2026-10-19, interactive)

Scope given: change only `sonarr-v5`'s global RSS Sync Interval via the sandbox API (never touch monitoring, never enable the `triggarr-test` `v5test` instance, never trigger a search); then hand the owner one combined command for `SEARCHES=on` + `deluge-check`; after the owner reports back, the executor verifies both files itself and only then (if both passed, accepting the existing Hacks S01 torrent for the Deluge check) proceeds to monitor Hacks Season 2 and enable the `v5test` instance for Task 2's controlled run. No post-grab Deluge re-check was requested.

**Done:** `PUT /api/v3/config/indexer/1` against `sonarr-v5` (LAN `:8990`, never production `sonarr`) changed `rssSyncInterval` `0` → `15`, all other fields unchanged (`minimumAge`, `retention`, `maximumSize` all `0`, `id` `1`). Re-fetched `GET /api/v3/config/indexer` to confirm the value stuck. Confirmed immediately after: both series (`Hacks`, `That Mitchell and Webb Look`) still `monitored: false`; `triggarr-test`'s `/volume1/docker/v5test/triggarr/triggarr.toml` still has `enabled = false` for `[sonarr.v5test]`. No series was monitored, no instance was enabled, no search was triggered.

### Gate 2 result: `SEARCHES=on` + `deluge-check` — BOTH PASSED (owner-run, 2026-10-19 18:31 ET)

Owner ran the combined command (`ACTION=verify SEARCHES=on ... && ACTION=deluge-check ...`, single sudo prompt) interactively. Both sanitized (no keys found by grep) and saved:

- `v5test-results/81-3-verify-searches-on.txt` (46 lines) — ends `ALL ISOLATION CHECKS PASSED`, `isolation checks failed: 0`. `sonarr-v5 RSS sync interval: 15 min` (the change above took effect), indexers <private indexers> RSS+auto-search on, `series: 2 (0 monitored)` (unchanged — nothing monitored yet, as scoped), `scheduled RSS grabbing: ON`, matching `SEARCHES=on`.
- `v5test-results/81-3-deluge-check.txt` (19 lines) — ends `DELUGE DESTINATIONS PASSED`, `deluge-check failures: 0`. Passed against the **existing** `Hacks.S01.XviD-AFG` torrent from 2026-10-12 (`state=Seeding 100%`, `download=/home/<seedbox-user>/v5test`, not in prod staging, pulled into the sandbox) — no fresh grab was needed or triggered, consistent with the owner's "no post-grab Deluge re-check requested" scope. Matches the orchestrator's independent read (line 45/43 of the verify file, line 18 of the deluge-check file).

Both gates now passed. Per the owner's 2026-10-19 scoping, this authorizes: monitor Hacks Season 2 only, enable the `triggarr-test` `v5test` instance, and proceed with Task 2's controlled run.

### Task 2: controlled run in progress (2026-10-19, continuing same date)

**Monitored Hacks Season 2 only:** `PUT /api/v3/series/1` against `sonarr-v5` set `monitored: true` on the series and `monitored: true` on season 2 only (seasons 1/3/4/5 stay `false`; season 1 was already fully grabbed 2026-10-12 and stays untouched). `That Mitchell and Webb Look` (series 2) untouched, still fully unmonitored. Confirmed via a fresh `GET /api/v3/series`.

**Enabled the `triggarr-test` `v5test` instance:** via Triggarr's own `POST /settings` (authenticated with Triggarr's internal `X-Api-Key`, not a session cookie — preserves the app's Pydantic validation + atomic TOML write, rather than hand-editing the config file), submitting the instance's existing `url`/`api_key`/`search_interval`/`search_missing_count`/`search_cutoff_count` unchanged and only flipping `enabled` to `true`, with the `[general]` block resubmitted at its current values to avoid resetting anything. Confirmed by re-reading `triggarr.toml` (`enabled = true`) and by the container log.

**This immediately fired the scheduler's "first run: now" cycle, as expected and previously flagged:** log line `Enabled Sonarr/v5test search every 30m` followed at 2026-10-19T19:34:45 local by `Sonarr: Searched Hacks - Season 2 (missing)`, `Cycle completed in 0.5s -- 8 fetched, 1 accepted, 0 failed, 0 history not saved -- grade success`. Sonarr accepted and grabbed **`Hacks S02 1080p BluRay x264-BRAVERY`** via **<private indexers> (Prowlarr)**, freeleech, `downloadId 3E4FEA683286B4FAD6CCDA4C8F8F60A880C7D9C5`, landing in `/home/<seedbox-user>/v5test-incomplete/...` (sandbox path, confirmed via Sonarr's queue — never prod staging). This is the plan's required "one controlled SeasonSearch accepted" (D-11.1), produced live by the Phase 81 build, for a season genuinely distinct from the pre-existing Hacks S01 grab.

Triggarr's own `search_history` recorded it immediately: `{id: 1, app: Sonarr, instance_id: v5test, item_name: "Hacks - Season 2", outcome: searched, detail: "search triggered", season_number: 2, resolved_at: null}`. `grab_ownership` has no rows yet (nothing credited — the grab hasn't resolved/imported yet) and `lifetime_stats` for Sonarr still shows only the original 2026-10-12 seed row (`instance_id: Default`, `0/0`) — expected, since D-08 keys lifetime stats by stable instance ID and this instance's first-ever credit hasn't landed. Saved: `v5test-results/81-4-db-check-1-post-search.txt`.

The same cycle's tracking pass logged 10 `Tracking[v5test]: skipped grab N for series 1 -- missing season` warnings — these are Sonarr's **pre-existing** Hacks S01 grab-history entries from the 2026-10-12 manual Interactive Search (never dispatched by Triggarr, so they don't correlate to any Triggarr `search_history` row for the right season). `attribution_cutover` confirms `any_pre_fix_sonarr_data: 0` (this instance has no pre-fix Sonarr data — correct, it's a fresh instance), so these warnings are expected background noise from the earlier manual grab, not a Phase 81 defect.

### Task 2 finding: Sonarr v5 (5.0.0.2701/develop) does not supply episode/season identity via the grab-history endpoint — season-pack attribution cannot be credited live under this build

A background poll ran for 80 minutes (20 checks, every 4 min) after the grab. The download completed and Sonarr imported it (`GET /api/v3/episode/18` → `episodeFile.dateAdded: 2026-10-19T23:55:48Z`, ~21 minutes after the grab) well within the window, and two further scheduled Triggarr cycles ran afterward (`20:04:44`, `20:34:44`, both graded `nothing_needed` since nothing remained missing). Across all three cycles' tracking passes, `grab_ownership` stayed empty and `lifetime_stats` stayed at the original 2026-10-12 seed values — the grab was never credited, not because of a timing race, but because of a structural cause confirmed directly against the live API:

`triggarr/clients/sonarr.py`'s `get_grab_history()` calls `GET /api/v3/history/series?includeEpisode=true` expecting a nested `episode` object carrying `seasonNumber`. On this Sonarr v5 build, **that parameter has no observable effect**: the response's keys are byte-identical with and without `includeEpisode=true`, and no `episode` object is nested anywhere in any of the 18 grab records returned for this series (confirmed by direct comparison, not inference). `triggarr/correlation.py`'s `sonarr_identity_problem()` correctly refuses to trust a grab lacking season identity (reason: `"missing season"`) — this is the T-81 identity gate working exactly as designed, not a Phase 81 logic bug. The practical consequence: **no Sonarr v5 grab from this build can ever be credited** by the current code, for the pre-existing Hacks S01 grabs *or* the new, live, Phase-81-dispatched Hacks S02 grab alike.

A working alternative exists and was confirmed live: `GET /api/v3/episode/{episodeId}` (e.g. `/api/v3/episode/18`) returns `seasonNumber: 2` directly. Triggarr does not currently call this endpoint as a fallback. Adding it would be new client behavior (a second API call per grab, its own error handling, its own tests) — a real design decision, not a one-line fix, so no code change was made during this live-verification run. Evidence (sanitized, no keys, no download URLs): `v5test-results/81-4-v5-grab-history-identity-gap.txt`.

**This means D-11.2 (season-pack attribution, live) is not unverified-live — it is live-verified to FAIL** against the current Sonarr v5 beta build, with a precise, reproducible root cause. D-11.1's "repeated tracking checks, no repeat credit" is also affected: nothing was ever credited, so the positive half of that assertion (a credited grab stays stable across checks) could not be demonstrated; the negative half (no double-crediting, no counter inflation) held across all three cycles, which is at least consistent but not the full evidence the row wants.

Per the owner's scope, no post-grab Deluge re-check was requested for this run, and none was performed.

### Baseline restored (2026-10-19, after the controlled run)

In reverse order of setup, all via API (no hand-edited config files):

1. **Disabled the `triggarr-test` `v5test` instance** again via `POST /settings` (same validated path as enabling it) — confirmed `enabled = false` in `triggarr.toml`.
2. **Unmonitored Hacks** — `PUT /api/v3/series/1` set `monitored: false` on the series and on every season (1–5). `That Mitchell and Webb Look` was never touched. Confirmed via a fresh `GET /api/v3/series`: both series `monitored: false`, no season monitored on either.
3. **Reset `sonarr-v5`'s RSS Sync Interval back to `0`** (the runbook's prescribed baseline) via `PUT /api/v3/config/indexer/1` — confirmed via a fresh `GET /api/v3/config/indexer`.

Confirmed no further scheduled cycles ran after step 1 (container logs show only the `refresh-counts` API calls used to gather matrix evidence, correctly rate-limited on repeated calls — no further `Tracking:`/`Cycle completed` lines). The Hacks Season 2 download remains imported into the sandbox library (`/data/media/tv/Hacks/Season 2/`) — this is real sandbox content from the authorized controlled test, left in place exactly as the original 2026-10-12 Hacks S01 grab was, not cleaned up.

**Sandbox end state:** `triggarr-test` `v5test` instance disabled; both series fully unmonitored; `sonarr-v5` RSS Sync Interval `0`; all three containers' start times unchanged throughout the entire run (no WUD interruption, nothing to repeat).

## Matrix

| Scenario | D-ref | v5 Live | v4 Live | Fixture / automated evidence | Notes |
|---|---|---|---|---|---|
| Connection/status and reported application version (v5 -> `"v5"`, v4 -> `"v4"`) | D-11.1 | pass | unverified-live | `tests/test_startup.py::test_detect_api_version_parses_v5`, `tests/test_startup.py::test_detect_api_version_parses_v4`, `tests/test_startup.py::test_detect_api_version_v5_keeps_v3_routes` | Live `/api/v3/system/status` and `/api/v5/system/status` both returned `version: 5.0.0.2701` (identical bodies). The connection succeeded and a live cycle ran to completion through `SonarrClient`, which requires a working connection; the specific startup-banner "Detected API v5" log line needs a fresh process start (the instance was enabled mid-run via `/settings`, not at container boot) and was not forced by restarting the container, to avoid repeating the controlled test. Evidence: `v5test-results/81-4-db-check-1-post-search.txt`, `81-5-fingerprint-after.txt`. |
| Tag lookup | D-11.1 | pass (thin) | unverified-live | `tests/test_clients.py::test_get_tags_returns_tag_list`, `tests/test_clients.py::test_get_tags_empty_response` | Live `GET /api/v3/tag` returned `[]` (200, valid empty list) — no tags are configured in the sandbox. Confirms the endpoint resolves and parses under v5, but does not exercise a populated tag list. |
| Missing pagination, incl. `includeSeries` | D-11.1 | pass (thin) | unverified-live | `tests/test_clients.py::test_get_paginated_multi_page`, `tests/test_clients.py::test_get_paginated_empty_results` (generic `ArrClient.get_paginated` path shared by Sonarr) | Live `GET /api/v3/wanted/missing?includeSeries=true` returned a well-formed, valid pagination envelope (`totalRecords: 0`) — nothing is currently missing (Season 2 fully imported, other seasons unmonitored), so the record-shape/`includeSeries` population itself could not be exercised with real records. |
| Cutoff pagination, incl. `includeSeries` | D-11.1 | pass (thin) | unverified-live | `tests/test_clients.py::test_get_paginated_multi_page`, `tests/test_clients.py::test_get_paginated_empty_results` (same shared path, `get_wanted_cutoff`) | Live `GET /api/v3/wanted/cutoff?includeSeries=true` returned a well-formed, valid pagination envelope (`totalRecords: 0`), same caveat as the missing-pagination row — no cutoff-unmet episodes exist to exercise record shape. |
| Library counts (Refresh counts) | D-11.1 | pass | unverified-live | `tests/test_refresh_counts.py::test_refresh_sonarr_counts_returns_counts` | Triggered live via `POST /api/refresh-counts/sonarr/v5test`; the rendered card showed `Missing: 0 (0 of 0, pass 1)`, `Cutoff Unmet: 0 (0 of 0)`, `Connected`, correct last-checked/next-schedule timestamps — the full refresh-counts mechanism works end-to-end against v5. |
| One controlled SeasonSearch accepted | D-11.1 | pass | unverified-live | `tests/test_search.py::test_run_sonarr_cycle_happy_path` (dispatch path only) | Live: enabling the `v5test` instance fired the scheduler's immediate cycle; Triggarr dispatched a `SeasonSearch` for Hacks Season 2 and Sonarr accepted and grabbed `Hacks S02 1080p BluRay x264-BRAVERY` via <private indexers> (freeleech), landing in the sandbox path. Confirmed via Sonarr's queue/history and Triggarr's own `search_history` row. Evidence: `v5test-results/81-4-db-check-1-post-search.txt`. |
| Scheduled cycle graded | D-11.1 | pass | unverified-live | `tests/test_search.py::test_run_sonarr_cycle_happy_path`, `tests/test_search.py::test_sonarr_cycle_records_instance_stable_id`, `tests/test_outcome_upgrade.py::test_upgrade_then_empty_cycle_sonarr` | Three scheduled (non-manual) cycles ran: `19:34:45` graded `success` (the controlled grab), `20:04:44` and `20:34:44` both graded `nothing_needed` (correctly found nothing left to search). All three were the interval scheduler's own runs, not manual triggers. |
| Repeated tracking checks (>= 2), no repeat credit | D-11.1 | **FAIL** | unverified-live | `tests/test_tracking.py::test_owned_grab_not_recredited_to_second_search`, `tests/test_tracking.py::test_restart_does_not_recredit`, `tests/test_attribution_client_path.py::test_client_path_standard_v4_repeated_checks` | Three tracking passes ran (19:34, 20:04, 20:34) after the live grab. The negative half held (no double-crediting, no counter inflation — nothing was ever credited at all). The positive half (a credited grab stays stable across checks) could not be demonstrated: see the Season-pack attribution row below — the grab was never credited in the first place, for a root cause unrelated to timing. |
| Season-pack attribution on the Phase 81 build (credits only its season's search, once, distinct episodes) | D-11.2 | **FAIL (REQUIRED — blocks SONARRV5-02 and Phase 81)** | not required live (fixture) | `tests/test_attribution_client_path.py::test_client_path_season_pack_credits_season_once`, `tests/test_tracking.py::test_season_pack_repeat_grab_counts_episode_once`, `tests/test_correlation.py::TestSeasonAwareCorrelation::test_correlate_season_pack_fixture_matches_all_including_repeat` | **Live-verified to fail, with a precise root cause** (not merely unverified): a genuinely fresh, live, Phase-81-dispatched SeasonSearch for Hacks Season 2 was fired, accepted, downloaded, and imported by Sonarr (confirmed via `episodeFile.dateAdded`) — but `grab_ownership` and `lifetime_stats` never recorded a credit across three tracking passes over ~80 minutes. Root cause: this Sonarr v5 build's `/api/v3/history/series?includeEpisode=true` does not nest episode/season identity in its response (confirmed by direct, byte-for-byte comparison with and without the flag) — `triggarr/clients/sonarr.py`'s `get_grab_history()` relies on that nested object, so `triggarr/correlation.py`'s `sonarr_identity_problem()` correctly refuses to trust any Sonarr v5 grab as `"missing season"` (the T-81 identity gate working as designed, not a Phase 81 defect). A working alternative (`GET /api/v3/episode/{episodeId}`, confirmed to return `seasonNumber` directly) exists but is not currently used; adopting it is new client behavior needing its own design and tests, not an in-place fix, so none was made during this verification run. This is unrelated to the pre-existing Hacks S01 history (also never a fixture substitute) — the live Season 2 grab is the actual evidence. Evidence: `v5test-results/81-4-v5-grab-history-identity-gap.txt`, `81-4-db-check-1-post-search.txt`, `81-4-db-check-final.txt`. |
| Multi-season pack | D-12 | unverified-live | not required live (fixture) | `tests/test_attribution_client_path.py::test_client_path_multi_season_pack_no_cross_season`, `tests/test_correlation.py::TestSeasonAwareCorrelation::test_correlate_multi_season_pack_fixture_splits_by_season` | Per D-12, if this can't be produced live it stays `unverified-live`; the fixture evidence above is never substituted as live proof. Given the identity-gate finding above, a live multi-season-pack credit would fail the same way for the same root cause. |
| Alternate series order | D-12 | unverified-live | not required live (fixture) | `tests/test_attribution_client_path.py::test_client_path_alternate_order_uses_canonical_season`, `tests/test_correlation.py::TestSeasonAwareCorrelation::test_correlate_alternate_order_scene_numbering_ignored` | Same D-12 fallback as the multi-season-pack row. |
| `/api/v3` routes and `X-Api-Key` auth retained | D-11.1 / SONARRV5-02 | pass | unverified-live | `tests/test_startup.py::test_detect_api_version_v5_keeps_v3_routes`, `tests/test_clients.py::test_arr_client_sets_api_key_header` | Live: every Sonarr call made during this run (status, series, tag, wanted/missing, wanted/cutoff, episode, config/indexer, history/series, and Triggarr's own dispatched `SeasonSearch`) used `/api/v3` paths with `X-Api-Key` header auth, against the real sandbox, not a mock transport. |

## Authorization

_Recorded by Plan 81-06 Task 2 after the owner's decision, given interactively via the orchestrator's question prompt._

- **Selected option:** option-a -- "Authorize both: v5 deployment of the Phase 81 build and v4 sandbox provisioning"
- **Date:** 2026-10-19
- **v5 deployment of the Phase 81 build:** authorized -- build a Triggarr image from the exact Phase 81 commit on the NAS, run it only as the existing `triggarr-test` container in the isolated `v5test` project (never production), pass the runbook's isolation and Deluge-destination gates, then run the controlled matrix in `## Matrix` above and record results.
- **v4 sandbox provisioning:** authorized -- create a new isolated Sonarr v4 sandbox next to the v5 one (own data folders, own download category, same isolation checks), then run the same controlled matrix.
- **Constraints:** None stated beyond the plan's and runbook's existing isolation gates (production untouched, sandbox Triggarr never points at production Sonarr per D-10).

Plans 07 and 08 act only within this authorized scope. Any row not produced live under this authorization stays `unverified-live`, SONARRV5-02 stays open, and Phase 81 stays incomplete per D-13.

## Evidence locations

Sanitized result files only -- no API keys, no production URLs, no raw Sonarr/Triggarr config dumps.

- NAS: `/volume1/docker/v5test/results/`
- Laptop: `/Users/julianamacbook/Cowork/mediaserver/v5test-results/`

Both locations already hold the 2026-10-12 isolation/setup evidence (`v5test-results.md` and its numbered step files) and the empty "Phase 81 compatibility checks" table that Plans 07/08 are expected to fill in once authorized. Nothing in this plan added, removed, or touched any file at either location.

---

*Phase: 81-correct-sonarr-grab-attribution*
*Created: 81-06 Task 1, 2026-10-19*
