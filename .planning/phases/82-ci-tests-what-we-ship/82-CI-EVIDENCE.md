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

## First real GitHub run (Plan 08, Task 3)

- **Pushed:** `git push origin ci-review-workflow` (fast-forward `3fa038a..3315a88`), updating PR #33. No force push, main untouched.
- **CI run:** [run 39697729420, attempt 1](https://github.com/thejuran/triggarr/actions/runs/39697729420) (workflow `CI`, event `pull_request`).

### Commit identities (D-34)

| Field | Value |
|---|---|
| PR head SHA | `3315a882e2e98d2a3a81752708bb0ec8269e3f88` |
| PR base SHA | `81eb55001b0118c026a8276150d852c89e71ff50` |
| Tested SHA (`github.sha` / checkout HEAD) | `16faed9ae7e54403ae200243fcf5118024271177` |
| Image revision label (`org.opencontainers.image.revision`) | `16faed9ae7e54403ae200243fcf5118024271177` |
| Image ID | `sha256:84783d0b818523ef554f1fd8e229a94c31d69ed45d41fb90f8174fd3896516d7` |
| image.tar sha256 | `6796993a93fa85925cc13bbfbbbc6e477def8eb0eb766b7cc923a3e63aecbff4` |

PR head SHA confirmed equal to `git log origin/ci-review-workflow -1 --format=%H` (`3315a882e2e98d2a3a81752708bb0ec8269e3f88`). Image revision label confirmed equal to the tested SHA by downloading the `audited-image` artifact from run 39697729420, verifying `sha256sum -c image.tar.sha256`, `docker load`-ing it in the scratch directory, confirming `docker image inspect --format '{{.Id}}'` equals `image-id.txt`, then reading the `org.opencontainers.image.revision` and `.version` labels (version label: `2.12.0`). The loaded image tag was removed from the local Docker daemon afterward (`docker image rm triggarr:ci-test`).

**Reconciliation:** `git fetch origin 16faed9ae7e54403ae200243fcf5118024271177` then `git rev-list --parents -n 1 16faed9ae7e54403ae200243fcf5118024271177` returned parents `81eb55001b0118c026a8276150d852c89e71ff50 3315a882e2e98d2a3a81752708bb0ec8269e3f88` (base, then head) -- confirmed via the job logs' own `HEAD is now at 16faed9 Merge 3315a882e2e98d2a3a81752708bb0ec8269e3f88 into 81eb55001b0118c026a8276150d852c89e71ff50`. Reconciliation: tested SHA `16faed9ae7e54403ae200243fcf5118024271177` is GitHub's merge of PR head `3315a882e2e98d2a3a81752708bb0ec8269e3f88` into base `81eb55001b0118c026a8276150d852c89e71ff50`; CI evidence below applies to `16faed9ae7e54403ae200243fcf5118024271177`, review evidence to `3315a882e2e98d2a3a81752708bb0ec8269e3f88`.

### CI evidence (tested SHA)

Run: https://github.com/thejuran/triggarr/actions/runs/39697729420, run ID `39697729420`, attempt `1`.

| Job | Conclusion | Duration |
|---|---|---|
| test | success | 2m6s |
| lint | success | 10s |
| secrets | success | 9s |
| dependencies | success | 10s |
| docker | success | 1m6s |
| image-smoke | success | 30s |
| browser-e2e | success | 1m24s |
| CI ready | success | 3s |

`image-smoke` log (`Run shipped-image smoke test` / `Rehearse release identity against audited image` steps):
```
[smoke] negative static-asset-missing: rejected as expected
SMOKE PASSED
Rehearsing release identity for image sha256:84783d0b818523ef554f1fd8e229a94c31d69ed45d41fb90f8174fd3896516d7 at commit 16faed9ae7e54403ae200243fcf5118024271177
matching: accepted 2.12.0
mismatched: rejected as expected (disagree)
malformed: rejected as expected (malformed)
missing: rejected as expected (missing)
```

**CISHIP-03 rehearsal evidence (D-31a, D-31c)**

| Case | Input | Expected outcome | Observed log line |
|---|---|---|---|
| matching | tag/package/image label all `2.12.0` | accepted | `matching: accepted 2.12.0` |
| mismatched | tag/package disagree with image label | rejected /disagree/ | `mismatched: rejected as expected (disagree)` |
| malformed | malformed tag | rejected /malformed/ | `malformed: rejected as expected (malformed)` |
| missing | missing version input | rejected /missing/, "image: missing" | `missing: rejected as expected (missing)` |

`browser-e2e` log (`Run browser regression suite` / `Require a complete browser-suite result` steps):
```
6 passed, 1 deselected in 30.25s
1 passed, 6 deselected in 10.66s
Browser suite result complete: credential and pages junit files both report success with no skips
```
`e2e-credential.xml`: 6 tests, 0 skipped/failures/errors (`credential_pages`). `e2e-pages.xml`: 1 test, 0 skipped/failures/errors (other pages). Matches the junit-count gate's required minimums (6 and 1) with zero skips.

### Review evidence (PR head)

- **Pre-push technical review:** see "Pre-push technical review" above (owner chose run, 3 passes, APPROVED, recorded 2026-10-21 against local SHA `3315a882e2e98d2a3a81752708bb0ec8269e3f88`).
- **Greptile Review:** `pending` at the time of this record (`gh pr checks 33`, checked immediately after the CI run above completed). Not paused on -- per D-35(2) this is recorded against the head SHA whenever it completes, not a stop in this plan.
- **Review acceptance:** `pending` at the time of this record. Not requested, not submitted, not inferred -- D-35(3) owner acceptance happens later, outside Plan 08, and is explicitly out of scope here.
- **Vibe-check:** owner-run, in parallel on `3315a882e2e98d2a3a81752708bb0ec8269e3f88` if the owner supplies one; no result recorded yet.

### Budget (D-14)

- **Baseline:** the most recent successful `CI` run on `main` whose head predates this phase's first workflow change (`3815822`, 2026-10-21T18:59:56-04:00) is [run 39660507361](https://github.com/thejuran/triggarr/actions/runs/39660507361), head `81eb55001b0118c026a8276150d852c89e71ff50` (merge of PR #32, committed 2026-10-21T15:18:38-04:00). Baseline workflow wall-clock (run created `2026-10-21T19:18:42Z` -> `CI ready` completed `2026-10-21T19:20:39Z`): **1m57s**.
- **New run:** workflow wall-clock (run created `2026-10-22T00:07:14Z` -> `CI ready` completed `2026-10-22T00:12:08Z`): **4m54s**.
- **Added critical-path time:** 2m57s (4m54s new wall-clock minus 1m57s baseline wall-clock; baseline run https://github.com/thejuran/triggarr/actions/runs/39660507361). The new jobs' own critical-path contribution (`docker` completed `00:10:33Z` -> `CI ready` started `00:12:05Z`, gated by `browser-e2e` completing at `00:12:02Z`) is 1m32s. Both figures are well under the ~5 minute D-14 target; no budget-exceeded stop applies.

### Required-check failure: CodeQL (stop condition)

`gh pr checks 33 --required` at head `3315a882e2e98d2a3a81752708bb0ec8269e3f88` shows the branch ruleset's four required status checks as: `CI ready` success, `Greptile Review` pending, `Review acceptance` pending, **`CodeQL` failure**. `CodeQL` is a required status check on `main` (`repos/thejuran/triggarr/rules/branches/main`, `required_status_checks` includes `context: "CodeQL"`, integration id `57789`), separate from the `ci.yml` workflow this plan adds jobs to.

- **Check run:** https://github.com/thejuran/triggarr/runs/119559248274 (completed in 3s, conclusion `failure`), part of the default-setup CodeQL analysis workflow run [39697723890](https://github.com/thejuran/triggarr/actions/runs/39697723890) (attempt 1; that analysis run itself has conclusion `success` -- the scan ran cleanly, it is the alert-count gate that failed).
- **Finding:** "2 new alerts including 2 high severity security vulnerabilities" introduced in code changed by this PR (`rule-id py/clear-text-storage-sensitive-data`, CWE-312/315/359, `security_severity_level: high`).
- **Key log lines (annotations):**
  ```
  tests/e2e/probes/probe_setup_fails_before_registration.py:38:40-38:60
    Clear-text storage of sensitive information
    This expression stores sensitive data (password) as clear text.

  tests/e2e/probes/probe_setup_fails_before_registration.py:51:38-51:45
    Clear-text storage of sensitive information
    This expression stores sensitive data (password) as clear text.
  ```
  (Alert numbers 13 and 14, both `state: open`, both flagging `Path(...).write_text(...)` calls that hand the probe's test-only password/API-key to the parent test process via a file -- a mechanism this phase's D-33 amendment introduced, pre-dating this plan's Task 3.)
- **Disposition:** per this plan's authorization boundary, a failing required check stops the plan here without changing tests/assertions or pushing a fix. This finding predates Task 3 (Task 3 made no code changes; it only pushed the already-committed head and recorded evidence) and is out of this task's scope to resolve. Recorded for the owner/next plan to triage (test-only probe using disposable, session-scoped credentials; CodeQL cannot see that distinction from the write-to-file pattern alone).
- **Reconciliation note:** this is the first failure recorded against this push; no second push was attempted.

This record is not owner acceptance (D-35 stop 3 happens later, on the final phase head). Main was not pushed; no review-acceptance approval was requested or submitted.
