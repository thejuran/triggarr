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
| Triggarr commit SHA (full) | _(empty)_ | _(empty)_ |
| Triggarr image tag | _(empty)_ | _(empty)_ |
| Triggarr image ID | _(empty)_ | _(empty)_ |
| Triggarr repo digest | _(empty)_ | _(empty)_ |
| Container start time | _(empty)_ | _(empty)_ |
| Sonarr version / branch | _(empty)_ | _(empty)_ |
| Sonarr runtime fingerprint (.NET / SQLite) | _(empty)_ | _(empty)_ |
| Date | _(empty)_ | _(empty)_ |

Prior fingerprint on file (`v5test-results.md`, 2026-10-12, not re-verified for this phase): Sonarr `5.0.0.2569` / develop, .NET 10.0.12, SQLite 3.53.4, image ref `linuxserver/sonarr:develop`, image ID `sha256:64e1d669b88d…`, repo digest `linuxserver/sonarr@sha256:2c1e9317f330…008f53`. This is historical setup evidence, not a current fingerprint — WUD may have advanced the build since.

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
