# Phase 85: Follow-on CI Improvements & Acceptance Usability - Pattern Map

**Mapped:** 2026-10-26
**Files analyzed:** 27 (new + modified, across CIMAINT-01..07, ACCEPT-01..03, D-13, D-16..D-20)
**Analogs found:** 24 / 27 (3 "no close analog" items use a documented first-party pattern instead — see below)

This phase has no application code. Every file is CI/build-pipeline tooling, review-tooling hardening, or policy docs. The repo's *own* existing CI scripts/workflows are the analog set — there is nowhere else in this codebase to look, and the research confirms every pattern below is already live here. Per the stop-at-3-5-analogs rule, this map treats the ~7 already-read core files as the complete analog set and does not search further.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `Dockerfile` (prod stage, CIMAINT-01) | config (multi-stage build) | file-I/O / transform | `Dockerfile` builder stage (pinned-tool install) + `ci.yml` `dependencies` job (`uv export --locked`) | exact (same repo, same command) |
| `.github/scripts/docker-lockfile-consistency.cjs` or inline `docker` job step (CIMAINT-01 negative check) | utility (CI gate) | transform (diff) | `ci.yml` `docker` job "Audit actual image dependencies" + "Verify release image round trip" steps (lines 114–151) | role-match |
| `.github/dependabot.yml` (CIMAINT-02, NEW) | config | batch (scheduled) | none in-repo (GitHub-native feature) — pattern from `docs/ci-reference-baseline-plan.md` "Automated maintenance PRs" | no analog (first-party GitHub feature, not code) |
| `.github/scripts/os-scan-gate.cjs` (CIMAINT-03, NEW) | utility (CI gate / classifier) | transform (JSON → block/report) | `.github/scripts/ci-job-consistency.cjs` (stdlib-only Node, parse + fail-closed throw) | role-match (strong — same language/style) |
| `.github/scripts/os-scan-gate.test.cjs` (NEW) | test | unit + fixture | `.github/scripts/ci-job-consistency.test.cjs` (`mutate()` helper, one problem-string per violation) | exact (same test idiom) |
| `os-scan-exceptions.yml` (CIMAINT-03/D-10, NEW) | config (reviewed data) | batch | `review-acceptance.cjs`'s `blockers`/`dispositions` shape (`{schema:1, ...}`, fail-closed validation) | role-match (schema-versioned register pattern) |
| actionlint job in `ci.yml` (CIMAINT-04) | config (CI job) | request-response (static analysis) | `ci.yml` `secrets` job (gitleaks: unconditional, cheap, no skip logic) + `lint` job (ruff) | exact |
| os-scan job in `ci.yml` (CIMAINT-03) | config (CI job) | file-I/O (scans `audited-image` artifact) | `ci.yml` `dependencies` job (pinned `uvx` tool, `--strict` fail-closed) + `docker` job's artifact download/verify steps | exact |
| coverage step in `ci.yml` `test` job (CIMAINT-06) | config (CI step) | transform (test run → artifact) | `ci.yml` `browser-e2e` job's `set +e` / capture exit / `set -e` idiom (lines 254–269) | exact |
| `.github/workflows/ci.yml` (D-13: Node test glob) | config | request-response | existing `node --test .github/scripts/*.test.cjs` step (line 33) | exact |
| `.github/workflows/ci.yml` (CIMAINT-05: drop `python-dist` upload) | config | file-I/O | `test` job "Save built Python distributions" step (lines 52–58, to be deleted) | exact |
| `.github/workflows/release.yml` (CIMAINT-07: split `release` → `publish-images` + `create-github-release`) | controller (workflow orchestration) | request-response | same file's existing `preflight` → `release` two-job `needs:`/`outputs:` wiring (lines 14–65) | exact (split the existing pattern further) |
| `.github/workflows/release.yml` (D-14: drop `dist/*` download/upload/verify) | controller | file-I/O | same file's "Download exact successful CI Python distributions" / "Verify distribution artifacts" steps (lines 121–134, to be deleted) | exact |
| `.github/scripts/release-policy.cjs` (`REQUIRED_JOBS` gains `os-scan`; outputs for job split) | service (policy/gate logic) | CRUD (list membership) + request-response | own `REQUIRED_JOBS` array (line 3) + `preflight()`/`validateEvidence()` (lines 67–109) | exact (self-analog, extend in place) |
| `.github/scripts/release-policy.test.cjs` | test | unit | existing test file (not fully read, but same `node:test` idiom as `ci-job-consistency.test.cjs`) | exact |
| `.github/scripts/artifact-promotion.test.cjs` (CIMAINT-05: remove dist-only assertions) | test | unit (string-position ordering) | own `orderingViolations()` helper + the two dist-named assertions at lines 7–17 (to be edited, confirmed via grep) | exact (self-analog, edit in place) |
| `.github/scripts/ci-job-consistency.cjs` (ACCEPT-03/D-02: skip-condition detector) | utility (CI gate) | transform (static text analysis) | own `extractJobIf()` (lines 177–208) and `checkJobListConsistency()` (lines 120–175) — same file, new exported function | exact (self-analog, extend in place) |
| `.github/scripts/ci-job-consistency.test.cjs` (ACCEPT-03: 4 fixture cases) | test | unit + fixture | own `mutate()` helper (lines 17–24) and per-violation `test(...)` blocks (lines 26–167) | exact |
| `.github/scripts/review-machinery-lists.cjs` + `.test.cjs` (D-17, NEW) | utility (drift guard) | transform (set-equality check) | `.github/scripts/ci-job-consistency.cjs`'s `checkJobListConsistency()` — identical "three hand-kept lists must agree" shape | exact pattern reuse |
| `.github/workflows/review-acceptance.yml` (ACCEPT-02: pass PR number + head to `assess()`) | controller | request-response | own existing `script:` block (lines 28–45), already passes `head`/`currentHead`/`dispositions`/`blockers` | exact (self-analog, extend in place) |
| `.github/scripts/review-acceptance.cjs` (`assess()` keyed by `pr_number:head`) | service (acceptance gate) | CRUD (keyed register lookup) | own `assess()` function (lines 1–27) — same fail-closed throw style | exact (self-analog, extend in place) |
| `.github/scripts/review-acceptance.test.cjs` (ACCEPT-02: concurrent-fixture cases) | test | unit + fixture | own `fixture()` helper + table-driven `blocks`/`allows` loops (lines 1–29) | exact |
| `docs/os-scan-policy.md` (CIMAINT-03/D-10, NEW) | config (policy doc) | — | `docs/review-classification-policy.md` (status line + numbered policy sections) | role-match (sibling policy doc, same `docs/` home) |
| `tests/codex_review_run.py` (D-18: SIGTERM/SIGHUP, drain timeout, getpass log, `_write_evidence_copy` cleanup, `--trusted` independent check) | service (review harness) | event-driven (subprocess/signal) | own `run_command()`/`_kill_group()` (lines 106–146), `redact_local_paths()` (309–337), `_write_evidence_copy()` (347–366), `--trusted`/`--untrusted` parser (684–705) | exact (self-analog, extend in place) |
| `tests/codex_report_status.py` (D-18: hollow-report guard, docstring fix) | service (report checker) | transform (JSON report → assessment) | own `assess_report()` hollow-report block (lines 410–423) | exact (self-analog, extend in place) |
| `tests/test_codex_review_run.py` / `tests/test_codex_report_status.py` (D-18 regression tests) | test | unit | own existing test files (`FakeRunner` fixture class, `test_execute_*`, `test_cli_*` patterns) | exact |
| `.claude/plugins/planchk-router/test/planchk-router.test.mjs` (D-13: no code change, CI wiring only) | test | unit | self (already stdlib `node:test`, already passes locally) | exact (zero-edit file; `ci.yml` is what changes) |
| `docs/codex-adversarial-review-contract.md` (D-16: fallback wording) | config (policy doc) | — | own "Decide the source's trust" paragraph (line 54) and Failure-rule paragraph (line 93) which already use "wait, retry later, or approve a fallback" | exact (self-analog, extend wording in place) |
| `docs/review-checkpoint-record.md` (D-16: fallback field; ACCEPT-01 checklist reuse) | config (policy doc) | — | own "Codex" table (lines 81–93), "Rules" untrusted-PENDING bullet (127–128), "Owner acceptance checklist" (153–176) | exact |
| `docs/buildomator-greptile-pilot.md` (D-16: pilot checklist Codex precondition; D-19: register shape doc) | config (policy doc) | — | own "Activation checklist" (line 25) and register-shape lines (73, 90, 92) | exact |
| `docs/owner-cli-acceptance.md` (D-19: serialization rule; ACCEPT-01: readiness note) | config (policy doc) | — | own numbered "Procedure" list (lines 13–20) | exact |
| `docs/review-classification-policy.md` (D-01: status-line amendment; D-17: sensitive-row/list alignment) | config (policy doc) | — | own status line (line 3) | exact |
| `.planning/REQUIREMENTS.md` / `.planning/ROADMAP.md` (D-01, D-14 amendments) | config (planning doc) | — | the Phase 83 D-14 amendment pattern cited directly in CONTEXT.md D-01 | exact (named precedent) |
| `.planning/backlog/MAINTENANCE.md` (D-15: resolve/remove completed carry-forward items) | config (planning doc) | — | own existing "Phase 83 carry-forward to Phase 85" / "Quick 261026-s2v carry-forward" sections | exact |
| `pyproject.toml` (`[project.optional-dependencies].dev` gains `pytest-cov`) | config | — | own existing `dev` extras list (lines 30–36) | exact |

