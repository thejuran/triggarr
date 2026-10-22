# Phase 82: CI Tests What We Ship - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log preserves the alternatives considered.

**Date:** 2026-10-21
**Phase:** 82-CI Tests What We Ship
**Areas discussed:** Broken-case proof, CI time budget, Release tag rules, Browser suite scope

---

## Broken-case proof

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid | Cheap negatives are permanent; the broken-entrypoint image is shown once and recorded | ✓ (refined) |
| All permanent | Every broken case runs every time, including a broken image build | |
| All one-time | Each shown once on the phase PR, with no permanent negatives | |

**User's choice:** Hybrid. Cheap negatives are permanent in their applicable jobs. The pill test continuously asserts correct behavior, and reintroducing the bug is a recorded sensitivity check. The broken-entrypoint demonstration is recorded at an exact commit (mutation, command, expected and actual failure, CI run), confirmed to fail for the intended reason, and repeated when the Dockerfile, entrypoint, probe or CI wiring changes. The repro recipe lives in the repo and durable evidence in verification records. A harness passes only on the expected rejection.

| Option | Description | Selected |
|--------|-------------|----------|
| Real failing CI run | Throwaway broken commit, link the red run, revert | ✓ (stricter) |
| Local run is enough | Run locally and paste the output | |

**User's choice:** For GitHub gate claims, more than a red run is needed: the broken commit and mutation, a run/job and logs showing the intended reason, `CI ready` also rejecting it with publication impossible, and the restored commit passing. It must use an isolated branch or draft PR with publication prevented, never a production tag. Local evidence is fine only for narrow claims. **This sets the evidence standard; it does not authorize pushing deliberate breakage.**

| Option | Description | Selected |
|--------|-------------|----------|
| Same code as real check | Negative tests call the exact script/function CI uses | ✓ |
| You decide | Leave to planning | |

**User's choice:** Same code. Don't duplicate validation logic; keep inputs and expected outcomes independent of the implementation; verify CI wiring and failure propagation separately.

---

## CI time budget

| Option | Description | Selected |
|--------|-------------|----------|
| Every PR, required | Both feed CI ready and block merge | ✓ (refined) |
| Every PR, browser optional | Browser suite non-blocking | |

**User's choice:** Required on code, runtime, dependency and relevant CI/control PRs. Docs-only PRs may later take an explicitly verified exemption, but an unexplained skip never counts as success. Main/release runs both against the exact publish-candidate image. Until the docs exemption exists, keep the existing required-check behavior.

| Option | Description | Selected |
|--------|-------------|----------|
| Up to ~5 min | Parallel jobs off the saved image | ✓ (as a target) |
| Up to ~10 min | More headroom | |
| As small as possible | Minimum assertions | |

**User's choice:** About 5 minutes as a target, not an estimate. Measure the critical path, including image load and browser setup. If over, investigate and report before expanding; never drop assertions to fit.

| Option | Description | Selected |
|--------|-------------|----------|
| No auto-retry; fix flakes | A failure is a failure | ✓ (amended) |
| One automatic retry | Retry once before failing | |

**User's choice:** No retries that turn a failure into a pass. Keep first-failure logs, screenshots and traces. Diagnostic reruns are fine but don't resolve a failure. Fix the test or the app and don't remove coverage. Quarantine needs owner approval, a tracked issue, and either equivalent coverage or a recorded gap.

---

## Release tag rules

| Option | Description | Selected |
|--------|-------------|----------|
| Package + image label | Tag = pyproject = image version label | ✓ (conditional) |
| Also require CHANGELOG entry | Plus a CHANGELOG section | |

**User's choice:** Package plus image label, on the condition that the existing test covers `__version__` and the root `uv.lock` version and is mandatory for the release commit (verified during discussion: `tests/test_version.py` runs in the `test` job, which `REQUIRED_JOBS` requires). Missing or malformed values fail closed. Keep the revision and digest checks. CHANGELOG stays a release-review item.

| Option | Description | Selected |
|--------|-------------|----------|
| Only vX.Y.Z | Reject any other v* tag | ✓ |
| Allow pre-releases | Publish -rcN as pre-releases | |

**User's choice:** Only stable vX.Y.Z, with a full-string match and no leading zeros except 0. Reject pre-release suffixes and build metadata. Pre-release support is deferred. Format alone doesn't protect `:latest`.

| Option | Description | Selected |
|--------|-------------|----------|
| Fail loudly, publish nothing | Clear message; tag stays | ✓ |
| Also auto-delete the tag | CI removes the bad tag | |

**User's choice:** Fail loudly and leave the tag (deletion is an owner action). Report the reason and the versions available, saying "not inspected" where the image wasn't reached. Verify the rejection happens before login, push, Release creation or asset upload. Keep the failed run.

---

## Browser suite scope

| Option | Description | Selected |
|--------|-------------|----------|
| First-run setup | Fresh → setup → admin → dashboard | ✓ |
| Login + wrong password | Core auth gate | ✓ |
| Logout | Session ends; protected pages redirect | ✓ |
| Password reset via token | Most complex flow | |

**User's choice:** Setup (setup is unavailable afterward), login (a wrong password stays out; valid credentials reach the dashboard) and logout (a fresh protected request redirects). Reset is deferred, keeping its existing coverage. Use disposable credentials and keep passwords, cookies and tokens out of artifacts.

| Option | Description | Selected |
|--------|-------------|----------|
| Request count over a window | No loop and continued refresh | ✓ (refined) |
| Only 'no loop' | Simpler | |

**User's choice:** Watch the initial load plus at least two scheduled refreshes, with a bounded range and timing tolerance. Confirm the refreshed response updates the pill. If timing is shortened, change only the timing, never trigger/swap. Demonstrate that both the original loop bug and disabled polling fail the test.

| Option | Description | Selected |
|--------|-------------|----------|
| Shipped image | Same saved CI image | ✓ |
| Dev server in test job | uvicorn from source | |

**User's choice:** The exact saved CI artifact, verified by identity. A fresh container with isolated config and test services, the normal entrypoint, no mounts and no rebuild. It may use a separate container from the smoke test, but the image artifact must be the same.

---

## Claude's Discretion

- Browser tool (Playwright expected), the timing-shortening mechanism (prefer browser clock control over a new runtime knob), fake *arr service design, job layout and artifact sharing, the exact preflight location of the tag check, and how the missing-asset negative is constructed cheaply.

## Deferred Ideas

- Pre-release tag support; a password-reset browser flow; CHANGELOG enforcement at release.
- The docs-only CI exemption (Phase 85, ACCEPT-03) and the CIMAINT follow-ons (Phase 85).
