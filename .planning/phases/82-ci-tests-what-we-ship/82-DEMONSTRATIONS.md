# Phase 82 — Negative demonstrations

This file records evidence that each new check fails for the reason it is meant to (D-06, D-08). Two kinds of evidence are kept separate (D-32):

- **(i) Browser sensitivity evidence:** the real browser assertions fail on a mutation of the shipped image. These runs are local, nothing is pushed, and they support only a narrow claim (D-07).
- **(ii) Gate enforcement evidence:** on isolated draft PRs, a failing or skipped mandatory job keeps `CI ready` red.

Recipes: `docs/ci-negative-demonstrations.md`.

## Audited image under test

The image is the `audited-image` artifact of the latest code-bearing phase run.

| Field | Value |
|---|---|
| CI run | [39701686221](https://github.com/thejuran/triggarr/actions/runs/39701686221), attempt 1 (`pull_request`) |
| PR head SHA | `0f08523252a41c4ad541dbf594dd50ac13e6af2e` |
| PR base SHA | `81eb55001b0118c026a8276150d852c89e71ff50` |
| Tested SHA (`github.sha` / checkout HEAD) | `35458d4a0eefc530c496f1dc067d082d4d84c5b5` |
| Image revision label | `35458d4a0eefc530c496f1dc067d082d4d84c5b5` (version label `2.12.0`) |
| Image ID (`image-id.txt`) | `sha256:66bbe15a99739806ced5f9aa42b9ce4257b7e1b3ed793bc5f6d6dc041a7017e8` |
| image.tar sha256 | `7902c6f4742c07ee122d4bc7b2216a5e594e6d1958daa442853db9820c273e9d` (`sha256sum -c` OK) |

Reconciliation: tested SHA `35458d4a0eefc530c496f1dc067d082d4d84c5b5` is GitHub's merge of PR head `0f08523252a41c4ad541dbf594dd50ac13e6af2e` into base `81eb55001b0118c026a8276150d852c89e71ff50`. `git rev-list --parents -n 1 35458d4` lists exactly that base and head, and the job log shows `HEAD is now at 35458d4 Merge 0f08523… into 81eb550…`. The CI evidence applies to `35458d4`; the review evidence applies to `0f08523`.

The image was loaded locally, and its ID equals `image-id.txt` and the ID the rehearsal printed. It was tagged `triggarr-demo:base`. Every `triggarr-demo:*` and `triggarr:ci-test` tag was removed afterwards.

## Browser sensitivity evidence (i)

This is a local demonstration setting. The claim is narrow (D-07): the real browser assertions detect these regressions in the shipped image. **This is not gate evidence.**

Method (Recipes 2 and 3, part i):
- Each variant is built `FROM triggarr-demo:base` using only `COPY` of the mutated template file or files (no RUN, no LABEL).
- The template files come from the tested commit.
- The suite is the CI `browser-e2e` non-credential invocation with the same flags: `-m "not credential_pages" --browser chromium --tracing retain-on-failure --screenshot only-on-failure`, plus `--output` and `--junitxml`.
- `TRIGGARR_E2E_IMAGE` and `EXPECTED_IMAGE_ID` are set for that command only.

**Control:** the same invocation against `triggarr-demo:base` passed (`tests 1, failures 0, skipped 0`).

**Manifest proof** (`find /app -type f -exec sha256sum {} + | sort -k2`, 68 files in the base image):
- `pill-loop` vs base differs only in `/app/triggarr/templates/partials/connection_pill.html`.
- `pill-disabled` vs base differs only in `/app/triggarr/templates/partials/connection_pill.html` and `/app/triggarr/templates/base.html`.

### Recipe 2 (i): pill request loop

- **Mutation:** partial `hx-trigger="every 30s"` → `hx-trigger="load, every 30s"`, the PR #27 bug.
- **Expected:** the test fails with "connection pill request loop".
- **Observed:** `AssertionError: connection pill request loop: 113 requests without any scheduled tick`. junit: tests 1, failures 1, skipped 0.

### Recipe 3 (i): pill polling disabled

- **Mutation:** partial `hx-trigger="every 30s"` removed; `base.html` placeholder `hx-trigger="load, every 30s"` → `hx-trigger="load"`.
- **Expected:** the test fails with "did not refresh after a scheduled interval".
- **Observed:** `Failed: connection pill did not refresh after a scheduled interval: expected at least 2 requests, saw 1`. junit: tests 1, failures 1, skipped 0.

### Artifact check (D-33)

Both failing output directories were checked as CI would upload them:
- `scan-complete.json` is present in each.
- The Playwright `trace.zip` was **withheld** by the byte scan in both runs, recorded in `withheld.txt` as "contains sensitive value". The trace records request headers carrying the registered session cookie. This is the designed fail-closed outcome.
- The remaining files are the failure screenshot `test-failed-1.png` (the dashboard, a non-credential page) and the container log, which the registry redacts.
- A byte search of those files found **no** `triggarr_session=<value>` and **no** stub key `ci-stub-key-not-a-secret`. The run's admin password is random per run and the registry redacts it from logs.
- No file came from a `credential_pages` test, which ran with all capture off.

Byte scanning is an extra defence. It is **not proof that screenshots are safe**, because pixels cannot be byte-searched. Screenshot safety rests on the capture policy: credential pages are never captured.

## Gate enforcement evidence (ii)

The three demonstration branches are staged **locally only**. Each is forked from PR head `0f08523252a41c4ad541dbf594dd50ac13e6af2e` and adds one commit titled "demo(82): DO NOT MERGE - <name> negative demonstration". None of them touches `tests/` or `.github/`, and `tests/test_header_redesign.py` is unchanged.

| Branch | Commit | Diff vs PR head |
|---|---|---|
| `demo/82-broken-entrypoint` | `f21acd0` | `entrypoint.sh` only: `python -m triggarr` → `python -m triggarr_missing_module` |
| `demo/82-pill-loop` | `468f721` | `triggarr/templates/partials/connection_pill.html` only |
| `demo/82-pill-disabled` | `f24a183` | the partial and `triggarr/templates/base.html` only |

Remote tag count before any demonstration push: **58** (`git ls-remote --tags origin | wc -l`). It must be unchanged afterwards (D-31e).

No demonstration can publish anything. PR events never trigger `release.yml`, which runs only after push CI on main (`workflow_run`) or on `v*` tags.

### Owner go-ahead

_Pending (D-10). No demonstration branch has been pushed._

### Recipe 1 (ii): broken entrypoint

The following fields are filled in after an approved push:
- PR head SHA, PR base SHA, tested SHA
- Image revision label, image ID and image.tar sha256
- Run URL, run ID and attempt
- Expected outcome: `image-smoke` fails with a `SMOKE FAILED` line from the first-run or seeded step, and `CI ready` fails
- Observed log line and per-job conclusions
- Reconciliation and cleanup

### Recipe 2 (ii): pill loop

This is gate enforcement evidence through the existing header unit tests. It is **not browser evidence** (see section (i)).

Expected outcome:
- the `test` job fails on `test_connection_pill_partial_does_not_retrigger_on_swap`;
- `docker`, `image-smoke` and `browser-e2e` are skipped;
- `CI ready` fails;
- image: not built (docker skipped).

The following fields are filled in after an approved push: PR head SHA, PR base SHA, tested SHA, run URL, run ID and attempt, observed log lines, per-job conclusions, Reconciliation and cleanup.

### Recipe 3 (ii): pill polling disabled

This is gate enforcement evidence through the existing header unit tests. It is **not browser evidence**.

Expected outcome:
- the `test` job fails on `test_connection_pill_loaded_via_htmx_in_header` and `test_connection_pill_partial_does_not_retrigger_on_swap`;
- the downstream jobs are skipped;
- `CI ready` fails;
- image: not built.

The fields to fill in after an approved push are the same as for Recipe 2.

## Restored final commit

The phase PR head on origin is `0f08523252a41c4ad541dbf594dd50ac13e6af2e`, with tested SHA `35458d4a0eefc530c496f1dc067d082d4d84c5b5` and run [39701686221](https://github.com/thejuran/triggarr/actions/runs/39701686221):
- All `ci.yml` jobs succeeded.
- `Greptile Review` passed.
- `CodeQL` failed on alert #16, the same scrypt-digest false positive as #15. The owner decided to dismiss #16 for the same reason (2026-10-21), and there are 0 open alerts. CodeQL is re-evaluated on the next push of the phase branch.

Local docs commits held for that push: `f659e29`, `75955d4`, `44d4f7f`, `0898dd7` and this record. Final-head checks are re-confirmed after the demonstrations and that push.

## Release identity (CISHIP-03) evidence

The per-run rehearsal in `image-smoke` calls `parseReleaseTag` and `releaseIdentityGate`, the same entry points `release.yml` calls, against the exact audited image (D-31a).

Commit identities are as in "Audited image under test" above: PR head `0f08523…`, PR base `81eb550…`, tested SHA `35458d4…`, image revision label `35458d4…`, image ID `sha256:66bbe15a…7017e8`, image.tar sha256 `7902c6f4…3e9d`. The Reconciliation line is the one recorded there. The run is [39701686221](https://github.com/thejuran/triggarr/actions/runs/39701686221), attempt 1. Earlier runs are recorded in `82-CI-EVIDENCE.md`.

| Case | Input | Expected | Observed log line |
|---|---|---|---|
| matching | tag, package and image label all `2.12.0` | accepted | `matching: accepted 2.12.0` |
| mismatched | the tag disagrees with the package and the image label | rejected /disagree/ | `mismatched: rejected as expected (disagree)` |
| malformed | malformed tag | rejected /malformed/ | `malformed: rejected as expected (malformed)` |
| missing | missing image version | rejected /missing/, "image: missing" | `missing: rejected as expected (missing)` |

The structural wiring tests from Plan 03 Task 3 (`publication_bypass_violations` and its 11 bypass negatives, plus `orderingViolations`) show that a rejection blocks registry login, image push and GitHub Release creation (D-31b, D-24). These permanent negatives run inside green CI runs. No deliberately red tag-triggered run is performed or required: D-31e applies, and D-07 forbids production tags.

Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release.