## Pattern Assignments

### `Dockerfile` (CIMAINT-01)

**Analog:** `Dockerfile` itself (builder-stage pinned-tool pattern) + `ci.yml`'s `dependencies` job.

**Existing pinned-tool-install pattern** (`Dockerfile` lines 1–18):
```dockerfile
FROM python:3.13-slim AS builder
ENV TAILWINDCSS_VERSION=v4.2.2
WORKDIR /build
COPY pyproject.toml .
COPY triggarr/ triggarr/
RUN pip install --no-cache-dir pytailwindcss \
    && tailwindcss_install \
    && tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --minify
```

**Existing lockfile-export pattern to mirror** (`.github/workflows/ci.yml` lines 167–179, the `dependencies` job):
```yaml
- name: Export locked production dependencies
  run: uv export --locked --no-dev --no-emit-project --no-hashes --format requirements-txt --output-file requirements-audit.txt
- name: Audit dependencies (scanner errors also fail)
  run: uvx --from pip-audit==2.10.1 pip-audit --strict --no-deps --disable-pip -r requirements-audit.txt
```

**Core pattern to add:** reuse the exact `uv export --locked --no-dev --no-emit-project --no-hashes` command inside a new Dockerfile build stage, then `pip install --no-deps -r <exported-file>` and `pip install --no-deps .` in the production stage (current line 32 is `RUN pip install --no-cache-dir .` with no `--no-deps` — this is the exact line that must change). Both `pip install` calls need `--no-deps` or the loose `[project.dependencies]` constraints in `pyproject.toml` (lines 9–22, no version pins) can silently re-resolve.

