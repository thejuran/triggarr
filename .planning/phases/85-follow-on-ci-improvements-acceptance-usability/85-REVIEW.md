---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T21:23:20Z
reviewed_head: bfae334e22e5b37ac414953d138b123e969d82c0
diff_base: 9978b7fafcafdfc7d400215c48211616ba75a0f3
iteration: 13
depth: standard
files_reviewed: 4
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/review-acceptance.yml
  - uv.lock
findings:
  critical: 0
  warning: 0
  info: 8
  total: 8
status: issues_found
---

# Phase 85: Code Review Report (iteration 13, Dependabot rollup #37-#42)

**Reviewed:** 2026-10-28T21:23:20Z (head `bfae334e22e5b37ac414953d138b123e969d82c0`, diff base `9978b7fafcafdfc7d400215c48211616ba75a0f3`)
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found (info items only: two new, six carried; no blocker, no warning)

## Summary

Scope: `git diff 9978b7f..bfae334`, which is commit bfae334. It changes 25 lines across the three workflows and the `uv.lock` dependency refresh.

What I checked on this tree:

- **The rollup matches the six Dependabot PRs exactly.** `uv.lock` is byte-identical to the head of PR #41 (`git diff <#41 head> bfae334 -- uv.lock pyproject.toml` is empty). Every added workflow line from #37, #38, #39, #40 and #42 is present. The line counts add up (2+5+5+12+1 = 25), so the rollup adds nothing extra.
- **Every action is pinned to a full commit hash, and each hash matches its tag.** I looked up each tag with `gh api repos/<r>/commits/<tag>`: checkout v7.0.1 = `3d3c42e5…`, setup-python v7.1.0 = `6d4fd22b…`, download-artifact v8.0.2 = `9000827c…`, gitleaks-action v3.0.0 = `e0c47f4f…`, login-action v4.7.0 = `81c6f93d…`. Every `uses:` line in `.github/workflows/` has a 40-character hash and a `# v…` comment. The login-action comment is less specific than the others (see IN-10).
- **The pinned gate ref in review-acceptance.yml did not change.** Only the checkout action's hash changed. `ref: 8df9eaf9d68ad0e5fce469ef8393d05bb4ba3fc3` and `persist-credentials: false` are the same as before.
- **release.yml (PR CI does not run it):**
  - It downloads `audited-image` by name, with `run-id` and `github-token` set (lines 87-93). download-artifact v8 still extracts a by-name download straight into `path`, so `image/image.tar`, `image.tar.sha256` and `image-id.txt` end up where the next step expects them. The ci.yml round-trip step (lines 180-194) exercises the same by-name download and checks the same files on every CI run.
  - The uploads still use upload-artifact v4 (`ea165f8d…`). That produces the zipped v4-backend artifact that download-artifact v8 reads by default.
  - v8 now fails on a digest mismatch. That only makes the release stricter.
  - login-action 4.7.0 has the same inputs (`registry`, `username`, `password`). It still comes after the identity gate, so the ordering tests in `tests/test_github_workflows.py` and `artifact-promotion.test.cjs` still hold.
- **uv.lock is internally consistent:**
  - Every new or changed artifact URL is on `files.pythonhosted.org`.
  - There are 42 new `sha256:` hashes, all 64 hex characters.
  - The new `opentelemetry-api` 1.45.1 entry has an sdist and a wheel, both hashed. It depends only on `typing-extensions`.
  - No new package source was added.
  - The lock format moved from `revision = 3` to `revision = 5`. The Dockerfile pins `UV_VERSION=0.12.17`, and that version reads the new lock: `uv export --locked --no-dev --no-emit-project` succeeds and gives `fastapi==0.162.0`, `starlette==1.10.0` and `opentelemetry-api==1.45.1`.
