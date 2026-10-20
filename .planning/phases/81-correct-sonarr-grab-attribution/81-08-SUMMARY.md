---
phase: 81-correct-sonarr-grab-attribution
plan: 08
subsystem: testing
tags: [sonarr, docker, api-compatibility, live-verification, v4, nas, gate-review]

# Dependency graph
requires:
  - phase: 81-06
    provides: "the live acceptance matrix shell and owner authorization (option-a) this plan executes against"
  - phase: 81-07
    provides: "the v5 sandbox pattern (isolation gate, Deluge-destination check, controlled-search procedure) this plan mirrors for v4"
  - phase: 81-12
    provides: "the fixed build (b35470b66f1287859319a6633ad3b0a34fbf7c39) this plan deploys and exercises live on v4, and the probe-assisted repeat-check pattern this plan reuses"
provides:
  - "A new isolated Sonarr v4 sandbox (sonarr-v4, pinned linuxserver/sonarr:4.0.20, no WUD) alongside the v5 one, reusing the existing triggarr-test container's multi-instance support instead of a second Triggarr"
  - "A twice-independently-reviewed, frozen gate script (setup-sonarr-v4-test.sh, sha256 00ca2909606dbd6f6e66c3ea86ef1e9ce7c49bc32e546a925fd95103a249d77e) with no interactive sudo requirement"
  - "Live-verified v4 core flows (connection/version, one controlled SeasonSearch, scheduled cycles, repeated tracking checks with probe-assisted repeat-credit verification) on build b35470b66f1287859319a6633ad3b0a34fbf7c39"
  - "A corrected, owner-reviewed Matrix record: tag lookup and missing/cutoff pagination explicitly kept unverified-live (not waived) on both v5 and v4; a production-restart observation recorded as correlation, not proof; full (non-truncated) build SHA, gate checksums, and downloadIds throughout"
  - "The v4 sandbox parked disabled per the owner's decision, with isolation settings and evidence retained for future live checks"