**Negative-check analog** (`ci.yml` docker job "Audit actual image dependencies" / "Verify release image round trip", lines 114–151): the existing `pip freeze --all --exclude triggarr > image-requirements.txt` step is the thing CIMAINT-01's new consistency check diffs against. Model the new `diff <(sort locked) <(sort image-requirements.txt)` step immediately after this existing step, in the same job, using the same fail-on-mismatch idiom already used by the round-trip `diff -u image-requirements.txt restored-requirements.txt` at line 151.

---

### `.github/scripts/os-scan-gate.cjs` (CIMAINT-03)

**Analog:** `.github/scripts/ci-job-consistency.cjs`

**Imports/style pattern** (ci-job-consistency.cjs is Node-stdlib-only, no `require` of any package):
```javascript
// Node stdlib only — no YAML library, no new dependency — so this stays
// installable with zero installs. (file header comment, lines 1-4)
```
No `require()` lines at all in the pure-logic file — only `module.exports` at the end (line 210):
```javascript
module.exports = {parseJobs, extractCiReady, checkJobListConsistency, extractJobIf};
```

**Core pattern — fail-closed, descriptive-problem-string classifier** (`checkJobListConsistency`, lines 120–175): the function takes a parsed input, pushes one human-readable string per violation into a `problems` array, and returns the array (empty = consistent). `os-scan-gate.cjs` should follow this exact shape: take parsed Trivy JSON + exceptions, return `{blocking: [...], reporting: [...]}` or push descriptive strings, never silently drop a finding. Note research's Pitfall 2: do **not** filter findings with `--ignore-unfixed`; the classifier must see every finding and decide block-vs-report itself, exactly like this function decides consistent-vs-not from the full parsed job graph rather than a pre-filtered one.

**Error handling pattern — throw to fail closed on structural surprises** (`extractCiReady`, lines 85–118):
```javascript
if (!job.needs || job.needs.length === 0) {
  throw new Error(`Aggregate job "${jobId}" has no "needs:"`);
}
```
Apply the same discipline to a Trivy scanner error (DB download failure, unparseable JSON): throw rather than return an empty/success-shaped result, matching D-12 and the existing `pip-audit --strict` job's fail-closed behavior (`ci.yml` line 120, `179`).

---

### `.github/scripts/os-scan-gate.test.cjs` (CIMAINT-03)

**Analog:** `.github/scripts/ci-job-consistency.test.cjs`

**Mutation-based negative-test pattern** (lines 17–24):
```javascript
function mutate(text, from, to) {
  assert.ok(text.includes(from), `expected to find ${JSON.stringify(from)} in text`);
  const result = text.replace(from, to);
  assert.notEqual(result, text, 'mutation did not change text');
  return result;
}
```
and the one-test-per-violation idiom (lines 26–35):
```javascript
test('real ci.yml and real REQUIRED_JOBS are consistent', () => {
  assert.deepEqual(checkJobListConsistency({workflowText: ciText, requiredJobs: REQUIRED_JOBS}), []);
});

test('renamed job id breaks consistency', () => {
  let mutated = mutate(ciText, '  lint:\n', '  ruff:\n');
  ...
  assert.ok(problems.length > 0);
});
```
Reuse this for the four classification cases: Critical+fix-available (blocks), Critical+no-fix (reports only), expired exception (blocks again), malformed exception entry (fails closed).

---

### `os-scan-exceptions.yml` (CIMAINT-03 / D-10)

**Analog:** `review-acceptance.cjs`'s register shapes (schema-versioned, fail-closed validated).

