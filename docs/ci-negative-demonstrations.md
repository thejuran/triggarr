# CI negative demonstrations and failure policy

This document is written for a reader who wants to understand what Phase 82's
new required CI checks actually prove, without reading test code. It explains
what each check is supposed to catch, how we proved that it catches it, and
what happens when a check fails. It does not grant permission to push anything
deliberately broken — that is a separate, explicit, one-time decision each
time (see "Ground rules" below).

## Purpose

Phase 82 adds three new mandatory CI checks that run on every pull request
against `main` before `CI ready` can pass:

- **`image-smoke`**: starts the exact image CI would publish, through its real
  startup process, and checks it actually works (health, login, static assets,
  writable config, surviving a restart).
- **`browser-e2e`**: drives a real browser against that same image and checks
  observable behavior — first-run setup, login, logout, and the dashboard's
  "connection" indicator (the "pill") polling correctly.
- **Release-identity rehearsal** (part of `image-smoke`): proves the release
  workflow's own tag/version-matching logic, run against the exact audited
  image, rejects a mismatched, malformed or missing version the same way it
  would at release time.

Adding a check is cheap; proving the check actually fails for the right
reason, on the real gate, is not automatic. This document records that proof.
A **negative demonstration** means: we deliberately broke something the check
is supposed to catch, ran the check, and confirmed it failed for the specific
reason it was supposed to, not for some unrelated reason. A demonstration that
passes (i.e., the broken thing was *not* rejected) is not evidence — it is a
failed demonstration and must be investigated before being recorded as
anything else.

## Two kinds of evidence

Not every negative demonstration proves the same thing, and conflating them
would overstate what we know. We keep two kinds separate:

**(i) Browser sensitivity evidence.** This proves that the real browser
assertions in `tests/e2e` — the exact files and harness that run in
`browser-e2e` — actually notice a specific bug when they run against it. We
prove this locally, on the maintainer's machine, against a throwaway image
built `FROM` the real audited CI image with only the buggy file swapped in. It
is never pushed, never published, and never runs on GitHub. This is a narrow
claim: "this test detects this bug when it runs." It says nothing about
whether GitHub's required gate would actually stop a real pull request
carrying that bug — browser sensitivity evidence is not gate evidence.

**(ii) Aggregate-gate enforcement evidence.** This proves that pushing the
broken commit to an isolated, clearly-labeled draft pull request on GitHub
actually turns `CI ready` red, through the real required-job graph. This is
the kind of evidence that supports a claim like "GitHub will block a pull
request that does this." It requires a real CI run.

An important wrinkle for the connection-pill mutations specifically: the
existing unit tests in `tests/test_header_redesign.py` —
`test_connection_pill_loaded_via_htmx_in_header` and
`test_connection_pill_partial_does_not_retrigger_on_swap` — already catch both
pill mutations described below, and they run in the `test` job. Because
`docker` depends on `test`, and `image-smoke`/`browser-e2e` both depend on
`docker`, a pushed pill mutation is rejected before it ever reaches
`browser-e2e`. That rejection is perfectly legitimate **gate enforcement**
evidence — it proves `CI ready` goes red — but it is explicitly **not**
browser evidence, and this document never describes it as such. These unit
tests are never weakened, skipped or deleted in order to let a mutation reach
the browser job; doing that would be a CI bypass, not a demonstration.

## Ground rules

- **D-07:** A claim that "GitHub's required gate rejects this" needs a real
  GitHub CI run, on an isolated test branch or a draft pull request, with
  publication structurally impossible (pull request runs never trigger the
  release workflow). It is never demonstrated against a production tag. Local
  evidence alone can only ever support a narrower claim, such as "this probe
  detects this specific bug when run directly" — it can never prove that the
  required gate enforces anything, because it never touches the actual gate.
- **D-10:** None of this evidence standard, nor this document, grants
  permission to push a deliberately broken commit or branch. Every single push
  of a deliberately broken commit needs the owner's own separate, explicit
  go-ahead, given at the time it is about to happen — not inferred from this
  document, and not inferred from a previous go-ahead for a different push.

## Evidence checklist per demonstration