- **The new opentelemetry-api runtime dependency, in the shipped image:**
  - FastAPI 0.162 now requires `opentelemetry-api>=1.44.0` and has a built-in `fastapi/telemetry` ASGI layer.
  - It only sends data anywhere if you opt in with `telemetry={"auto_configure": True}` or `FASTAPI_OTEL_AUTO_CONFIGURE=true` (`_api.py:72-77`, `_runtime.py:87-93`). `OTEL_SDK_DISABLED=true` also turns it off.
  - Without opt-in, spans go to the API's built-in no-op provider. The image does not ship the OpenTelemetry SDK or exporters (they are in the `opentelemetry`/`standard` extras, which triggarr does not install). So by default nothing leaves the container and nothing new is logged.
  - If an operator does opt in, the URL query is recorded with sensitive keys masked (`_asgi.py:305-318`).
  - One sharp edge for operators who opt in is set aside as SA-12.
- **FastAPI/Starlette API surface used by triggarr:**
  - triggarr uses `FastAPI(lifespan=...)`, `add_middleware` with three `BaseHTTPMiddleware` subclasses, `StaticFiles` mounted at `/static`, `Jinja2Templates.TemplateResponse` called with `request=`, `name=` and `context=` keywords, `APIRouter`, `Request`, and the HTML/JSON/redirect response classes.
  - None of these changed in a way that breaks triggarr. The full suite passes on the new versions: `uv run pytest tests/ -q -x` reports 2688 passed and 38 warnings.
  - The warnings are two test-client deprecations. One of them is a forward-compatibility signal (IN-11).
- No `pull_request_target` appears in the repo, so the Node-24 runtime moves (checkout v7, setup-python v7, gitleaks v3) widen no trust boundary. gitleaks v3 keeps the same inputs (`GITHUB_TOKEN`, `GITLEAKS_ENABLE_COMMENTS`).

**Regressions:** none found in this diff.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Info

### IN-10 (new): The login-action comment says `# v4` while every other bumped action names its exact release

**File:** `.github/workflows/release.yml:121, 143`
**Issue:** Dependabot rewrote the other comments to exact versions (`# v7.0.1`, `# v7.1.0`, `# v8.0.2`, `# v3.0.0`). The login-action comment stayed `# v4`. The comment is not wrong: the floating `v4` tag currently points at the same commit as `v4.7.0` (`81c6f93d…`). But the hash in the diff changed while its comment did not. A reader cannot tell from the file which 4.x release is pinned, and the comment will stay `v4` after the `v4` tag moves on.
**Fix:** Optional. Change both comments to `# v4.7.0`. Dependabot keeps whatever comment style it finds, so this is a one-time change.

### IN-11 (new): The new Starlette deprecates its test client running on `httpx`

**File:** `uv.lock` (starlette 1.10.0); affects `tests/test_auth_integration.py`, `tests/test_auth_middleware.py`, `tests/test_auth_routes.py`, `tests/test_reset.py`
**Issue:** On this tree `starlette.testclient` imports `httpx2` if it is installed. Otherwise it falls back to `httpx` and raises `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`. A later Starlette release that removes the fallback would break every `TestClient` test at import time. That would show up as a failing Dependabot PR, not as a silent bug. The suite also warns about per-request `cookies=` in those auth tests. This does not affect the shipped image.
**Fix:** Optional, and not part of this rollup. Record a backlog item to add `httpx2` to the dev extra, and to set cookies on the client instance instead of per request.

### IN-09 (carried from iteration 11): Seven now-redundant `monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)` lines remain