**Schema-versioned register pattern** (`review-acceptance.cjs` lines 4–8, and `docs/buildomator-greptile-pilot.md` lines 90/92):
```javascript
if (!blockers || blockers.schema !== 1 || !Array.isArray(blockers.open)) throw Error('Missing blocker register');
if (blockers.open.length) throw Error(`Open accepted blockers: ${blockers.open.join(', ')}`);
if (!dispositions || dispositions.schema !== 1 || typeof dispositions.items !== 'object' || dispositions.items === null) {
  throw Error('Missing finding dispositions');
}
```
Give `os-scan-exceptions.yml` the same discipline: each entry carries `id`, `package`, `reason`, `approved_by`, `expires` (per D-10), and a validator rejects — rather than silently drops — anything missing, unexpired-but-too-far-out (>30 days), or with no expiry at all, mirroring `dispositions.items[id]` requiring `head`, `decision` in `{'fixed','false_positive'}`, and 20+ chars of `evidence` (review-acceptance.cjs lines 17–23).

---

### actionlint job + os-scan job in `ci.yml` (CIMAINT-03, CIMAINT-04)

**Analog:** `ci.yml`'s `secrets` job (unconditional, no skip logic) and `dependencies` job (pinned-tool via `uvx`, fail-closed).

**Unconditional-job pattern** (`secrets` job, lines 153–165): no `if:`, no path filter, just runs every time — this is the exact shape that makes "a skip can't fake a pass" true by construction, per research Pattern 6 and CIMAINT-04's design.
```yaml
secrets:
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
      with:
        fetch-depth: 0
        persist-credentials: false
    - uses: gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7 # v2
      ...
```

**Pinned-binary-tool pattern** (`dependencies` job, lines 167–179, and Dockerfile's `pytailwindcss` install at lines 16–18): install a pinned version via a committed command, never a floating third-party Action. Apply this directly to actionlint and Trivy (per research's Pitfall 1 — do **not** add `uses: aquasecurity/trivy-action@...` or `uses: aquasecurity/setup-trivy@...`).

