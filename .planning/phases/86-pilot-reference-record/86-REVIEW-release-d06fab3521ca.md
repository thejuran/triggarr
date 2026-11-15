---
phase: 86-pilot-reference-record
review_kind: explicit code review of a non-phase change (v2.12.1 release PR, not yet pushed)
reviewed: 2026-11-14T20:56:46Z
reviewed_head: d06fab3521ca37d0325847e19cd419decf634e54
reviewed_base: e5e158451a0e731dbe6012ee0bf3e6e179b2ee25
branch: release-v2.12.1
depth: standard
depth_requested: standard
depth_actual: standard
files_reviewed: 4
files_reviewed_list:
  - CHANGELOG.md
  - pyproject.toml
  - triggarr/__init__.py
  - uv.lock
findings:
  critical: 0
  warning: 1
  info: 5
  total: 6
status: issues_found
---

# Phase 86 (release v2.12.1): Code Review Report

**Reviewed:** 2026-11-14T20:56:46Z
**Head:** `d06fab3521ca37d0325847e19cd419decf634e54` (branch `release-v2.12.1`)
**Base:** `e5e158451a0e731dbe6012ee0bf3e6e179b2ee25` (merge-base with `origin/main`)
**Depth:** standard (requested standard, actual standard)
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Scope was the code-class diff of the release PR: `CHANGELOG.md`, `pyproject.toml`,
`triggarr/__init__.py`, `uv.lock`. The changelog claims were checked against
`git diff v2.12.0..HEAD` for `triggarr/`, `Dockerfile`, `pyproject.toml`, `uv.lock`,
`.github/` and `README.md`.

The version bump and the lockfile are sound. One changelog statement is false on this
head: the FastAPI `FASTAPI_OTEL_AUTO_CONFIGURE` upgrade note says the web UI fails at
startup, and with the locked FastAPI 0.162.4 it does not (WR-01). Five further changelog
wordings are overstated or imprecise (IN-01 to IN-04) and one release-mechanics note is
recorded (IN-05). No defect was found in the version identity or the lockfile.

Checks run on this head (working tree stayed clean, head unchanged):

| Check | Result |
| --- | --- |
| `uv run pytest tests/ -x -q` | 3282 passed, 1 skipped, exit 0 (includes changelog and version tests) |
| `uv run ruff check triggarr/ tests/` | All checks passed |
| `node --test .github/scripts/*.test.cjs` | 613 pass, 0 fail |
| `uv lock --check` (uv 0.12.17, the Dockerfile's pinned version) | exit 0, 56 packages |
| `uv export --locked --no-dev --no-emit-project` on a scratch copy | exit 0; 37 pinned runtime requirements, 563 hashes |
| Changelog parser on `CHANGELOG.md` | v2.12.1 section renders; tags balanced (24 sections, 45 lists) |

Verified as accurate:

- **Version identity.** `pyproject.toml`, `triggarr/__init__.py` and the `triggarr` entry
  in `uv.lock` all read `2.12.1`; `tests/test_version.py` passes. `get_display_version()`
  returns `v2.12.1`. The update check compares `__version__` with the latest release tag,
  so a `v2.12.1` release shows no update. The image version label is not in the
  Dockerfile: `ci.yml:126-147` reads it from `pyproject.toml` at build, and
  `release.yml:100-119` compares that label, the tag and `pyproject.toml` at the release
  commit through `release-policy.cjs`. `parseReleaseTag("refs/tags/v2.12.1")` gives
  `2.12.1`, `parseProjectVersion` finds exactly one `version = "2.12.1"` in `[project]`.
  A `v2.12.1` tag on this tree's content passes the identity gate (see IN-05 for which
  commit the tag must sit on).
- **uv.lock.** `revision = 5` unchanged from the base. Package changes against the base
  are exactly: fastapi 0.162.0 to 0.162.4 (adds `anyio` as a direct dependency, already
  locked at 4.14.2), python-multipart 0.0.32 to 0.0.33, pytest 9.1.1 to 9.2.0, ruff
  0.17.3 to 0.17.4, playwright 1.64.1 to 1.65.0, both `pyee` entries removed, triggarr
  2.12.0 to 2.12.1. Every registry package has a hash on every artifact and resolves from
  `pypi.org`. The runtime export contains no dev package and no `pyee`.
- **Changelog claims that hold.** zlib1g upgrade with both CVE ids and a build-failing
  version check (`Dockerfile:46-56`); hash-checked lockfile install
  (`Dockerfile:21-34`, `58-63`); dependency versions FastAPI 0.162.4, Starlette 1.10.0,
  APScheduler 3.11.3, python-multipart 0.0.33 match `uv.lock` and are the complete list
  of runtime version changes since the v2.12.0 lock (plus the new `opentelemetry-api`);
  wheel/sdist no longer attached (`release.yml:174-204` against the v2.12.0 workflow's
  `dist/*` upload); Refresh counts skips a malformed record and stays connected
  (`triggarr/search/engine.py` `refresh_*_counts`); image smoke, browser tests on the
  audited image, release identity gate, OS scan, actionlint, grouped Dependabot updates,
  and `contents: read` on the job that publishes `:main`/`:dev`.
