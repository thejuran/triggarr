# Phase 82: CI Tests What We Ship - Pattern Map

**Mapped:** 2026-10-21
**Files analyzed:** 15
**Analogs found:** 12 / 15 (3 flagged "No Analog Found" — new artifact classes)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `.github/workflows/ci.yml` (add `image-smoke`, `browser-e2e` jobs; extend `ci-ready`) | config (CI workflow) | event-driven | `.github/workflows/ci.yml` — existing `docker` job + `ci-ready` job (same file) | exact |
| `.github/workflows/release.yml` (add tag/version identity steps) | config (release workflow) | request-response (pre-publish gate) | `.github/workflows/release.yml` — existing tag-conditional steps (same file) | exact |
| `.github/scripts/release-policy.cjs` (add `validateTagFormat`, `validateVersionIdentity`; extend `REQUIRED_JOBS`) | service/utility (pure validation) | transform | `.github/scripts/release-policy.cjs` — `validateEvidence` (same file) | exact |
| `.github/scripts/release-policy.test.cjs` (add positive/negative cases) | test | transform | `.github/scripts/release-policy.test.cjs` (same file) | exact |
| `.github/scripts/artifact-promotion.test.cjs` (add wiring assertion) | test | transform (static text-position check) | `.github/scripts/artifact-promotion.test.cjs` (same file) | exact |
| `.github/scripts/ci-job-consistency.test.cjs` (optional — new job names likely auto-covered) | test | transform | `.github/scripts/ci-job-consistency.test.cjs` (same file) | exact |
| New `image-smoke` job script/steps (container lifecycle + HTTP checks) | utility / test (smoke driver) | request-response + file-I/O + event-driven | `.github/workflows/ci.yml` `docker` job's inline bash steps (`Audit actual image dependencies`, `Save the audited image`, `Verify release image round trip`) | role-match |
| Minimal stub *arr HTTP service, e.g. `tests/fixtures/arr_stub/app.py` | service (test double) | request-response | `triggarr/clients/base.py::validate_connection` (status contract) + `triggarr/web/routes.py::health` (minimal JSON handler shape) | partial-match |
| `tests/e2e/conftest.py` | config/fixture | request-response | `tests/conftest.py` (same role, different data flow) | role-match |
| `tests/e2e/test_pill_polling.py` | test | event-driven (polling) | `tests/test_header_redesign.py::test_connection_pill_partial_does_not_retrigger_on_swap` | role-match |
| `tests/e2e/test_setup_login_logout.py` | test | request-response (browser flow) | `tests/test_auth_integration.py::test_full_setup_login_use_logout_flow` | exact (flow logic) / role-match (tool) |
| `pyproject.toml` (add `playwright`, `pytest-playwright` to `dev` extra) | config | — | `pyproject.toml` — existing `[project.optional-dependencies] dev = [...]` (same file) | exact |
| `uv.lock` (regenerate) | config (generated) | — | n/a — run `uv lock`, do not hand-edit | exact |
| Recorded-demonstration reproduction recipe (D-08), location TBD by planner | config/doc | — | `docs/owner-cli-acceptance.md` (structured procedure/evidence doc style) | partial-match |
| `.github/scripts/ci-job-consistency.cjs` | — | — | **unchanged** — already generic, no edit expected | n/a |

## Pattern Assignments

### `.github/workflows/ci.yml` — new `image-smoke` and `browser-e2e` jobs (config, event-driven)

**Analog:** same file, `docker` job (lines 78–151) and `ci-ready` job (lines 181–203)