**Artifact-reuse pattern** (`docker` job's `audited-image` artifact, lines 122–136, and its consumers in `image-smoke`/`browser-e2e`, lines 197–207/242–252): the os-scan job must `actions/download-artifact` the same `audited-image` artifact and `sha256sum -c image.tar.sha256` before scanning — never rebuild the image.

**Required-job wiring:** new jobs join `ci-ready`'s `needs:` list (line 323) and the Python `required = {...}` set (line 333) together, exactly as `ci-job-consistency.cjs`/`.test.cjs` already enforce they must (this is the existing guard that stops a job from being silently added to one list but not the other).

---

### coverage step in `ci.yml` `test` job (CIMAINT-06)

**Analog:** `ci.yml`'s `browser-e2e` job (`set +e` / capture exit / `set -e`, lines 254–269).

**Exit-status-preserving pattern**:
```bash
set +e
uv run --no-sync pytest tests/e2e -q ... --junitxml e2e-credential.xml
credential_status=$?
uv run --no-sync pytest tests/e2e -q ... --junitxml e2e-pages.xml
pages_status=$?
set -e
if [ "$credential_status" -ne 0 ] || [ "$pages_status" -ne 0 ]; then
  echo "Browser regression suite failed: ..." >&2
  exit 1
fi
```
Apply identically to the `test` job's pytest invocation: add `--cov=triggarr --cov-branch --cov-report=xml:coverage.xml` to the existing `uv run --no-sync pytest tests/ -q --junitxml=test-results.xml` (line 41), capture `$?` under `set +e`/`set -e`, and re-assert failure explicitly — coverage collection must never mask a real test failure.

**Artifact-upload pattern** (`test` job "Upload test evidence", lines 43–50):
```yaml
- name: Upload test evidence
  if: always()
  uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
  with:
    name: test-results
    path: test-results.xml
    if-no-files-found: error
    retention-days: 14
```
Reuse this exact shape for `coverage.xml` + a new `coverage-provenance.json` (naming `github.event.pull_request.head.sha` vs. `github.sha` explicitly, per research Pitfall 4), with `if-no-files-found: error` so a missing coverage file fails loudly rather than silently.

---

### `.github/workflows/release.yml` split (CIMAINT-07)

**Analog:** the file's own existing `preflight` → `release` two-job pattern (lines 14–65).

**Scoped-permissions + outputs pattern already live here**:
```yaml
preflight:
  permissions:
    contents: read
    actions: read
  outputs:
    sha: ${{ steps.policy.outputs.sha }}
  steps:
    - uses: actions/checkout@... # sparse-checkout: .github/scripts
    - uses: actions/github-script@...
      id: policy
      with:
        script: |
          const {preflight} = require('./.github/scripts/release-policy.cjs');
          await preflight({github, context, core});

release:
  needs: preflight
  permissions:
    packages: write
    contents: write
    actions: read
```
Split `release` into `publish-images` (`permissions: {contents: read, packages: write, actions: read}`, everything through "Publish audited image without rebuilding", line 176–184) and `create-github-release` (`needs: [preflight, publish-images]`, `permissions: {contents: write}` only, just the "Create GitHub Release" step, lines 186–201, gated `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')` exactly as today). This is the identical `needs:`/`outputs:`/scoped-`permissions:` shape the file already demonstrates one level up — not a new mechanism.

**D-14 interaction:** the "Download exact successful CI Python distributions" / "Verify distribution artifacts before any publication" steps (lines 121–134) and the `dist/*` args in "Create GitHub Release" (lines 193–200) are deleted. `.github/scripts/artifact-promotion.test.cjs`'s `'both exact-run artifacts are downloaded...'` test (lines 7–17) asserts exactly 2 `run-id:` occurrences and both dist-only step names — **this test must be edited in the same change**, not left to fail or silently pass on stale assertions.

---

### `.github/scripts/release-policy.cjs` (`REQUIRED_JOBS`, job-split support)

**Analog:** itself — extend in place.

```javascript
const REQUIRED_JOBS = ['test', 'lint', 'docker', 'secrets', 'dependencies', 'image-smoke', 'browser-e2e', 'CI ready'];
```
Add `'os-scan'` (and `'actionlint'` if made a named-required entry) to this array, and to `ci.yml`'s `needs:`/Python-`required` sets in lockstep — `ci-job-consistency.test.cjs`'s existing tests (e.g. "extra job only in REQUIRED_JOBS breaks consistency", lines 45–48) already fail the build if these three copies drift, so no new test is strictly needed for *that* drift, only for the new skip-condition detector (ACCEPT-03/D-02).

`validateEvidence()`'s per-job existence check (lines 77–82) is the pattern the release job split must keep satisfying:
```javascript
for (const name of REQUIRED_JOBS) {
  const job = jobs.find(j => j.name === name && j.run_id === run.id);
  if (!job || job.status !== 'completed' || job.conclusion !== 'success') {
    throw new Error(`Required CI job missing or unsuccessful: ${name}`);
  }
}
```

---

### `.github/scripts/ci-job-consistency.cjs` — skip-condition detector (ACCEPT-03 / D-02)

**Analog:** itself — `extractJobIf()` (lines 177–208) already extracts and normalizes a job's `if:` condition (single-line or folded `>-`/`|` block). D-02's new detector is a sibling function that scans every mandatory job's raw `lines` (already captured by `parseJobs()`, lines 32–79) for `paths-ignore`, a path `filter:`, or any other per-job skip condition, and fails if found on a job in `REQUIRED_JOBS`. Build it the same way `checkJobListConsistency` is built: parse once with `parseJobs`, then push a descriptive problem string per offending job.

**Fixture-diff testing approach (D-02):** feed the four fixture diffs (ordinary-docs, sensitive-docs, mixed, misclassified) as literal workflow-YAML strings into this same function — the same entry point CI invokes — exactly as `ci-job-consistency.test.cjs` already does with inline `mutate(ciText, ...)` calls rather than separate files on disk (see "extra job only in ci-ready needs breaks consistency", lines 37–43, which builds a whole fake job inline).

---

### `.github/scripts/review-machinery-lists.cjs` (D-17, drift guard)

**Analog:** `.github/scripts/ci-job-consistency.cjs`'s `checkJobListConsistency()` — same three-lists-must-agree shape, just different source lists (the classification policy's sensitive row in `docs/review-classification-policy.md`, the Codex scope exclusions, the acceptance-prerequisite list in `docs/review-checkpoint-record.md`'s "Owner acceptance checklist"). Reuse the exact `findDuplicates()`/problems-array/`module.exports` idiom (lines 17–25, 210).

---

### `.github/scripts/review-acceptance.cjs` — PR+head keying (ACCEPT-02 / D-19)

**Analog:** itself — extend `assess()` in place.

**Current flat-register shape to change** (lines 1–8):
```javascript
function assess({head, currentHead, checks, comments, dispositions, blockers}) {
  if (!/^[0-9a-f]{40}$/.test(head || '') || currentHead !== head) throw Error('PR head changed; approval is stale');
  if (!blockers || blockers.schema !== 1 || !Array.isArray(blockers.open)) throw Error('Missing blocker register');
  ...
```
Add a `prNumber` parameter and look up only `register.by_pr_head[`${prNumber}:${head}`]` (per research Pattern 9), so one PR's `gh variable set` (a whole-value overwrite, confirmed via direct read of `review-acceptance.yml`) cannot erase another PR's slice. Keep every existing fail-closed check (`schema !== 1`, missing register, stale head) unchanged — only the top-level lookup becomes keyed.

**Workflow wiring to extend** (`review-acceptance.yml` lines 28–45): `context.payload.pull_request.number` is already available in this script block (`eventPR.number`, line 36) — pass it through to `assess()` alongside `head`.

**Concurrent-fixture test pattern** (`review-acceptance.test.cjs` lines 4–8, table-driven `blocks`/`allows` loops at lines 11–29): add a case that builds two fixtures for PR A (`head: 'a'*40`) and PR B (`head: 'b'*40`), asserts `assess()` on A's slice is unaffected after B's slice is written — the same `fixture()`-clone-and-mutate idiom already used for every other case in this file.

---

### `tests/codex_review_run.py` (D-18 hardening)

**Analog:** itself — extend each function in place; this is the single most code-dense cluster in the phase.

**SIGTERM/SIGHUP handling — analog is the existing `BaseException` cleanup path** (`run_command`, lines 128–146):
```python
with subprocess.Popen(argv, start_new_session=True, **kwargs) as proc:
    try:
        stdout, stderr = proc.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_group(proc)
        exc.stdout, exc.stderr = proc.communicate()
        raise
    except BaseException:
        _kill_group(proc)
        proc.wait()
        raise
```
and `_kill_group` itself (lines 106–109):
```python
def _kill_group(proc: subprocess.Popen) -> None:
    # ProcessLookupError: the whole group has already exited.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
```
Register `signal.signal(signal.SIGTERM, handler)`/`SIGHUP` near the top of `main()` (lines 715–741) that calls the same `_kill_group`-style cleanup on whatever `Popen` is currently tracked (module-level or a `contextvars` reference), then re-raises/exits — reusing `_kill_group`'s exact suppress-`ProcessLookupError` idiom rather than inventing a new one.

**Post-kill drain timeout — analog is the existing `TimeoutExpired` branch itself** (line 137, `exc.stdout, exc.stderr = proc.communicate()` with no timeout): add a short bounded `timeout=` to that specific call and fall back to partial output / a drain-timed-out marker on a second `TimeoutExpired`, following the same `except subprocess.TimeoutExpired` idiom used one level up.

**`getpass.getuser()` silent-swallow fix — analog is `redact_local_paths`'s own surrounding `try`/`except` style** (lines 329–332):
```python
try:
    user = getpass.getuser()
except (KeyError, OSError):
    user = ""
```
This file's module docstring already establishes "plain `print()`, not loguru" as its logging convention (per research's Code Examples section) — add `print(f"warning: getpass.getuser() failed ...")` in the `except` body, matching `RunnerError`'s own plain-words style (line 149: `"""A failure the CLI reports in plain words, without a traceback."""`).

