# Phase 82: CI Tests What We Ship - Context

**Gathered:** 2026-10-21
**Status:** Ready for planning

<domain>
## Phase Boundary

CI proves the exact artifact it will publish actually works. Three new mandatory checks are added and joined to the existing required gate:

1. **Shipped-image startup smoke test** (CISHIP-01): the saved, audited publish-candidate image is started through its normal entrypoint with isolated config and test services. The test verifies health, setup/login, static assets, writable config and persistence across a restart.
2. **Browser regression suite** (CISHIP-02): the connection-pill request loop, plus first-run setup, login (valid and wrong password) and logout, all asserted as observable behavior.
3. **Release-version identity** (CISHIP-03): before any version-tag publication, the tag, package version and audited image version label must agree.

All new jobs feed `CI ready` together with the consistency checks (CISHIP-04). The published image stays the tested, audited artifact and is never rebuilt.

Out of this phase: the docs/planning-only CI exemption (Phase 85, ACCEPT-03), lockfile-matched Docker deps, OS-image audit, actionlint, coverage artifacts, and publish-permission narrowing (Phase 85, CIMAINT-*). Also out: pre-release tag support and a password-reset browser flow (deferred).

</domain>

<decisions>
## Implementation Decisions

### Broken-case proof (evidence standard)
- **D-01:** The approach is hybrid. Cheap negative tests are permanent and run in the CI job they apply to: version/tag mismatch and malformed tags, a missing static asset, and the related wiring checks. The expensive negative, a deliberately broken-entrypoint image, is demonstrated and recorded rather than rebuilt on every run.
- **D-02:** The connection-pill browser test continuously asserts correct behavior on every run. Reintroducing the polling bug is a *recorded sensitivity check*, not a second browser run on every CI run.
- **D-03:** A negative-test harness passes **only when it observes the expected, specific rejection**, never on any failure. Each negative case asserts the failure reason.
- **D-04:** Permanent negative tests feed deliberately invalid input into the **same script or function CI actually invokes** (the pattern the existing `.github/scripts/*.test.cjs` release-policy tests use) and assert the specific rejection. They must not duplicate the validation logic. Test inputs and expected outcomes stay independent of the implementation.
- **D-05:** CI wiring is verified separately from function behavior. Testing a function does not prove that the workflow invokes it or that its failure reaches `CI ready`. Extend the existing job-consistency / workflow tests to cover the wiring.
- **D-06:** Every recorded demonstration (broken entrypoint, pill-bug reintroduction, and any other one-time negative) captures:
  - the exact broken commit and the minimal deliberate mutation
  - the command run and the expected failure
  - the actual failure, and the CI run/job with logs showing it failed **for the intended reason**
  - confirmation that `CI ready` also rejects it and publication cannot proceed
  - the restored final commit and its successful applicable checks
- **D-07:** Claims that GitHub's gate enforces a check require a real GitHub CI run, on an isolated test branch or draft PR with publication prevented, never a production tag. Local evidence is acceptable only for narrowly stated claims such as "this startup probe detects a broken entrypoint". Local evidence can never prove that the required gate enforces the result.
- **D-08:** The reproduction recipe for each demonstration lives in the repository. Durable evidence goes in the phase verification records, not only in expiring Actions logs or artifacts.
- **D-09:** Repeat the broken-entrypoint demonstration whenever the Dockerfile, the entrypoint, the startup probe or the related CI wiring changes.
- **D-10:** This evidence standard **does not authorize pushing deliberate breakage.** Each push of a deliberately broken commit or branch needs the owner's separate, explicit go-ahead at execution time.

