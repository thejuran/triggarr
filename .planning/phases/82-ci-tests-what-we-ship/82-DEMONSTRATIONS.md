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

### Re-run with recorded image IDs (2026-10-22, prompted by Greptile's review of `6c577d4`)

The first run did not capture the variant image IDs, the exact commands or the config comparison before its images were removed. The variants were rebuilt from the same verified audited tarball (`image.tar` sha256 `7902c6f4…3e9d`, `sha256sum -c` OK, loaded ID equal to `image-id.txt`) using the same two Dockerfiles (COPY only), and re-run with the fixed pill test from `42a5e0b`.

| Image | Image ID | Result |
|---|---|---|
| `triggarr-demo:base` | `sha256:66bbe15a99739806ced5f9aa42b9ce4257b7e1b3ed793bc5f6d6dc041a7017e8` | passed (control): `1 passed, 6 deselected` |
| `triggarr-demo:pill-loop` | `sha256:d6ff42c13626b3d6ec95b356e956be154a819dc8454dd66f5b4b6c10cac0e231` | failed: `AssertionError: connection pill request loop: 114 requests without any scheduled tick` |
| `triggarr-demo:pill-disabled` | `sha256:33dc23e364035e1d4010664bf83812ddb3142e27f05c25f3629a4e8d408cc815` | failed: `Failed: connection pill did not refresh after a scheduled interval: expected at least 2 requests, saw 1` |

Config comparison: `.Config.Entrypoint`, `.Cmd`, `.Env` and `.Labels` are byte-identical between base and each variant. The file manifest diff is as recorded above.

Exact commands (each with the CI non-credential flags):
```
base CMD: TRIGGARR_E2E_IMAGE=triggarr-demo:base EXPECTED_IMAGE_ID=sha256:66bbe15a99739806ced5f9aa42b9ce4257b7e1b3ed793bc5f6d6dc041a7017e8 uv run --no-sync pytest tests/e2e -q -p no:cacheprovider -m "not credential_pages" --browser chromium --tracing retain-on-failure --screenshot only-on-failure --output <scratch>/p09/rerun/base/pages --junitxml <scratch>/p09/rerun/base/e2e-pages.xml
pill-loop CMD: TRIGGARR_E2E_IMAGE=triggarr-demo:pill-loop EXPECTED_IMAGE_ID=sha256:d6ff42c13626b3d6ec95b356e956be154a819dc8454dd66f5b4b6c10cac0e231 uv run --no-sync pytest tests/e2e -q -p no:cacheprovider -m "not credential_pages" --browser chromium --tracing retain-on-failure --screenshot only-on-failure --output <scratch>/p09/rerun/pill-loop/pages --junitxml <scratch>/p09/rerun/pill-loop/e2e-pages.xml
pill-disabled CMD: TRIGGARR_E2E_IMAGE=triggarr-demo:pill-disabled EXPECTED_IMAGE_ID=sha256:33dc23e364035e1d4010664bf83812ddb3142e27f05c25f3629a4e8d408cc815 uv run --no-sync pytest tests/e2e -q -p no:cacheprovider -m "not credential_pages" --browser chromium --tracing retain-on-failure --screenshot only-on-failure --output <scratch>/p09/rerun/pill-disabled/pages --junitxml <scratch>/p09/rerun/pill-disabled/e2e-pages.xml
```

All three images were removed afterwards; no `triggarr-demo:*` image and no labelled container, volume or network remains.

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

Owner decision, 2026-10-22 (verbatim):

> Push only the broken-entrypoint demonstration as a draft PR. Record its intended failure and CI ready failure, then close it and delete its demonstration branch. Retain the local pill sensitivity evidence; explicitly record that the pill mutations were not demonstrated on GitHub. Treat those two remote demonstrations as waived, not passed. No merge, release, or production tag is authorized.

- **Approved for push:** `demo/82-broken-entrypoint` only.
- **Waived, not passed:** the pill-loop and pill-disabled gate-enforcement demonstrations (Recipes 2 (ii) and 3 (ii)). They are not demonstrated on GitHub. The local browser sensitivity evidence (i) above is retained.
- **Not authorized:** no merge, no release, no production tag.

### Recipe 1 (ii): broken entrypoint

