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
| Triggarr commit SHA (full) | `a139879794c621692593346f35b3c98700b9b222` | _(empty — fill after Task 2's full matrix run)_ |
| Triggarr image tag | `triggarr:phase81-a139879794` | _(empty)_ |
| Triggarr image ID | `sha256:72e6b23f0697f3748844025ce9dcbc9dff63dbaf8d6852037e986a7859add219` | _(empty)_ |
| Triggarr repo digest | n/a — local NAS build, never pushed to a registry (matches runbook guidance to avoid `@sha256` pins that WUD can't parse; image ID above is the authoritative identity) | _(empty)_ |
| Container start time | `2026-10-19T22:06:35.036944811Z` | _(empty)_ |
| Sonarr version / branch | `5.0.0.2701` / `develop` (sonarr-v5 container; WUD auto-advanced it from the 2026-10-12 `5.0.0.2569` baseline — expected per the sandbox docs) | _(empty)_ |
| Sonarr runtime fingerprint (.NET / SQLite) | `.NET 10.0.13` / `SQLite 3.53.4` | _(empty)_ |
| Date | 2026-10-19 | _(empty)_ |

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

## Matrix

| Scenario | D-ref | v5 Live | v4 Live | Fixture / automated evidence | Notes |
|---|---|---|---|---|---|
| Connection/status and reported application version (v5 -> `"v5"`, v4 -> `"v4"`) | D-11.1 | unverified-live | unverified-live | `tests/test_startup.py::test_detect_api_version_parses_v5`, `tests/test_startup.py::test_detect_api_version_parses_v4`, `tests/test_startup.py::test_detect_api_version_v5_keeps_v3_routes` | Live check must read the sandbox's real `/api/v3/system/status` response, not a fixture-shaped stand-in. |
| Tag lookup | D-11.1 | unverified-live | unverified-live | `tests/test_clients.py::test_get_tags_returns_tag_list`, `tests/test_clients.py::test_get_tags_empty_response` | |
| Missing pagination, incl. `includeSeries` | D-11.1 | unverified-live | unverified-live | `tests/test_clients.py::test_get_paginated_multi_page`, `tests/test_clients.py::test_get_paginated_empty_results` (generic `ArrClient.get_paginated` path shared by Sonarr) | No existing unit test asserts the `includeSeries=true` param value itself on `get_wanted_missing` — that assertion lives only in the source (`triggarr/clients/sonarr.py`). Flagged honestly rather than citing a test that doesn't exist. |
| Cutoff pagination, incl. `includeSeries` | D-11.1 | unverified-live | unverified-live | `tests/test_clients.py::test_get_paginated_multi_page`, `tests/test_clients.py::test_get_paginated_empty_results` (same shared path, `get_wanted_cutoff`) | Same gap as the missing-pagination row: no dedicated `includeSeries` param-value assertion exists today. |
| Library counts (Refresh counts) | D-11.1 | unverified-live | unverified-live | `tests/test_refresh_counts.py::test_refresh_sonarr_counts_returns_counts` | |
| One controlled SeasonSearch accepted | D-11.1 | unverified-live | unverified-live | `tests/test_search.py::test_run_sonarr_cycle_happy_path` (dispatch path only) | No fixture proves a real Sonarr instance accepting a live `SeasonSearch` command -- that is inherently a live-only check. |
| Scheduled cycle graded | D-11.1 | unverified-live | unverified-live | `tests/test_search.py::test_run_sonarr_cycle_happy_path`, `tests/test_search.py::test_sonarr_cycle_records_instance_stable_id`, `tests/test_outcome_upgrade.py::test_upgrade_then_empty_cycle_sonarr` | |
| Repeated tracking checks (>= 2), no repeat credit | D-11.1 | unverified-live | unverified-live | `tests/test_tracking.py::test_owned_grab_not_recredited_to_second_search`, `tests/test_tracking.py::test_restart_does_not_recredit`, `tests/test_attribution_client_path.py::test_client_path_standard_v4_repeated_checks` | |
| Season-pack attribution on the Phase 81 build (credits only its season's search, once, distinct episodes) | D-11.2 | unverified-live (REQUIRED -- blocks SONARRV5-02 and Phase 81 if missing) | not required live (fixture) | `tests/test_attribution_client_path.py::test_client_path_season_pack_credits_season_once`, `tests/test_tracking.py::test_season_pack_repeat_grab_counts_episode_once`, `tests/test_correlation.py::TestSeasonAwareCorrelation::test_correlate_season_pack_fixture_matches_all_including_repeat` | The Hacks S01 season pack already grabbed in the v5 sandbox (`v5test-results.md`, 2026-10-12, release `Hacks.S01.XviD-AFG`) is only a **candidate fixture source** per D-11.2. Its presence in sandbox history does not prove the Phase 81 build's attribution logic processed it -- this row needs a controlled search + tracking check run against the actual Phase 81 commit, not a retroactive read of pre-existing history. |
| Multi-season pack | D-12 | unverified-live | not required live (fixture) | `tests/test_attribution_client_path.py::test_client_path_multi_season_pack_no_cross_season`, `tests/test_correlation.py::TestSeasonAwareCorrelation::test_correlate_multi_season_pack_fixture_splits_by_season` | Per D-12, if this can't be produced live it stays `unverified-live`; the fixture evidence above is never substituted as live proof. |
| Alternate series order | D-12 | unverified-live | not required live (fixture) | `tests/test_attribution_client_path.py::test_client_path_alternate_order_uses_canonical_season`, `tests/test_correlation.py::TestSeasonAwareCorrelation::test_correlate_alternate_order_scene_numbering_ignored` | Same D-12 fallback as the multi-season-pack row. |
| `/api/v3` routes and `X-Api-Key` auth retained | D-11.1 / SONARRV5-02 | unverified-live | unverified-live | `tests/test_startup.py::test_detect_api_version_v5_keeps_v3_routes`, `tests/test_clients.py::test_arr_client_sets_api_key_header` | Confirms route/header behavior in fixtures; live check must show the sandbox's actual request path and header, not a mock transport. |

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
