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
- **Resolved (partially):** owner chose to **fix** (not dismiss) the finding, commit `6c8354e` (`fix(82): stop the capture-policy probe writing credentials to disk`), pushed on top of this plan's two local evidence commits. Alerts #13 and #14 are both confirmed `fixed` at the new head (see the Second GitHub run section below for the `most_recent_instance.state` check). `CodeQL` still fails at the new head on a new alert (#15), so this is a partial resolution, not a closed stop -- see below.

This record is not owner acceptance (D-35 stop 3 happens later, on the final phase head). Main was not pushed; no review-acceptance approval was requested or submitted.

## Second GitHub run (after CodeQL fix 6c8354e)

- **Pushed:** `git push origin ci-review-workflow` (fast-forward `3315a88..6c8354e`), updating PR #33. No force push, main untouched. This push carried the two prior local-only evidence commits (`1a0fdae`, `399e6ec`) plus the owner's CodeQL fix (`6c8354e`).
- **CI run:** [run 39699460532, attempt 1](https://github.com/thejuran/triggarr/actions/runs/39699460532) (workflow `CI`, event `pull_request`).

### Commit identities (D-34)

| Field | Value |
|---|---|
| PR head SHA | `6c8354e932292bc5fdb6609388d32a673ba6070f` |
| PR base SHA | `81eb55001b0118c026a8276150d852c89e71ff50` |
| Tested SHA (`github.sha` / checkout HEAD) | `03c94f2e4519e16e3596e38c9d244d8bc8cd9f19` |
| Image revision label (`org.opencontainers.image.revision`) | `03c94f2e4519e16e3596e38c9d244d8bc8cd9f19` |
| Image ID | `sha256:f0a89c53d491eea27668f4117e13165ee6546f242ca75da52b63e50419f0a194` |
| image.tar sha256 | `4959fa4067f1715e38def31c16d44d8e555480b2444d38023ac03e89a3467cf6` |

PR head SHA confirmed equal to `git log origin/ci-review-workflow -1 --format=%H` (`6c8354e932292bc5fdb6609388d32a673ba6070f`). Image revision label confirmed equal to the tested SHA by downloading the `audited-image` artifact from run 39699460532 into the same scratch directory (prior run's artifact files removed first), verifying `sha256sum -c image.tar.sha256`, `docker load`-ing it, confirming `docker image inspect --format '{{.Id}}'` equals `image-id.txt`, then reading the `org.opencontainers.image.revision` and `.version` labels (version label: `2.12.0`, unchanged). The loaded image tag was removed from the local Docker daemon afterward.

**Reconciliation:** `git fetch origin 03c94f2e4519e16e3596e38c9d244d8bc8cd9f19` then `git rev-list --parents -n 1 03c94f2e4519e16e3596e38c9d244d8bc8cd9f19` returned parents `81eb55001b0118c026a8276150d852c89e71ff50 6c8354e932292bc5fdb6609388d32a673ba6070f` (base, then head) -- confirmed via the job logs' own `HEAD is now at 03c94f2 Merge 6c8354e932292bc5fdb6609388d32a673ba6070f into 81eb55001b0118c026a8276150d852c89e71ff50`. Reconciliation: tested SHA `03c94f2e4519e16e3596e38c9d244d8bc8cd9f19` is GitHub's merge of PR head `6c8354e932292bc5fdb6609388d32a673ba6070f` into base `81eb55001b0118c026a8276150d852c89e71ff50`; CI evidence below applies to `03c94f2e4519e16e3596e38c9d244d8bc8cd9f19`, review evidence to `6c8354e932292bc5fdb6609388d32a673ba6070f`.

### CI evidence (tested SHA)

Run: https://github.com/thejuran/triggarr/actions/runs/39699460532, run ID `39699460532`, attempt `1`.

| Job | Conclusion | Duration |
|---|---|---|
| test | success | 2m8s |
| lint | success | 8s |
| secrets | success | 9s |
| dependencies | success | 12s |
| docker | success | 35s |
| image-smoke | success | 38s |
| browser-e2e | success | 1m22s |
| CI ready | success | 3s |

`image-smoke` log (`Run shipped-image smoke test` / `Rehearse release identity against audited image` steps):
```
[smoke] negative static-asset-missing: rejected as expected
SMOKE PASSED
Rehearsing release identity for image sha256:f0a89c53d491eea27668f4117e13165ee6546f242ca75da52b63e50419f0a194 at commit 03c94f2e4519e16e3596e38c9d244d8bc8cd9f19
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
6 passed, 1 deselected in 32.63s
1 passed, 6 deselected in 11.01s
Browser suite result complete: credential and pages junit files both report success with no skips
```
`e2e-credential.xml`: 6 tests, 0 skipped/failures/errors (`credential_pages`). `e2e-pages.xml`: 1 test, 0 skipped/failures/errors (other pages). Matches the junit-count gate's required minimums (6 and 1) with zero skips. This also exercises the fixed probe path (the credential-pages run includes `test_capture_policy.py`, which now hands the admin password through the environment and checks for leaks via the salted-fingerprint window scan instead of a plaintext file).

### Review evidence (PR head)

- **Pre-push technical review:** unchanged -- see "Pre-push technical review" above. The CodeQL fix (`6c8354e`) was supplied directly by the owner after the first run's checkpoint, with local verification reported by the owner (2160 unit tests, ruff clean, capture-guard unit tests 5/5, browser suite credential_pages 6 passed / pages 1 passed against a fresh local image) -- not a second `/deep-review` pass.
- **Greptile Review:** `pending` at the time of this record (`gh pr checks 33`, checked immediately after the CI run above completed). Not paused on -- per D-35(2) this is recorded against the head SHA whenever it completes, not a stop in this plan.
- **Review acceptance:** `pending` at the time of this record. Not requested, not submitted, not inferred -- D-35(3) owner acceptance happens later, outside Plan 08, and is explicitly out of scope here.
- **Vibe-check:** owner-run, in parallel on `6c8354e932292bc5fdb6609388d32a673ba6070f` if the owner supplies one; no result recorded yet.

### Budget (D-14)

- **Baseline:** same baseline as the first run -- [run 39660507361](https://github.com/thejuran/triggarr/actions/runs/39660507361), head `81eb55001b0118c026a8276150d852c89e71ff50`, workflow wall-clock **1m57s**.
- **New run:** workflow wall-clock (run created `2026-10-22T00:24:06Z` -> `CI ready` completed `2026-10-22T00:28:26Z`): **4m20s**.
- **Added critical-path time:** 2m23s (4m20s new wall-clock minus 1m57s baseline wall-clock; baseline run https://github.com/thejuran/triggarr/actions/runs/39660507361). The new jobs' own critical-path contribution (`docker` completed `00:26:56Z` -> `CI ready` started `00:28:23Z`, gated by `browser-e2e` completing at `00:28:20Z`) is 1m27s. Both figures are well under the ~5 minute D-14 target; no budget-exceeded stop applies.

### CodeQL at the new head -- still failing (new finding, not yet resolved)

`gh pr checks 33` at head `6c8354e932292bc5fdb6609388d32a673ba6070f` shows: `CI ready` success, `browser-e2e` success, `dependencies` success, `docker` success, `image-smoke` success, `lint` success, `secrets` success, `test` success, `Greptile Review` pending, `Review acceptance` pending, **`CodeQL` failure** (check run https://github.com/thejuran/triggarr/runs/119565047641, completed in 2s, conclusion `failure`; the underlying analysis run [39699457242](https://github.com/thejuran/triggarr/actions/runs/39699457242) itself concluded `success` -- same pattern as the first run, the scan ran cleanly and it is the alert-count gate that failed).

- **Alerts #13 and #14 (the original two): confirmed fixed.** `gh api repos/thejuran/triggarr/code-scanning/alerts/13` and `.../14`, read via `.most_recent_instance`, both show `"state":"fixed"` at `commit_sha: 3315a882e2e98d2a3a81752708bb0ec8269e3f88` (fixed at the commit immediately before `6c8354e` took effect, i.e. by `6c8354e`'s removal of the plaintext password-file and raw-API-key-file writes).
- **New alert (#15): one new high-severity finding**, same rule, same file, different line. `gh api "repos/thejuran/triggarr/code-scanning/alerts?ref=refs/pull/33/head"` lists alert `15` as `state: open` at `tests/e2e/probes/probe_setup_fails_before_registration.py:53`, `commit_sha: 6c8354e932292bc5fdb6609388d32a673ba6070f`. Check-run output: *"1 new alert including 1 high severity security vulnerability"*.
- **Key log lines (annotation):**
  ```
  tests/e2e/probes/probe_setup_fails_before_registration.py:53:38-53:75
    Clear-text storage of sensitive information
    This expression stores [sensitive data (secret)] as clear text.
  ```
  The flagged line is `Path(digest_file).write_text(secret_fingerprint(api_key, salt_hex))` -- the fix's own replacement write. CodeQL's `py/clear-text-storage-sensitive-data` query still treats the value written to disk as tainted by the sensitive `api_key` source: its taint tracking does not recognize `hashlib.scrypt`-derived output as a sanitizer that clears the "sensitive data" flow, even though the digest is a one-way salted fingerprint rather than the recoverable secret.
- **Disposition:** per this plan's authorization boundary and the coordinator's explicit instruction, a still-failing required check stops the plan here again, without a further fix attempt or a second push. Alerts #13/#14 are a genuine, confirmed improvement; alert #15 is a new, not-yet-resolved required-check failure on a one-way-hash write pattern, which needs either a CodeQL-recognized sanitizer annotation/suppression (with rationale) or a further structural change (e.g. not persisting the digest to a file at all, using an in-memory IPC channel instead) -- an owner/architectural call outside this task's authorized scope.
- **Reconciliation note:** this is the first failure recorded against the second push (`6c8354e`); no third push was attempted.

#### Alert #15 disposition

Alerts #13 and #14 (`py/clear-text-storage-sensitive-data`, the plaintext password-file and raw-API-key-file writes) were fixed in `6c8354e`. Alert #15 (same rule, `tests/e2e/probes/probe_setup_fails_before_registration.py:53`, the salted scrypt digest write) was **dismissed by the owner as a false positive**, 2026-10-21, via the GitHub code-scanning API (`dismissed_by: thejuran`, `dismissed_reason: "false positive"`), with this comment:

> Owner decision 2026-10-21: one-way salted scrypt digest of a disposable per-run e2e API key (D-27); no recoverable secret is stored. The real plaintext writes (#13, #14) were fixed in 6c8354e.

Verified via `gh api repos/thejuran/triggarr/code-scanning/alerts/15`: `state: dismissed`, `dismissed_at: 2026-10-22T00:34:18Z`, `dismissed_by: thejuran`, `dismissed_reason: "false positive"`, `dismissed_comment` matching the text above. Open code-scanning alerts on `refs/pull/33/head` are now 0.

CodeQL's `py/clear-text-storage-sensitive-data` taint analysis treats any value derived from the tracked sensitive source (here, the API key) as itself sensitive, regardless of whether the derivation is reversible -- it does not recognize `hashlib.scrypt` (or hashing in general) as a sanitizer for this query, so a one-way digest of a secret still trips the rule. That is a static-analysis limitation, not a report of an actual recoverable-secret-on-disk condition, which is the basis for the owner's dismissal.

### Final head checks

Docs-only commit `3f8f5f7` (recording the alert #15 disposition above) was pushed on top of `6c8354e` (fast-forward `6c8354e..3f8f5f7`), carrying `9df705b`, `f41c065` and `3f8f5f7`. This head makes no code changes versus `6c8354e` -- the Second GitHub run section above is the full CI evidence record for the code; only a confirmation run is needed here.

- **New PR head SHA:** `3f8f5f7532d2f26266e947a0aca7a8d563c76b67` (confirmed equal to `git log origin/ci-review-workflow -1 --format=%H` and to `gh pr view 33 --json headRefOid`).
- **CI run:** https://github.com/thejuran/triggarr/actions/runs/39700561470, run ID `39700561470`, attempt `1`.
- **Per-job conclusions (all `success`):** `test`, `lint`, `secrets`, `dependencies`, `docker`, `image-smoke`, `browser-e2e`, `CI ready`.
- **This run's own identities (D-34; a docs-only head still builds a new image labelled with its own `github.sha`):**

| Field | Value |
|---|---|
| PR head SHA | `3f8f5f7532d2f26266e947a0aca7a8d563c76b67` |
| PR base SHA | `81eb55001b0118c026a8276150d852c89e71ff50` |
| Tested SHA (`github.sha` / checkout HEAD) | `97a244a04ce9c44e2231d568e4dd961671499e6a` |
| Image revision label | `97a244a04ce9c44e2231d568e4dd961671499e6a` |
| Image ID | `sha256:13dcaa52ddc67ed3b3bcc2f14f80618d5c9aa44779a0581361c643acd04e37d0` |
| image.tar sha256 | `354c89b1c2bc63dfcd6099add5353331544a7171f57c08bb73891d63d0cd8758` |

  Reconciliation: tested SHA `97a244a04ce9c44e2231d568e4dd961671499e6a` is GitHub's merge of PR head `3f8f5f7532d2f26266e947a0aca7a8d563c76b67` into base `81eb55001b0118c026a8276150d852c89e71ff50` (job log: `HEAD is now at 97a244a Merge 3f8f5f7… into 81eb550…`); CI evidence for this run applies to `97a244a…`, review evidence to `3f8f5f7…`. Verified from the run's `audited-image` artifact: `sha256sum -c image.tar.sha256` OK, loaded image ID equals `image-id.txt` and the rehearsal's printed image ID, revision label equals the tested SHA, version label `2.12.0`; the loaded tag was removed afterwards. (Recorded after the fact, prompted by Greptile's review of `0f08523`.)
- **CodeQL:** `pass` (check run https://github.com/thejuran/triggarr/runs/119568626183, 3s) -- the alert-count gate is now green, consistent with 0 open code-scanning alerts on this ref.
- **Greptile Review:** `pending` at time of this record. **Review acceptance:** `pending` at time of this record. Neither paused on; neither touched; no approval requested or submitted.

All branch-ruleset required checks this plan can observe synchronously (`CI ready`, `CodeQL`) are green at this head.

This record is not owner acceptance (D-35 stop 3 happens later, on the final phase head). Main was not pushed; no review-acceptance approval was requested or submitted; no `review-acceptance` environment was touched.

## Greptile findings on PR #33 and the fix push (`0f08523`)

Greptile's reviews of `3315a88`, `6c8354e` and `3f8f5f7` raised six findings. Each was checked against the code. Five were real (one a regression from `6c8354e`) and one was already fixed in the held commit `f659e29`. The owner chose to fix all of them in one batch and one push.

| Finding | Disposition | Evidence |
|---|---|---|
| P1 `tests/e2e/test_capture_policy.py:173`: a single Docker-health sample can fail a healthy build | Fixed `4aa74cc`: `stack.wait_for_docker_health(parent_app_name, timeout=90)` | Browser suite green locally (6 + 1) and in CI on `0f08523` |
| P2 `tests/e2e/conftest.py:73`: `SensitiveRegistry` repr prints registered secrets | Fixed `4aa74cc`: `values` uses `field(..., repr=False)` | Regression test `tests/test_e2e_secret_hygiene.py::test_sensitive_registry_repr_hides_registered_values` failed before the fix (`1b44915`) and passes after |
| P2 `tests/e2e/test_capture_policy.py:122`: a blank API key passes the fingerprint check (regression from `6c8354e`) | Fixed `4aa74cc`: `api_key_handoff` only fingerprints a 32-hex key; otherwise no file is written and the parent's check fails | Regression tests `test_api_key_handoff_*` failed before the fix (`1b44915`) and pass after |
| P2 `tests/e2e/conftest.py:358`: container logs are lost on setup failures | Fixed `4aa74cc`: logs are saved when `wait_for_http_health` raises and when the setup or call report failed | Code review only; a real startup failure was not triggered |
| P2 `82-VALIDATION.md:23`: the documented full-suite command is refused by the capture guard | Fixed `0f08523`: replaced with the two CI invocations | Doc |
| P2 `82-08-SUMMARY.md:114`: handoff says alert #15 is open | Already fixed in `f659e29`; `0f08523` also corrects the summary's attribution (the CodeQL fix and the #15 dismissal were made by the orchestrating session on the owner's decision) | Doc |

Local gate at `0f08523`: 2164 unit tests, ruff clean, JS tests 0 failures, actionlint clean, and the browser suite against a fresh local image (6 + 1 passed).

**CI on `0f08523`:** all `ci.yml` jobs and `Greptile Review` passed (run https://github.com/thejuran/triggarr/actions/runs/39701686221). **CodeQL failed** with alert #16: the same rule on the same scrypt digest write, now at line 56, because `4aa74cc` moved the line. The owner decided (2026-10-21) to dismiss #16 for the same reason as #15. It was dismissed via the code-scanning API (`dismissed_reason: "false positive"`, `dismissed_by: thejuran`) with this comment: "Owner decision 2026-10-21 (same as #15): one-way salted scrypt digest of a disposable per-run e2e API key (D-27); no recoverable secret is stored. Reopened as #16 only because 4aa74cc moved the line (key-shape guard added)." Open alerts on `refs/pull/33/head`: 0. CodeQL is re-evaluated on the next push. Because a dismissal is tied to the flagged code, any further edit to that line will reopen it.

Greptile's review of `0f08523` raised one more P2: the third run's image identity fields were missing. They are now added to "Final head checks" above. This docs-only change is held locally and goes out with the next substantive push (owner rule: no pushes made only for docs).
