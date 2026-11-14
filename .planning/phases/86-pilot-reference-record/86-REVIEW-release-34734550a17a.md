---
phase: 86-pilot-reference-record
review_kind: review after fixes of a non-phase change (v2.12.1 release PR, not yet pushed)
reviewed: 2026-11-14T21:08:19Z
reviewed_head: 34734550a17a3c0f4c2f80063da0c957622b03b6
reviewed_base: e5e158451a0e731dbe6012ee0bf3e6e179b2ee25
previous_head: d06fab3521ca37d0325847e19cd419decf634e54
previous_review: .planning/phases/86-pilot-reference-record/86-REVIEW-release-d06fab3521ca.md
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

# Phase 86 (release v2.12.1): Code Review Report, review after fixes

**Reviewed:** 2026-11-14T21:08:19Z
**Head:** `34734550a17a3c0f4c2f80063da0c957622b03b6` (branch `release-v2.12.1`)
**Base:** `e5e158451a0e731dbe6012ee0bf3e6e179b2ee25` (merge-base with `origin/main`)
**Previous head reviewed:** `d06fab3521ca37d0325847e19cd419decf634e54`
**Depth:** standard (requested standard, actual standard)
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Scope was the code-class diff of the release PR: `CHANGELOG.md`, `pyproject.toml`,
`triggarr/__init__.py`, `uv.lock`. Since the previous head only `CHANGELOG.md` changed
in scope (14 lines, the `## v2.12.1` entry). Every sentence of the current entry was
re-checked against the code on this head relative to tag `v2.12.0`.

The rewording fixes the previous warning and three of the four information findings
cleanly. The fourth (IN-01, the `opentelemetry-api` wording) was replaced by a new
problem, and it is more serious than the one it replaced: the entry now states that
v2.12.0 did not include `opentelemetry-api`, and moves the CVE fix out of the Security
section. That is true of the v2.12.0 lockfile but almost certainly false of the
published v2.12.0 Docker image, which was not built from the lockfile (WR-01). The
previous review's own suggested wording led here; its caveat about the published image
was recorded under "Not verified" and has now been checked against the public package
index.

Version identity and the lockfile are unchanged from the previous head and sound.

