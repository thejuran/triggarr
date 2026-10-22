---
phase: 82-ci-tests-what-we-ship
plan: "09"
status: complete
subsystem: ci
tags: [negative-evidence, browser-sensitivity, gate-enforcement, cishiP-03]
requires: ["82-08"]
provides:
  - "Browser sensitivity evidence (i) for both pill regressions on the exact audited CI image (local, narrow claim per D-07)"
  - "Gate enforcement evidence (ii) on GitHub for the broken entrypoint (draft PR #34)"
  - "CISHIP-03 release-identity evidence section with the verbatim D-31d limitation"
affects: ["Phase 82 verification (records the owner-waived pill gate demonstrations)"]
key-files:
  created:
    - .planning/phases/82-ci-tests-what-we-ship/82-DEMONSTRATIONS.md
requirements-completed: [CISHIP-01, CISHIP-02, CISHIP-03, CISHIP-04]
---

# Plan 82-09 Summary: negative demonstrations

**Both pill regressions are caught by the real browser test on the exact audited CI image. The broken-entrypoint demonstration on GitHub kept `CI ready` red. The owner waived the two pill gate demonstrations on GitHub; they are recorded as waived, not passed.**

## Browser sensitivity evidence (i), local, no push

- **Audited image:** run 39701686221 (PR head `0f08523`, tested SHA `35458d4`, image `sha256:66bbe15a…`, revision label = tested SHA). The image.tar checksum was verified.
- **Variants:** built `FROM` that image with only `COPY` of the mutated template files. The manifest diff over 68 files shows only those template paths changed.
- **Loop variant:** `connection pill request loop: 113 requests without any scheduled tick`.
- **Polling-disabled variant:** `connection pill did not refresh after a scheduled interval: expected at least 2 requests, saw 1`.
- **Control:** the base image passed.
- **Artifacts:**
  - The byte scan withheld each run's trace (it carries the session cookie); this is fail-closed by design.
  - The remaining dashboard screenshot and the logs contain no session cookie and no stub key.
  - Byte scanning is an extra defence, not proof that screenshots are safe.

## Gate enforcement evidence (ii), GitHub

The owner's go-ahead (2026-10-22, recorded verbatim in 82-DEMONSTRATIONS.md) covered the broken entrypoint only.

**Broken entrypoint:** draft PR #34, run 39790931780.
- `image-smoke` failed: `SMOKE FAILED [first-run] …`.
- `browser-e2e` failed: the app never became healthy.
- `CI ready` failed: "Mandatory jobs did not succeed".
- test, lint, secrets, dependencies and docker succeeded.
- The identities reconcile: tested SHA `311ff59` is the merge of demo head `f21acd0` into base `81eb550`.
- The failure artifact contained each container's redacted logs naming the root cause, which exercised Greptile fix #4 on a real failure.
- PR #34 was closed, not merged, and its branch was deleted. The remote tag count is unchanged at 58.

**Pill loop and pill polling disabled:** waived by the owner, not passed. They were not demonstrated on GitHub, so the gate claim for these two mutations is unproven there. Their branches were never pushed and were deleted locally.

## Release identity (CISHIP-03)

The per-run rehearsal in `image-smoke` covers four cases: matching accepted, mismatched /disagree/, malformed /malformed/ and missing /missing/. The structural wiring tests show that a rejection blocks publication. No tag-triggered run was performed (D-31e).

Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release.

## Deviations

- The Task 1 executor stalled twice; the stream watchdog fired after its image load and again after it created the first worktree. The orchestrator finished Task 1 directly using the executor's completed outputs: the variant builds, manifests, junit results and artifacts. It read the image labels from the tarball's config instead of a second `docker load`.
- The `SMOKE FAILED [first-run]` message reads "expected exit 1 with a default-config log line, got exit=1". It names the exit code but not the missing log line, which is ambiguous. This is a cosmetic follow-up, not a gate defect.

## Self-Check: PASSED
- The verbatim D-31d sentence appears in 82-DEMONSTRATIONS.md and in this summary.
- No `demo/82-*` branch remains on origin, PR #34 is closed and not merged, and the tag count is unchanged.
- No `triggarr-demo:*` image remains, and nothing was merged, released or tagged.