**File:** `tests/test_codex_review_run.py:332, 496, 628, 671, 686, 1101, 1241` (also 2392; not in this round's scope)
**Issue:** Recorded as in iteration 12. Not re-raised.

### IN-05 (carried from iteration 9): The pins file header points to evidence in a phase folder that will be archived, and nothing checks its "checked" date

**File:** `.github/tool-pins.env:1-5` (not in this round's scope)
**Issue:** Recorded as in iteration 9. Not re-raised.

### IN-03 (carried from iteration 8): The drain-timeout fallback decodes as UTF-8 and ignores the caller's `encoding`, `errors` and newline handling

**File:** `tests/codex_review_run.py:211-222` (not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-04 (carried from iteration 8): The new end-to-end test assumes the child prints within one second

**File:** `tests/test_codex_review_run.py:2079-2111` (line numbers before b272d82; not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-01 (carried from iteration 7, owner left out of scope): The Node detector's quoted-key support misses YAML escape spellings

**File:** `.github/scripts/ci-job-consistency.cjs:589-596` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

### IN-02 (carried from iteration 7, owner left out of scope): Run-splitting logic is duplicated

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 133-137` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

## Convention (advisory, never blocks, not counted)

### CV-01: The convention checker flags `review-acceptance.yml` for kebab-case naming (no action recommended)

**File:** `.github/workflows/review-acceptance.yml:1`
**Deviation:** The file name uses kebab case (`review-acceptance`).
**Convention:** The checker derived camelCase file names from the JS/TS corpus.
**Fix:** Do not rename it. Every workflow file in `.github/workflows/` uses kebab case, which is the GitHub convention. Required-check names, the `review-acceptance` environment, and the tests refer to this path. This diff did not touch the file name. It is recorded only because the shared checker emitted it.

## Accepted residuals (carried, not counted)

### Iteration-7 WR-01: Run-together reviewer names typed in one case (`claudecode`, `bmreviewer`, `gsdagent`, `codexreviewrun`) still pass

**File:** `.github/scripts/codex-fallback.cjs:113-137`
**Status:** The owner accepted this as a residual after iteration 7. Recorded here for continuity. Not re-raised, and not counted in `findings`.

## Set aside (needs ruling)

### SA-12 (new): An operator who turns on FastAPI's automatic telemetry gets a startup failure instead of a working export

**Where:** `uv.lock` (fastapi 0.162.0; `fastapi/telemetry/_runtime.py:87-131`); `triggarr/__main__.py:68`
**Why excluded:** By default it does nothing, and it needs an environment variable that triggarr does not document. It is a product question, not a defect in this diff.
**Effect if left as is:** Suppose a user's container environment has `FASTAPI_OTEL_AUTO_CONFIGURE=true` and an `OTEL_EXPORTER_OTLP_ENDPOINT`, for example from a stack-wide compose `environment:` block. FastAPI then tries to import the OpenTelemetry SDK, which the image does not ship. It raises `FastAPIError` before lifespan startup, so the web UI does not come up. The error message is clear. With the variable unset, which is the normal case, nothing changes.
**Needs:** Ruling. (a) Accept as is. (b) Pass `telemetry={"auto_configure": False}` in `FastAPI(...)` so triggarr ignores the variable. (c) Document that OpenTelemetry export is unsupported. I recommend (a) for this rollup and, if wanted, (b) as a later one-line backlog change.

### SA-11 (carried from iteration 11): No test covers `main()`'s "phase-dir does not exist" refusal

Unchanged from `85-REVIEW.iter11.md`.

### SA-10 (carried from iteration 10): The fixture copies and the phase-83 originals can drift apart

Unchanged from `85-REVIEW.iter10.md`.

### SA-08 (carried from iteration 9): resolved by b272d82

Unchanged from `85-REVIEW.iter10.md`.

### SA-09 (carried from iteration 9): `.github/tool-pins.env` is not on the sensitive-path list

Unchanged from `85-REVIEW.iter9.md`.

### SA-07 (carried from iteration 8): When stderr is not captured, `exc.stderr` gets a made-up drain marker

Unchanged from `85-REVIEW.iter8.md`.

### SA-01 to SA-06 (carried from iteration 7)

Unchanged from `85-REVIEW.iter7.md`:
- **SA-01:** Acceptance runs on the gate it introduces.
- **SA-02:** The register schema cutover strands open PRs.
- **SA-03:** Dependabot `uv` updates have no cooldown. This rollup is an instance of it: fastapi went from 0.136.3 to 0.162.0, a jump of 26 minor versions in one bump. It is still inside the current ruling.
- **SA-04:** A runner-changing PR can certify its own base cross-grade. Owner-recorded follow-up.
- **SA-05:** Reusable workflows and local actions are not inspected. Owner-recorded follow-up.
- **SA-06:** Digit splitting creates initial-like false positives. Inside the accepted residual.

---

_Reviewed: 2026-10-28T21:23:20Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