### CI time budget and run policy
- **D-11:** Both the startup smoke test and the browser suite are required: they feed `CI ready`, and a failure blocks merge. This applies to code, runtime, dependency and relevant CI/control PRs.
- **D-12:** An ordinary planning/docs-only PR may later take an explicitly verified exemption path. That path is **not built in this phase** (it is Phase 85, ACCEPT-03). Until it is implemented and verified, the existing required-check behavior stays exactly as it is, so every new job runs on every PR. An unexplained skipped job must never count as success.
- **D-13:** On a push to main and on release, both checks run against the exact publish-candidate image before publication. PR results alone don't establish that artifact's readiness. This depends on CI's existing main-push run and the release policy's `REQUIRED_JOBS`.
- **D-14:** The budget is a target of **about 5 minutes added PR wall-clock time**, not a proven estimate. Measure the added critical-path time against the current CI baseline, including image download/load and browser setup, and parallelize where practical. If the added time exceeds 5 minutes, investigate and report the tradeoff to the owner before expanding the budget. Never remove required assertions or weaken failure handling to hit the target.
- **D-15:** Browser tests get **no automatic retries** that turn a failure into a pass. Keep logs, screenshots and browser traces from the *first* failure. A diagnostic rerun may help investigation, but a later pass alone doesn't resolve a failure.
- **D-16:** Fix flaky tests or the application; never remove required coverage to get CI green. A temporary quarantine needs explicit owner approval, a tracked issue, and either equivalent coverage or a clearly recorded acceptance gap.

### Release tag rules
- **D-17:** Before publication, the tag (without its leading `v`), the `pyproject.toml` version and the exact audited image's `org.opencontainers.image.version` label must all agree. A missing or malformed value fails closed.
- **D-18:** `__version__` and the root package version in `uv.lock` are covered by the existing `tests/test_version.py`, which runs in the `test` job. `release-policy.cjs` `REQUIRED_JOBS` already requires that job on the exact release commit. This was confirmed during discussion; the planner re-confirms it and keeps it mandatory.
- **D-19:** Keep the existing image revision and digest/ID identity checks. A matching version label alone doesn't prove artifact identity.
- **D-20:** CHANGELOG completeness stays a release-review item and is **not** part of this identity gate.
- **D-21:** Only stable `vX.Y.Z` tags publish. The full string must match, with nonnegative integers and no leading zeros except `0` itself. Reject malformed tags, pre-release suffixes and build metadata before any publication. Tag format alone doesn't protect `:latest`: the existing commit eligibility, version agreement and exact-artifact checks must still pass.
- **D-22:** On mismatch, fail loudly and publish nothing. **Leave the git tag untouched**: deleting it is an explicit owner action, and CI gets no tag-write permission for it.
- **D-23:** The rejection message reports the reason and the tag, package and image versions available at that point. If validation stops before the image is inspected, report "not inspected" rather than inventing a value.
- **D-24:** Verify the rejection happens before registry login, image push, GitHub Release creation or release-asset upload. Keep the failed run and its diagnostic evidence.

### Browser suite scope
- **D-25:** The suite covers three flows:
  - **First-run setup:** fresh isolated config → setup → create admin → dashboard. Afterward, setup is no longer available.
  - **Login:** a wrong password leaves protected pages inaccessible; valid credentials reach the dashboard.
  - **Logout:** ends the browser session; a fresh request to a protected page redirects to login.
- **D-26:** The password-reset browser flow is deferred and keeps its existing unit/integration coverage.
- **D-27:** Use disposable test credentials only. Passwords, cookies, session values and tokens must not appear in captured artifacts: screenshots, traces, logs or HAR files.
- **D-28:** The connection-pill test watches the initial load and **at least two scheduled refreshes**. It asserts:
  - requests stay bounded, with no request loop
  - polling continues on schedule
  - the refreshed response actually updates the pill (so the test services must be able to change reported state between polls)

  Use a bounded range with timing tolerance, never an exact count at a fragile deadline.
- **D-29:** If the 30s interval is shortened for the test, change **only the timing**, never the htmx `hx-trigger`/`hx-swap` behavior under test. Demonstrate that both the original request-loop bug (`load, every 30s` re-triggering on the outerHTML swap) and disabled polling make the test fail.
- **D-30:** The browser suite runs against the **shipped image**: the exact saved CI artifact intended for publication, verified by image identity against `image-id.txt` and the sha256. It uses a fresh container with isolated writable config and test services, the normal entrypoint and packaged assets, no source mounts and no rebuild. It may use a separate container from the smoke test for isolation, but both must use the same image artifact.