Run on GitHub with owner approval: draft PR [#34](https://github.com/thejuran/triggarr/pull/34), "DO NOT MERGE - Phase 82 negative demonstration: broken entrypoint".

| Field | Value |
|---|---|
| PR head SHA (demo commit) | `f21acd0c4187b4eecef204d12ef307c2d74e0255` |
| PR base SHA | `81eb55001b0118c026a8276150d852c89e71ff50` |
| Tested SHA (`github.sha`) | `311ff59cdda09d178b39dbe4ca8142b7bc5e1d8a` |
| Image revision label | `311ff59cdda09d178b39dbe4ca8142b7bc5e1d8a` (read from the artifact's image config) |
| Image ID | `sha256:69c75f3ae1d9b7a4de9a2904369bc409e4dc4a19892a308491c27b0d4520ea9d` |
| image.tar sha256 | `58379d0381932be8c9c70a9636780c4935c7befd55ff89ef07430863b45bcf77` (`sha256sum -c` OK) |
| Run | [39790931780](https://github.com/thejuran/triggarr/actions/runs/39790931780), attempt 1, conclusion `failure` |

Reconciliation: tested SHA `311ff59cdda09d178b39dbe4ca8142b7bc5e1d8a` is GitHub's merge of demo head `f21acd0c4187b4eecef204d12ef307c2d74e0255` into base `81eb55001b0118c026a8276150d852c89e71ff50`. `git rev-list --parents -n 1` lists exactly that base and head, and the job log shows `HEAD is now at 311ff59 Merge f21acd0… into 81eb550…`.

- **Expected:** `image-smoke` fails with a `SMOKE FAILED` line from the first-run or seeded step, and `CI ready` fails.
- **Observed (`image-smoke`):** `SMOKE FAILED [first-run] expected exit 1 with a default-config log line, got exit=1`. The container exited 1 because the module was missing, but the "Default config written to" line never appeared, so the first-run check rejected it for the intended reason. The wording "expected exit 1 … got exit=1" is ambiguous, because the check's message names the exit code but not the missing log line. That is a cosmetic follow-up, not a gate defect.
- **Observed (`browser-e2e`, also red, as expected for an app that cannot start):** `SmokeCheckError: [health-timeout] did not become healthy within 30s: <urlopen error [Errno 111] Connection refused>`. The uploaded `browser-e2e-failure` artifact contains each container's redacted logs, saved on setup failure (the Greptile #4 fix, `4aa74cc`, now exercised on a real failure). Each log shows the root cause `/usr/local/bin/python: No module named triggarr_missing_module`. No stub key and no session cookie appear in the artifact, and the byte scan withheld nothing.
- **Observed (`CI ready`):** `Mandatory jobs did not succeed: {'image-smoke': 'failure', 'browser-e2e': 'failure'}`, exit code 1.
- **Per-job conclusions:** test success, lint success, secrets success, dependencies success, docker success, image-smoke **failure**, browser-e2e **failure**, CI ready **failure**.
- **Publication:** impossible. This was a `pull_request` run, and `release.yml` runs only after push CI on main or on `v*` tags.
- **Cleanup:** PR #34 closed (not merged) with the comment "Negative demonstration recorded in Phase 82 evidence". `demo/82-broken-entrypoint` deleted on origin and locally. No `demo/82-*` branch remains on origin. The remote tag count is still **58**, unchanged. The waived pill branches were never pushed and were deleted locally.

### Recipe 2 (ii): pill loop

**Status: WAIVED by owner decision 2026-10-22, not passed. Not demonstrated on GitHub. The gate claim for this mutation is unproven on GitHub.** The intended evidence is kept below for reference.

This is gate enforcement evidence through the existing header unit tests. It is **not browser evidence** (see section (i)).

Expected outcome:
- the `test` job fails on `test_connection_pill_partial_does_not_retrigger_on_swap`;
- `docker`, `image-smoke` and `browser-e2e` are skipped;
- `CI ready` fails;
- image: not built (docker skipped).

The following fields are filled in after an approved push: PR head SHA, PR base SHA, tested SHA, run URL, run ID and attempt, observed log lines, per-job conclusions, Reconciliation and cleanup.

### Recipe 3 (ii): pill polling disabled

**Status: WAIVED by owner decision 2026-10-22, not passed. Not demonstrated on GitHub. The gate claim for this mutation is unproven on GitHub.** The intended evidence is kept below for reference.

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

PR #33's head on origin was still `0f08523252a41c4ad541dbf594dd50ac13e6af2e` after the demonstration, so no demonstration touched it. Local docs commits held for that push: `f659e29`, `75955d4`, `44d4f7f`, `0898dd7` and this record. Final-head checks are re-confirmed after the demonstrations and that push.

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