**`_write_evidence_copy` directory-leak fix — analog is the function's own `lexists` precondition** (lines 347–366):
```python
if os.path.lexists(directory):
    raise RunnerError(f"the reviewed tree already contains {relative_dir}; refusing to write evidence into it")
try:
    directory.mkdir()
    fd = os.open(worktree / EVIDENCE_RELPATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
except OSError as exc:
    raise RunnerError(f"could not create the evidence copy in the worktree: {type(exc).__name__}") from exc
```
Wrap the `mkdir()`/`os.open()` pair's `except OSError` with `contextlib.suppress(OSError): directory.rmdir()` before re-raising — `contextlib` is already imported (line 42) and already used elsewhere in this file (`_kill_group`), so this is reusing an existing import/idiom, not adding one.

**`--trusted` independent verification — analog is the existing mutually-exclusive flag parser** (lines 693–705):
```python
trust = parser.add_mutually_exclusive_group(required=True)
trust.add_argument("--trusted", dest="trusted", action="store_true", ...)
trust.add_argument("--untrusted", dest="trusted", action="store_false", ...)
```
and the refusal path in `main()` (lines 724–726):
```python
if not run.trusted:
    print(f"error: {UNTRUSTED_REFUSAL}")
    return 2
```
D-18's SA-01 fix adds an independent check (e.g. `gh pr view <N> --json headRepositoryOwner,authorAssociation` via the same `run_command`/subprocess pattern already used for `git`/`codex`/`pytest` invocations in this file) that can override an operator-supplied `--trusted` to `False` when the PR is actually from a fork or `dependabot[bot]` — reuse `run_command`'s existing `CommandRunner` injection point (already used for testability per `FakeRunner` in the test file) rather than calling `subprocess` directly inline.

---

### `tests/codex_report_status.py` (D-18 hollow-report guard)

**Analog:** itself — `assess_report()`'s existing hollow-report block (lines 410–423):
```python
commands = report.get("commands_run")
if isinstance(commands, list) and not any(
    isinstance(entry, dict) and _non_blank(entry.get("command")) for entry in commands
):
    reasons.append("no commands run: the report gives no evidence the diff was inspected")
```
Extend the `any(...)` predicate to additionally require `entry.get("exit_code") is not None`, following the exact `reasons.append(...)` + `isinstance`/`_non_blank` idiom already used three lines above for the `coverage` list check (lines 412–417). `_non_blank()` (already defined at line 223 per the earlier grep) is the existing helper to reuse, not reimplement.