### Release identity evidence (owner decision, 2026-10-21)
- **D-31:** The owner accepts bounded CISHIP-03 evidence on these conditions:
  - (a) **Rehearsal fidelity.** The CI rehearsal calls the exact same validation entry points `release.yml` uses (`parseReleaseTag` and `releaseIdentityGate` from `release-policy.cjs`), not a re-implementation, against the exact saved/audited publish-candidate image (same image ID as the `audited-image` artifact's `image-id.txt`). It covers four input cases: matching, mismatched, malformed and missing version inputs. Each negative case asserts its specific rejection reason.
  - (b) **Wiring means blocking, not ordering.** Wiring tests must show a rejection blocks every publication path: registry login (`docker/login-action`), image push/promotion and GitHub Release creation. No `always()`, `cancelled()`/`!cancelled()`, `failure()` or `continue-on-error` bypass; the gate is in the same job before them, or a downstream publishing job `needs:` it; no other publication path in `release.yml` skips it. Tests must fail if someone adds a bypass.
  - (c) **Evidence record.** Evidence records the commit identities defined in D-34 (PR head SHA, PR base SHA, tested SHA, image revision label), image identity (image ID / tarball sha256), the CI run URL, run ID and attempt, and the expected rejection reason for each negative case. (Amended by D-34, 2026-10-21: "exact commit SHA" means the tested SHA for CI evidence, reconciled against the PR head.)
  - (d) **Limitation wording**, recorded verbatim: "Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release."
  - (e) **Evidence standard.** Permanent negative tests may produce a green CI run by correctly detecting the expected failures. A deliberately red tag-triggered run is **not** required and is not performed. The deliberately broken draft-PR demonstrations for the entrypoint and the pill stay as planned, each push still needing the owner's go-ahead (D-10).

### Evidence and checkpoint corrections (owner review of 4ca7c23, 2026-10-21)
- **D-32:** Two kinds of pill-regression evidence are kept apart.
  - (i) **Browser sensitivity evidence**: the real browser suite (same `tests/e2e` files, same harness, same CI flags) fails on each mutation (request loop, polling disabled). It runs against variant images built `FROM` the exact audited CI image of the phase head, where the only change is the pill template file(s), verified by a file-manifest diff. This runs on the maintainer machine in a clearly labelled demonstration setting (`triggarr-demo:*` tags, scratch directory, never pushed or published). That is a narrow claim, which D-07 allows locally. Reason: the existing header unit tests (`tests/test_header_redesign.py`) reject both mutations in the `test` job, and `docker` needs `test`, so a pushed mutation never reaches `browser-e2e`. Reaching it on GitHub would need a new or altered workflow, which counts as a CI bypass.
  - (ii) **Aggregate-gate enforcement evidence**: on isolated draft PRs (owner go-ahead before each push, D-10), the broken entrypoint fails `image-smoke`. The pill mutations fail the `test` job through the existing header tests, so `docker`, `image-smoke` and `browser-e2e` are skipped. In every case `CI ready` stays red. The unit-test catch is legitimate gate evidence and is labelled as such, not as browser evidence.
  - The header tests are never weakened, skipped or deleted. No CI bypass. Never main, never a production tag.
- **D-33:** Screenshot and trace safety is achieved by prevention, not detection. Tests that render credential or API-key pages (setup/registration, login, logout) are marked `credential_pages` and run with tracing, screenshots and video off. A conftest guard refuses to run them with any capture enabled. Captured tests authenticate by injecting a session cookie obtained over HTTP and visit only pages that show no credential or API key. A probe in which setup fails *before* the API key is registered must leave no capture holding it. Byte scanning of artifacts stays as an extra defence only. It is not proof that screenshots are safe, because pixels cannot be byte-searched.
- **D-34:** Evidence records commit identities as separate fields:
  - PR head SHA
  - PR base SHA
  - tested SHA (`github.sha`, which equals the checkout HEAD; on `pull_request` this can be GitHub's synthetic merge commit)
  - image revision label (`org.opencontainers.image.revision`)
  - image ID / tarball sha256

  CI evidence (smoke, browser, rehearsal) is tied to the tested SHA. Review evidence (Greptile, vibe-check, owner acceptance) is tied to the PR head and base. Every record includes an explicit reconciliation line explaining any difference between the head and the tested SHA. Example: the tested SHA is the merge of head H into base B, verified through the merge commit's parents. This amends D-31(c).
- **D-35:** Checkpoints follow `docs/buildomator-greptile-pilot.md` and `docs/owner-cli-acceptance.md`, with three distinct activities that are never merged into one stop:
  - (1) **Budget/CI-minutes review**: stops only when D-14's ~5-minute threshold is exceeded.
  - (2) **Technical review**: the `/deep-review` offer is settled *before* the push as its own step. Greptile reviews the pushed head automatically. The owner may run vibe-check in parallel on the same head SHA. There is no pause after every push.
  - (3) **Exact-commit owner acceptance** through the `review-acceptance` environment, on the final phase head. It happens after CI, the current Greptile review, any vibe-check and the dispositions are complete, outside Plans 08/09.

  The only stops in Plans 08/09 are: the pre-push deep-review decision, a D-14 budget overrun, and the D-10 go-ahead before each deliberately broken push.

### Claude's Discretion
- Browser tool choice. Playwright is expected, added as a dev/CI dependency without changing the runtime image.
- How timing is shortened for the pill test. Prefer browser-side clock control (for example Playwright's clock API) over adding a new runtime config knob to the app. A new runtime setting would be a product change and needs owner approval.
- Design of the fake *arr test services: a minimal stub HTTP service that answers the endpoints startup and health need, with switchable connected/disconnected state.
- Job layout: separate jobs vs. steps, how the saved `audited-image` artifact is shared between the smoke and browser jobs, and the restart/persistence mechanics.
- Where the tag/version check lives inside the release preflight path, and how it reads the audited image label before any login or push.
- How the missing-static-asset negative is constructed as a cheap permanent test without a second full image build.

</decisions>

<specifics>
## Specific Ideas

- Shipped image means the saved `audited-image` artifact (image.tar plus sha256 plus image-id.txt) produced by the `docker` job. Verify identity before using it, the same way the release job does.
- The pill regression is the PR #27 fix (`d41b484`): `hx-trigger="load, every 30s"` became `"every 30s"` in `triggarr/templates/partials/connection_pill.html`. Today's guard in `tests/test_header_redesign.py` is a template-text check, and the browser test adds the behavioral guarantee.
- The existing pip-freeze step overrides the entrypoint (`--entrypoint python`), so it proves nothing about startup. The new smoke test must use the real `ENTRYPOINT ["/entrypoint.sh"]` (PUID/PGID handling, setpriv drop) and the image HEALTHCHECK/`/health`.
- Persistence across restart means config and state written to the isolated `/config` volume survive a `docker stop`/`start` (or a new container on the same volume). The admin account created in setup still works afterward.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md`: CISHIP-01..04, the milestone standing rules (positive and negative evidence, GitHub- vs instruction-enforced, docs-only policy timing), and the Out of Scope table (no rebuild-after-test, no registry writes in PR tests, no weakening CI/pinning)
- `.planning/ROADMAP.md` §"Phase 82: CI Tests What We Ship": goal and the four success criteria
- `docs/ci-reference-baseline-plan.md` §"First bounded implementation: test what we ship", plus "Retain / do not copy blindly" and "Definition of ready to serve as the reference"

### CI and release machinery (integration points)
- `.github/workflows/ci.yml`: jobs `test`, `lint`, `docker` (build → pip-audit → save `audited-image` → round trip), `secrets`, `dependencies`, `ci-ready` (Python `required` set; the only required CI status context is `CI ready`)
- `.github/workflows/release.yml`: `preflight` and `release`; loads `release-policy.cjs` from **main**, never from the tag; downloads the exact CI `audited-image`; publishes without rebuilding; creates the GitHub Release on tag push
- `.github/scripts/release-policy.cjs`: `REQUIRED_JOBS` and `validateEvidence`. New mandatory jobs must be added here too. Changing this file is a release-safeguard change.
- `.github/scripts/ci-job-consistency.cjs` (+ `.test.cjs`): keeps the three copies of the mandatory job list in sync. It must be extended for the new jobs.
- `.github/scripts/release-policy.test.cjs`, `.github/scripts/artifact-promotion.test.cjs`: the existing pattern for negative tests against the real policy code
- `.github/workflows/review-acceptance.yml`: pinned to the reviewed policy commit `40fe2671…`. Do **not** touch it in this phase; updating that pin is a separate safeguard change.
- `tests/test_github_workflows.py`, `tests/test_version.py`: existing Python-side workflow and version consistency tests

### Shipped artifact
- `Dockerfile`: two-stage build (Tailwind builder → runtime), `HEALTHCHECK` on `/health`, `VOLUME /config`, `ENTRYPOINT ["/entrypoint.sh"]`
- `entrypoint.sh`: PUID/PGID handling, `/config` ownership, setpriv privilege drop, `exec python -m triggarr`
- `triggarr/templates/partials/connection_pill.html`, `tests/test_header_redesign.py`: the pill regression and its current static guard

### Project rules
- `CLAUDE.md`: SecretStr/no-secrets-in-logs, the Buildomator + Greptile pilot rules (feature branch + PR, don't weaken CI or suppress findings, fresh checks after fixes), and owner CLI acceptance
- `docs/owner-cli-acceptance.md`: exact-commit owner approval transport (unchanged by this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `audited-image` artifact (image.tar, image.tar.sha256, image-id.txt) and the round-trip verification in `ci.yml` `docker`: the new jobs download it and verify identity rather than rebuilding.
- The `ci-ready` aggregate pattern (`needs` + exact `required` set + all-success check) already fails on a missing, unexpected or skipped job.
- Node stdlib test harness (`node --test .github/scripts/*.test.cjs`, run in the `test` job): the natural home for permanent tag/version negative tests against `release-policy.cjs`.
- The `image-meta` step in the `docker` job already reads `pyproject.toml` and sets the image's `org.opencontainers.image.version` label.

### Established Patterns
- All actions pinned to full SHAs, with workflow `permissions: contents: read` by default, per-job `timeout-minutes`, and concurrency cancellation on CI. New jobs follow all of these.
- Release logic is loaded from `main` (sparse checkout of `.github/scripts`), so tag contents can't alter the policy.
- Tests use mocked *arr services (respx/fixtures), and no real credentials appear anywhere in CI.

### Integration Points
- New job IDs must be added to: `ci.yml` `ci-ready` `needs` and its Python `required` set; `release-policy.cjs` `REQUIRED_JOBS`; and the job-consistency checks (all three, together, per CISHIP-04).
- Tag/version validation goes in the release preflight/release path, before `docker/login-action`, any `docker push` and `gh release create`/`upload`.
- Branch ruleset requires `CI ready`, `Greptile Review`, `Review acceptance` and `CodeQL`. No ruleset change is needed if the new jobs feed `CI ready`.

</code_context>

<deferred>
## Deferred Ideas

- Pre-release tag support (`vX.Y.Z-rcN`) that publishes without moving `:latest`: a future milestone.
- A password-reset flow in the browser suite: keep the existing unit/integration coverage for now.
- CHANGELOG-entry enforcement at release: stays a release-review item and is not an identity gate.
- The docs/planning-only CI exemption path: Phase 85 (ACCEPT-03), after Phase 83 defines the classification policy.
- Lockfile-matched Docker dependencies, the OS-image audit, actionlint, coverage artifacts and publish-permission narrowing: Phase 85 (CIMAINT-01..07).

</deferred>

---

*Phase: 82-ci-tests-what-we-ship*
*Context gathered: 2026-10-21*
