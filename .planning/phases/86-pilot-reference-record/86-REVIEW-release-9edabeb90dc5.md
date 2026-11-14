---
phase: 86-pilot-reference-record
review_kind: review after fixes of a non-phase change (v2.12.1 release PR, not yet pushed), final round
reviewed: 2026-11-14T21:17:34Z
reviewed_head: 9edabeb90dc5ed51ebb784dcd38bc520818f25eb
reviewed_base: e5e158451a0e731dbe6012ee0bf3e6e179b2ee25
previous_head: 34734550a17a3c0f4c2f80063da0c957622b03b6
previous_review: .planning/phases/86-pilot-reference-record/86-REVIEW-release-34734550a17a.md
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
  info: 1
  total: 2
status: issues_found
---

# Phase 86 (release v2.12.1): Code Review Report, review after fixes (final round)

**Reviewed:** 2026-11-14T21:17:34Z
**Head:** `9edabeb90dc5ed51ebb784dcd38bc520818f25eb` (branch `release-v2.12.1`)
**Base:** `e5e158451a0e731dbe6012ee0bf3e6e179b2ee25` (merge-base with `origin/main`)
**Previous head reviewed:** `34734550a17a3c0f4c2f80063da0c957622b03b6`
**Depth:** standard (requested standard, actual standard)
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Scope was the code-class diff of the release PR: `CHANGELOG.md`, `pyproject.toml`,
`triggarr/__init__.py`, `uv.lock`. Since the previous head only `CHANGELOG.md` changed
in scope (three lines of the `## v2.12.1` entry). Every sentence of the current entry
was re-checked against the code on this head relative to tag `v2.12.0`, against
`uv.lock`, and against the image facts supplied with the review request (taken as
given; no Docker command was run).

The previous warning is fixed. The `opentelemetry-api` fix is now under Security with
the correct statement about the v2.12.0 image, the false "did not include" clause is
gone, the intro is plural, and the dependency line now lists only packages that
actually changed in the image, with correct before and after versions (APScheduler was
rightly dropped: the v2.12.0 image already had 3.11.3).

One new warning follows from the same correction. The entry now compares against the
published v2.12.0 image rather than the v2.12.0 lockfile, and against that baseline
the dependency line is incomplete in the other direction: because v2.12.0 was built
from unpinned dependencies and v2.12.1 is built from the lockfile, about twenty
libraries in the v2.12.1 image are very likely **older** than in the v2.12.0 image
(the web server uvicorn by thirteen minor versions, pydantic by two). The entry lists
three upgrades and no rollbacks (WR-01). This is inferred from the public package
index, not from the image, and is confirmable with the same one-line image inspection
already used for this revision.

Version identity and the lockfile are unchanged from the previous head and sound.