- **Rendering.** Format matches earlier entries. The intro sentence under the heading is
  not rendered in-app; that is the same for every earlier entry. Backticks show
  literally, as in v2.12.0.

Convention rule packs: not applicable. The changed files are Markdown, TOML, a lockfile
and one Python file; no pack covers them, so nothing was emitted.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: The `FASTAPI_OTEL_AUTO_CONFIGURE` upgrade note is false on this head

**File:** `CHANGELOG.md:29`

**Issue:** The entry says: "If your container environment sets
`FASTAPI_OTEL_AUTO_CONFIGURE=true` together with an OTLP endpoint, the web UI fails at
startup with an error." With the locked FastAPI 0.162.4 the web UI starts normally. FastAPI
catches the telemetry setup error and logs a warning instead.

**Failure scenario:** A user who has those variables set stack-wide reads the in-app
changelog, expects Triggarr to refuse to start, and either removes the variables from a
shared compose block for no reason or holds off upgrading. A user who reads it the other
way assumes that a running Triggarr means telemetry export is working, when nothing is
exported.

**Evidence:**

- `fastapi/telemetry/_runtime.py:210-222` in the installed 0.162.4 wraps
  `_configure_from_environment(config)` in `try/except Exception` with the comment
  "Optional telemetry setup must not prevent application startup" and logs
  `FastAPI automatic telemetry configuration failed: ...`.