Every recorded demonstration (in `82-DEMONSTRATIONS.md`, see "Durable evidence
location" below) captures all of the following, in plain language:

1. **The exact broken commit and the minimal deliberate mutation** — precisely
   what was changed, and nothing else, verified by a diff.
2. **The command run and the expected failure** — what we expected to see
   fail, and why.
3. **The actual failure, with logs** — the real failing output, and which CI
   run/job produced it, showing it failed for the intended reason rather than
   some unrelated problem.
4. **Confirmation that `CI ready` also rejects it** — not just that one job
   failed, but that the aggregate gate goes red and publication cannot
   proceed.
5. **The restored final commit and its successful applicable checks** —
   evidence that the repository was put back to a healthy state afterward.

Each demonstration record also carries the commit-identity fields from D-34,
kept as separate values rather than one blended "the commit" field, because a
pull-request CI run does not always test exactly the PR head commit:

- **PR head SHA** — the exact commit at the tip of the pull request branch.
- **PR base SHA** — the commit the pull request is being compared against.
- **Tested SHA** (`github.sha` / checkout HEAD) — the commit the CI run
  actually checked out and tested. On a `pull_request` trigger this is
  normally GitHub's own synthetic merge of the head into the base, not the
  head commit itself.
- **Image revision label** — the `org.opencontainers.image.revision` label
  baked into the built image, which should equal the tested SHA.
- **Image ID and `image.tar` sha256** — the concrete identity of the exact
  image artifact that was tested, so "the image we tested" is never just
  assumed to match "the image we're talking about."
- **Run URL, run ID and attempt** — so the evidence points at one specific,
  re-checkable GitHub Actions run.
- **Expected rejection reason** — stated before looking at the logs.
- **Observed log line** — the actual line that shows the rejection happened,
  quoted directly.
- **A "Reconciliation:" line** — because the tested SHA and the PR head SHA
  can differ (see above), every record explicitly says how they relate. For a
  normal `pull_request` run, this line explains that the tested SHA is
  GitHub's merge of the PR head into the PR base, so the CI evidence below
  applies to that merge commit while the review evidence (Greptile, vibe-check,
  owner acceptance) applies to the head commit itself. If the tested SHA ever
  turned out not to reconcile against the recorded head and base, that would
  be reported rather than silently assumed away.

## Recipe 1: broken entrypoint (gate enforcement evidence, kind ii)

**Mutation:** change the last line of `entrypoint.sh` so it execs
`python -m triggarr_missing_module` instead of the real application module.
This is the smallest possible change that makes the container fail to start
while leaving everything else (image build, health check wiring, permissions
handling) untouched.

**Expected failure:** the `image-smoke` job fails with a `SMOKE FAILED` line
from either the first-run step or the seeded-setup step (whichever runs
first), because the container never reaches a healthy state. `CI ready` then
fails because `image-smoke` is one of its required jobs.

**Why publication is structurally impossible here:** this demonstration only
ever runs as a pull request against `main`. Pull request runs never trigger
`release.yml` — only a version tag does — so there is no path by which this
broken image could reach a registry or a GitHub Release, regardless of what
any job reports.

**Recipe (draft PR):**

1. Confirm the owner's go-ahead for this specific push, right before pushing
   (D-10). This document does not supply that go-ahead.
2. Create a branch named `demo/82-broken-entrypoint` from the current phase
   head.
3. Make only the described one-line mutation to `entrypoint.sh`.
4. Push the branch and open a draft pull request:
   `gh pr create --draft --title "DO NOT MERGE - Phase 82 negative demonstration: broken entrypoint" --base main --head demo/82-broken-entrypoint --body "Deliberate broken-entrypoint demonstration per docs/ci-negative-demonstrations.md Recipe 1. Owner go-ahead obtained. Will be closed and the branch deleted after capturing evidence."`
5. Watch the run with `gh run watch`. Capture the run URL, run ID and attempt,
   the `image-smoke` job's `SMOKE FAILED [...]` line, and the `CI ready`
   job's failure output.
6. **Restore:** close the draft pull request
   (`gh pr close <number> --delete-branch`), confirming the branch is deleted
   and nothing from it was merged.

**Local recipe (no push, browser-sensitivity style confirmation only):** this
particular mutation does not have a meaningful local-only variant beyond what
Plan 04 already captured while building the smoke driver — a locally built,
never-pushed, never-committed broken-entrypoint image produced the same
`SMOKE FAILED [first-run]` line directly against `tests/harness/image_smoke.py`.
That local run is narrow local evidence only (D-07) and is not a substitute
for the draft-PR run above when a *gate enforcement* claim is needed.

## Recipe 2: pill request loop (both evidence kinds)

**Mutation:** change `tests/e2e`'s target behavior for
`triggarr/templates/partials/connection_pill.html`'s `hx-trigger` attribute
from `"every 30s"` back to `"load, every 30s"` — this is the exact bug fixed
by PR #27 (`d41b484`): because the partial replaces itself via `outerHTML`,
the `load` trigger refires on every swap, producing a tight request loop.

**(i) Browser sensitivity evidence — local, no push:**

1. Download the `audited-image` artifact from the phase head's CI run (or use
   a local build of the exact same tree) and verify it the same way
   `image-smoke` does: `sha256sum -c image.tar.sha256`, then confirm the
   loaded image's ID matches `image-id.txt`.