Checks run on this head (working tree stayed clean, head unchanged before and after):

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `9edabeb90dc5ed51ebb784dcd38bc520818f25eb` |
| `git status --short` | empty before and after |
| `uv run pytest tests/ -x -q` | 3282 passed, 1 skipped, exit 0 |
| `uv run pytest tests/test_changelog.py tests/test_version.py -q` | 22 passed |
| `uv run ruff check triggarr/ tests/` | All checks passed |
| `uv lock --check` (uv 0.12.17, the Dockerfile's pinned version) | exit 0, 56 packages |
| `uv.lock` header | `version = 1`, `revision = 5` |
| Version identity | `2.12.1` in `pyproject.toml:7`, `triggarr/__init__.py:1` and the `triggarr` package in `uv.lock` |
| `parse_changelog(..., latest_only=True)` | v2.12.1 renders 5 categories and 9 bullets from 9 source bullets (Security 2, Fixes 2, Improvements 2, Upgrade notes 1, Internal 2); quotes escaped as `&quot;`; over the full file `ul` 45/45, `li` 127/127, `h3` 24/24, `h4` 45/45, `div` 24/24 balanced; no non-ASCII and no trailing whitespace in the entry |

Backticks render literally in the in-app view, as they do in earlier entries; not a
regression.

Convention rule packs: not applicable. The changed files are Markdown, TOML, a lockfile
and a one-line Python file; no pack covers them, so nothing was emitted.

## Original vs. refreshed findings

| Prior ID | Prior finding (head `34734550a17a`) | Status on `9edabeb90dc5` | Evidence |
| --- | --- | --- | --- |
| WR-01 | Entry said v2.12.0 "did not include" `opentelemetry-api`, filed the CVE fix under Improvements, intro said "A security update" (singular) | **Fixed** | `CHANGELOG.md:9` is a Security bullet: "updated to 1.45.2 (CVE-2026-126360). The v2.12.0 image contained 1.45.1, installed as a dependency of FastAPI." `uv.lock` locks 1.45.2 with FastAPI as the only dependant and no marker, so `uv export --no-dev` includes it. Image facts: v2.12.0 had 1.45.1, the local build has 1.45.2. Public index: advisory GHSA-mf5v-w3w3-f6cg / CVE-2026-126360 is listed against 1.45.1 with `fixed_in` 1.45.2. `CHANGELOG.md:5` now reads "Security updates for the Docker image and its dependencies". The phrase "did not include" no longer appears. |
| IN-01 | The `v2.12.1` tag must sit on the `main` commit that push CI ran on | **Still applies** (release mechanics, not a defect in the diff) | Carried forward as current IN-01. `.github/` is unchanged since the previous head. |

## Sentence-by-sentence verification of the current entry

| Line | Claim | Result |
| --- | --- | --- |
| 5 | "Security updates for the Docker image and its dependencies, plus two small fixes to Refresh counts and the dashboard cards." | Holds. Two security items (one OS package, one Python dependency), two fixes. |
| 9 | `opentelemetry-api` updated to 1.45.2 (CVE-2026-126360); v2.12.0 image contained 1.45.1 as a FastAPI dependency | Holds. See WR-01 row above. FastAPI 0.158.1 (the version in the v2.12.0 image) declares the dependency; Triggarr itself never did (`git show v2.12.0:pyproject.toml`). |
| 11 | Image upgrades `zlib1g` (two CVE ids); build fails if the fixed version is absent | Holds. `Dockerfile:45-55`: `--only-upgrade zlib1g`, then `dpkg --compare-versions ... ge "1:1.3.dfsg+really1.3.1-1+deb13u1"` in the same `RUN`. Image facts: v2.12.0 had `-1+b1` (below the floor), the local build has `-1+deb13u1`. |
| 15 | Refresh counts no longer disconnects on one malformed record; skipped and logged; stays connected | Holds. Unchanged since the previous head, where it was verified against `triggarr/search/engine.py` (`refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts`); `tests/test_refresh_counts.py` passes. |
| 17 | Card label on a card with no failed searches; a Failed card always says "failure reason(s)" | Holds. `triggarr/templates/partials/cycle_grade.html:29-37`: both non-failure labels require `failed == 0`, no fetch failure, no other-kind row and `grade != 'failed'`; every other card, including every Failed card, gets "failure reason(s)". Template strings match the quoted labels. |
| 21 | Image installs from the lockfile with hash checking, so it runs the versions that were tested | Holds. `Dockerfile:25-34` (`uv export --locked --no-dev`), `60-62` (`pip install --require-hashes --no-deps`), `67` (`pip install --no-deps .`). |
| 23 | "Dependency updates in the image: FastAPI 0.162.4 (v2.12.0 shipped 0.158.1), Starlette 1.10.0 (was 1.9.0), python-multipart 0.0.33 (was 0.0.32)." | Every number is correct: `uv.lock` has fastapi 0.162.4, starlette 1.10.0, python-multipart 0.0.33; the "was" values match the image facts. APScheduler is correctly absent (3.11.3 in both). **Incomplete as a description of what changed in the image**: see WR-01. |
| 27 | Wheel and sdist no longer attached | Holds. Unchanged; `README.md` install section says the same. |
| 31 | Pipeline starts the exact image, runs browser tests on it, rejects a mismatched tag | Holds. Unchanged since the previous head (`.github/` untouched). |
| 33 | OS scanning, workflow linting, grouped dependency updates; `:main`/`:dev` without write permission | Holds. Unchanged since the previous head; `SECURITY.md` gained the matching Build Pipeline note. |

Application changes since `v2.12.0` under `triggarr/` are `search/engine.py` (Refresh
counts), `search/outcome.py` and `templates/partials/cycle_grade.html` (card label) and
the version string. All are covered by the entry. The only user-visible change the
entry does not cover is the one in WR-01.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: The entry lists three dependency upgrades "in the image" but not that about twenty other libraries very likely go backwards from the v2.12.0 image

**File:** `CHANGELOG.md:23` (also `CHANGELOG.md:21`)

**Issue:** The revision changed the baseline of the dependency line from the v2.12.0
lockfile to the published v2.12.0 image ("in the image", "v2.12.0 shipped 0.158.1").
That is the right baseline, but it cuts both ways. The v2.12.0 image was built with an
unpinned `pip install .`, so every dependency resolved to the newest release on the
build day (2026-10-21). The v2.12.1 image is built from `uv.lock`, in which most
runtime packages have not moved since they were first locked, some of them a year
ago. So relative to the image people are running today, v2.12.1 raises three packages
(plus `opentelemetry-api`) and lowers roughly twenty, including the web server and the
validation library. The entry mentions only the raises. A reader takes "Dependency
updates in the image" as the list of what changed.

This was already true at the earlier heads; it was not visible while the entry
compared lockfile to lockfile, and the previous review checked completeness only
"against the v2.12.0 lockfile".

**Failure scenario:** A user compares the two images (or a scanner diffs them) and
finds uvicorn at 0.41.0 where v2.12.0 had 0.54.0, pydantic at 2.12.5 where it had
2.14.1, and so on, in a release whose notes describe security and dependency
*updates*. The notes then look wrong or careless at exactly the point where they are
trying to be precise. A second, smaller risk: any upstream fix made between the locked
version and the version v2.12.0 happened to ship is silently withdrawn from users.
No known vulnerability is reintroduced (see evidence), and the locked set is the one
the test suite and the image smoke and browser tests actually run on, so this is a
disclosure gap rather than a known functional or security defect.

**Evidence:**

- `git show v2.12.0:Dockerfile` installs with `pip install --no-cache-dir .` and copies
  no lockfile; `Dockerfile:60-67` on this head installs only the locked set.
- Public package index, queried during this review (package names only): for each
  runtime package, the newest non-prerelease, non-yanked version uploaded before
  2026-10-21T18:30Z. This method reproduces all five supplied image facts exactly
  (fastapi 0.158.1, starlette 1.9.0, opentelemetry-api 1.45.1, python-multipart 0.0.32,
  apscheduler 3.11.3), which is why the rest of the table is treated as a strong
  inference rather than a guess.

  | Package | Newest on the v2.12.0 build day (inferred image content) | `uv.lock` on this head (v2.12.1 image) |
  | --- | --- | --- |
  | uvicorn | 0.54.0 | 0.41.0 |
  | pydantic | 2.14.1 | 2.12.5 |
  | pydantic-core | 2.50.1 | 2.41.5 |
  | pydantic-settings | 2.16.1 | 2.14.2 |
  | anyio | 4.15.1 | 4.14.2 |
  | click | 8.5.0 | 8.3.1 |
  | websockets | 17.3 | 16.0 |
  | httptools | 0.9.0 | 0.7.1 |
  | uvloop | 0.23.0 | 0.22.1 |
  | watchfiles | 1.3.0 | 1.1.1 |
  | idna | 3.20 | 3.15 |
  | tzlocal | 5.4.4 | 5.3.1 |
  | python-dotenv | 1.2.4 | 1.2.2 |
  | markupsafe | 3.0.4 | 3.0.3 |
  | typing-inspection | 0.4.4 | 0.4.2 |
  | annotated-types | 0.8.0 | 0.7.0 |
  | annotated-doc | 0.0.5 | 0.0.4 |

  Unchanged by the same method: aiofiles, aiosqlite, apscheduler, bcrypt, certifi, h11,
  httpcore, httpx, itsdangerous, jinja2, loguru, pyyaml, tomli-w, tomlkit.
- The exact versions pip chose on the build day can differ from "newest by upload
  date" where a dependant caps a version (for example pydantic-core is pinned by
  pydantic), so individual rows may be off; the direction and scale are not in doubt
  for the packages locked many months before the build day (uvicorn locked version
  uploaded 2026-02-16, pydantic 2025-11-26, click 2025-11-15).
