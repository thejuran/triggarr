---
phase: 86-pilot-reference-record
review_kind: review of the pushed PR head of a non-phase change (v2.12.1 release PR #60); evidence-only commit on top of a reviewed head
reviewed: 2026-11-14T23:26:26Z
reviewed_head: e1f50adf28802631854c4432d9754e79145b7b6d
reviewed_base: e5e158451a0e731dbe6012ee0bf3e6e179b2ee25
previous_head: e568dabefc0de2fd8756c8965f8af473875bb482
previous_review: .planning/phases/86-pilot-reference-record/86-REVIEW-release-e568dabefc0d.md
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

# Phase 86 (release v2.12.1): Code Review Report, pushed PR head

**Reviewed:** 2026-11-14T23:26:26Z
**Head:** `e1f50adf28802631854c4432d9754e79145b7b6d` (branch `release-v2.12.1`; equals `origin/release-v2.12.1`)
**Base:** `e5e158451a0e731dbe6012ee0bf3e6e179b2ee25` (merge-base with `origin/main`)
**Previous head reviewed:** `e568dabefc0de2fd8756c8965f8af473875bb482`
**Depth:** standard (requested standard, actual standard)
**Files Reviewed:** 4
**Status:** issues_found (info only; no critical, no warning)

## Summary

The claim under test was that this head adds one commit on top of the previously
reviewed head and that the commit only adds review evidence under `.planning/`. That
claim holds. The four code-class files are the same git objects on both heads, so the
code under review is unchanged.

A fresh standard review of the four files found no defect. The three info items from
the previous head all still apply, unchanged; one of them is now recorded in the
maintenance backlog. No new finding was raised.

Nothing unpublishable was found in the newly added planning and evidence text.

## 1. Is the new commit evidence-only?

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `e1f50adf28802631854c4432d9754e79145b7b6d` |
| Commits in `e568dabefc0d..HEAD` | one: `e1f50adf` "docs(release): review record and evidence for v2.12.1 head e568dab" |
| Files outside `.planning/` in `e568dabefc0d..HEAD` | none |
| Files outside `.planning/` in `base..HEAD` | exactly `CHANGELOG.md`, `pyproject.toml`, `triggarr/__init__.py`, `uv.lock` |
| In-scope diff against base, previous head vs. this head | byte-identical: both are 358,777 bytes with SHA-256 `54be4b7def9d95e3f9b80f569998be165c79861a23b9c33edc36de2b0291a8b6` |
| Blob ids of the four files, previous head vs. this head | identical for all four (`a6c4b478`, `701aa820`, `96fc614c`, `41e420db`) |
| Working tree | clean before and after all checks; head unchanged |

Files the commit touches (8, 633 lines added, none removed):

| File | Change | Mode | Kind |
| --- | --- | --- | --- |
| `.planning/backlog/MAINTENANCE.md` | modified, +1 line | 100644 | backlog note (the `idna` doc follow-up) |
| `.planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md` | modified, +102 lines | 100644 | checkpoint record |
| `.planning/phases/86-pilot-reference-record/86-REVIEW-release-e568dabefc0d.md` | added | 100644 | previous review report |
| `.planning/phases/86-pilot-reference-record/codex/e568dabefc0d-release-v2-12-1-a1.last.json` | added | 100644 | Codex result (valid JSON, verdict `no-findings`, `review_complete` true) |
| `.planning/phases/86-pilot-reference-record/codex/e568dabefc0d-release-v2-12-1-a1.meta.json` | added | 100644 | harness metadata (valid JSON) |
| `.planning/phases/86-pilot-reference-record/codex/e568dabefc0d-release-v2-12-1-a1.prompt.txt` | added | 100644 | the fixed review prompt as sent |
| `.planning/phases/86-pilot-reference-record/codex/e568dabefc0d-release-v2-12-1-a1.pytest.txt` | added | 100644 | harness test output |
| `.planning/phases/86-pilot-reference-record/codex/e568dabefc0d-release-v2-12-1-a1.status.json` | added | 100644 | harness status (valid JSON, `complete`) |

- None is a `*-PLAN.md` file. `.planning/config.json` is not touched.
- None is executable: every file is mode 100644, none starts with a shebang, and the
  file types are Markdown text, plain text and JSON.
- Instruction-like content: the only file written as instructions is the `.prompt.txt`
  file, which is the saved copy of the fixed Codex review template for the previous
  head. It is a record of what was sent, it is not read by any workflow or agent as
  input, and its text only asks for a read-only review. A pattern scan of all added
  lines for override phrasing, piped downloads, destructive commands and shebangs
  found nothing.

**Method note.** The first attempt at the byte-identity comparison passed the four
paths as a single unsplit shell variable, which matched no file and produced two
identical hashes of empty output. That result was discarded. The figures above are
from the rerun with the four paths given explicitly, and the non-zero byte count and
the matching blob ids confirm the comparison was over real content.

## 2. Fresh review of the four in-scope files

| Check | Result |
| --- | --- |
| Version identity | `2.12.1` in `pyproject.toml:7`, `triggarr/__init__.py:1` and the `triggarr` package in `uv.lock:1142-1143` |
| `uv lock --check` (uv 0.12.17, the version `Dockerfile:27` pins) | exit 0, 55 packages resolved |
| `uv.lock` header | `version = 1`, `revision = 5`, `requires-python = ">=3.11"` |
| Locked versions named in the changelog | fastapi 0.162.4, starlette 1.10.0, python-multipart 0.0.33, opentelemetry-api 1.45.2: all match `CHANGELOG.md:9` and `CHANGELOG.md:23` |
| `parse_changelog(text, latest_only=True)` from `triggarr/changelog.py` | renders only v2.12.1: 5 categories, 9 bullets; tags balanced (`ul` 5/5, `li` 9/9, `h3` 1/1, `h4` 5/5, `div` 1/1); quotes are HTML-escaped; v2.12.0 is not included |
| Entry text hygiene (`CHANGELOG.md:1-34`) | no non-ASCII characters, no trailing whitespace |
| Convention rule packs | not applicable: Markdown, TOML, a lockfile and a one-line Python file; no pack covers them |

Changelog accuracy against the code relative to tag `v2.12.0`:

| Line | Claim | Verdict |
| --- | --- | --- |
| `CHANGELOG.md:9` | `opentelemetry-api` 1.45.2; v2.12.0 image had 1.45.1 | Lock has 1.45.2; the 1.45.1 figure matches the supplied image fact |
| `CHANGELOG.md:11` | Image upgrades `zlib1g`; build fails if the fixed version is absent | `Dockerfile:52-55` upgrades it and ends with a `dpkg --compare-versions` check that fails the build; the v2.12.0 Dockerfile had no such step, matching the supplied "unfixed zlib1g" fact |
| `CHANGELOG.md:15` | One malformed record no longer marks an instance disconnected; it is skipped and logged | `triggarr/search/engine.py` now screens records per item in all three app paths; the disconnected outcome remains only as a backstop |
| `CHANGELOG.md:17` | Card wording: "skipped record(s)", "detail(s)", and "failure reason(s)" on a Failed card | `triggarr/templates/partials/cycle_grade.html` and the `kind` field added in `triggarr/search/outcome.py` implement exactly these three branches |
| `CHANGELOG.md:21` | Image installs from the lockfile with hash checking | `Dockerfile:25-34` exports with `--locked`; `Dockerfile:61` installs with `--require-hashes --no-deps`. v2.12.0 used a plain `pip install .` |
| `CHANGELOG.md:23` | FastAPI, Starlette, python-multipart old and new versions; every other library unchanged | New values match the lock; old values match the supplied image facts. See IN-01 for the wording gap |
| `CHANGELOG.md:27` | Wheel and sdist no longer attached to releases | The v2.12.0 release workflow built and uploaded `dist/*`; the current `.github/workflows/release.yml` has no such step |
| `CHANGELOG.md:31-33` | Pipeline tests the exact image, rejects a mismatched tag, adds scanning and linting | Present in `.github/workflows/ci.yml` and `.github/workflows/release.yml` (image version label check and release identity gate at `release.yml:100-119`) |

Backticks in the entry render literally in the in-app view (the parser does not turn
them into code styling). Ten earlier bullets in `CHANGELOG.md` do the same, so this
follows the file's existing practice and is not raised.

## 3. Test and lint runs on this head

| Command | Result |
| --- | --- |
| `uv run pytest tests/ -x -q` (Python 3.11) | 3282 passed, 1 skipped, 38 warnings, exit 0 |
| `uv run ruff check triggarr/ tests/` | All checks passed, exit 0 |

The warnings are Starlette test-client deprecation notices in the auth and reset
tests, the same family as on the previous head.

## 4. Publication check of the newly added text

All 633 added lines were scanned for local absolute paths, home-directory and temp
paths, operating-system usernames, email addresses, private hostnames, private and
tailnet address ranges, credential and token patterns, and remote-shell commands.

**Nothing to report.** The only matches were:

- The repository's own public identifier, in
  `.planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md` (the Scope line
  of the new section, and the published image name on the "Not run on this head"
  line). This is the public repository and registry name, already present throughout
  the repository.
- The words `SecretStr` in the previous review report, which name a type, not a value.

The saved pytest output contains no local paths. The harness metadata records
`"author": null` and `"pr_number": null`, and file hashes only.

## Original vs. refreshed findings

| Prior ID | Prior finding (head `e568dabefc0d`) | Status on `e1f50adf2880` | Evidence |
| --- | --- | --- | --- |
| IN-01 | "Every other library in the image stays at the version v2.12.0 shipped" does not strictly cover `opentelemetry-api` and `pip` | **Still applies, unchanged** | `CHANGELOG.md` is the same blob on both heads. Carried forward as current IN-01. |
| IN-02 | `docs/ci-negative-demonstrations.md` still names `idna` 3.15 as the locked version | **Still applies; now tracked** | The doc is unchanged (`docs/ci-negative-demonstrations.md:276` still reads "lock 3.15"); the lock pins 3.20. This head adds a backlog entry for it in `.planning/backlog/MAINTENANCE.md:21`. Carried forward as current IN-02. |
| IN-03 | The `v2.12.1` tag must sit on the `main` commit that push CI ran on | **Still applies** (release mechanics, not a defect in the diff) | `.github/` is unchanged since the previous head. Carried forward as current IN-03. |

## Narrative Findings (AI reviewer)

## Info

### IN-01: "Every other library in the image stays at the version v2.12.0 shipped" does not strictly cover `opentelemetry-api` and `pip` (carried forward)

**File:** `CHANGELOG.md:23` (with `CHANGELOG.md:9`)

**Issue:** The bullet names three libraries and then says every other library is
unchanged. By the supplied image facts two more Python packages differ:
`opentelemetry-api` (1.45.1 to 1.45.2) and `pip`. The first is disclosed fourteen
lines earlier as the Security item, so nothing is hidden; the sentence read on its
own is not literally true.

**Effect:** Someone comparing the package lists of the two images finds five changed
libraries where the wording implies three. No one is misled about risk: both extras
are upgrades and one is the headline security fix.

**Fix:** Optional wording change:

```markdown
  * Dependency updates in the image: FastAPI 0.162.4 (v2.12.0 shipped 0.158.1), Starlette 1.10.0 (was 1.9.0), python-multipart 0.0.33 (was 0.0.32). Apart from these and the `opentelemetry-api` security update above, every library Triggarr installs stays at the version v2.12.0 shipped.
```

### IN-02: The lockfile-mismatch demonstration recipe still names `idna` 3.15 as the locked version (carried forward; now in the backlog)

**File:** `docs/ci-negative-demonstrations.md:266-267`, `docs/ci-negative-demonstrations.md:276`
(outside the reviewed diff; made stale by the `uv.lock` change in this PR)

**Issue:** The recipe's expected failure text is
`version mismatch: idna lock 3.15 image 3.4`. The lock now pins `idna` 3.20.

**Effect:** The demonstration still fails at the same step, but the next person to
repeat it sees `lock 3.20` where the document says `lock 3.15` and has to work out
whether the gate failed for the documented reason.

**Fix:** Update the expected text to 3.20, or make the recipe independent of the pin.
This head records the follow-up at `.planning/backlog/MAINTENANCE.md:21`, to be fixed
in a reviewed PR; that is an adequate disposition and nothing further is needed in
this PR.

### IN-03: The `v2.12.1` tag must go on the `main` commit that push CI ran on (carried forward)

**File:** `.github/scripts/release-policy.cjs` (`validateEvidence`), `.github/workflows/release.yml`

**Issue:** Not a defect in this diff. The release preflight requires a successful
push CI run on `main` whose head commit equals the tagged commit. After a merge
commit that is the merge commit, not this head or any earlier commit on the release
branch.

**Fix:** After the merge, wait for push CI on `main` to succeed and tag the `main`
head.

## Set aside (needs ruling)

### SA-01: Standalone `pip install git+...` users are not covered by the image statements (carried forward)

**Where:** `pyproject.toml:10-24`, `CHANGELOG.md:9`, `CHANGELOG.md:21-23`
**Why excluded:** The release diff does not change dependency floors, and the entry
scopes the lockfile and version statements to the Docker image.
**Effect if left as is:** A source install resolves from the loose constraints, so an
existing environment upgraded in place can keep `opentelemetry-api` 1.45.1.
**Needs:** ruling from the developer: in scope / defer / accept.

### SA-02: FastAPI 0.162 turns on its native telemetry instrumentation by default (carried forward)

**Where:** `triggarr/__main__.py` (`FastAPI(lifespan=...)`), SA-12 in `.planning/backlog/MAINTENANCE.md`
**Why excluded:** Introduced by an earlier roll-up and already recorded as an owner
call; with only `opentelemetry-api` installed the providers are no-ops.
**Effect if left as is:** None in the shipped image.
**Needs:** ruling from the developer: accept, or disable auto-configuration explicitly.

### SA-03: `pydantic-settings[toml]` in `pyproject.toml` is now a no-op extra (carried forward)

**Where:** `pyproject.toml:10`
**Why excluded:** Not changed by this diff and harmless.
**Effect if left as is:** None today; a warning about an unknown extra if upstream
ever removes it.
**Needs:** ruling from the developer: accept / drop the `[toml]` suffix later.

## Not verified

- **Image contents, both images.** No Docker command was run. The v2.12.0 image's
  package versions and the statement that a build of this branch differs from it only
  in fastapi, starlette, python-multipart, opentelemetry-api, pip and triggarr were
  taken as given from the review request.
- **Checks from the previous round that were not repeated.** The package-by-package
  lockfile comparison, the Dockerfile export command, the Python 3.13 test run,
  `pip-audit`, and the `.github/scripts` tests were not re-run. They were run on the
  previous head, and `uv.lock`, `pyproject.toml` and the other two files are the same
  git objects on this head, so those results carry over by identity, not by a new run.
- **Browser tests and GitHub-side state.** `tests/e2e` runs only in CI against the
  built image. No workflow was executed, and the PR's CI status, check runs and
  Dependabot alerts were not queried.
- **CVE identifiers.** Not re-checked against an external source.
- **Codex evidence content.** The added Codex files were read for publication safety
  and well-formedness only. Their conclusions were not used as evidence for this
  review, and whether they satisfy the Codex review contract was not assessed.

---

_Reviewed: 2026-11-14T23:26:26Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