**Download-and-verify pattern to copy for both new jobs** (adapt from `docker` job's round-trip step, lines 138–151):
```yaml
      - name: Download the published CI artifact for round-trip verification
        uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
        with:
          name: audited-image
          path: restored-image
      - name: Verify release image round trip
        working-directory: restored-image
        run: |
          sha256sum -c image.tar.sha256
          docker image rm triggarr:ci-test
          docker load -i image.tar
          test "$(docker image inspect triggarr:ci-test --format '{{.Id}}')" = "$(cat image-id.txt)"
```
No `run-id:` needed — `image-smoke`/`browser-e2e` run in the same workflow run as `docker`, so `actions/download-artifact` resolves by name alone (unlike `release.yml`'s cross-workflow download, which needs `run-id`).

**Job skeleton conventions to copy** (every job in this file, e.g. lines 17–20, 60–63, 153–160):
```yaml
  <job-id>:
    needs: [docker]
    timeout-minutes: 20
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
```
Every job: full-SHA-pinned actions, explicit `timeout-minutes`, top-level `permissions: contents: read` (workflow-level, line 13–14) inherited unless overridden.

**`ci-ready` aggregate pattern to extend** (lines 181–203, copy verbatim structure, only the two sets change):
```yaml
  ci-ready:
    name: CI ready
    if: always()
    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e]
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - name: Require every mandatory job to succeed
        env:
          RESULTS: ${{ toJSON(needs) }}
        run: |
          python3 - <<'PY'
          import json, os, sys
          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e"}
          results = json.loads(os.environ["RESULTS"])
          if set(results) != required:
              sys.exit("Missing or unexpected mandatory CI jobs")
          bad = {name: job.get("result") for name, job in results.items() if job.get("result") != "success"}
          if bad:
              sys.exit(f"Mandatory jobs did not succeed: {bad}")
          print("All mandatory CI jobs succeeded. This does not attest to Greptile review or product acceptance.")
          PY
```
**Critical:** `ci-job-consistency.cjs`'s `extractCiReady()` treats a job's *effective name* as its `name:` override if present, else its id — keep new job ids (`image-smoke`, `browser-e2e`) identical to their `REQUIRED_JOBS` entries (no `name:` override) unless deliberately overriding both together (Anti-Pattern, RESEARCH.md).

**Image provenance read, for the Docker-layer missing-static-asset negative** (lines 88–99 show the project's inline-Python-heredoc convention for reading/validating `pyproject.toml`/image metadata inside a `run:` block — reuse this *style*, not this exact code, for any smoke-test Python needed inline in the new job).

---

### `.github/workflows/release.yml` — tag-format + version-identity steps (config, request-response)

**Analog:** same file — the existing tag-only conditional step pair (lines 93–106) and the `recheck`/`preflight` pattern (lines 73–78)

**Tag-only conditional step pattern to copy** (lines 93–106 — note the narrower `if:` than the job-level `if:`, Pitfall 6):
```yaml
      - name: Download exact successful CI Python distributions
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
        uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
        with:
          name: python-dist
          path: dist
          run-id: ${{ steps.recheck.outputs.run_id }}
          github-token: ${{ secrets.GITHUB_TOKEN }}

      - name: Verify distribution artifacts before any publication
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
        run: |
          compgen -G 'dist/*.whl' > /dev/null
          compgen -G 'dist/*.tar.gz' > /dev/null
```
New tag-format/version-identity steps must use this **exact same narrower condition** `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')` — not the job-level `if:` (lines 52–58), which also covers the `workflow_run` main-push path where there is no tag to validate. `tests/test_github_workflows.py::test_release_workflow_run_requires_same_repo_push_ci` already pins the job-level `if:` string verbatim — any new Python-side test for the tag-only steps should follow that same normalize-whitespace-and-compare pattern (see below).

**`github-script` invocation pattern to copy** (lines 38–44, 73–78 — this is how `release-policy.cjs` functions are invoked from workflow YAML):
```yaml
      - uses: actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd # v8
        id: policy
        with:
          script: |
            const {preflight} = require('./.github/scripts/release-policy.cjs');
            await preflight({github, context, core});
```
New steps follow this exactly: `require('./.github/scripts/release-policy.cjs')`, destructure the new exported functions, call them, let a thrown `Error` fail the step naturally (fails closed — no explicit `core.setFailed` needed, matching existing style).

**Placement constraint (D-24):** new steps must sit strictly before `docker/login-action` (line 108) — i.e., immediately after "Verify and load audited image" (line 86–91) and before line 108. Do **not** move the sparse-checkout (`sparse-checkout: .github/scripts`, line 37/72) to include `pyproject.toml` — compare against the image's own `org.opencontainers.image.version` label instead (Anti-Pattern in RESEARCH.md).

---

### `.github/scripts/release-policy.cjs` — `validateTagFormat` / `validateVersionIdentity` (service/utility, transform)

**Analog:** same file, `validateEvidence` (lines 4–21)

**Fail-closed pure-function pattern to copy exactly:**
```javascript
function validateEvidence({sha, mainSha, ancestry, runs, jobs, tag}) {
  if (!/^[a-f0-9]{40}$/.test(sha || '')) throw new Error('Invalid release commit');
  if (!tag && sha !== mainSha) throw new Error('Superseded main build; refusing to republish old main');
  if (!['identical', 'behind'].includes(ancestry)) throw new Error('Release commit is not on main');
  // ...
  return sha;
}
```
Every validation function in this file: destructured single-object argument, regex/membership guard clauses that `throw new Error('<specific reason>')` immediately (never silently return false), and a plain return value (never a boolean) on success — the thrown message is what D-23 requires to "report the reason." Export alongside the existing triple:
```javascript
module.exports = {REQUIRED_JOBS, validateEvidence, preflight, validateTagFormat, validateVersionIdentity};
```
**`REQUIRED_JOBS` extension (line 2):**
```javascript
const REQUIRED_JOBS = ['test', 'lint', 'docker', 'secrets', 'dependencies', 'image-smoke', 'browser-e2e', 'CI ready'];
```
Must keep `'CI ready'` as the last (aggregate) entry — `checkJobListConsistency()` in `ci-job-consistency.cjs` (lines 144–149) asserts `requiredJobs[requiredJobs.length - 1] === ciReady.displayName`.

---

### `.github/scripts/release-policy.test.cjs` — new positive/negative cases (test, transform)

**Analog:** same file (lines 1–23) — table/loop-driven `node:test` + `node:assert/strict` style

**Pattern to copy:**
```javascript
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {REQUIRED_JOBS, validateEvidence} = require('./release-policy.cjs');
// ...
for (const conclusion of ['skipped','neutral','failure','cancelled','timed_out',null]) {
 test(`rejects ${conclusion} job even if run says success`, () => {
   const e=evidence(); e.jobs[0].conclusion=conclusion;
   assert.throws(()=>validateEvidence(e));
 });
}
```
New negative cases for `validateTagFormat`/`validateVersionIdentity` must follow D-04: feed the deliberately invalid input (malformed tag strings, mismatched version labels) into the real exported function and assert the specific throw, never duplicate the regex/comparison logic in the test. Use `assert.throws(() => fn(bad), /expected substring/)` to pin the *reason*, matching how `preflight` rejection tests assert `/Untrusted/`, `/Superseded/`, `/has not succeeded/` (lines 65, 71, 74, 79 in this file).

---

### `.github/scripts/artifact-promotion.test.cjs` — wiring assertion for new validation steps (test, static text-position check)

**Analog:** same file (lines 7–17), `'both exact-run artifacts are downloaded and checked before publication'`

**Pattern to copy exactly** (string-position assertions against the raw YAML text, no YAML parser):
```javascript
test('both exact-run artifacts are downloaded and checked before publication',()=>{
 const publish=release.indexOf('      - name: Publish audited image');
 assert.ok(publish>0);
 for(const name of ['Download exact successful CI image','Verify and load audited image',
 'Download exact successful CI Python distributions','Verify distribution artifacts before any publication']) {
   const pos=release.indexOf(`      - name: ${name}`);
   assert.ok(pos>=0 && pos<publish,`${name} must precede publishing`);
 }
});
```
New test: add `'Validate tag format'` and `'Validate tag/image version identity'` (or whatever step names the planner chooses) to this same `indexOf`-before-`publish` loop, and add a second assertion that the version-identity step runs before `docker/login-action` specifically (`release.indexOf('docker/login-action')`), satisfying D-05 and D-24 together — this file is exactly the established pattern for "CI wiring verified separately from function behavior."

---

### New `image-smoke` job steps — container lifecycle + HTTP checks (utility/test, request-response + file-I/O + event-driven)

**Analog:** `.github/workflows/ci.yml` `docker` job's inline bash steps (lines 114–120, 122–126, 143–151) — no dedicated smoke-test script exists yet in this repo; this is the closest *style* analog, not an exact-role match.

**Inline-bash-step conventions to copy:**
```yaml
      - name: Audit actual image dependencies
        run: |
          docker run --rm --entrypoint python triggarr:ci-test -m pip freeze --all --exclude triggarr > image-requirements.txt
          test -s image-requirements.txt
```
Plain `run: |` blocks, no separate shell-script file, assertions via `test`/`diff`/exit codes rather than a custom test framework — the new `image-smoke` job's health/setup/login/static/config/restart checks should follow this same inline-bash-step shape (per Claude's Discretion: "Job layout... separate jobs vs. steps" is left open, but the existing repo convention favors inline `run:` blocks over new script files for CI-only, one-off container orchestration).

**Isolated config volume pattern** (RESEARCH.md Architecture Pattern 3, grounded in `triggarr/models/config.py::get_config_dir()` lines 20–31):
```python
raw = os.environ.get("TRIGGARR_CONFIG_DIR", "/config")
```
The real app already reads config location exclusively from this env var — no test-only code path needed. Mount a fresh named Docker volume at `/config` with `-e TRIGGARR_CONFIG_DIR=/config` against the real `ENTRYPOINT ["/entrypoint.sh"]` (`Dockerfile` line 51, `entrypoint.sh` full file) to get an isolated, writable, persistent config directory for free.

**CSRF/Origin pitfall when writing the smoke test's HTTP client** (`triggarr/web/middleware.py::OriginCheckMiddleware`, lines 64–89):
```python
if origin:
    if urlparse(origin).netloc != host:
        return Response("Forbidden", status_code=403)
elif referer and urlparse(referer).netloc != host:
    return Response("Forbidden", status_code=403)
# Neither header present: allow (same-origin browser behavior)
```
A plain `curl`/`requests.post()` smoke check (no `Origin`/`Referer` header) passes this gate unmodified — don't add an `Origin` header unless it is set to exactly match the container's externally-reachable `Host:port`.

---

### Minimal stub *arr HTTP service — e.g. `tests/fixtures/arr_stub/app.py` (service/test-double, request-response)

**Analog:** `triggarr/clients/base.py::validate_connection` (lines 238–247) for the contract the stub must satisfy, and `triggarr/web/routes.py::health` (lines 252–255) for the minimal-JSON-handler shape already used in this codebase.

**Contract the stub must satisfy** (`triggarr/clients/base.py` line 43–44, 247–253; `triggarr/models/arr.py::SystemStatus` lines 127–136):
```python
_status_path: str = "/api/v3/system/status"   # Radarr/Sonarr default; Lidarr overrides to /api/v1/system/status (triggarr/clients/lidarr.py:25)
# ...
response = await self._client.get(self._status_path)
response.raise_for_status()
status = SystemStatus.model_validate(response.json())   # only `version: str` is required; extra="ignore"
```
So the stub's minimal positive response only needs `{"version": "5.0.0.0"}` (any string) on `GET /api/v3/system/status` (and `/api/v1/system/status` if Lidarr is exercised) with HTTP 200; a disconnected-state toggle should make that endpoint return a non-2xx (matching the `httpx.HTTPStatusError`/`httpx.ConnectError` branches already handled in `validate_connection`, lines 254–268).

**Minimal-handler style to copy** (`triggarr/web/routes.py` lines 252–255):
```python
@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint for uptime monitors."""
    return JSONResponse({"status": "ok"})
```
Keep the stub this thin — a single-file FastAPI (or stdlib `http.server`) app with one status route and one control route, per Claude's Discretion and the "Don't Hand-Roll" guidance (no full *arr API clone needed).

**Test-mock shape for reference** (`tests/test_clients.py`, pattern used throughout, e.g. line 122): existing tests already build `httpx.AsyncClient(transport=<MockTransport>)` fixtures against this same `_status_path` contract — read `tests/test_clients.py` near any of the `client._client = httpx.AsyncClient(transport=transport, base_url="http://test")` lines for the exact JSON shapes already asserted against `SystemStatus`-shaped responses, to keep the stub's response bodies consistent with what the app's own test suite already expects.

---

### `tests/e2e/conftest.py` (config/fixture, request-response)

**Analog:** `tests/conftest.py` (full file, 50+ lines) — fixture/factory conventions

**Pattern to copy:**
```python
"""Shared test fixtures and factory functions for Triggarr tests."""

from __future__ import annotations

import pytest

from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
# ...

@pytest.fixture(autouse=True)
def _reset_disabled_warned():
    """Reset AuthMiddleware._disabled_warned_at before each test to avoid order-dependent failures."""
    AuthMiddleware._disabled_warned_at = 0.0
    yield
    AuthMiddleware._disabled_warned_at = 0.0
```
`tests/e2e/conftest.py` should follow the same module docstring + `from __future__ import annotations` + plain `@pytest.fixture` (not autouse, unless a base_url/stub-control fixture truly needs to run for every e2e test) conventions. Per A5 (RESEARCH.md), this directory's tests must stay out of the default `pytest tests/ -q` collection used by the `test` job — either a `tests/e2e/__init__.py`-free layout invoked only via an explicit `pytest tests/e2e` path in the new `browser-e2e` job, or a pytest marker + `-m "not e2e"` exclusion added to the `test` job's existing command (`ci.yml` line 41). This repo's `[tool.pytest.ini_options]` block (`pyproject.toml`, `asyncio_mode = "auto"`) is global — Playwright's **sync** fixtures (plain `def test_...`) coexist fine with `asyncio_mode = "auto"` as long as e2e test functions are not declared `async def`.

---

### `tests/e2e/test_pill_polling.py` (test, event-driven/polling)

**Analog:** `tests/test_header_redesign.py` (existing static guard for the same bug class — read near `test_connection_pill_partial_does_not_retrigger_on_swap`) plus the two real templates that define the behavior under test:
- `triggarr/templates/partials/connection_pill.html` lines 3–6: `hx-trigger="every 30s"` (partial, on every re-render)
- `triggarr/templates/base.html` line 95: `hx-trigger="load, every 30s"` (initial-page placeholder only)

**Core pattern (from RESEARCH.md Code Examples, grounded in these two files + Playwright's official Clock API — treat as starting point, not gospel, per Open Question 1):**
```python
def test_pill_polls_on_bounded_schedule(page, base_url):
    pill_requests = []
    page.on("request", lambda req: pill_requests.append(req) if "/partials/connection-pill" in req.url else None)

    page.clock.install()
    page.goto(base_url)
    assert len(pill_requests) == 1  # the "load" trigger on base.html's placeholder

    page.clock.fast_forward("00:31")
    assert len(pill_requests) == 2  # first "every 30s" tick
    page.clock.fast_forward("00:31")
    assert len(pill_requests) == 3  # second "every 30s" tick -- D-28

    assert len(pill_requests) <= 5  # bounded, not exact (D-28)
```
**State-change mechanism (Pitfall 2, A1):** drive the connected/disconnected flip via the existing `POST /api/refresh-counts/{app}/{instance}` route (`triggarr/web/routes.py` lines 1095–1201) against the stub *arr's toggled reachability — do **not** wait on the real APScheduler `search_interval` (minutes-only, `triggarr/search/scheduler.py`). This endpoint already mutates `ist["connected"]` in place exactly like a scheduled cycle (lines 1154–1175), so invoking it from the test harness between two pill polls is reusing an already-tested code path, not inventing new app behavior.

---

### `tests/e2e/test_setup_login_logout.py` (test, request-response / browser flow)

**Analog:** `tests/test_auth_integration.py::test_full_setup_login_use_logout_flow` (lines 106–153) — **the strongest analog in this phase**: same flow, same assertions, different driving mechanism (Playwright browser vs. `TestClient`).

**Exact field names / flow to replicate as real browser interactions:**
```python
def test_full_setup_login_use_logout_flow(tmp_path: Path):
    """Complete flow: setup creates creds, login works, logout blocks access."""
    # Step 1: Unconfigured -> redirects to /setup
    resp = client.get(_PROTECTED_ROUTE, headers={"Accept": "text/html"})
    assert resp.status_code == 302
    assert "/setup" in resp.headers["location"]

    # Step 2: Complete setup
    resp = client.post(
        "/setup",
        data={"username": "admin", "password": "mypass123", "confirm_password": "mypass123"},
    )
    assert resp.status_code == 200
    assert "Account Created" in resp.text or "api-key" in resp.text.lower()
    session_cookie = resp.cookies.get("triggarr_session")
    assert session_cookie  # Setup auto-logs in
    # ... (Steps 3-7: protected access, logout -> 303 to /login, denied after logout, re-login, access again)
```
Map this 1:1 to Playwright: `page.goto("/setup")` form fields are named `username`/`password`/`confirm_password` (same names), the success state checks for "Account Created"/api-key text, the session cookie is named `triggarr_session`, `/logout` is a `POST` producing a redirect to `/login`, and a fresh request to a protected page after logout redirects to `/login` — these are the exact strings/names D-25's three flows (setup, login, logout) must assert against. The wrong-password case is covered by the login route's error branch (`triggarr/web/routes.py` lines 1619–1632, `"Invalid username or password"`).

**D-27 secrets-in-artifacts guard:** use a disposable test password distinct from any real credential (the existing test files already use literal test passwords like `"mypass123"`/`"testpass123"` — follow that convention, not a "realistic-looking" one), and configure Playwright with `tracing="retain-on-failure"` / default-off screenshots (Pitfall 4) rather than always-on capture.

---

### `pyproject.toml` — add `playwright`, `pytest-playwright` to `dev` extra (config)

**Analog:** same file, `[project.optional-dependencies]` (lines 28–33)

**Pattern to copy exactly:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=9.0.3",
    "pytest-asyncio",
    "pytailwindcss",
    "ruff",
    "playwright>=1.60",
    "pytest-playwright>=0.9",
]
```
Keep everything in the single existing `dev` extra (A4) — this repo has no separate `e2e` extra, and `uv sync --extra dev` is already the CI-wide convention (`ci.yml` lines 30, 73). Must run `uv lock` (not just `uv sync`) after this edit and commit the updated `uv.lock` in the same change (Pitfall 5) — `test`/`lint`/`dependencies` jobs all use `--locked`.

---

## Shared Patterns

### Full-SHA action pinning + per-job timeout + workflow-level read-only permissions
**Source:** `.github/workflows/ci.yml` lines 13–14, 21, 23, 25; `.github/workflows/release.yml` lines 11–12
**Apply to:** `image-smoke`, `browser-e2e`, and every new/modified step in both workflows.
```yaml
permissions:
  contents: read
# ...
    timeout-minutes: 20
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
```
No new action may be added without resolving and pinning its current full-commit SHA at implementation time (Open Question 2) — never reuse a SHA from training data or an unrelated example.

### Single point of truth for "mandatory job" membership
**Source:** `.github/scripts/release-policy.cjs` (`REQUIRED_JOBS`, line 2), `.github/scripts/ci-job-consistency.cjs` (`checkJobListConsistency`, lines 123–175), `.github/workflows/ci.yml` (`ci-ready`, lines 181–203)
**Apply to:** `.github/workflows/ci.yml`, `.github/scripts/release-policy.cjs` together, in the same change — editing `REQUIRED_JOBS` plus `ci-ready`'s `needs:` and Python `required` set is what makes CISHIP-04 true: `ci-job-consistency.test.cjs`'s existing `'real ci.yml and real REQUIRED_JOBS are consistent'` test (line 25) auto-covers the new names with zero edits to the checker itself once the three copies agree.

### Fail-closed validation: throw with a specific reason, never return a bare boolean
**Source:** `.github/scripts/release-policy.cjs::validateEvidence` (lines 4–21)
**Apply to:** `validateTagFormat`, `validateVersionIdentity`, and any new Python smoke-test assertions.
```javascript
if (!/^[a-f0-9]{40}$/.test(sha || '')) throw new Error('Invalid release commit');
```

### Download-and-verify the `audited-image` artifact, never rebuild
**Source:** `.github/workflows/ci.yml` `docker` job (lines 138–151); `.github/workflows/release.yml` `release` job (lines 79–91)
**Apply to:** `image-smoke`, `browser-e2e`, and the version-identity-label read step — all consume the same artifact; D-30/D-19 require identity verification (`sha256sum -c` + `docker image inspect --format '{{.Id}}'`) by every consumer, not just the original `docker` job.

### Wiring tests live apart from behavior tests, both against the real file text
**Source:** `.github/scripts/artifact-promotion.test.cjs` (string-position assertions), `.github/scripts/ci-job-consistency.test.cjs` (`parseJobs`/`extractCiReady`), `tests/test_github_workflows.py` (PyYAML-parsed assertions)
**Apply to:** Any new CISHIP-04/D-05 test proving a function's failure actually reaches `CI ready` or precedes publication — write it as a parse/position assertion against the literal `ci.yml`/`release.yml` text, not a reimplementation of the YAML semantics.

### Real existing auth flow is the ground truth for the browser suite
**Source:** `tests/test_auth_integration.py`, `triggarr/web/routes.py` (setup/login/logout routes), `triggarr/web/middleware.py::AuthMiddleware`
**Apply to:** `tests/e2e/test_setup_login_logout.py` — field names, cookie name (`triggarr_session`), status codes (302/303), and redirect targets must match the already-tested integration behavior exactly; the browser suite proves the same contract through a real browser, it does not get to invent new semantics.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Recorded-demonstration reproduction recipe (D-08: broken-entrypoint, pill-bug reintroduction) | config/doc | — | No existing file in this repo captures a "deliberate breakage + CI run + logs + restoration" evidence trail; `docs/owner-cli-acceptance.md` is the closest *style* analog (structured, numbered procedure + evidence capture) but is a different concern (owner approval transport, not CI-negative evidence). Planner should decide whether this lives under `docs/`, in the phase's own `.planning/phases/82-.../` verification record, or both. |
| New `image-smoke` job's container-lifecycle script, if extracted to its own file (vs. inline `run:` steps) | utility | request-response + file-I/O + event-driven | No shell-script file exists anywhere in `.github/scripts/` (all `.cjs`) or elsewhere in the repo for container orchestration — every existing CI container operation is an inline `run: |` block in `ci.yml`/`release.yml`. If the planner wants a standalone script, there is no repo convention to match; follow the inline-step style shown above instead, or introduce a new, clearly-scoped script only if step count becomes unmanageable. |
| Minimal stub *arr HTTP service's own packaging (Dockerfile or `uv run python -m ...` entry point) | config | file-I/O | No throwaway-test-service image exists in this repo today; the Dockerfile for the shipped product (`Dockerfile`, 2-stage build) is not a template for a disposable test fixture. Use the plainest option (a `uv run python -m tests.fixtures.arr_stub` process on the Docker network, per RESEARCH.md's Wave 0 Gaps) rather than inventing a second multi-stage Dockerfile. |

## Conventions

Derived repo-wide via the shared deterministic module (`gsd-tools.cjs verify conventions --derive`); scoping to `.github` or `tests` alone returned `no-app-files` (the deriver's file-classifier doesn't recognize `.cjs`/`.py` test-script files as "app files" in isolation), so the table below is the repo-wide result.

| Axis | Dominant | Share | Entropy | Status |
|------|----------|-------|---------|--------|
| File-name casing | camel | 77.4% | 0.609 | named contract |
| Identifier casing | (none — split camel/Pascal/CONSTANT) | 43.2% | 0.784 | contested hotspot |
| Export style | — | — | — | insufficient-data |
| Import style | — | — | — | insufficient-data |
| Python wildcard imports | explicit (no `import *`) | 100% | 0.0 | named contract |
| Python import relativity | absolute | 100% | 0.0 | named contract |

**Contested hotspots (author's choice):** Identifier casing is contested repo-wide (43% dominant share, high entropy) because this repo deliberately spans two consistent-but-different per-directory conventions: `bin/lib/**`-style CJS (`.github/scripts/*.cjs` here) uses `module.exports = {...}` / `require(...)` with `camelCase` function names and `UPPER_SNAKE` constants (e.g. `REQUIRED_JOBS`, `validateEvidence`), while Python under `triggarr/**`/`tests/**` uses `snake_case` functions and `PascalCase` classes/Pydantic models (e.g. `SystemStatus`, `validate_connection`). This phase's new files sit squarely on both sides of that split (`.github/scripts/release-policy.cjs` vs. `tests/e2e/*.py`) — each half is internally consistent per-directory; it is contested only when averaged across the whole repo. Match the local directory's style exactly (as all excerpts above already do) rather than trying to reconcile the two: a `.cjs` file written in `snake_case` or a Python test written in `camelCase` would be the actual convention violation, even though the repo-wide number looks "contested."

## Metadata

**Analog search scope:** `.github/workflows/`, `.github/scripts/`, `Dockerfile`, `entrypoint.sh`, `pyproject.toml`, `triggarr/web/`, `triggarr/models/`, `triggarr/clients/`, `triggarr/search/`, `triggarr/templates/`, `tests/`
**Files scanned:** 24 (listed in RESEARCH.md Sources, re-read directly during pattern mapping: `ci.yml`, `release.yml`, `release-policy.cjs` + its test, `ci-job-consistency.cjs` + its test, `artifact-promotion.test.cjs`, `Dockerfile`, `entrypoint.sh`, `pyproject.toml`, `tests/test_version.py`, `tests/test_github_workflows.py`, `tests/test_header_redesign.py`, `tests/test_auth_integration.py`, `tests/conftest.py`, `triggarr/web/routes.py`, `triggarr/web/middleware.py`, `triggarr/models/config.py`, `triggarr/clients/base.py`, `triggarr/models/arr.py`, `triggarr/templates/base.html`, `triggarr/templates/partials/connection_pill.html`, `docs/owner-cli-acceptance.md`)
**Pattern extraction date:** 2026-10-21