Checks run on this head (working tree stayed clean, head unchanged):

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `34734550a17a3c0f4c2f80063da0c957622b03b6` |
| `uv run pytest tests/ -x -q` | 3282 passed, 1 skipped, exit 0 |
| `uv run pytest tests/test_changelog.py tests/test_version.py -q` | 22 passed |
| `uv run ruff check triggarr/ tests/` | All checks passed |
| `uv lock --check` (uv 0.12.17, the Dockerfile's pinned version) | exit 0, 56 packages |
| `parse_changelog` on `CHANGELOG.md` | v2.12.1 renders 5 categories, 8 bullets from 8 source bullets; tags balanced over 24 sections; no non-ASCII or trailing whitespace in the entry |

Convention rule packs: not applicable. The changed files are Markdown, TOML, a lockfile
and a one-line Python file; no pack covers them, so nothing was emitted.

## Original vs. refreshed findings

| Prior ID | Prior finding (head `d06fab3521ca`) | Status on `34734550a17a` | Evidence |
| --- | --- | --- | --- |
| WR-01 | `FASTAPI_OTEL_AUTO_CONFIGURE` upgrade note said the web UI fails at startup | **Fixed** (bullet removed) | The "Upgrade notes" section now has one bullet (`CHANGELOG.md:25`). No upgrade action exists, so removal is accurate. SA-12 in `.planning/backlog/MAINTENANCE.md:142` carries a dated correction. |
| IN-01 | `opentelemetry-api` described as "updated" though absent from the v2.12.0 lockfile | **Replaced by a new problem** (current WR-01) | New text at `CHANGELOG.md:21` asserts v2.12.0 "did not include" the package and files the CVE fix under Improvements. True for the lockfile, not for the published image. |
| IN-02 | "skipped and counted, the same way a scheduled cycle handles it" | **Fixed** | `CHANGELOG.md:13` now reads "skipped and logged, and the instance stays connected". Matches `_screen_queue` / `_log_malformed_skip` (`triggarr/search/engine.py:156-213`) and the throwaway `CycleTally` in the three `refresh_*_counts` helpers; `connected = True` is set after the fetch and the per-record skips no longer raise. |
| IN-03 | Dashboard-card bullet claimed grouping and an unconditional relabel | **Fixed** | `CHANGELOG.md:15` now scopes the claim to a card with no failed searches and quotes the labels. Matches `triggarr/templates/partials/cycle_grade.html:29-37` (see verification below). |
| IN-04 | "The published image is the tested image, not a rebuild" read as new | **Fixed** (sentence removed) | `CHANGELOG.md:29`. The remaining sentence lists only what is new since v2.12.0. |
| IN-05 | The `v2.12.1` tag must sit on the `main` commit that push CI ran on | **Still applies** (release mechanics, not a defect in the diff) | Carried forward as current IN-01. It now also follows that neither `d06fab3` nor `3473455` is the commit to tag. |

## Sentence-by-sentence verification of the current entry

| Line | Claim | Result |
| --- | --- | --- |
| 5 | "A security update for the Docker image, plus two small fixes..." | Accurate as a description of the entry as written; understates the release if WR-01 is accepted (two security fixes reach image users, not one). Not rendered in-app, same as every earlier entry. |
| 9 | Image upgrades `zlib1g` (two CVE ids); build fails if the fixed version is absent | Holds. `Dockerfile:45-55`: `--only-upgrade zlib1g` followed by `dpkg --compare-versions ... ge` in the same `RUN`. |
| 13 | Refresh counts no longer disconnects on one malformed record; skipped and logged; stays connected | Holds. `triggarr/search/engine.py` `refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts` fetch with `allow_non_object_records=True` and screen per item before every step that reads a field. The remaining `except (AttributeError, KeyError, TypeError)` is a backstop for other faults. |
| 15 | Card label on a card with no failed searches; Failed card always says "failure reason(s)" | Holds. Template strings are exactly `Show N detail(s)`, `Show N skipped record(s)` and `Show N failure reason(s)`. Both non-failure branches require `failed == 0`, no fetch failure, no other-kind row and `grade != 'failed'`; everything else, including every Failed card, falls to "failure reason(s)". `grade_cycle` (`triggarr/search/outcome.py:76-81`) grades a skipped-record cycle with at least one accepted search as Partial, so the "skipped record(s)" branch is reachable. |
| 19 | Image installs from the lockfile with hash checking | Holds. `Dockerfile:25-34` (`uv export --locked --no-dev`), `60-62` (`pip install --require-hashes --no-deps`), `67` (`--no-deps .`). CI also compares the image against `uv.lock` (`.github/workflows/ci.yml` docker job). |
| 21 | FastAPI 0.162.4, Starlette 1.10.0, APScheduler 3.11.3, python-multipart 0.0.33 | Versions match `uv.lock`. These four plus `opentelemetry-api` are the complete set of runtime version changes against the v2.12.0 lockfile. |
| 21 | "FastAPI now depends on `opentelemetry-api`, which v2.12.0 did not include; this release ships 1.45.2, which has the fix for CVE-2026-126360" | First half **not supported for the published image**, see WR-01. Second half holds: `uv.lock` locks 1.45.2, FastAPI is its only dependant, and the public index lists the advisory as fixed in 1.45.2. |
| 25 | Wheel and sdist no longer attached | Holds. `.github/workflows/release.yml` `github-release` job runs `gh release create` with no files; the v2.12.0 workflow uploaded `dist/*`. `README.md` already describes the source install. |
| 29 | Pipeline starts the exact image, runs browser tests on it, rejects a mismatched tag | Holds. `ci.yml` `image-smoke` and `browser-e2e` run on the saved `audited-image`; `release.yml` publishes that artifact and runs `releaseIdentityGate`. None of the three existed at v2.12.0. |
| 31 | OS scanning, workflow linting, grouped dependency updates; `:main`/`:dev` without write permission | Holds. `ci.yml` `os-scan` and `actionlint` jobs; `.github/dependabot.yml` is new with `groups`; in `release.yml` the publishing job has `contents: read` and only the tag-only `github-release` job has `contents: write`. |

Nothing user-visible since v2.12.0 is missing: the only application changes in
`triggarr/` are `search/engine.py` (Refresh counts), `search/outcome.py` and
`templates/partials/cycle_grade.html` (card label), and the version string.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: The entry says v2.12.0 did not include `opentelemetry-api`; the published v2.12.0 image almost certainly did, at the vulnerable version

**File:** `CHANGELOG.md:21` (also `CHANGELOG.md:5`, `CHANGELOG.md:7-9`)

**Issue:** The sentence "FastAPI now depends on `opentelemetry-api`, which v2.12.0 did
not include" is true only of the v2.12.0 lockfile. The v2.12.0 Docker image was not
built from the lockfile. Its Dockerfile ran `pip install --no-cache-dir .`, which
resolved `fastapi>=0.136.3` to whatever was newest on the build day. On that day the
newest FastAPI already required `opentelemetry-api`, and the newest
`opentelemetry-api` was 1.45.1, the version affected by CVE-2026-126360. So for people
running the v2.12.0 image, v2.12.1 most likely fixes a known vulnerability, and the
entry tells them the opposite: the fix sits under "Improvements", the Security section
lists only `zlib1g`, and the intro says "A security update" in the singular.

**Failure scenario:** A user on the v2.12.0 image reads the in-app changelog to decide
how soon to upgrade. They see one OS-package fix under Security and a statement that
v2.12.0 never had the affected library, and treat the upgrade as low priority. A user
or scanner who inspects the v2.12.0 image and finds `opentelemetry-api` 1.45.1 sees a
release note that contradicts the image.

**Evidence:**

- `git show v2.12.0:Dockerfile` line 32: `RUN pip install --no-cache-dir .`. No lockfile
  is copied into that image; the lockfile install was added after the tag (`Dockerfile`
  diff `v2.12.0..HEAD`).
- `git show v2.12.0:pyproject.toml`: `fastapi>=0.136.3`, no upper bound, no
  `opentelemetry-api` constraint.
- The v2.12.0 version bump is commit `18a6dce` (2026-10-21T18:00Z) and the tag is on
  the merge `dbb38fa` (2026-10-21T18:18:59Z). `COPY pyproject.toml .` precedes the
  install, so the version bump invalidated any cached dependency layer; the install
  resolved on or about 2026-10-21.
- Public package index, queried during this review: FastAPI 0.137.0 and 0.140.0 do not
  require `opentelemetry-api`; 0.143.0, 0.145.0, 0.146.0, 0.147.0 (uploaded
  2026-10-19), 0.155.0, 0.156.8, 0.157.0, 0.158.0, 0.158.1 (uploaded
  2026-10-21T17:47Z), 0.158.2 and 0.159.x all declare `opentelemetry-api>=1.44.0` as a
  core requirement. The newest release at the time of the merge was 0.158.1.
- Same index: `opentelemetry-api` 1.45.1 was uploaded 2026-10-06 and 1.45.2 on
  2026-10-29, so 1.45.1 was the newest on the build day. The index lists
  GHSA-mf5v-w3w3-f6cg / CVE-2026-126360 against 1.45.1 with `fixed_in: 1.45.2`.
- The v2.12.0 CI audited the image's `pip freeze` with `pip-audit`, but the advisory was
  not published until November (`.planning/STATE.md:92` records it first failing CI on
  2026-11-13), so that audit could not have flagged it.
- The image itself was not pulled or inspected (see "Not verified"). The conclusion
  rests on the build recipe, the tag time and the index's upload times, which leave no
  resolution path that omits the package.

**Fix:** Confirm with one read-only command against the published v2.12.0 image
(`docker run --rm --entrypoint python <published v2.12.0 image> -m pip show opentelemetry-api`),
then word the entry to match. If it shows 1.45.1 (expected):

```markdown
A security update for the Docker image and one of its Python dependencies, plus two small fixes to Refresh counts and the dashboard cards.

* Security:

  * `opentelemetry-api` 1.45.2 (CVE-2026-126360). FastAPI installs it as a dependency. The v2.12.0 image was built from unpinned dependencies and shipped the affected 1.45.1.

  * The Docker image upgrades `zlib1g` (CVE-2026-76844, CVE-2026-85091). The image build fails if the fixed version is not installed.
```

and reduce the Improvements bullet to the four version numbers. If the owner prefers
not to inspect the image, drop the clause "which v2.12.0 did not include" and move the
CVE sentence to Security without a claim about v2.12.0 either way. Whether the CVE is
reachable through Triggarr's use of FastAPI was not assessed; the entry should not
claim it is or is not.

## Info

### IN-01: The `v2.12.1` tag must go on the `main` commit that push CI ran on (carried forward from prior IN-05)

**File:** `.github/scripts/release-policy.cjs` (`validateEvidence`), `.github/workflows/release.yml:31-43`

**Issue:** Unchanged from the previous review and not a defect in this diff. The release
preflight requires a successful push CI run on `main` whose `head_sha` equals the tagged
commit. After a merge commit, that is the merge commit, not `d06fab3` (whose subject is
"release: v2.12.1") and not this head.

**Fix:** After the merge, wait for push CI on `main` to succeed and tag the `main` head.

## Set aside (needs ruling)

### SA-01: Standalone `pip install git+...` users are not covered by the lockfile claims (carried forward)

**Where:** `pyproject.toml:15-22`, `README.md` install section, `CHANGELOG.md:19-21`
**Why excluded:** The release diff does not change dependency floors, and the entry
scopes the hash-checked install to the Docker image.
**Effect if left as is:** A source install resolves from the loose constraints, so an
existing environment upgraded in place can keep `opentelemetry-api` 1.45.1. The
dependency and CVE statements are only guaranteed for the image.
**Needs:** ruling from the developer: in scope (raise floors or say "Docker image") / defer / accept.

### SA-02: FastAPI 0.162 turns on its native telemetry instrumentation by default (carried forward)

**Where:** `triggarr/__main__.py` (`FastAPI(lifespan=...)`), SA-12 in `.planning/backlog/MAINTENANCE.md:142`
**Why excluded:** Introduced by an earlier roll-up and already recorded as an owner
call; with only `opentelemetry-api` installed the providers are no-ops.
**Effect if left as is:** None in the shipped image. If an OpenTelemetry SDK were ever
added to the image, request telemetry would flow wherever the environment points.
**Needs:** ruling from the developer: accept, or disable auto-configuration explicitly.

## Not verified

- **Contents of the published v2.12.0 image.** Not pulled or inspected; no Docker
  commands were run. WR-01 is inferred from the v2.12.0 Dockerfile, the tag time and
  public index upload dates. The exact CI run time for the v2.12.0 image was not
  looked up.
- **CVE identifiers.** CVE-2026-126360 was matched against the public package index's
  advisory data for `opentelemetry-api` (affected 1.45.1, fixed 1.45.2). CVE-2026-76844
  and CVE-2026-85091 (`zlib1g`) were matched against the Dockerfile comment and planning
  records only. The repository's Dependabot alerts were not queried.
- **Docker build and image contents on this head.** Not run by instruction. The
  `zlib1g` version check and the `--require-hashes` install were read, not executed.
- **Browser tests and GitHub-side release steps.** `tests/e2e` runs only in CI against
  the audited image. Workflow files were read; no workflow was executed.
- **Node workflow-script tests.** Not re-run in this pass; `.github/` is unchanged since
  the previous head, where they passed.

---

_Reviewed: 2026-11-14T21:08:19Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
