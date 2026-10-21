---
phase: 81-correct-sonarr-grab-attribution
plan: 07
subsystem: testing
tags: [sonarr, docker, api-compatibility, live-verification, v5, nas]

# Dependency graph
requires:
  - phase: 81-correct-sonarr-grab-attribution (plans 01-06)
    provides: the attribution/cutover implementation and the live acceptance matrix shell this plan executes against
provides:
  - A Phase 81 build deployed and gate-verified on the isolated v5 sandbox (`triggarr-test`, exact commit `a139879794c621692593346f35b3c98700b9b222`)
  - Live-verified pass/fail/reachability-only results for every v5 matrix row, with sanitized evidence files
  - A precise, reproducible root-cause finding: Sonarr v5 (5.0.0.2701/develop)'s `/api/v3/history/series?includeEpisode=true` never nests episode/season identity, so Triggarr's identity gate correctly refuses to credit any v5 grab
  - Owner-reviewed, verbatim-recorded decision: keep SONARRV5-02 open, plan a targeted episode-endpoint fallback fix, then re-run the season-pack and tracking checks
affects: [81-08 (v4 sandbox), a future gap-closure plan for Sonarr v5 episode-identity fallback, SONARRV5-02 closure, Phase 81 completion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Authenticating Triggarr's own API with its internal X-Api-Key (from [auth].api_key in triggarr.toml) to drive /settings changes through the app's own Pydantic validation + atomic TOML write, instead of hand-editing config files"
    - "Docker-only passwordless evidence gathering (docker inspect/logs/exec) as a fallback when a gate script's sudo requirements are owner-only"

key-files:
  created:
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-1-fingerprint-before.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-2-verify-searches-off.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-3-verify-searches-on.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-3-deluge-check.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-4-db-check-1-post-search.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-4-db-check-final.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-4-v5-grab-history-identity-gap.txt
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-5-fingerprint-after.txt
  modified:
    - .planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md

key-decisions:
  - "Deployed the exact Phase 81 commit by streaming git archive HEAD to the NAS and building there (not the Mac's arm64 build), tagged with an org.opencontainers.image.revision label matching the SHA exactly"
  - "Split sudo-gated gate steps (isolation verify, Deluge-destination check) to the owner, kept everything passwordless (docker build/compose/inspect/logs/exec, direct Sonarr/Triggarr API calls) with the executor -- per the owner's 'you run the gates' decision"
  - "Chose Hacks Season 2 (never before grabbed) as the controlled-test target, distinct from the pre-existing Hacks S01 history, to avoid any ambiguity about whether the Phase 81 build's own logic was actually exercised"
  - "Enabled the v5test instance through Triggarr's own /settings endpoint (authenticated with its internal API key) rather than hand-editing triggarr.toml, to keep the app's Pydantic validation and atomic write in the loop"
  - "Did not attempt an in-place code fix for the discovered v5 identity-gate gap -- confirmed as a genuine live API compatibility finding requiring new client design (episode-endpoint fallback, series verification, caching), not a quick patch, per the owner's own review"
  - "Owner review: keep both FAIL rows as FAIL, SONARRV5-02 stays open; reworded three rows from 'pass (thin)' to 'reachable only' since an empty-sandbox 200 response proves reachability, not filtering/pagination correctness; confirmed no claim anywhere that v4/production is unaffected"

patterns-established:
  - "Pattern: when a NAS gate script mixes NOPASSWD docker commands with password-gated sudo (config reads, mkdir/chown, embedded python), split execution so the owner runs only the gated invocation while the executor does everything reachable via docker inspect/logs/exec and direct app APIs"

requirements-completed: []  # SONARRV5-02 stays explicitly OPEN per D-13 and the owner's 2026-10-19 review -- see below

# Metrics
duration: ~4h10m elapsed across three owner-gated pauses and an 80-min sandbox observation window (not continuous active work)
completed: 2026-10-19
---

# Phase 81 Plan 07: Live v5 Sandbox Verification Summary

**Deployed the exact Phase 81 build to the isolated v5 sandbox, ran the full live matrix, and found a precise, reproducible Sonarr v5 API compatibility gap that blocks season-pack attribution -- owner-reviewed and recorded, SONARRV5-02 stays open pending a targeted fix.**

## Performance

- **Duration:** ~4h10m elapsed (18:11 ET first commit -> 22:19 ET last commit), including three owner-gated pauses (interactive sudo gates) and an 80-minute sandbox observation window while a real download/import completed and two further scheduled cycles ran. Active executor work was a small fraction of this span.
- **Started:** 2026-10-19T18:11:22-04:00 (first commit this continuation)
- **Completed:** 2026-10-19T22:19:21-04:00
- **Tasks:** 3 (Task 1: deploy + gates; Task 2: controlled run + baseline restore; Task 3: owner review)
- **Files modified:** 1 tracked file (`81-LIVE-MATRIX.md`), 8 new sanitized evidence files outside the repo (`Cowork/mediaserver/v5test-results/`)

## Accomplishments

- Deployed a Triggarr image built from the exact Phase 81 commit (`a139879794c621692593346f35b3c98700b9b222`) to the isolated `triggarr-test` container, verified by revision label, image ID, and start time -- never touching production.
- Passed both isolation gates (`SEARCHES=off`, then `SEARCHES=on` + Deluge-destination check), run interactively by the owner per their explicit "you run the gates" decision, with the executor doing everything password-free in between (RSS config, build, compose retarget).
- Ran a genuinely live, Phase-81-dispatched controlled SeasonSearch (Hacks Season 2) through to a real grab, download, and Sonarr import -- confirmed via Sonarr's own API, not inferred.
- Discovered and precisely documented a real Sonarr v5 (5.0.0.2701/develop) API compatibility gap: `/api/v3/history/series?includeEpisode=true` never nests episode/season identity, so Triggarr's identity-trust gate correctly refuses to credit any v5 grab -- confirmed by direct, byte-for-byte comparison of the API response with and without the flag, and cross-checked against the working `GET /api/v3/episode/{id}` alternative.
- Restored the sandbox to baseline (instance disabled, nothing monitored, RSS interval back to 0) with no WUD interruption during the entire run.
- Got the owner's interactive review recorded verbatim, including their directed next step for a follow-up gap-closure plan.

## Task Commits

Each task step was committed atomically (all `docs` type -- this plan is execution/verification only, no application code changed):

1. **Task 1 (deploy):** `61e59e2` -- deploy Phase 81 build, await owner gate
2. **Task 1 (gate 1):** `9b3be1a` -- record SEARCHES=off gate pass, surface Step 4 ordering conflict
3. **Task 1 (RSS prep):** `a91eee9` -- set sandbox RSS sync interval only, per owner's scoped go-ahead
4. **Task 1 (gate 2):** `ba6b084` -- record SEARCHES=on + deluge-check gate pass
5. **Task 2 (controlled run):** `c475a78` -- monitor Hacks S02, enable v5test instance, controlled grab fires
6. **Task 2 (completion):** `b5fca06` -- complete Task 2 live matrix, record v5 identity-gate finding, restore baseline
7. **Task 3 (owner review):** `777c523` -- record owner review, apply reporting corrections

**Plan metadata:** this commit (docs: SUMMARY)

_Note: this plan has no TDD tasks -- it is a live-environment verification run, not a code-authoring plan._

## Files Created/Modified

- `.planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md` - Build identity (before/after), full gate narrative, Task 2 controlled-run findings, complete Matrix table results, owner review, baseline restore record
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-1-fingerprint-before.txt` - Pre-deploy sandbox fingerprint (docker-only, passwordless)
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-2-verify-searches-off.txt` - Owner-run isolation gate 1 (sanitized)
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-3-verify-searches-on.txt` - Owner-run isolation gate 2 (sanitized)
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-3-deluge-check.txt` - Owner-run Deluge-destination check (sanitized)
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-4-db-check-1-post-search.txt` - Triggarr DB snapshot immediately after the controlled SeasonSearch
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-4-db-check-final.txt` - Triggarr DB snapshot after baseline restore (still uncredited)
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-4-v5-grab-history-identity-gap.txt` - The root-cause evidence: raw grab-history response shape vs. the working episode-lookup alternative
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-5-fingerprint-after.txt` - Post-run sandbox fingerprint, confirming no WUD interruption

## Decisions Made

See `key-decisions` in the frontmatter above. In short: deploy from a NAS-side `git archive` build (never the Mac's arm64 build); split sudo-gated gate steps to the owner while the executor did everything passwordless; use Hacks Season 2 (never-grabbed) as the controlled-test target; drive Triggarr's instance-enable through its own validated `/settings` API rather than hand-editing config; do not attempt an in-place fix for the discovered v5 compatibility gap; and, per the owner's Task 3 review, keep both FAIL rows as FAIL, reword the three thin-pass rows to reachability-only, and confirm no claim anywhere that v4/production is unaffected.

## Deviations from Plan

### Auto-fixed / Adapted Issues

**1. [Rule 3 - Blocking, adapted via checkpoint] NAS gate script requires interactive sudo beyond the NOPASSWD docker allowlist**
- **Found during:** Task 1
- **Issue:** `setup-sonarr-v5-test.sh`'s `ACTION=verify`/`ACTION=deluge-check` paths use bare `sudo` for config reads, `mkdir`/`chown`, and embedded Python checks; only `/usr/local/bin/docker`/`docker-compose` are NOPASSWD on this NAS.
- **Fix:** Per the owner's explicit "you run the gates" decision, split execution: owner ran the two gated scripts interactively (their own password); executor did the build, compose retarget, config changes, and all evidence-gathering via NOPASSWD docker commands and direct app APIs.
- **Files modified:** `81-LIVE-MATRIX.md` (narrative), no script was modified.
- **Verification:** Both gates independently confirmed passed (`ALL ISOLATION CHECKS PASSED`, `DELUGE DESTINATIONS PASSED`) by reading the owner-run output files.
- **Committed in:** `61e59e2`, `9b3be1a`, `ba6b084`

**2. [Rule 4 - architectural, asked rather than acted] Runbook Step 4's ordering conflicted with the owner's "never enable before the gate passes" instruction**
- **Found during:** Task 1, between gates
- **Issue:** The runbook wants RSS sync/monitoring/schedule enabled *before* `SEARCHES=on` runs (since the gate's own pass condition depends on that state); the owner's instruction said not to enable any of that until the gate passes.
- **Resolution:** Surfaced the exact mechanics (what the gate checks, what's genuinely safe to change ahead of time) in a checkpoint rather than deciding unilaterally. Owner authorized a narrow scope: executor changes only the Sonarr-side RSS interval; owner runs the combined gate; only after both pass does monitoring/enabling happen.
- **Files modified:** `81-LIVE-MATRIX.md`
- **Committed in:** `9b3be1a`, `a91eee9`, `ba6b084`

**3. [Not a deviation -- a genuine live finding] Sonarr v5 API compatibility gap discovered during the controlled run**
- This is the plan's intended output, not a deviation: D-11.2 (season-pack attribution) was live-verified to FAIL with a precise root cause (see Matrix table and the Task 2 finding section in `81-LIVE-MATRIX.md`). No code fix was attempted -- per the owner's own review, this needs a follow-up plan (episode-endpoint fallback with series verification, cached per tracking check, skip-on-failure-to-identify, a sanitized real-v5 fixture, then a repeat of the season-pack and tracking checks).

---

**Total deviations:** 2 adapted via checkpoint (both owner-decided, not unilateral), plus 1 genuine live finding that is the plan's own intended output.
**Impact on plan:** No scope creep. The plan's purpose -- live v5 verification -- was fully carried out; the FAIL result is the correct, honest outcome of that verification, not a shortfall in execution.

## Issues Encountered

- A background monitoring script's Sonarr-queue check had a shell-quoting bug (nested `ssh`/`python3 -c` quoting collision) and silently produced empty JSON for 80 minutes; the Triggarr DB-extract half of the same script worked throughout and, combined with direct re-checks after the monitor timed out, provided the evidence needed. No incorrect conclusion resulted -- the direct re-check confirmed the root cause independently of the broken queue check.
- Reading `triggarr.toml`/Sonarr's host-level config files via `docker exec ... cat` as container root returned `Permission denied` in a few cases (likely container user-namespace remapping); worked around by reading the same files directly over SSH as the owning host user (`<nas-user>`) instead, which is a legitimate access path, not a bypass.

## User Setup Required

None - no external service configuration required. This plan only exercised the already-provisioned v5 sandbox.

## Next Phase Readiness

- **SONARRV5-02 stays open** (per D-13 and the owner's explicit 2026-10-19 review): the season-pack attribution requirement is live-verified to FAIL against the current Sonarr v5 build, with a precise, reproducible root cause and a clear, owner-approved path to a fix.
- **Phase 81 stays incomplete** in ROADMAP.md/STATE.md terms (this plan did not touch those files -- the orchestrator owns that update, per explicit instruction for this plan).
- **Follow-up work needed, scoped by the owner's review:** when Sonarr grab history lacks season information, resolve the episode's season via `GET /api/v3/episode/{episodeId}` and verify the series matches before trusting it; cache that lookup within each tracking check (not per-grab); skip credit entirely if identity still cannot be established (never guess); replace the schema-derived test fixture with a sanitized real Sonarr v5 response; then repeat the season-pack and subsequent tracking checks to confirm the fix.
- **81-08 (v4 sandbox)** is unaffected by this plan and remains a separate, not-yet-provisioned step; every v4 Live cell in the matrix stays `unverified-live` until it runs.
- **Sandbox left at baseline:** `triggarr-test` `v5test` instance disabled, nothing monitored, RSS interval `0`, no WUD interruption during the run (nothing needs repeating). The imported Hacks Season 2 files remain in the sandbox library as real evidence of the controlled test.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-19*

## Self-Check: PASSED

All 10 claimed files confirmed present on disk (`81-LIVE-MATRIX.md`, this `81-07-SUMMARY.md`, and all 8 sanitized evidence files under `/Users/julianamacbook/Cowork/mediaserver/v5test-results/`). All 7 claimed commit hashes (`61e59e2`, `9b3be1a`, `a91eee9`, `ba6b084`, `c475a78`, `b5fca06`, `777c523`) confirmed present via `git log --oneline --all`. No missing items.