affects: [81-09 (if it exists), SONARRV5-02 closure, Phase 81 completion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reusing an existing multi-instance Triggarr container for a second isolated sandbox instance, instead of standing up a second Triggarr container, when the shared container already resolves the new sandbox by network alias"
    - "Designing a gate script to avoid bare `sudo` entirely by using `sudo docker exec` (the one NOPASSWD rule) plus host-path reads for world-readable/owner-readable files, eliminating the owner's interactive-password requirement found in the v5 precedent"
    - "A rescoped per-container mount-pattern check (bash `case` statement) so a shared/reused container's own legitimate mount isn't flagged by a pattern meant for the new sandbox's containers only"
    - "Fail-closed empty-state checks (treat non-200/parse-error/wrong-type as NOT-empty) immediately before any bounded live action that could duplicate a search"
    - "Probe-assisted repeat-tracking-check verification via labelled synthetic pending search_history rows with an early-expiring window, confirmed trackable via the app's own read-only get_trackable_entries before being relied on as evidence"

key-files:
  created:
    - /Users/julianamacbook/Cowork/mediaserver/SANDBOX-sonarr-v4.md
    - /Users/julianamacbook/Cowork/mediaserver/setup-sonarr-v4-test.sh (frozen, sha256 00ca2909606dbd6f6e66c3ea86ef1e9ce7c49bc32e546a925fd95103a249d77e)
    - /Users/julianamacbook/Cowork/mediaserver/setup-sonarr-v4-test-pre-review.sh
    - /Users/julianamacbook/Cowork/mediaserver/v5test-results/81-v4-{1..19}-*.txt (20 sanitized evidence files)
  modified:
    - .planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md

key-decisions:
  - "Reused the existing triggarr-test container (adding a v4test Sonarr instance) instead of provisioning a second Triggarr container, since the plan's own layout note only required a second Triggarr port if one was actually needed"
  - "Designed the v4 gate script to need no interactive sudo at all, after confirming this NAS's actual file permissions (world-writable /volume1/docker, owner-readable config files) make it unnecessary -- a deliberate adaptation of the v5 precedent's owner-gated sudo pattern, not a security relaxation"
  - "Owner chose option A (wire indexers/download client by hand) for the credential checkpoint, keeping credential entry out of the executor's hands entirely"
  - "Two independent script reviews (first full review: 5 blockers/12 warnings addressed; second quick re-check after an owner-flagged false positive in the W8 mount check) before freezing any gate script version -- the first frozen sha (90e9e8e5...) was superseded, not reused, once the false positive was found"
  - "Owner chose the standard import path (re-monitor, restart seedsyncarr-v4test for import, stop it again, fresh eligibility checks, then enable) over alternatives, correcting the executor's assumption that import was itself required for tracking credit (it reads Sonarr's grab history directly; the real constraint was avoiding a duplicate search)"
  - "Task 3 owner review corrected two overclaims before acceptance: tag lookup/missing/cutoff pagination must read unverified-live (not implicitly passing) on both v5 and v4, and the production sonarr restart must be recorded as 'consistent with a WUD update, cause unconfirmed' rather than asserted as WUD's doing"
  - "v4 sandbox parked disabled (not torn down) per explicit owner decision, since outstanding v4 live checks (tag lookup, pagination) may still need it; the isolation gate must be rerun before any future search against it"

patterns-established:
  - "When an owner's Task 3 review corrects an executor's prior wording (e.g., a blanket PASS claim that silently included still-open sub-checks), preserve the original wording in history and apply the correction as a new, clearly dated append -- never edit prior text to make it look like the corrected version was there from the start"
  - "A gate script freeze is void the moment the script changes, even for an owner-approved bugfix -- a superseded sha must be marked as such explicitly, and the new sha must go through its own review before anything runs against it"

requirements-completed: []  # SONARRV5-02 stays explicitly OPEN -- see Judgment and Owner review (v4) sections in 81-LIVE-MATRIX.md. Tag lookup, missing pagination, and cutoff pagination remain required, unverified-live D-11.1 core-flow checks on both v5 and v4; 81-09 (or whichever plan follows) may not waive them or mark SONARRV5-02 complete on this basis.

# Metrics
duration: ~2h46m elapsed (14:46 ET first commit -> 17:32 ET last commit) across many owner-gated pauses, two independent script reviews, a seedbox SSH-block interruption, and scheduled-cycle/probe observation windows -- active executor work was a small fraction of this span
completed: 2026-10-20
---

# Phase 81 Plan 08: Isolated v4 Sandbox and Live Verification Summary

**Provisioned and live-verified an isolated, pinned Sonarr v4 sandbox (reusing the existing multi-instance triggarr-test container) with a twice-reviewed, frozen, sudo-password-free gate script; ran a controlled SeasonSearch to a genuine single-download season-pack credit with probe-assisted repeat-check verification on build b35470b66f1287859319a6633ad3b0a34fbf7c39; and recorded an owner-corrected matrix that keeps tag lookup and missing/cutoff pagination explicitly open rather than silently passing.**

## Performance

- **Duration:** ~2h46m elapsed (2026-10-20T14:46:03-04:00 first commit -> 2026-10-20T17:31:38-04:00 last commit), spanning a credential-handling checkpoint, two independent gate-script reviews (one full, one quick re-check after an owner-flagged false positive), a seedbox SSH-block interruption and recovery, and multiple scheduled-cycle/probe observation windows. Active executor work was a small fraction of this span -- most elapsed time was owner decisions, reviews, and waiting on real scheduled cycles.
- **Started:** 2026-10-20T14:46:03-04:00
- **Completed:** 2026-10-20T17:31:38-04:00
- **Tasks:** 3 (Task 1: provision + gate the v4 sandbox; Task 2: controlled run; Task 3: owner review)
- **Files modified:** 1 tracked file (`81-LIVE-MATRIX.md`, 17 commits), 4 new/modified files outside the repo (`SANDBOX-sonarr-v4.md`, `setup-sonarr-v4-test.sh` + its pre-review copy, this plan's own SUMMARY), 20 new sanitized evidence files (`Cowork/mediaserver/v5test-results/81-v4-*`)

## Accomplishments

- Provisioned an isolated Sonarr v4 sandbox (`sonarr-v4`, pinned `linuxserver/sonarr:4.0.20`, `seedsyncarr-v4test`) as a new compose project, reusing the existing `triggarr-test` container's multi-instance support instead of standing up a second Triggarr -- no password required for any of it, after confirming this NAS's actual permissions make the v5 precedent's owner-gated-sudo pattern unnecessary here.
- Took the gate script (`setup-sonarr-v4-test.sh`) through the owner's required credential checkpoint (owner wired indexers/download client by hand), two independent reviews (5 blockers + 12 warnings addressed in the first; a false positive in the W8 mount check found and fixed in the second, requiring the first frozen checksum to be superseded), and froze it at sha256 `00ca2909606dbd6f6e66c3ea86ef1e9ce7c49bc32e546a925fd95103a249d77e` -- confirmed identical on laptop and NAS throughout.
- Passed the full gate sequence on the frozen script: `SEARCHES=off` (twice, including after an unrelated seedbox credential rotation), `SEARCHES=on` (owner-run), and `deluge-check` (failed once on a seedbox-side SSH block, passed on rerun once the block cleared).
- Ran a real, owner-authorized controlled `SeasonSearch` for Hacks Season 2 on `sonarr-v4`: a genuine single-download season pack (full `downloadId` `DC45E9DF9775E0B1B63D0EFFF0BE84363893FFA8`), credited once for all 8 distinct episodes by the fixed build, confirmed via fail-closed pre/post-enable eligibility checks and zero unexpected search commands throughout.
- Ran two probe-assisted repeat-tracking checks (labelled synthetic pending rows, no search sent) that both resolved `unresolved` with no re-credit and no counter movement -- the positive half of D-11.1 demonstrated independently on v4.
- Restored the sandbox to baseline after the controlled run, then recorded the owner's explicit decision to park it disabled (not torn down) for possible future use.
- Got the owner's Task 3 review recorded verbatim, including two corrections that prevent this plan's evidence from being read as more complete than it is: tag lookup/missing/cutoff pagination stay `unverified-live` (not silently passing) on both v5 and v4, and the production `sonarr` restart observed during review prep is recorded as a correlation with WUD, not a proven cause.

## Task Commits

Each task step was committed atomically (all `docs` type -- this plan is execution/verification only, no application code changed):

1. **Task 1 (provision + SEARCHES=off):** `761e118` -- provision isolated v4 sandbox, pass SEARCHES=off gate
2. **Task 1 (credential checkpoint + wiring check):** `f5ef768` -- record owner credential/gate decisions and v4 wiring check
3. **Task 1 (WUD fix + first script revision):** `adc17d6` -- apply WUD exclusion fix and gate-script review findings
4. **Task 1 (second-review fixes + freeze):** `22a3f1b` -- fix items 1-2, reconcile docs, freeze the v4 gate script
5. **Task 1 (frozen-script false positive found):** `3fd34db` -- record frozen-script SEARCHES=off run -- false positive found
6. **Task 1 (rescope + supersede):** `a52bdec` -- rescope W8 to v4 containers, record credential incident
7. **Task 1 (re-freeze + pass):** `62a68dc` -- freeze v4 gate script, pass SEARCHES=off, prep SEARCHES=on notes
8. **Task 1 (post-rotation rerun + RSS prep):** `e5751a6` -- post-rotation searches-off rerun, RSS-only prep, owner decisions
9. **Task 2 (bounded enable, zero searches):** `8e02c58` -- enable v4test instance (bounded live action), confirm zero searches
10. **Task 2 (grab succeeded, deluge-check failed on the seedbox):** `74cc1ac` -- Task 2 controlled run -- grab succeeded, deluge-check failed on the seedbox
11. **Task 2 (deluge-check passes post-recovery):** `3827d34` -- deluge-check passes post-seedbox-recovery; tracking credit blocked
12. **Task 2 (credit + probes + baseline restore):** `a345156` -- Task 2 controlled v4 run complete -- credit, probes, baseline
13. **Task 3 (owner review recorded, corrections applied):** `87bd57a` -- record Task 3 owner review, correct overclaims, restore full IDs

**Plan metadata:** this commit (docs: SUMMARY)

_Note: this plan has no TDD tasks -- it is a live-environment verification run, not a code-authoring plan._

## Files Created/Modified

- `.planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md` - Full v4 sandbox narrative (provisioning, two gate-script reviews, credential checkpoint, controlled run, probes, owner reviews and corrections), updated Matrix table (v4 Live column filled in; v5+v4 tag/pagination cells corrected to unverified-live)
- `/Users/julianamacbook/Cowork/mediaserver/SANDBOX-sonarr-v4.md` - v4 sandbox layout, ports, isolation rules, teardown, and the no-sudo-needed/design-choice rationale
- `/Users/julianamacbook/Cowork/mediaserver/setup-sonarr-v4-test.sh` - The frozen gate script (sha256 `00ca2909606dbd6f6e66c3ea86ef1e9ce7c49bc32e546a925fd95103a249d77e`)
- `/Users/julianamacbook/Cowork/mediaserver/setup-sonarr-v4-test-pre-review.sh` - Pre-first-review copy, kept for diffing
- `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-v4-{1..19}-*.txt` (20 files) - Sanitized evidence: fingerprints, gate outputs (off/on, both passes and the one failure), wiring check, WUD exclusion, probe inserts and repeat-check results, enable-and-credit record, pre-enable/post-import eligibility checks

## Decisions Made

See `key-decisions` in the frontmatter. In short: reuse `triggarr-test` rather than a second Triggarr container; design the gate script to need no interactive sudo at all (confirmed safe on this NAS's actual permissions); owner wired credentials by hand rather than the executor; two independent reviews and a superseded-then-refrozen checksum before any gate ran against the real wiring; owner corrected an executor assumption that import was required for tracking credit; owner's Task 3 review corrected two overclaims (tag/pagination rows, the production-restart attribution) before accepting the evidence record; v4 sandbox parked disabled per explicit owner choice.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] W8 mount check false-positived on triggarr-test's own legitimate shared mount**
- **Found during:** the frozen script's own first `SEARCHES=off` run
- **Issue:** the v5-sandbox/prod-data-path mount pattern added during the first review ran against all three containers, including `triggarr-test` -- whose one legitimate `/config` mount (`/volume1/docker/v5test/triggarr`) necessarily lives under `v5test` by this plan's own design (the shared container is reused for both sandboxes' instances).
- **Fix:** scoped the pattern to run only for `sonarr-v4`/`seedsyncarr-v4test`; `triggarr-test` keeps its other checks (confirmed via a minimal non-rig dry test: the legitimate mount passes, synthetic forbidden mounts on either v4 container still fail).
- **Files modified:** `setup-sonarr-v4-test.sh` (previously-frozen sha superseded, new sha re-reviewed and re-frozen).
- **Verification:** independent quick re-check (FREEZE-READY verdict), then a clean full `SEARCHES=off` run on the re-frozen script.
- **Committed in:** `a52bdec`, `62a68dc`

**2. [Rule 1 - Bug] Label-options check could fall through silently on an empty/falsy result**
- **Found during:** the second independent review
- **Issue:** an empty dict returned from `label.get_options` without raising would hit neither the `except` branch nor the `if lo:` assertion, so neither `LABELOK` nor `LABELFAIL` was ever printed -- the gate would pass having checked nothing.
- **Fix:** added an explicit `else` branch printing `LABELFAIL ... missing/empty options`; verified with a synthetic 4-case dry-run harness (empty dict, raising, safe-off, unsafe-on) with no live Deluge contact.
- **Files modified:** `setup-sonarr-v4-test.sh`
- **Verification:** harness output matched expectations for all 4 cases; later confirmed against live data (`LABELOK` on the real `tv-v4test` label).
- **Committed in:** `22a3f1b`

**3. [Rule 4 - architectural, asked rather than acted] Whether import was required before tracking could credit the controlled search**
- **Found during:** between the failed and recovered `deluge-check` runs
- **Issue:** the executor initially assumed crediting `search_history` row 5 required the Season 2 files to be imported.
- **Resolution:** the owner corrected this directly (tracking reads Sonarr's grab history, which already had all 8 grab records; the real constraint was avoiding a duplicate search) and then chose the standard import path anyway, which the executor followed exactly.
- **Committed in:** `3827d34`, `8e02c58`, `a345156`

### Judgment reconciliation (not a deviation, the owner's own designed review mechanism)

- Task 3's review corrected the executor's own prior "D-11.3 (v4 core flows, live): PASS" bullet, which had silently omitted that tag lookup and missing/cutoff pagination stayed unverified-live. Per the owner's explicit instruction, this is now a precise partial breakdown, and the Matrix table's v5+v4 cells for those three rows were corrected to read `unverified-live` with an explicit "required, cannot be waived" note. This is the Task 3 review mechanism working exactly as designed, not a shortfall in Task 2's execution.

---

**Total deviations:** 2 auto-fixed (Rule 1, both script-logic bugs found via independent review, not self-discovered), 1 architectural question the owner answered directly, plus 1 judgment reconciliation that is the plan's own intended Task 3 mechanism.
**Impact on plan:** No scope creep. Both auto-fixes were caught by independent review before anything ran against the live wiring, exactly as the owner's "review it, then you run it" / "independent quick re-check" decisions were designed to catch. The Task 3 correction keeps the evidence record honest rather than overclaiming completeness.

## Issues Encountered

- **Seedbox SSH block (resolved, not this plan's fault):** immediately after the controlled grab, `ACTION=deluge-check` failed with `ssh: connect to host <seedbox-host> port 22: Connection refused`. Cause: the seedbox had blocked the home IP's SSH access following unrelated repeated authentication attempts from other services during the earlier password-rotation period -- a seedbox-side protective measure, not a defect in this script or sandbox. No retry loop was attempted (per instruction); baseline was restored, `seedsyncarr-v4test` was stopped at `2026-10-20T20:53:40Z` to reduce SSH load, and the port reopened at `2026-10-20T20:55:48Z`. The rerun against the same existing grab passed cleanly (`DELUGE DESTINATIONS PASSED`).
- _[Security-sensitive detail removed before publication; the full record is kept privately.]_
- **Production `sonarr` restart observed during Task 3 review prep (external, not this plan's action):** the orchestrator found prod `sonarr` had been recreated from `linuxserver/sonarr:latest` partway through this plan's execution. No Phase 81 action targeted it (every production check in this phase only ever reads prod's API/compose file). Recorded per the owner's correction as "consistent with a WUD update; cause unconfirmed" -- not asserted as proven fact.

## User Setup Required

None beyond the owner actions already part of this plan's design (wiring indexers/download client by hand at the credential checkpoint, reviewing and approving the gate script twice, running the `SEARCHES=on` gate personally, authorizing the bounded live actions and the controlled test, rotating the exposed seedbox credential, and the Task 3 review itself) -- no external service configuration required beyond what the owner already did.

## Next Phase Readiness

- **SONARRV5-02 stays open** (per the owner's explicit 2026-10-20 Task 3 review): tag lookup, missing pagination, and cutoff pagination remain required, unverified-live D-11.1 core-flow checks on **both** v5 and v4. Any following plan (e.g., 81-09) may not waive them or mark SONARRV5-02 complete on this basis.
- **Phase 81 stays incomplete** in ROADMAP.md/STATE.md terms (this plan did not touch those files -- the orchestrator owns that update; unrelated pre-existing uncommitted owner edits to `STATE.md`/`ROADMAP.md`/`docs/bm-greptile-codex-blueprint.md` were present at session start and were never modified, staged, or committed by this plan).
- **This plan's acceptance does not imply Phase 81 completion, a release exception, or merge/deployment approval** -- stated explicitly per the owner's Task 3 instruction.
- **v4 sandbox parked disabled, not torn down** (owner's explicit choice, since outstanding v4 live checks may still need it): `triggarr-test`'s `v4test` instance disabled, Hacks test series unmonitored, `sonarr-v4` RSS Sync Interval `0`, `seedsyncarr-v4test` stopped. Isolation settings and all evidence are retained. **The isolation gate (frozen script, sha-verified first) must be rerun before any future search** against this sandbox.
- **D-11.3 (v4 core flows) is a partial result**, not a blanket pass: connection/version, one controlled SeasonSearch, scheduled cycles, and repeated tracking checks (probe-assisted) are live-verified; tag lookup, missing/cutoff pagination, and library counts (refresh-counts) remain open for v4 as well as v5.
- **Season-pack attribution (D-11.2)** stays accepted on the v5 row (per 81-12's owner decision); the v4 Season 2 pack credit is recorded as supplementary, not required, cross-version evidence.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-20*

## Self-Check: PASSED

All 5 named tracked/external files confirmed present on disk (`SANDBOX-sonarr-v4.md`, `setup-sonarr-v4-test.sh`, `setup-sonarr-v4-test-pre-review.sh`, `81-LIVE-MATRIX.md`, this `81-08-SUMMARY.md`). All 20 sanitized evidence files confirmed present under `/Users/julianamacbook/Cowork/mediaserver/v5test-results/81-v4-*`. All 13 claimed Task commit hashes confirmed present via `git log --oneline --all`. The frozen gate script's live sha256 (`00ca2909606dbd6f6e66c3ea86ef1e9ce7c49bc32e546a925fd95103a249d77e`) matches the value recorded throughout this summary and the Matrix. No missing items.
