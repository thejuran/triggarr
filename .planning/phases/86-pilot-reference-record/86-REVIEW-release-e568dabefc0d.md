---
phase: 86-pilot-reference-record
review_kind: review after fixes of a non-phase change (v2.12.1 release PR, not yet pushed), owner-approved extra round
reviewed: 2026-11-14T21:29:02Z
reviewed_head: e568dabefc0de2fd8756c8965f8af473875bb482
reviewed_base: e5e158451a0e731dbe6012ee0bf3e6e179b2ee25
previous_head: 9edabeb90dc5ed51ebb784dcd38bc520818f25eb
previous_review: .planning/phases/86-pilot-reference-record/86-REVIEW-release-9edabeb90dc5.md
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
  warning: 0
  info: 3
  total: 3
status: issues_found
---

# Phase 86 (release v2.12.1): Code Review Report, review after fixes (extra round)

**Reviewed:** 2026-11-14T21:29:02Z
**Head:** `e568dabefc0de2fd8756c8965f8af473875bb482` (branch `release-v2.12.1`)
**Base:** `e5e158451a0e731dbe6012ee0bf3e6e179b2ee25` (merge-base with `origin/main`)
**Previous head reviewed:** `9edabeb90dc5ed51ebb784dcd38bc520818f25eb`
**Depth:** standard (requested standard, actual standard)
**Files Reviewed:** 4
**Status:** issues_found (info only; no critical, no warning)

## Summary

Scope was the code-class diff of the release PR: `CHANGELOG.md`, `pyproject.toml`,
`triggarr/__init__.py`, `uv.lock`. Since the previous head, `uv.lock` was refreshed and
one sentence was added to `CHANGELOG.md:23`.

The previous warning is fixed. The lockfile now pins the 18 libraries at the versions
the request says were read from the published v2.12.0 image, so installing from the
lockfile no longer moves anything backwards. Parsing both versions of the lock shows
the change is exactly those 18 version moves plus the removal of `tomli`, and nothing
else. Nothing moved backwards relative to `origin/main`'s lock. The lock is valid, every
changed package carries hashes, the Dockerfile's export step produces a complete
runtime set, and the full test suite passes on both Python 3.11 and Python 3.13 (the
image's and CI's version) with no new deprecation warnings.

No defect was found in the diff. Three info items remain: one wording imprecision in
the new changelog sentence, one documentation line outside the diff that the lock
refresh made stale, and the carried-forward release-mechanics note.