2. In a scratch directory outside the repository, write a throwaway
   Dockerfile: `FROM <the verified image>`, with only
   `connection_pill.html`'s `hx-trigger` replaced.
3. Build it as `triggarr-demo:pill-loop`.
4. Prove via a file-manifest diff (for example, comparing
   `docker run --rm --entrypoint find <image> /app/triggarr/templates -type f`
   output, or diffing the two images' template directories) that only the one
   file differs between the audited image and `triggarr-demo:pill-loop`.
5. Run the exact same non-credential browser invocation `ci.yml`'s
   `browser-e2e` job uses (`tests/e2e -m "not credential_pages"` with the
   same flags) against `triggarr-demo:pill-loop`.
6. **Expected result:** the test fails with "connection pill request loop" (the
   assertion in `tests/e2e/test_pill_polling.py` that bounds the request
   count).
7. **Cleanup:** `docker rmi triggarr-demo:pill-loop` and remove the scratch
   directory. This image is never pushed and never tagged for any registry.

**(ii) Gate enforcement evidence — draft PR:**

1. Confirm the owner's go-ahead for this specific push (D-10).
2. Create a branch named `demo/82-pill-loop`, make only the
   `hx-trigger="load, every 30s"` mutation described above, and open a draft
   pull request:
   `gh pr create --draft --title "DO NOT MERGE - Phase 82 negative demonstration: pill loop" --base main --head demo/82-pill-loop --body "Deliberate pill-loop demonstration per docs/ci-negative-demonstrations.md Recipe 2. Owner go-ahead obtained. Will be closed and the branch deleted after capturing evidence."`
3. **Expected result:** the `test` job fails on
   `test_connection_pill_partial_does_not_retrigger_on_swap` in
   `tests/test_header_redesign.py`. Because `docker` needs `test`, the
   `docker`, `image-smoke` and `browser-e2e` jobs are skipped rather than run,
   and `CI ready` fails because its required-job check does not accept a
   skipped job as success.
4. **Restore:** close the draft pull request and delete the branch
   (`gh pr close <number> --delete-branch`).

## Recipe 3: pill polling disabled (both evidence kinds)

**Mutation:** remove the `"every 30s"` schedule entirely — from the partial
itself and from the `base.html` placeholder's `hx-trigger="load, every 30s"`
— so the pill never polls again after its first load.

**(i) Browser sensitivity evidence — local, no push:** same procedure as
Recipe 2 (i), using a scratch image tagged `triggarr-demo:pill-disabled`,
built from the same verified audited image with both files' `hx-trigger`
changed and verified by the same file-manifest-diff step. **Expected result:**
the test fails with "did not refresh after a scheduled interval" (the
assertion in `tests/e2e/test_pill_polling.py` that expects at least two
requests after two scheduled ticks). Cleanup: `docker rmi
triggarr-demo:pill-disabled` and remove the scratch directory; this image is
never pushed and never tagged for any registry.

**(ii) Gate enforcement evidence — draft PR:** same procedure as Recipe 2
(ii), branch `demo/82-pill-disabled`, draft pull request title
"DO NOT MERGE - Phase 82 negative demonstration: pill disabled". **Expected
result:** the `test` job fails on both
`test_connection_pill_loaded_via_htmx_in_header` and
`test_connection_pill_partial_does_not_retrigger_on_swap` in
`tests/test_header_redesign.py` (the placeholder change breaks the first, the
partial change breaks the second). Downstream jobs (`docker`, `image-smoke`,
`browser-e2e`) are skipped, and `CI ready` fails. Restore the same way:
`gh pr close <number> --delete-branch`.

## Recipe 4: image disagrees with uv.lock (gate enforcement evidence, kind ii)

**Purpose:** proves CIMAINT-01's "Check image dependencies match uv.lock" step
in the `docker` job turns `CI ready` red when the running image's resolved
`idna` version diverges from the lockfile, through a real CI run on this
phase's own pull request — not a throwaway pull request.

**Owner go-ahead required at the time of the push (D-10):** this document
does not supply that go-ahead. It is requested and recorded as part of Plan
85-19's hand-off, immediately before the push happens.

**Mutation:** append one line to the Dockerfile's production stage, directly
after the existing locked, hash-checked install step:

```
RUN pip install --no-cache-dir --no-deps "idna==3.4"
```

`3.4` is a real released PyPI version of `idna`, different from the
lockfile's pinned `3.15` (the same version pair Plan 85-08 already proved
locally). This reintroduces, inside the production stage only, exactly the
version-mismatch class the hash-checked install was built to close.

