---
phase: 81-correct-sonarr-grab-attribution
plan: 10
subsystem: testing
tags: [sonarr, fixtures, v5, nas, sandbox, hygiene]

# Dependency graph
requires:
  - phase: 81-02
    provides: "tests/sonarr_fixtures.py loader and the original four synthesized Sonarr fixtures this plan relabels/replaces"
  - phase: 81-07
    provides: "the live v5 identity-gap finding (81-4-v5-grab-history-identity-gap.txt) this plan's live capture independently reproduces"
provides:
  - "Sanitized, live-captured real Sonarr v5 fixtures: history_season_pack_v5.json (18 grab records, no nested episode key) and episodes_v5.json (series episode list + per-episode-id lookups)"
  - "Three schema-derived fixtures relabelled honestly as *_nested_synth.json with origin: synthesized and a shape_note explaining why they stay synthetic"
  - "sonarr_fixtures.py origin validation (live-capture vs. synthesized) plus load_sonarr_episode_fixture/load_sonarr_series_episode_list loaders"
  - "tests/test_sonarr_fixture_hygiene.py guarding every Sonarr fixture against credential/path/host leakage and pinning the no-nested-episode-key live finding"
affects: [81-11, 81-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only, version-guarded capture scripts run via ssh with the API key held only in a remote shell/env var, never echoed or written to any file, piped into a sanitizer that fails closed on any residual secret/path/URL before the result is written to the repo"
    - "Fixture _meta.origin as an explicit live-capture vs. synthesized discriminator, enforced by the loader, distinct from the pre-existing live_evidence: false flag which both origins always carry"

key-files:
  created:
    - tests/fixtures/sonarr/episodes_v5.json
    - tests/fixtures/sonarr/history_season_pack_nested_synth.json
    - tests/fixtures/sonarr/history_multi_season_pack_nested_synth.json
    - tests/fixtures/sonarr/history_alternate_order_nested_synth.json
    - tests/test_sonarr_fixture_hygiene.py
  modified:
    - tests/fixtures/sonarr/history_season_pack_v5.json
    - tests/fixtures/sonarr/history_standard_v4.json
    - tests/sonarr_fixtures.py
    - tests/test_correlation.py
    - tests/test_clients.py
    - tests/test_attribution_client_path.py

key-decisions:
  - "Capture via a two-stage ssh script: an outer bash script reads the sandbox API key from sonarr-v5's own /config/config.xml (NOPASSWD docker exec) into an env var and never echoes it; a heredoc-embedded Python script reads the key only from os.environ and makes all GETs, so no shell string-interpolation of the key or of any response body was needed anywhere"
  - "Sanitizer applies a whitelist to episode objects (id, seriesId, tvdbId, seasonNumber, episodeNumber, title, airDate, airDateUtc, hasFile, monitored, plus any scene/absolute-numbering key) rather than a blacklist, so nested episodeFile/overview/images/series objects and any untracked future upstream field are dropped by default, not just the fields observed in this one capture"
  - "The same shape_note text applies to all three *_nested_synth.json files since the generic reason (synthesized from the v3 OpenAPI schema; v5 omits the nested episode object; multi-season/alternate-order scenarios don't exist in the sandbox) holds for each"

requirements-completed: []  # Fixture-only gap closure; SONARRV5-02/-03 completion is gated on 81-11/81-12 per D-13, owned by the orchestrator's STATE/ROADMAP/REQUIREMENTS updates, not this plan

# Metrics
duration: ~30min
completed: 2026-10-19
---

# Phase 81 Plan 10: Live Sonarr v5 Fixture Capture and Fixture Hygiene Summary

**Captured and sanitized a real Sonarr v5 (5.0.0.2701/develop) grab-history and episode-identity response from the isolated sandbox, relabelled the three schema-derived fixtures as honestly synthesized, and added a hygiene test that fails the suite on any credential/path/host leak in a Sonarr fixture.**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-10-19 (captured_at recorded in the fixtures: 2026-10-20T03:01:17Z UTC)
- **Tasks:** 2 (both complete)
- **Files modified:** 11 (5 created, 6 modified)

## Accomplishments

- Read-only GET capture against the isolated v5 sandbox (`sonarr-v5`, LAN `http://maguffynas:8990`), version-guarded to abort unless `system/status` reported a `5.x` version (observed: `5.0.0.2701`/`develop`). Pulled `GET /api/v3/history/series?seriesId=1&eventType=grabbed&includeEpisode=true` (18 records), `GET /api/v3/episode?seriesId=1` (47 series-episode entries), and `GET /api/v3/episode/{id}` once per each of the 18 distinct `episodeId`s found in history.
- Sanitized the capture before it touched the repo: `data` cleared to `{}`, the two distinct `downloadId` values replaced with stable `DL-REDACTED-1`/`DL-REDACTED-2` placeholders, and every episode object reduced to a fixed field whitelist (dropping `episodeFile`, `overview`, `images`, the nested `series` object, and any path/URL-bearing key). Confirmed zero 40-hex strings, URLs, `/home/`, `/data/`, `<seedbox-provider>`, `maguffynas`, or `apikey` substrings, and zero `downloadUrl`/`guid`/`torrentInfoHash`/`indexer` keys in the final fixture files.
- Independently reproduced the Plan 81-07 live finding in fixture form: all 18 captured history records keep their full real key set (`customFormatScore, customFormats, data, date, downloadId, episodeId, eventType, id, languages, quality, qualityCutoffNotMet, seriesId, sourceTitle`) with **no nested `episode` key anywhere** -- `history_season_pack_v5.json` now pins this as a regression-testable fact (`test_live_v5_history_has_no_nested_episode_key`), not just a one-off narrative finding.
- Renamed the three schema-derived fixtures to `*_nested_synth.json`, relabelled `_meta.origin: "synthesized"`, `_meta.sonarr_major: "synthetic (nested-episode shape)"`, and added a `shape_note` explaining they model the pre-v5 nested-episode shape and that multi-season/alternate-order scenarios can't be captured from the sandbox (no such series or grabs exist there). `history_standard_v4.json` gained `_meta.origin: "synthesized"`.
- `tests/sonarr_fixtures.py` now validates `_meta.origin` (`"live-capture"` vs `"synthesized"`) with origin-specific checks (live-capture requires `captured_at`, `sonarr_version`, `sanitized_fields`, `sanitized: true`; synthesized requires `source` to say so), and gained `load_sonarr_episode_fixture`/`load_sonarr_series_episode_list` for the new `episodes_v5.json` shape.
- Repointed the seven fixture references the plan named (three in `test_correlation.py`, one in `test_clients.py`, three in `test_attribution_client_path.py`) to the renamed `*_nested_synth` fixtures with **no assertion changes** -- confirmed via `git diff` showing only fixture-name strings and docstrings changed in those three files.
- Added `tests/test_sonarr_fixture_hygiene.py` (5 tests): every fixture is valid JSON and labelled `live_evidence: false` with a recognized `origin`; no fixture contains a 40-hex string or the banned host/path/credential substrings; no fixture contains a `downloadUrl`/`guid`/`torrentInfoHash`/`indexer` key at any depth; the live v5 history fixture has no nested `episode` key; `episodes_v5.json`'s `series_list["1"]` is non-empty and every entry has `seriesId == 1`.

## Task Commits

1. **Task 1: Capture and sanitize live v5 history and episode responses (read-only)**
   - `ffdcde1` test(81-10): capture sanitized live Sonarr v5 history and episode fixtures
2. **Task 2: Update the loader, repoint references and add the fixture hygiene test**
   - `7587bfa` test(81-10): replace schema-derived v5 fixture with sanitized live capture

_Note: this plan adds no production (`triggarr/`) behavior, so both commits are `test(...)` only -- no `feat`/RED-GREEN cycle applies._

## Files Created/Modified

- `tests/fixtures/sonarr/history_season_pack_v5.json` - **Replaced** with the sanitized live v5 capture (18 real grab records, `origin: live-capture`)
- `tests/fixtures/sonarr/episodes_v5.json` - **New**: sanitized live `series_list` (47 entries for series 1) and per-id `episodes` map (18 entries)
- `tests/fixtures/sonarr/history_season_pack_nested_synth.json` - Renamed from `history_season_pack_v5.json`; relabelled `origin: synthesized`, `sonarr_major: "synthetic (nested-episode shape)"`, added `shape_note`
- `tests/fixtures/sonarr/history_multi_season_pack_nested_synth.json` - Renamed/relabelled the same way
- `tests/fixtures/sonarr/history_alternate_order_nested_synth.json` - Renamed/relabelled the same way
- `tests/fixtures/sonarr/history_standard_v4.json` - Gained `_meta.origin: "synthesized"` only
- `tests/sonarr_fixtures.py` - Origin validation; `load_sonarr_episode_fixture`, `load_sonarr_series_episode_list`; rewritten module docstring
- `tests/test_sonarr_fixture_hygiene.py` - **New**: 5 hygiene/pinning tests over every fixture under `tests/fixtures/sonarr/`
- `tests/test_correlation.py`, `tests/test_clients.py`, `tests/test_attribution_client_path.py` - Repointed 7 fixture-name references to the `*_nested_synth` names; `test_attribution_client_path.py`'s module docstring rewritten to say which fixtures are live-captured vs. synthesized

## Decisions Made

See `key-decisions` in the frontmatter. In short: the capture script never lets the API key or any response body touch shell string-interpolation (env var in, heredoc Python script reading `os.environ`, JSON out over stdout only); the episode sanitizer is a whitelist, not a blacklist, so it fails closed against future unknown Sonarr fields; and the three nested-episode-shape fixtures share one `shape_note` since the same generic reason applies to all three.

## Deviations from Plan

None - plan executed exactly as written. The task's `read_first` interfaces (exact history key set, 18 records, no nested `episode` key, `GET /api/v3/episode/18 -> seasonNumber: 2`) all matched the freshly captured live data exactly, so no correction to the plan's documented facts was needed.

## Issues Encountered

None. The capture succeeded on the first attempt: `system/status` reported `5.0.0.2701` (passing the version guard), and all 18 `GET /api/v3/episode/{id}` calls succeeded.

## User Setup Required

None - no external service configuration required. The sandbox API key was read transiently inside the remote shell and never written to any file, printed, or logged.

## Next Phase Readiness

- Plan 81-11 can now write the episode-endpoint fallback (`GET /api/v3/episode/{episodeId}` -> verify series -> cache per tracking check -> skip on failure, per the owner's 2026-10-19 review) against `history_season_pack_v5.json` and `episodes_v5.json`, which carry the real v5 response shape rather than a schema guess.
- Plan 81-12 can rerun the season-pack and tracking-check live matrix rows against the fix this fixture work unblocks.
- No blockers. Full suite (1962 tests) and `ruff check triggarr/ tests/` both pass clean at the end of this plan.

### Facts recorded for traceability (plan output spec)

- **Sonarr version / branch / capture date:** `5.0.0.2701` / `develop`, captured `2026-10-20T03:01:17Z` (2026-10-19 evening ET)
- **History record count:** 18
- **Series-list length (series 1, "Hacks"):** 47
- **Distinct S2 episode count in history:** 8 (`episodeId` 11-18, the Phase 81 S02 season-pack grab)
- **`sanitized_fields` (history):** `data` cleared to `{}`; `downloadId` replaced with stable `DL-REDACTED-<n>` placeholders (2 distinct values observed); `sourceTitle` redacted only if it names an indexer/tracker or holds a URL (none did in this capture)
- **`sanitized_fields` (episodes):** dropped `episodeFile`, `overview`, `images`, `series` nested objects; dropped any key holding a path or URL; kept only `id, seriesId, tvdbId, seasonNumber, episodeNumber, title, airDate, airDateUtc, hasFile, monitored` and scene/absolute-numbering keys (`absoluteEpisodeNumber`, `unverifiedSceneNumbering`)
- **Observed coverage fact (not hard-asserted, per the plan):** every one of the 18 history `episodeId`s is present in `episodes_v5.json`'s per-id `episodes` map -- no gap to report for this capture.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-19*

## Self-Check: PASSED

All 11 created/modified files confirmed present on disk (`tests/fixtures/sonarr/history_season_pack_v5.json`, `episodes_v5.json`, the three `*_nested_synth.json` files, `history_standard_v4.json`, `tests/sonarr_fixtures.py`, `tests/test_sonarr_fixture_hygiene.py`, `tests/test_correlation.py`, `tests/test_clients.py`, `tests/test_attribution_client_path.py`). Both task commits (`ffdcde1`, `7587bfa`) confirmed present in `git log --oneline --all`. Full suite (`uv run pytest tests/ -x -q` -> 1962 passed) and `uv run ruff check triggarr/ tests/` (-> all checks passed) re-run and confirmed immediately before writing this summary. No sandbox state was changed (GET requests only); no production host was contacted; no raw capture or API key remains in the session scratchpad (both deleted after sanitization) or in any committed file (confirmed via the hygiene test and direct grep).