Checks run on this head (working tree clean and head unchanged before and after):

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `e568dabefc0de2fd8756c8965f8af473875bb482` |
| `git status --short` | empty before and after |
| `uv lock --check` (uv 0.12.17, the Dockerfile's pinned version) | exit 0, 55 packages, no warnings |
| `uv.lock` header | `version = 1`, `revision = 5`, `requires-python = ">=3.11"`, resolution markers unchanged |
| `uv export --locked --no-dev --no-emit-project` (the Dockerfile's command) | exit 0, 39 entries, all hash-pinned; no `tomli` |
| `uv run pytest tests/ -x -q -W default` on Python 3.11.14 | 3282 passed, 1 skipped, exit 0 |
| Same suite on Python 3.13.12, separate throwaway environment built from the lock | 3282 passed, 1 skipped, exit 0 |
| `uv run ruff check triggarr/ tests/` | All checks passed |
| `node --test .github/scripts/*.test.cjs` | 613 passed, 0 failed |
| `pip-audit --strict --no-deps --disable-pip` (2.10.1) on the exported runtime set | No known vulnerabilities found |
| `.github/scripts/image_lock_consistency.py` `compare()` on the exported set against a simulated Linux / Python 3.13 image holding exactly the locked versions plus pip | no mismatches |
| `parse_changelog(..., latest_only=True)` | v2.12.1 renders 5 categories, 9 bullets; tags balanced (`ul` 5/5, `li` 9/9, `h3` 1/1, `h4` 5/5, `div` 1/1); the new sentence renders inside the dependency bullet; no non-ASCII, no trailing whitespace |
| Version identity | `2.12.1` in `pyproject.toml:7`, `triggarr/__init__.py:1` and the `triggarr` package in `uv.lock` |

Convention rule packs: not applicable. The changed files are Markdown, TOML, a lockfile
and a one-line Python file; no pack covers them, so nothing was emitted.

## Original vs. refreshed findings

| Prior ID | Prior finding (head `9edabeb90dc5`) | Status on `e568dabefc0d` | Evidence |
| --- | --- | --- | --- |
| WR-01 | The entry listed three dependency upgrades "in the image" but about twenty other libraries would go backwards from the published v2.12.0 image, because v2.12.0 was built unpinned and v2.12.1 installs from the lockfile | **Fixed** (by the lockfile refresh the owner chose, plus one sentence) | `uv.lock` now pins all 18 at the versions supplied as read from the v2.12.0 image: annotated-doc 0.0.5, annotated-types 0.8.0, anyio 4.15.1, click 8.5.0, httptools 0.9.0, idna 3.20, markupsafe 3.0.4, pydantic 2.14.1, pydantic-core 2.50.1, pydantic-settings 2.16.1, python-dotenv 1.2.4, typing-extensions 4.16.0, typing-inspection 0.4.4, tzlocal 5.4.4, uvicorn 0.54.0, uvloop 0.23.0, watchfiles 1.3.0, websockets 17.3. These match the 17 rows the previous review inferred from the public index, plus typing-extensions. The runtime export contains exactly these versions. With the supplied image fact (the rebuilt image differs from v2.12.0 only in fastapi, starlette, python-multipart, opentelemetry-api, pip and triggarr), nothing goes backwards. `CHANGELOG.md:23` now ends "Every other library in the image stays at the version v2.12.0 shipped." See current IN-01 for a small wording gap in that sentence. |
| IN-01 | The `v2.12.1` tag must sit on the `main` commit that push CI ran on | **Still applies** (release mechanics, not a defect in the diff) | Carried forward as current IN-03. `.github/` is unchanged since the previous head. |

## What was checked

### 1. Lockfile integrity

- **Exact change set since `9edabeb90dc5`.** Both versions of `uv.lock` were parsed and
  compared package by package (version, source, sdist, wheels, dependencies). Changed:
  the 18 packages above, each a forward version move. Removed: `tomli` 2.4.0. The
  `triggarr` entry changed only in that its `pydantic-settings` dependency no longer
  records the `toml` extra (explained below). No other package differs in any field.
  Dependency-edge changes inside the 18 are upstream metadata changes: `click` 8.5.0
  and `uvicorn[standard]` 0.54.0 no longer require `colorama` on Windows,
  `pydantic-settings` 2.16.1 now requires `typing-extensions`, and `anyio` 4.15.1
  widens its `typing-extensions` marker. None affects the Linux image.
- **Hashes and sources.** Every registry package in the lock has `sha256` hashes on its
  sdist and on every wheel, all from the public index's file host; the only non-registry
  entry is the project itself. The 18 changed packages each have an sdist and 1 to 153
  wheels.
- **Nothing backwards relative to `origin/main`.** Every version difference from
  `origin/main`'s lock is a forward move (compared with PEP 440 ordering). Besides the
  18: fastapi 0.162.0 to 0.162.4, python-multipart 0.0.32 to 0.0.33, and dev-only
  playwright, pytest, ruff (forward) with `pyee` and `tomli` removed.
- **Lower bounds.** `uv lock --check` passes against `pyproject.toml`; the bounded
  packages are fastapi 0.162.4 (>=0.136.3), starlette 1.10.0 (>=1.3.1), python-multipart
  0.0.33 (>=0.0.31), apscheduler 3.11.3 (>=3.11,<4), tomlkit 0.15.2 (>=0.15.2).
- **Dockerfile export and install (`Dockerfile:25-34`, `60-62`).** The exact export
  command runs clean with the pinned uv and yields 39 hash-pinned entries. Entries with
  markers that are false on Linux (`colorama`, `tzdata`, `win32-setctime`) are skipped by
  pip. Binary packages in the set (bcrypt, httptools, markupsafe, pydantic-core, pyyaml,
  uvloop, watchfiles) all have manylinux wheels for CPython 3.13 on x86_64 and aarch64,
  so `pip install --require-hashes --no-deps` needs no compiler; websockets has a
  pure-Python wheel as fallback.
- **Why `tomli` disappeared, and whether anything needs it.** In the previous lock the
  only package depending on `tomli` was `pydantic-settings` 2.14.2 through its `toml`
  extra. `pydantic-settings` 2.16.1 still declares the `toml` extra but the extra is
  empty (read from the installed package metadata), so the resolver has nothing to
  pull in. `pyproject.toml:10` (`pydantic-settings[toml]`) is therefore still valid and
  produces no warning; it is now a no-op. Nothing imports `tomli`: the application and
  tests use the standard-library `tomllib` (`triggarr/config.py:11` and six test
  modules), which exists on every supported Python (`requires-python >=3.11`). The
  Docker build stages run Python 3.13 and install only `pytailwindcss` and `uv`. The
  dev export contains no `tomli` requirement either. Both full test runs passed without
  it installed.

### 2. Compatibility of the 18 moves

- **pydantic 2.14.1 / pydantic-core 2.50.1 / pydantic-settings 2.16.1.** Used in
  `triggarr/models/config.py` (`BaseSettings`, `TomlConfigSettingsSource`,
  `settings_customise_sources`, `SecretStr`, validators), `triggarr/models/arr.py`,
  the clients and `triggarr/web/routes.py`. The config, TOML round-trip, SecretStr and
  auth tests all pass on both Python versions. With warnings shown (`-W default`) the
  run reports no pydantic or pydantic-settings deprecation warning.
- **uvicorn 0.54.0.** `triggarr/__main__.py:75-83` builds
  `uvicorn.Config(app, host, port, log_level, root_path, proxy_headers, forwarded_allow_ips)`.
  Constructing and loading that exact configuration on Python 3.13 with warnings turned
  into errors succeeds: all seven arguments are still accepted and none is deprecated.
  It selects the httptools HTTP implementation and the websockets implementation from
  the locked versions without error. `entrypoint.sh` passes no uvicorn flags (it runs
  `python -m triggarr`).
- **anyio, httptools, websockets, uvloop, watchfiles, click, tzlocal, idna, markupsafe,
  python-dotenv, typing helpers.** None is imported directly by `triggarr/` or `tests/`;
  they are reached only through uvicorn, httpx, starlette, pydantic, APScheduler and
  Jinja2, which the suite exercises.
- **Warnings in the test run.** 34 warnings, all from Starlette's test client (httpx
  deprecation notice and per-request cookies). Starlette and httpx did not change on
  this head, so these are not caused by the refresh.
- **Field evidence (supplied).** Production has run these 18 versions with v2.12.0 code
  since 2026-10-21, and the application changes since then are confined to
  `triggarr/search/engine.py`, `triggarr/search/outcome.py` and
  `triggarr/templates/partials/cycle_grade.html`, none of which touches these libraries
  directly. `git diff v2.12.0..HEAD --stat -- triggarr/` was not re-run in this round;
  the previous review verified the same file list.

### 3. Dev and CI tooling

- No test pins any of the 18 versions. `tests/test_image_lock_consistency.py:87-94`
  uses `anyio==4.11.0` only as parser fixture text. `tests/test_version.py` reads the
  lock for the project version only. CI installs with `uv sync --locked` and exports
  with `uv export --locked`, so it follows the lock.
- One documentation line outside the diff names the old `idna` pin: see IN-02.

### 4. Changelog entry

Every sentence verified in the previous round is unchanged and still holds. The
dependency line's three "was" values match the supplied image facts and its three new
values match the lock. The new sentence is true for the 18 libraries and the unchanged
ones; see IN-01 for the two libraries it does not strictly cover. `CHANGELOG.md:21`
("the published image runs the same versions that were tested") holds: CI tests run
from the same lock, and the suite passed here on that lock.

## Narrative Findings (AI reviewer)

## Info

### IN-01: "Every other library in the image stays at the version v2.12.0 shipped" does not strictly cover `opentelemetry-api` and `pip`

**File:** `CHANGELOG.md:23` (with `CHANGELOG.md:9`)

**Issue:** The bullet lists three libraries (FastAPI, Starlette, python-multipart) and
then says every other library stays at the v2.12.0 version. By the supplied image
facts, two more Python packages differ: `opentelemetry-api` 1.45.1 to 1.45.2 and `pip`
26.2.1 to 26.2.2 (pip comes with the base image, not from the lockfile). The
`opentelemetry-api` change is disclosed fourteen lines earlier as a Security item, so
nothing is hidden; read on its own, though, the sentence is not literally true.

**Failure scenario:** A reader who diffs the package lists of the two images finds five
changed libraries where the bullet's wording implies three. No one is misled about
risk: the extra two are both upgrades and one is the headline security fix.

**Evidence:** Supplied image facts; `uv.lock` has opentelemetry-api 1.45.2.

**Fix:** Optional wording change, for example:

```markdown
  * Dependency updates in the image: FastAPI 0.162.4 (v2.12.0 shipped 0.158.1), Starlette 1.10.0 (was 1.9.0), python-multipart 0.0.33 (was 0.0.32). Apart from these and the `opentelemetry-api` security update above, every library Triggarr installs stays at the version v2.12.0 shipped.
```

"Every library Triggarr installs" also excludes the base image's own `pip` without
having to name it.

### IN-02: The lockfile-mismatch demonstration recipe still names `idna` 3.15 as the locked version

**File:** `docs/ci-negative-demonstrations.md:267`, `docs/ci-negative-demonstrations.md:276`
(outside the reviewed diff; made stale by the `uv.lock` change on this head)

**Issue:** Recipe 4 says the lockfile pins `idna` `3.15` and gives the expected failure
text `version mismatch: idna lock 3.15 image 3.4`. The lock now pins `idna` 3.20.

**Failure scenario:** The demonstration still works, since 3.4 differs from 3.20 and the
`docker` job fails at the same step. But the next person who repeats it gets
`version mismatch: idna lock 3.20 image 3.4`, which does not match the documented
expected text, and has to work out whether the gate failed for the documented reason.
No test checks this line (the full suite, including `tests/test_docs_accuracy.py`,
passes).

**Evidence:** `uv.lock` `idna` entry is 3.20; the two doc lines quoted above.

**Fix:** Update both lines to 3.20, or make the recipe independent of the pin ("the
lockfile's pinned version, shown in the failure text"). The parenthetical about the
version pair proved locally in Plan 85-08 is history and should keep saying 3.15. This
can ride in the release PR or the next substantive push; it does not need its own PR.

### IN-03: The `v2.12.1` tag must go on the `main` commit that push CI ran on (carried forward)

**File:** `.github/scripts/release-policy.cjs` (`validateEvidence`), `.github/workflows/release.yml:31-43`

**Issue:** Unchanged from the previous reviews and not a defect in this diff. The
release preflight requires a successful push CI run on `main` whose `head_sha` equals
the tagged commit. After a merge commit that is the merge commit, not this head or any
earlier commit on the release branch.

**Fix:** After the merge, wait for push CI on `main` to succeed and tag the `main` head.

## Set aside (needs ruling)

### SA-01: Standalone `pip install git+...` users are not covered by the image statements (carried forward)

**Where:** `pyproject.toml:10-24`, `README.md` install section, `CHANGELOG.md:9`, `CHANGELOG.md:21-23`
**Why excluded:** The release diff does not change dependency floors, and the entry
scopes the lockfile and version statements to the Docker image.
**Effect if left as is:** A source install resolves from the loose constraints, so an
existing environment upgraded in place can keep `opentelemetry-api` 1.45.1.
**Needs:** ruling from the developer: in scope (raise the floor or say "in the Docker image") / defer / accept.

### SA-02: FastAPI 0.162 turns on its native telemetry instrumentation by default (carried forward)

**Where:** `triggarr/__main__.py:68` (`FastAPI(lifespan=...)`), SA-12 in `.planning/backlog/MAINTENANCE.md`
**Why excluded:** Introduced by an earlier roll-up and already recorded as an owner
call; with only `opentelemetry-api` installed the providers are no-ops.
**Effect if left as is:** None in the shipped image.
**Needs:** ruling from the developer: accept, or disable auto-configuration explicitly.

### SA-03: `pydantic-settings[toml]` in `pyproject.toml` is now a no-op extra

**Where:** `pyproject.toml:10`
**Why excluded:** Not changed by this diff and harmless: the extra still exists
upstream, it is simply empty from 2.16 on, and the supported Python versions read TOML
with the standard library.
**Effect if left as is:** None. If upstream ever removes the extra, installers would
print a warning about an unknown extra.
**Needs:** ruling from the developer: accept / drop the `[toml]` suffix in a later change.

## Not verified

- **Image contents, both images.** No Docker command was run. That the 18 pinned
  versions are what the published v2.12.0 image contains, that the rebuilt image
  differs from it only in the six listed packages, and that it starts and serves pages
  were taken as given from the review request. Independent support: 17 of the 18 match
  the previous review's public-index inference, and the exported set equals the pinned
  list.
- **Docker build on this head.** The export command was run on the host with the
  Dockerfile's pinned uv; the `pip install --require-hashes --no-deps` step and the
  `zlib1g` check were read, not executed. Wheel availability for the image's Python and
  both common Linux architectures was checked from the lock.
- **Runtime behaviour under uvicorn 0.54 beyond configuration.** Proxy-header handling,
  lifespan and shutdown drain on SIGTERM were not exercised against a running server
  here; the configuration loads without warnings, and the supplied production history
  covers these versions with v2.12.0 code.
- **Browser tests and GitHub-side steps.** `tests/e2e` runs only in CI against the built
  image. No workflow was executed. The repository's Dependabot alerts were not queried;
  `pip-audit` on the locked runtime set was re-run here and is clean.
- **CVE identifiers.** Not re-checked in this round; unchanged since the previous review.

---

_Reviewed: 2026-11-14T21:29:02Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
