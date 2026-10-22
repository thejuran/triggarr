# Phase 82 — CI evidence

Durable record of the first real GitHub runs of the Phase 82 checks (D-08), with commit identities kept separate (D-34). Plan 82-08 writes this file; Plan 82-09 adds the negative demonstrations to `82-DEMONSTRATIONS.md`.

## Pre-push technical review

- **Date:** 2026-10-21
- **Decision:** owner chose **run /deep-review** before the push (D-35 stop 2; the only stop before the push).
- **Local SHA reviewed:** `3d28bc0a6b18d9f19d6ada26dea97be67a8a2127` (phase range `07f9670..3d28bc0`, `.planning/` and `uv.lock` excluded; `uv.lock` changes are additions only).
- **Local gate at that SHA, before review:** `node --test .github/scripts/*.test.cjs` 115 pass / 0 fail; `uv run --no-sync pytest tests/ -q` 2160 passed; `uv run --no-sync ruff check triggarr/ tests/` clean; `actionlint` clean.
- **Outcome:** `/vibe-check:deep-review` ran 3 passes (7 native lanes + Codex on passes 1–2; 6 native + Codex on pass 3) and closed **APPROVED** (`.turingmind/REVIEW.md`, state format 53, archived state `.turingmind/state/format-53/82-ci-tests-what-we-ship.json.archived-2026-10-21`). Codex verdict on pass 3: approve.
- **Fix commits (all on `ci-review-workflow`, after `3d28bc0`):**
  - `a59bb3b` — password-leak assertion now checks the password the probe subprocess actually used.
  - `d05b1b3` — pill test waits with `page.wait_for_timeout` so Playwright keeps dispatching request events (previously `time.sleep` could hide a fired request and fail a healthy build; reproduced by execution).
  - `ea3a973` — `tests/harness/checks.py` closes urllib responses on every path.
  - `2d85236` — release-identity rehearsal no longer fails CI when `pyproject` carries a dev version (reproduced: `2.13.0.dev0` / `2.13.0-dev` previously failed with "malformed tag").
  - `d3e46ab` — `Credentials` password hidden from `repr`: the repaired leak check exposed that pytest failure tracebacks printed the e2e admin password into CI logs.
  - `131a598` — rehearsal decides releasability through `release-policy.cjs`'s own `parseReleaseTag` (no copied regex).
  - `1133126` — on a dev version the rehearsal still requires the image version label to be present and equal to the package version.
- **Owner decisions recorded in the review:** two Codex-raised rows dismissed as already fixed (`d05b1b3`, `1133126`); vibe-check cannot close a Codex row by recheck.
- **Re-run local checks at `11331263b0db29d9f66a62fa46190819f711b418` (head to be pushed):** `node --test .github/scripts/*.test.cjs` 117 pass / 0 fail; `uv run pytest tests/ -x -q` 2160 passed; ruff clean; `actionlint` clean. Browser suite against a fresh local build of `d3e46ab` (no browser-facing change since): credential_pages 6 passed, other pages 1 passed (3/3 repeat runs); loop-bug variant still fails with "connection pill request loop". Rehearsal matrix: `2.12.0`/`2.12.0` pass, `2.12.0`/`9.9.9` fail, `2.13.0.dev0`/same pass, `2.13.0.dev0`/`9.9.9` fail, `2.13.0.dev0`/empty fail, `2.6.1-dev`/same pass.
- This record is not owner acceptance (D-35 stop 3 happens later, on the final phase head).