**Expected failing job and specific failure text:** the `docker` job fails at
its "Check image dependencies match uv.lock" step. `image_lock_consistency.py`
prints and exits non-zero on:

```
version mismatch: idna lock 3.15 image 3.4
```

**Expected skipped jobs:** `image-smoke`, `browser-e2e` and `os-scan` each
`needs: [docker]`, so once `docker` fails GitHub reports them skipped rather
than run. `CI ready` fails because a skipped required job never counts as a
success.

**Evidence fields:** PR head SHA, PR base SHA, tested SHA with a
reconciliation line against the PR head/base, run URL, run ID and attempt,
and the job conclusions for `docker`, `image-smoke`, `browser-e2e`, `os-scan`
and `CI ready`.

**Restore:** `git revert --no-edit <demo commit>`, pushed to the same PR
branch. History is kept; this is never a force push and never a branch
deletion.

**Repeat when (D-09):** the Dockerfile's production-stage install,
`image_lock_consistency.py`'s comparison logic, or the `docker` job's "Check
image dependencies match uv.lock" step changes.

## Recipe 5: workflow lint failure (gate enforcement evidence, kind ii)

**Purpose:** proves CIMAINT-04's unconditional `actionlint` job turns
`CI ready` red when a workflow file is invalid, through a real CI run on this
phase's own pull request — not a throwaway pull request.

**Owner go-ahead required at the time of the push (D-10):** this document
does not supply that go-ahead. It is requested and recorded as part of Plan
85-19's hand-off, immediately before the push happens.

**Mutation:** add a new file `.github/workflows/demo-actionlint-negative.yml`:

```yaml
name: Demo Actionlint Negative

on:
  workflow_dispatch:

jobs:
  demo:
    runs-on: ubuntu-latest
    steps:
      - name: Reference an undefined step output
        run: echo "${{ steps.missing.outputs.value }}"
```

The workflow's only trigger is `workflow_dispatch`, so nothing ever causes it
to actually run as part of this push or the pull request's own CI event —
`actionlint` lints the file's syntax and expression types regardless of
whether the workflow itself ever executes.

**Expected failing job and specific failure text:** the `actionlint` job
fails. `actionlint`'s output on `demo-actionlint-negative.yml` contains:

```
property "missing" is not defined in object type {} [expression]
```

for the `steps.missing.outputs.value` expression.

**Expected skipped jobs:** none. `actionlint` has no `needs`, no `if` and no
`continue-on-error`, so it always runs and fails under its own evaluation;
nothing else depends on it, so nothing else is skipped. `CI ready` fails
because `actionlint` is one of its required jobs.

**Evidence fields:** PR head SHA, PR base SHA, tested SHA with a
reconciliation line, run URL, run ID and attempt, and the job conclusions for
`actionlint` and `CI ready`.

**Restore:** `git revert --no-edit <demo commit>`, pushed to the same PR
branch. History is kept; this is never a force push and never a branch
deletion.

**Repeat when (D-09):** the `actionlint` job's wiring, its pinned binary
version, or its unconditional-run guarantee changes.

## Where and how these run

Both Recipe 4's and Recipe 5's mutations ship as **one commit**, pushed to
the phase's own pull request branch after that phase's normal end-of-phase
push — never a separate or throwaway pull request (Phase 85 D-02; one PR per
phase), never to `main`, and never as a tag. The push is never forced. Once
both checks' failure evidence is captured, a **restore push** follows with
`git revert --no-edit <demo commit>` on the same branch, which keeps history
intact and needs no force push. The broken head is never marked approved, and
its `review-acceptance` run is never approved. CI, the paired BM + Codex
review, the checkpoint record, and owner acceptance are all taken fresh on
the restored head — never carried over from the broken head or from any
earlier head. Greptile may automatically review both the negative head and
the restored head while its free credits last; the go-ahead request and the
recorded evidence disclose this (D-03), rather than treating it as a reason
to decline.

## When to repeat a demonstration (D-09)