- Same index, advisory data for every locked runtime version on this head: zero
  advisories listed. So the rollback reintroduces no publicly known vulnerability as
  of this review.

**Fix:** This is a wording fix plus one owner decision; no code change is required to
ship.

1. Confirm with the image inspection already used for this revision, extended to a few
   names (`uvicorn`, `pydantic`, `anyio`, `click`, `websockets`).
2. If confirmed, say so in the entry. Suggested replacement for the two Improvements
   bullets (adjust numbers to what the inspection shows):

```markdown
  * The Docker image installs its Python dependencies from the project lockfile with hash checking, so the published image runs the same versions that were tested. The v2.12.0 image was built from unpinned dependencies, so some libraries in this image are older than the ones v2.12.0 happened to ship (for example uvicorn 0.41.0, was 0.54.0, and pydantic 2.12.5, was 2.14.1).

  * Newer in the image: FastAPI 0.162.4 (v2.12.0 shipped 0.158.1), Starlette 1.10.0 (was 1.9.0), python-multipart 0.0.33 (was 0.0.32).
```

3. Owner decision (product, not wording): accept shipping the older, tested set in this
   patch release, or refresh the lockfile so the image does not go backwards. Refreshing
   moves about twenty packages at once and needs the full CI and image tests again, which
   is a larger change than a patch release normally carries; accepting and disclosing is
   the lower-risk path, with a lockfile refresh as a follow-up.

