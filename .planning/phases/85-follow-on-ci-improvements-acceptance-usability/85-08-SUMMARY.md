---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "08"
subsystem: infra
tags: [docker, uv, pip, lockfile, ci, dependency-audit]

# Dependency graph
requires: []
provides:
  - Dockerfile production stage installs runtime dependencies from a hash-checked
    `uv export --locked` of uv.lock instead of re-resolving pyproject.toml
  - .github/scripts/image_lock_consistency.py: standalone checker comparing a
    locked requirements export against an image's pip freeze, PEP 508
    marker-aware and PEP 503 name-normalized
  - Local positive and negative evidence that the checker catches a deliberately
    mismatched package version
affects: [85-11 (CI wiring of this check into ci.yml's docker job)]

# Tech tracking
tech-stack:
  added:
    - uv 0.12.17 (build-only Dockerfile stage, pinned, never ships)
    - packaging (lazy-imported inside compare(), already a transitive dev
      dependency via pytest; never imported at module scope)
  patterns:
    - Multi-stage Dockerfile dependency install: a build-only `deps` stage
      exports a hash-pinned requirements file from uv.lock; the production
      stage installs it with `--require-hashes --no-deps`, then installs the
      project itself with `--no-deps`, so pyproject's loose constraints can
      never re-resolve a different version.
    - Lockfile/image consistency check: PEP 503-normalized name comparison,
      PEP 508 marker evaluation against the image's own dumped environment
      (never the host running the check), narrow `pip`-only allowlist for
      base-image tooling, fail-closed on unpinned lock entries or unsupported
      freeze lines.

key-files:
  created:
    - .github/scripts/image_lock_consistency.py
    - tests/test_image_lock_consistency.py
  modified:
    - Dockerfile

key-decisions:
  - "Both production-stage pip installs use --no-deps (hash-checked requirements install, then the project itself), closing the only path where pyproject.toml's loose constraints could re-resolve a different version than uv.lock."
  - "The deps stage is build-only (never COPY'd into the final image) and pins uv by exact version via an ENV UV_VERSION line."
  - "compare() imports packaging.markers.Marker lazily inside the function body so --dump-environment can run inside the bare production image with zero third-party packages."

patterns-established:
  - "Lockfile/image consistency checker: compares a `uv export --locked` export against `pip freeze` under the image's own dumped marker environment, PEP 503-normalized, with a narrow pip-only allowlist for base-image tooling."

requirements-completed: [CIMAINT-01]

# Metrics
duration: ~17min
completed: 2026-10-27
---

# Phase 85 Plan 08: Lockfile-Matched Docker Dependencies Summary

**Dockerfile installs runtime dependencies from a hash-checked `uv export --locked` of uv.lock instead of `pip install .`, proven by a new PEP 508/503-aware consistency checker with a local positive match and a local negative mismatch demonstration.**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-10-27 (approx., first commit 08:46:27-04:00)
- **Completed:** 2026-10-27T12:56Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created script, 1 created test file, 1 modified Dockerfile)

## Accomplishments
- Added `.github/scripts/image_lock_consistency.py`, a stdlib-only-at-dump-time checker that parses a `uv export --locked` requirements file and a `pip freeze` output, evaluates PEP 508 markers against the image's own dumped environment, normalizes names per PEP 503, and reports missing/mismatched/extra packages (only `pip` allowlisted as base-image tooling).
- Rewired the Dockerfile's production stage: a new build-only `deps` stage pins `uv==0.12.17` and exports `uv.lock` with hashes; the production stage installs that export with `pip install --require-hashes --no-deps`, then installs Triggarr itself with `--no-deps` — closing the gap where `pip install .` could silently re-resolve pyproject.toml's loose version constraints.
- Proved the mechanism locally: a real build's `pip freeze` matched the real `uv export` (checker exit 0), `output.css` from the Tailwind builder stage is unchanged and present, the shipped-image smoke harness passed against the locally built image, and a deliberately downgraded `idna` package made the checker fail with the exact required message.

## Task Commits

1. **Task 1: Lockfile/image consistency checker (TDD)**
   - `cf0c6e1` test(85-08): add failing image/lockfile consistency tests
   - `d594f7e` feat(85-08): add image/lockfile consistency checker (CIMAINT-01)
2. **Task 2: Install from uv.lock in the Dockerfile; prove match, unchanged runtime, and a local mismatch failure**
   - `88a0faf` build(85-08): install runtime dependencies from uv.lock with hash checking (CIMAINT-01)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `.github/scripts/image_lock_consistency.py` - Lockfile/image consistency checker (`normalize_name`, `parse_locked`, `parse_freeze`, `dump_environment`, `compare`, `main`); packaging imported lazily inside `compare()` only.
- `tests/test_image_lock_consistency.py` - 15 tests covering every behavior case in the plan (match with marker-skip + pip allowlist, missing/mismatch/extra, name normalization, hash-continuation/marker parsing, fail-closed unpinned/unsupported input, stdlib-only environment dump, CLI exit codes and output).
- `Dockerfile` - New build-only `deps` stage (pins `uv==0.12.17`, runs `uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file requirements-locked.txt`); production stage now does `COPY --from=deps ... && pip install --require-hashes --no-deps -r ... && rm ...` before the existing `pyproject.toml`/`triggarr/`/`CHANGELOG.md` copies and `pip install --no-deps .`. Tailwind builder stage and everything after the dependency install (output.css copy, entrypoint, user, healthcheck) are byte-identical to before.

## Decisions Made
- `uv` is pinned by exact version (`ENV UV_VERSION=0.12.17`, matching the locally installed version used elsewhere in this repo's CI) in a stage that is never copied into the final image.
- The checker's `allowed_extra` defaults to `frozenset({"pip"})` only — no `setuptools`/`wheel` exception was needed; the real built image's `pip freeze --all --exclude triggarr` contained no such packages, so the plan's "stop and record why" instruction for that case did not trigger.
- Problems returned by `compare()` are sorted for stable, deterministic CI output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Local proof built on `linux/arm64` instead of the plan's specified `linux/amd64`, due to a QEMU emulation crash on this host**
- **Found during:** Task 2 (local proof step)
- **Issue:** `docker build --platform linux/amd64 -t triggarr:p85-local .` crashed inside the new `deps` stage with `qemu: uncaught target signal 11 (Segmentation fault)` the moment the pip-installed `uv==0.12.17` binary executed. Isolated independently: a bare `pip install uv==0.12.17 && uv --version` under the same `--platform linux/amd64` emulation on this host segfaults identically, before any `uv export` logic runs — confirming this is a QEMU-user/Rust-binary emulation incompatibility on this Docker Desktop installation, not a defect in the Dockerfile or the checker.
- **Fix:** Ran the entire local-proof sequence (build, `pip freeze`, `uv export`, `--dump-environment`, checker positive case, output.css check, smoke harness, and the negative mismatch demonstration) on `linux/arm64` instead — this Mac's native, non-emulated Docker platform. `uv export --locked` resolves and exports the lockfile's arm64-appropriate hash set when run inside an arm64 container, so every step stayed internally consistent (the lockfile export, the hash-checked install, the `pip freeze`, and the checker comparison all describe the same platform). The mechanism being proven — export-then-hash-checked-install, then freeze-vs-lock comparison — is platform-independent logic; no amd64-specific code path exists in either the Dockerfile or the checker.
- **Cost if wrong:** If `--require-hashes` installation or the checker's marker/name handling had an amd64-specific defect (e.g. a hash mismatch unique to the manylinux amd64 wheel set, or a marker that evaluates differently under `platform_machine=x86_64`), this arm64-only local proof would not surface it. Real, non-emulated amd64 verification happens for free once this image builds on GitHub Actions' actual x86_64 runners; wiring this checker into `ci.yml`'s `docker` job (where that verification becomes automatic and required) is Plan 85-11, explicitly out of this plan's scope per the plan's own Purpose line ("CI wiring is Plan 85-11").
- **Files modified:** none beyond the Dockerfile change Task 2 already specified.
- **Verification:** `docker build --platform linux/arm64 -t triggarr:p85-08-local .` succeeded, including the `--require-hashes --no-deps` install step; see "Local Evidence" below for every check run against that image.
- **Committed in:** `88a0faf` (Task 2 commit) — the deviation is a verification-method substitution, not a code change, so nothing additional was committed for it.

---

**Total deviations:** 1 auto-fixed (1 blocking — local verification platform substitution)
**Impact on plan:** No change to the Dockerfile or checker logic from the plan as specified. The substitution only affects which CPU architecture the local proof ran on; the plan's narrow local claim ("local evidence... GitHub enforcement is demonstrated in Plan 85-18") already anticipates that full CI enforcement is a separate, later concern.

## Local Evidence

All local proof was run against `triggarr:p85-08-local`, built with `docker build --platform linux/arm64 -t triggarr:p85-08-local .` (see the deviation above for why `arm64`, not the plan's `amd64`, was used). Image ID: `sha256:55767a91fe56195f698182d4218e1fc4e848b53a48df0b0be334707435121089`. All scratch artifacts (the frozen requirements, the locked export, the dumped environment, the demo image's freeze) were written only under `/tmp/p85-08-scratch/`, never inside the repo; `git status --porcelain` showed no generated files at any point.

- **Positive consistency check:** `uv run --no-sync python .github/scripts/image_lock_consistency.py --locked requirements-locked.txt --freeze image-requirements.txt --environment image-environment.json` exited `0` and printed `Image dependencies match uv.lock`.
- **`output.css` unchanged and present:** `docker run --rm --entrypoint test triggarr:p85-08-local -s /app/triggarr/static/css/output.css` succeeded; size is 41874 bytes (`docker run --rm --entrypoint wc ... -c ...`).
- **No undeclared base-image extras:** the real `pip freeze --all --exclude triggarr` from the built image (37 lines) contained only the 36 locked runtime packages plus `pip` — no `setuptools`/`wheel` or any other extra, so the plan's "stop and record why before widening the allowlist" instruction never triggered.
- **Shipped-image smoke harness:** `uv run --no-sync python -m tests.harness.image_smoke run --image triggarr:p85-08-local --expected-image-id-file <scratch image-id.txt>` printed `SMOKE PASSED` (steps 0 through E, including the missing-static-asset negative).
- **Negative mismatch demonstration:** built a two-line scratch Dockerfile (`FROM triggarr:p85-08-local` + `RUN pip install --no-cache-dir --no-deps "idna==3.4"`, a real, different released PyPI version from the locked `idna==3.15`) as `triggarr-demo:lock-mismatch`, froze it, dumped its environment, and ran the checker: exit code `1`, output exactly `version mismatch: idna lock 3.15 image 3.4`. The demo image was removed afterward (`docker rmi triggarr-demo:lock-mismatch`); the local proof image `triggarr:p85-08-local` was also removed after evidence collection.
- **Own tests (W06 scope):** `uv run --no-sync pytest tests/test_image_lock_consistency.py -x -q` — 15 passed.
- **Dockerfile grep checks (plan's automated verify):** `uv export --locked` (1), `--require-hashes --no-deps -r` (1), `pip install --no-cache-dir --no-deps .` (1), the old re-resolving `pip install --no-cache-dir .` line (0), `COPY --from=builder /build/triggarr/static/css/output.css` unchanged (1).

## Issues Encountered
None beyond the QEMU/amd64-emulation platform substitution documented above as a deviation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `.github/scripts/image_lock_consistency.py` is ready to be wired into `ci.yml`'s `docker` job (Plan 85-11), where it would run on a real, non-emulated x86_64 GitHub Actions runner — the environment where the amd64-specific platform question from this plan's deviation gets a definitive, non-emulated answer.
- No blockers for subsequent Phase 85 plans.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `.github/scripts/image_lock_consistency.py`
- FOUND: `tests/test_image_lock_consistency.py`
- FOUND: `Dockerfile`
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-08-SUMMARY.md`
- FOUND commit: `cf0c6e1` (test(85-08))
- FOUND commit: `d594f7e` (feat(85-08))
- FOUND commit: `88a0faf` (build(85-08))