- **Repeat Recipe 1** whenever the `Dockerfile`, `entrypoint.sh`, the smoke
  driver (`tests/harness/image_smoke.py`, `tests/harness/stack.py`,
  `tests/harness/checks.py`), or the `image-smoke`/`browser-e2e`/`ci-ready`
  wiring changes.
- **Repeat Recipes 2 and 3, part (i)** whenever the pill templates or
  `tests/e2e/test_pill_polling.py` change.
- **Repeat Recipes 2 and 3, part (ii)** whenever the `test`/`docker`/
  `ci-ready` wiring changes.

A changed test or wiring file is exactly the situation where an old
demonstration stops being trustworthy evidence for the current code, so this
is not optional busywork — it is what keeps the evidence record honest.

## Capture policy (D-33)

Any page that could show a credential or an API key (setup/registration,
login, logout) is never screenshotted, traced, or recorded on video. This is
enforced by a guard in `tests/e2e/conftest.py` that refuses to run a
`credential_pages`-marked test together with any capture flag enabled, and it
checks the test session's *final* selected items (after any `-m`/`-k`
filtering), not the raw collected list, so a filtered run that excludes
credential pages is allowed to capture normally.

Byte-scanning captured artifacts for secret strings is kept as an *extra*
defense for text-based files (traces, logs, HAR files). It is not proof that
screenshots are safe, because a screenshot is pixels, not text — pixels cannot
be byte-searched for a leaked value. The real protection is prevention
(capture is off before the credential-showing test ever runs), not detection
after the fact.

## Browser-suite failure policy (D-15, D-16)

- **No automatic retries.** A browser test that fails once is a failure. We do
  not rerun it hoping for a different result, and we never interpret a later
  pass as having "resolved" an earlier failure.
- **Keep the first failure's artifacts.** Logs, screenshots and traces from
  the *first* failing run are what gets investigated; a diagnostic rerun (if
  one is done at all) is for investigation only, never a replacement for
  those original artifacts.
- **Fix the test or the application — never delete required coverage** to make
  CI green. If a test is found to be flaky, the fix is to make it reliable or
  fix the underlying application behavior it was catching, not to remove the
  assertion.
- **Quarantine requires explicit owner approval.** A temporary quarantine of a
  flaky test needs the owner's explicit sign-off, a tracked issue describing
  why, and either equivalent coverage some other way or a clearly recorded
  acceptance gap. It is never a unilateral decision made to unblock a merge.

## Release identity evidence (D-31)

The per-run rehearsal inside the `image-smoke` job (see "Release-identity
rehearsal" above) calls `release.yml`'s own real entry points —
`parseReleaseTag` and `releaseIdentityGate` from `release-policy.cjs` — against
the exact audited image, not a reimplementation of that logic. It covers four
input cases every run: a matching version, a mismatched version (rejected as
"disagree"), a malformed tag (rejected as "malformed"), and a missing version
input (rejected as "missing"). The structural wiring tests in
`tests/test_github_workflows.py` separately fail if anyone adds a bypass
around this gate (an `if:`, `continue-on-error`, or an alternate publishing
path that skips it).

Because these permanent negative-case checks already run, and already observe
the exact expected rejection for each case, inside every ordinary green CI
run, a deliberately red tag-triggered run against a real `vX.Y.Z`-style tag is
not required to prove CISHIP-03, and is not performed (D-31e) — consistent
with D-07's rule against ever demonstrating anything against a production
tag.

This is still a bounded claim, and it is stated here verbatim, exactly as the
owner accepted it:

Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release.

## Review and acceptance (D-35)

CI evidence (the smoke test, the browser suite, the release-identity
rehearsal) binds to the **tested SHA** — the commit CI actually checked out
and ran against, per the "Reconciliation:" line above. Review evidence
(Greptile's automatic review, any owner-run vibe-check) binds to the **PR
head** instead, because those tools review the pull request's own commit, not
GitHub's synthetic merge. Owner acceptance through the protected
`review-acceptance` environment follows the separate procedure in
`docs/owner-cli-acceptance.md`, applies only to the final phase head after all
of this phase's plans are complete, and is not requested, granted or implied
by any demonstration recorded under this document.

## Durable evidence location

The actual filled-in record for each demonstration — commit identities, run
URLs, observed log lines, and the restoration confirmation — lives in
`.planning/phases/82-ci-tests-what-we-ship/82-DEMONSTRATIONS.md` (D-08), not
only in GitHub Actions' own logs and artifacts, which expire. This document is
the recipe; `82-DEMONSTRATIONS.md` is the evidence.