- Reproduced in the project environment (fastapi 0.162.4, opentelemetry-api 1.45.2, no
  OpenTelemetry SDK or exporter installed, which matches the image's locked set): a
  FastAPI app with `FASTAPI_OTEL_AUTO_CONFIGURE=true` and
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` completes lifespan startup under
  both Starlette's test client and a real uvicorn server, serves a request with 200, and
  logs: `FastAPI automatic telemetry configuration failed: Automatic OpenTelemetry export
  requires fastapi[opentelemetry] or fastapi[standard]. ...`.
- The copy of FastAPI 0.162.0 in the local uv cache has the same catch, so the SA-12 note
  in `.planning/backlog/MAINTENANCE.md:142` ("fails at startup with a clear error") looks
  wrong as recorded, not just outdated. Only the recorded note supports the changelog
  wording; the code and the reproduction contradict it.
- `triggarr/` has no reference to either variable, so Triggarr adds no failure of its own.

**Fix:** Replace the bullet with what happens, for example:

```markdown
  * FastAPI 0.162 adds opt-in OpenTelemetry auto-configuration. Triggarr's image does not include an OpenTelemetry exporter, so if your container environment sets `FASTAPI_OTEL_AUTO_CONFIGURE=true` together with an OTLP endpoint, Triggarr logs a warning at startup and exports nothing. The web UI starts normally. Leave the variable unset (the default) and nothing changes.
```

Or drop the bullet, since no upgrade action is needed. Correct SA-12 in
`.planning/backlog/MAINTENANCE.md` in the same change so the wrong note is not reused.

## Info

### IN-01: `opentelemetry-api` is described as "updated", but it is new since v2.12.0

**File:** `CHANGELOG.md:9`

**Issue:** The v2.12.0 lockfile has no `opentelemetry-api` package at all (FastAPI was
0.136.3 there). It entered `uv.lock` in `bfae334` (Dependabot roll-up #37-#42, after the
v2.12.0 tag) at 1.45.1 and was bumped to 1.45.2 in `4940373`. The vulnerable 1.45.1 was
only ever in `:main`/`:dev` builds from this lockfile. "Updated to 1.45.2
(CVE-2026-126360)" under Security reads as if the v2.12.0 release carried the vulnerable
version.

**Fix:** Say what changed relative to the last release, for example: "`opentelemetry-api`
is now installed as a dependency of FastAPI, at 1.45.2, which includes the fix for
CVE-2026-126360." Moving it to Improvements next to the dependency list would also be
accurate. See "Not verified" for the one caveat about the published v2.12.0 image.

### IN-02: "skipped and counted, the same way a scheduled cycle handles it" overstates the Refresh counts fix

**File:** `CHANGELOG.md:15` (code: `triggarr/search/engine.py` `refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts`)

**Issue:** A scheduled cycle records the skip in the cycle record and shows "N records
skipped - malformed data" on the dashboard card. Refresh counts uses a throwaway
`CycleTally` whose comment says it is "never persisted to ist or surfaced on the
dashboard"; the only trace is a warning in System Logs. A user who reads "counted, the
same way" will look for a count on the card and not find one.

**Fix:** "The bad record is skipped and logged, and the instance stays connected."

### IN-03: The dashboard-card bullet claims more than the template does

**File:** `CHANGELOG.md:17` (code: `triggarr/templates/partials/cycle_grade.html:18-37`)

**Issue:** Two parts are loose. (a) "Dashboard cards group the last cycle's reasons by
kind" suggests the rows are visibly grouped. The rows are listed in the same order as
before; `kind` only selects the summary label. (b) "Skipped and unevaluated rows are no
longer labelled as failures" holds only when the card has no real failure and is not
graded Failed. A Partial card with one failure and one skipped-records row still says
"Show 2 failure reasons", and a Failed card with only unevaluated rows says "failure
reason(s)" (the entry does state the Failed case).

**Fix:** "On a card with no failed searches, skipped-record and unevaluated rows are no
longer labelled as failures: the card says 'skipped record(s)' or 'detail(s)'. A red
Failed card always says 'failure reason(s)'."

### IN-04: "The published image is the tested image, not a rebuild" is not new in v2.12.1

**File:** `CHANGELOG.md:33`

**Issue:** The v2.12.0 release workflow already had "Download exact successful CI image"
and "Publish audited image without rebuilding". What is new since v2.12.0 is the image
smoke start, the browser tests on that image and the tag/package/image identity gate,
which the first sentence of the bullet covers. The second sentence is true but reads as
a change in this release.

**Fix:** Drop the second sentence, or write "As before, the published image is the
tested image, not a rebuild."

### IN-05: The `v2.12.1` tag must go on the commit on `main` that CI ran on, not on `d06fab3`

**File:** `.github/scripts/release-policy.cjs:70-88` (`validateEvidence`), `.github/workflows/release.yml:31-43`

**Issue:** Not a defect in this diff; a release-mechanics consequence worth stating
because the question was whether a tag on this tree passes. The identity gate passes on
this content. The preflight before it requires a successful push CI run on `main` whose
`head_sha` equals the tagged commit. If the PR is merged with a merge commit (the usual
`gh pr merge --merge`), the push CI on `main` runs on the merge commit, so a tag placed
on `d06fab3521ca` is rejected with "Latest push CI for this exact commit has not
succeeded".

**Fix:** After the merge, wait for push CI on `main` to succeed and tag the `main` head
commit.

## Set aside (needs ruling)

### SA-01: Standalone `pip install git+...` users are not covered by the lockfile claims

**Where:** `pyproject.toml:15-22`, `README.md:101-109`, `CHANGELOG.md:21-23`
**Why excluded:** The release diff does not change dependency floors, and the changelog
scopes the hash-checked install to the Docker image. Raising floors is a product decision
about a route the README now describes as a source install.
**Effect if left as is:** A standalone install resolves from the loose constraints
(`fastapi>=0.136.3`, `python-multipart>=0.0.31`, no `opentelemetry-api` constraint), not
from `uv.lock`. A fresh install gets current versions; an existing environment upgraded
in place can keep older ones, so the Security and Dependency bullets are only guaranteed
for the image.
**Needs:** ruling from the developer: in scope (raise floors or say "Docker image" in
the Security bullet) / defer / accept.

### SA-02: FastAPI 0.162 turns on its native telemetry instrumentation by default

**Where:** `triggarr/__main__.py:68` (`FastAPI(lifespan=...)`), SA-12 in `.planning/backlog/MAINTENANCE.md:142`
**Why excluded:** Introduced by the earlier roll-up (#37-#42), already recorded as an
owner call, and with only `opentelemetry-api` installed the providers are no-ops, so
nothing is collected or exported.
**Effect if left as is:** None in the shipped image. If an OpenTelemetry SDK were ever
added to the image, request telemetry would start flowing wherever the environment
points without a Triggarr setting controlling it.
**Needs:** ruling from the developer when SA-12 is corrected (see WR-01): accept, or pass
`telemetry={"auto_configure": False}` explicitly.

## Not verified

- **CVE identifiers.** CVE-2026-126360, CVE-2026-76844 and CVE-2026-85091 were matched
  against the commit messages, the Dockerfile comment and the planning records only. No
  advisory database was queried.
- **What the published v2.12.0 image contained.** That image installed from
  `pyproject.toml`'s loose constraints at build time, not from the lockfile, so whether it
  included `opentelemetry-api` (IN-01) depends on the FastAPI version PyPI served on
  2026-10-21. Only the v2.12.0 lockfile was checked.
- **Docker build and image contents.** Not run here by instruction. The lockfile export
  step was reproduced with uv 0.12.17 on a scratch copy; the `pip install
  --require-hashes --no-deps` step and the zlib1g check were not.
- **WR-01 inside the built image and through Triggarr's own app.** The reproduction used
  a minimal FastAPI app in the project environment, under the test client and uvicorn.
  Triggarr's full app was not started with the variables set, and whether the FastAPI
  warning reaches Triggarr's log viewer was not checked.
- **Browser tests with Playwright 1.65.0.** `tests/e2e` needs the audited image and a
  browser and runs only in CI's `browser-e2e` job; the dropped `pyee` dependency was
  checked in the lockfile only.
- **GitHub-side release steps.** The preflight, artifact download and identity gate were
  read and their unit tests run; no workflow was executed.

---

_Reviewed: 2026-11-14T20:56:46Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