---

### `tests/test_codex_review_run.py` / `tests/test_codex_report_status.py` (D-18 regression tests)

**Analog:** the existing test files' own fixtures — `FakeRunner` class (line 391) and table-driven `test_execute_*`/`test_cli_*` functions (lines 395–600+) already exercise `run_command`, `--trusted`/`--untrusted`, and evidence-writing paths. Each D-18 sub-item gets one new `test_*` function following this file's existing naming (`test_<subject>_<behavior>`) and fixture style, not a new test framework or file layout.

---

### `.claude/plugins/planchk-router/test/planchk-router.test.mjs` (D-13 — CI wiring only)

**Analog:** `ci.yml`'s existing Node test step (line 33):
```yaml
- name: Test release safety policy
  run: node --test .github/scripts/*.test.cjs
```
Per research Pitfall 6, `node --test <dir>/` does not recurse on this runner's Node version — extend the existing line with an explicit second path/glob rather than a directory:
```yaml
run: node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs
```
The test file itself (already using `node:test`/`node:assert/strict`, confirmed stdlib-only at lines 1–16) needs no code changes — this is purely a one-line `ci.yml` edit.

---

### Policy docs (D-01, D-16, D-19, D-20) — `docs/*.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`

**Analog:** the Phase 83 D-14 amendment, explicitly cited in CONTEXT.md D-01 as "the pattern" to follow — a short, dated, named-decision amendment to the requirement/criterion text rather than a rewrite. Within each doc, match its existing structure:
- `docs/review-classification-policy.md` line 3's single status sentence (`"Status: active from Phase 83 (v2.13). Instruction-enforced: GitHub does not yet check it (Phase 85, ACCEPT-03)."`) — edit this exact sentence once ACCEPT-03 resolves to "no new mechanism" (D-01), don't add a parallel paragraph elsewhere.
- `docs/codex-adversarial-review-contract.md` already states the fallback vocabulary verbatim at lines 54 and 93 (`"wait, retry later, or approve a fallback"`) — D-16 adds the *definition* of "owner-approved fallback" next to this existing sentence, and `docs/review-checkpoint-record.md`'s "Rules" section (line 128) already cross-references this contract — add the new checkpoint-record field (e.g. a "Fallback" row) next to its existing "Codex" table (lines 81–93), following that table's own `| Field | Value |` shape.
- `docs/owner-cli-acceptance.md`'s numbered "Procedure" list (lines 13–20) is where ACCEPT-01's "prerequisites visible in one place" and ACCEPT-02's serialization rule both attach — step 1 (line 13) already enumerates CI/Greptile/Codex/dispositions as prerequisites; extend this step's prose rather than adding a new numbered step, consistent with D-20's "don't build a new orchestrator."
- `docs/review-checkpoint-record.md`'s "Owner acceptance checklist" (lines 153–176) is the existing D-12 (Phase 83) template ACCEPT-01 builds on, per CONTEXT.md D-20 — this is the literal analog, not a new design.

---

## Shared Patterns

### Stdlib-only Node test/gate scripts
**Source:** `.github/scripts/ci-job-consistency.cjs` + `.test.cjs`
**Apply to:** `os-scan-gate.cjs`, `review-machinery-lists.cjs`, and every extension to `release-policy.cjs`/`review-acceptance.cjs`.
```javascript
// No YAML library, no new dependency — stays installable with zero installs.
// Throw to fail closed on anything structurally unexpected; return an array
// of human-readable problem strings (empty = consistent) for everything else.
```

### Fail-closed scanner/auditor pattern
**Source:** `ci.yml` `dependencies` job, "Audit dependencies (scanner errors also fail)" (line 178) and `pip-audit --strict` (lines 120, 179)
**Apply to:** the new Trivy os-scan step and `os-scan-gate.cjs`'s handling of DB-download/parse failures (D-12).
```yaml
- name: Audit dependencies (scanner errors also fail)
  run: uvx --from pip-audit==2.10.1 pip-audit --strict --no-deps --disable-pip -r requirements-audit.txt
```

### Pinned-binary install, never a wrapper Action
**Source:** `Dockerfile` lines 9–18 (`pytailwindcss`) and `ci.yml`'s `uvx --from pip-audit==2.10.1 ...`
**Apply to:** actionlint and Trivy CLI installs (CIMAINT-03/CIMAINT-04) — explicitly never `aquasecurity/trivy-action`/`setup-trivy` (compromised March 2026, CVE-2026-33634).

### Exit-status-preserving test/coverage runs
**Source:** `ci.yml` `browser-e2e` job, lines 254–269
**Apply to:** the new coverage-collecting step in the `test` job (CIMAINT-06) — `set +e` / capture `$?` / `set -e` / explicit re-check, never let a wrapping tool mask a real failure.