## Info

### IN-01: The `v2.12.1` tag must go on the `main` commit that push CI ran on (carried forward)

**File:** `.github/scripts/release-policy.cjs` (`validateEvidence`), `.github/workflows/release.yml:31-43`

**Issue:** Unchanged from the two previous reviews and not a defect in this diff. The
release preflight requires a successful push CI run on `main` whose `head_sha` equals
the tagged commit. After a merge commit that is the merge commit, not `d06fab3`
(subject "release: v2.12.1"), not `3473455` and not this head.

**Fix:** After the merge, wait for push CI on `main` to succeed and tag the `main` head.

## Set aside (needs ruling)

### SA-01: Standalone `pip install git+...` users are not covered by the image statements (carried forward)

**Where:** `pyproject.toml:15-22`, `README.md` install section, `CHANGELOG.md:9`, `CHANGELOG.md:21-23`
**Why excluded:** The release diff does not change dependency floors, and the entry
scopes the lockfile and version statements to the Docker image. The Security bullet at
line 9 is the one statement not explicitly scoped to the image.
**Effect if left as is:** A source install resolves from the loose constraints, so an
existing environment upgraded in place can keep `opentelemetry-api` 1.45.1.
**Needs:** ruling from the developer: in scope (raise the floor or say "in the Docker image") / defer / accept.

### SA-02: FastAPI 0.162 turns on its native telemetry instrumentation by default (carried forward)

**Where:** `triggarr/__main__.py` (`FastAPI(lifespan=...)`), SA-12 in `.planning/backlog/MAINTENANCE.md`
**Why excluded:** Introduced by an earlier roll-up and already recorded as an owner
call; with only `opentelemetry-api` installed the providers are no-ops.
**Effect if left as is:** None in the shipped image. If an OpenTelemetry SDK were ever
added to the image, request telemetry would flow wherever the environment points.
**Needs:** ruling from the developer: accept, or disable auto-configuration explicitly.

## Not verified

- **Image contents, both images.** No Docker command was run. The v2.12.0 and local
  build facts (triggarr, fastapi, starlette, opentelemetry-api, python-multipart,
  apscheduler, zlib1g) were taken as given from the review request. The other package
  versions in the v2.12.0 image (WR-01) are inferred from public index upload dates,
  not read from the image.
- **CVE identifiers.** CVE-2026-126360 was matched against the public index's advisory
  data. CVE-2026-76844 and CVE-2026-85091 (`zlib1g`) were matched against the
  Dockerfile comment only. Whether CVE-2026-126360 is reachable through Triggarr's use
  of FastAPI was not assessed; the entry does not claim either way. The repository's
  Dependabot alerts were not queried.
- **Docker build on this head.** The `zlib1g` version check and the `--require-hashes`
  install were read, not executed.
- **Browser tests and GitHub-side release steps.** `tests/e2e` runs only in CI against
  the audited image. No workflow was executed.
- **Node workflow-script tests.** Not re-run; `.github/` is unchanged since the head
  where they last passed.

---

_Reviewed: 2026-11-14T21:17:34Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