### Exact-artifact promotion (never rebuild after test)
**Source:** `ci.yml` `docker` job's `audited-image` artifact (lines 122–136) + `release.yml`'s `actions/download-artifact` with `run-id: ${{ steps.recheck.outputs.run_id }}` (lines 87–93)
**Apply to:** the os-scan job (scans the saved `image.tar`, never rebuilds) and the split `publish-images` job (still tags/pushes the same downloaded, re-verified tarball).

### Schema-versioned, fail-closed registers
**Source:** `.github/scripts/review-acceptance.cjs` lines 1–8 (`blockers.schema !== 1`, `dispositions.schema !== 1`)
**Apply to:** `os-scan-exceptions.yml`'s validator and the PR+head-keyed acceptance register (ACCEPT-02).

### Full-SHA Action pinning with version comment
**Source:** every `uses:` line in `ci.yml`/`release.yml` (e.g. `actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6`)
**Apply to:** any new `uses:` line this phase adds (there should be none for Trivy/actionlint themselves, per the pinned-binary pattern above, but `actions/checkout`/`actions/download-artifact` reuse in new jobs must keep this convention).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/dependabot.yml` | config | batch | Pure GitHub-native feature (no code in this repo configures or consumes it); pattern comes from `docs/ci-reference-baseline-plan.md`'s "Automated maintenance PRs" section and the research's verified `groups`/`cooldown`/`applies-to` semantics, not from an existing file. |
| `docs/os-scan-policy.md` | config (policy doc) | — | No prior "build-pipeline" policy doc exists in `docs/`; styled after the sibling `docs/review-classification-policy.md`'s status-line convention, but there is no pre-existing scanning-policy doc to call a true analog. |
| Trivy's generated `.trivyignore.yaml` | config (CI-generated, not committed) | transform | Generated at CI time from `os-scan-exceptions.yml`; not a repo file, so it has no analog to map — only `os-scan-exceptions.yml` (the committed source of truth) is a real file in this phase. |

## Conventions

Derived via the shared `gsd-tools.cjs verify conventions --derive` module (repo-wide; `.github/scripts` alone returned `no-app-files` and is excluded from these counts since its `.cjs` config scripts aren't classified as "app files" by the tool):

| Axis | Dominant | Share | Entropy | Status |
|---|---|---|---|---|
| File-name casing | camelCase | 77.4% | 0.609 | Named contract (≥70%) |
| Identifier casing | — (mixed camel/Pascal) | 43.2% | 0.784 | Contested hotspot (<70%) |
| Export style | — | — | — | Insufficient data (repo-wide sample has no qualifying export sites) |
| Import style | — | — | — | Insufficient data (same) |
| Python wildcard imports | explicit (no `import *`) | 100% | 0.0 | Named contract |
| Python import relativity | absolute | 100% | 0.0 | Named contract |

Identifier casing is contested repo-wide (camelCase 95, PascalCase 94, CONSTANT_CASE 22, other 9) because JS object fields/functions (`checkJobListConsistency`, `releaseIdentityGate`) sit alongside Python classes (`ReviewRun`, `RunnerError`, `Assessment`) and module-level constants (`REQUIRED_JOBS`, `EVIDENCE_RELPATH`, `CODEX_TIMEOUT_SECONDS`). This repo's own `.cjs` scripts and `.py` harness files are each internally consistent (camelCase functions in `.cjs`, PascalCase classes + CONSTANT_CASE module constants in `.py`); the contest only appears when counted across both languages at once.

**Contested hotspots (author's choice).** The reference pattern for a contested-but-locally-consistent split is the GSD tool's own CJS↔SDK dual resolver (`bin/lib/**` is CJS `module.exports`/`require`; `sdk/src/**` is ESM `export`/`import`) — each half is internally consistent per directory, contested only when compared repo-wide. Treat Triggarr's `.cjs`/`.py` identifier-casing split the same way: new code in `.github/scripts/*.cjs` matches that directory's existing camelCase-function / `module.exports` style; new code in `tests/*.py` matches that directory's existing PascalCase-class / CONSTANT_CASE-constant / `from __future__ import annotations` style. Do not force one casing convention across the CJS/Python boundary this phase straddles — match the file's own directory, not a repo-wide average.

## Metadata

**Analog search scope:** `.github/workflows/`, `.github/scripts/`, `Dockerfile`, `pyproject.toml`, `tests/codex_review_run.py`, `tests/codex_report_status.py`, `.claude/plugins/planchk-router/test/`, `docs/*.md` (review/acceptance/policy docs), `.planning/backlog/MAINTENANCE.md` — the complete set of CI/review-tooling files in this repository. No `.claude/skills/` content exists in this repo beyond an unrelated `aidesigner-frontend` placeholder directory, so no skill rules were loaded.
**Files scanned:** ~20 files read directly (workflows, scripts, Dockerfile, pyproject.toml, Python harness, docs); `gsd-tools.cjs verify conventions --derive` scanned the full repo tree for the Conventions section.
**Pattern extraction date:** 2026-10-26

---

*Phase: 85-follow-on-ci-improvements-acceptance-usability*
