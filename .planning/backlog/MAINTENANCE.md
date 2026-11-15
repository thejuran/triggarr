# Triggarr maintenance

Updated 2026-10-30. Small ongoing work and change-time rules; not a separate development milestone. Confirm existing implementation and current need before acting.

## Change-time rules

- **Atomic writes (former 999.8):** preserve atomic replacement, secret-file permissions, cleanup and durability. Fix demonstrated defects with focused tests; no mandatory consolidation of all writers/public APIs.
- **URL validation (former 999.11):** ship migration/recovery and a regression test alongside any future rule that rejects a previously supported configuration. Do not prebuild a generic migration framework or weaken validation.
- Preserve changelog escaping and its tests, and ordinary login/setup/settings usability and accessibility checks.

## Small follow-ups

- **Probe scoring for `--verify-boundary --with-probes` (Phase 85.1, owner decision run 3, 2026-10-29):** the supplementary probe in `tests/codex_review_run.py` downgrades the verdict on any item type outside `ALLOWED_ITEM_TYPES`, treating a blocked tool attempt (an `error` event where the disabled code-mode host refused the call, no tool item executed, no planted token observed, with a model reply) the same as a real tool item executing, a planted token (A/B/C) being observed, or no model reply at all. Live run 3 hit exactly the blocked-tool-attempt case and the owner accepted it as an exception rather than a real exposure. (2026-10-30, inferred, transcript not kept: run 3's `error` was likely the startup "Code Mode is unavailable" notice from the code-mode-only default model, not a refused tool call -- recheck this item's premise before scheduling it.) Proposed rule: fail (downgrade) on a real tool item, an observed token, or no `agent_message` at all; record but do not downgrade an `error` event when the model still replied (i.e. a disabled surface correctly refused the call). Real reviews keep the strict rule unchanged regardless: any non-allowed event still means INCOMPLETE and the owner fallback. Source: `85.1-UNTRUSTED-BOUNDARY.md` "## Owner decision (run 3)", 2026-10-29. Not scheduled.
- **Commit-author verification before adding any write-access collaborator (Phase 85.1 stopping rule, owner decision 2026-10-30: "apply the stopping rule"):** the untrusted-PR design defends against bots and forks and assumes the owner is the only collaborator with write access (docs/codex-adversarial-review-contract.md, "Threat model and stopping rule"). Two findings at `c7c34a5` need a second write-access collaborator and are recorded, not fixed: BM iteration-4 WR-01 (a collaborator pushes to a Dependabot branch, so the bot exemption from the CI-independence rule still applies) and SA-05 (a collaborator pushes to an owner PR, so the head is classed trusted and `pytest` runs their code locally). Both come from deciding trust by who opened the PR rather than who wrote its commits. Precondition before granting anyone write access: build a check that every commit in `merge-base..head` is a verified commit by its claimed author (bot or owner), and use it in `_verify_trust_pr`/`headTrustFor` and `ci_independence_rule_applies`/`ciIndependenceRuleApplies` (fail closed on a read error; one shared helper; JS/Python parity row). Not scheduled; required before any collaborator is added.
- **Linux Docker hosts for the untrusted-PR review (BM SA-01, Phase 85.1, owner 2026-10-29: "Mac only"):** on a Linux Docker host every inspection-only review ends INCOMPLETE because the container user (10001) cannot read/write the per-run bind-mounted dirs; it fails safe. Linux hosts are out of scope; supporting them needs a uid/permission strategy for the per-run dirs. Not scheduled.
- **Restrict review-container egress to the OpenAI endpoint (Phase 85.1 D-05, recorded 2026-10-28):** the untrusted-head Codex review container uses Docker's default bridge network with no published ports, and its egress is not restricted to the model endpoint (D-04). Add an allowlisting proxy or an internal network so the container can reach only the OpenAI API. Not built in Phase 85.1 by owner decision; until then the accepted residual risk in docs/codex-adversarial-review-contract.md (D-07) applies.
- **Phase 85.1 iteration-5 info items (owner: backlog, 2026-10-30):** source `85.1-REVIEW.md` iteration 5 (head `3eda427`); owner instruction "fix round 5; backlog the rest". Not scheduled.
  - **IN-01:** when readiness's own `.github/` diff fails (`ciDefinitionsChanged === null`), the blocked Codex detail still says "rerun the inspection-only review, which stops with the CI-independence reason"; a rerun can succeed and never stop, so the hint loops. Branch the detail on `ciDefinitionsChanged` (`.github/scripts/acceptance-readiness.cjs:140-147`, `codexStatusFor`).
  - **IN-02:** `codex-fallback.cjs validate` re-verification reads only `author,isCrossRepository`, so it does not check that PR `#<pr>`'s `headRefOid` equals `--head` or that its author equals `--pr-author`, and its `git diff` runs from the current directory rather than the repository root (`.github/scripts/codex-fallback.cjs:636-660`, `715-717`).
  - **IN-03:** the `.github` CI-definition pathspec is defined three times with no drift test (`.github/scripts/codex-fallback.cjs:12-15`, `.github/scripts/acceptance-readiness.cjs:50`, `tests/codex_review_run.py` `CI_DEFINITION_PATHSPECS`), and the one-line error formatter is duplicated (`codex-fallback.cjs:625-627` `oneLine()`, `acceptance-readiness.cjs:631-632`). Export and reuse both and pin the JS constant against the Python tuple.
- **Update the `idna` versions in `docs/ci-negative-demonstrations.md` (v2.12.1 release review, BM IN-02 at head `e568dab`, 2026-11-14):** the lockfile-mismatch recipe (around lines 267 and 276) says the lock pins `idna` 3.15; the v2.12.1 lockfile refresh moved it to 3.20. The demonstration still works; only the expected text is stale. The file is an operational procedure (sensitive class), so fix it in a reviewed PR.
- **Remove the temporary `zlib1g` upgrade step from the Dockerfile (PR #57, BM IN-01 at head `8e3d6b4`, 2026-11-13):** the production stage installs Debian's fixed `zlib1g` (CVE-2026-76844, CVE-2026-85091) and fails the build below `1:1.3.dfsg+really1.3.1-1+deb13u1`, because `python:3.13-slim` had not been rebuilt. Once the base image carries that version the step does nothing but still makes every uncached build depend on Debian's mirrors. Check at the next monthly base-image update and remove it then. Related owner rulings still open: whether `docs/os-scan-policy.md` should list a targeted in-image upgrade as an allowed response to a red scan (BM SA-01, vibe-check architecture), and whether the Codex review runner's entry points should accept an injected clock so tests need not patch it (BM SA-01 at head `4940373`).
- Revalidate the README screenshot and CI action-runtime tasks in [TODO.md](../../TODO.md). Close already-delivered work rather than repeating it; update only remaining discrepancies.
- Recheck the old v2.9 Retry-Connection button behavior and bug-report version options; fix confirmed user-facing problems while touching those areas. URL-validation deduplication is optional local cleanup, not its own plan.
- **Phase 85.1 iteration-6 info items (owner: "backlog both", 2026-10-30):** source `85.1-REVIEW.md` iteration 6 (head `66985e9`). (1) IN-01: after Ctrl-C the Docker daemon may finish a `docker create` after the ledger's absence check, leaving a stopped, never-started container with no escalation (reasoned, not reproduced) -- add a second delayed absence check for names with no recorded ID, or document the window; the live procedure's `docker ps -a --filter ancestor=...` step still catches it. (2) IN-02: the `docker create` non-zero-exit branches (clean failure: no escalation; half-created container: removed by name) have no tests; the scripted docker runner needs to simulate both (`tests/codex_review_run.py` create sites, `tests/test_codex_review_container.py`). Not scheduled.
- **Reopen Phase 85.1's live criterion when Codex allows it (owner exception, 2026-10-30):** untrusted (bot/fork) inspection-only reviews end INCOMPLETE because Codex 0.153.4's default model `gpt-6-astra` is code-mode-only, so with `code_mode_host` disabled Codex emits a startup `error` notice that the strict event audit rejects (`tests/codex_review_run.py` `audit_event_types`). Disabling `code_mode` does not help; `-m gpt-5.5` does (quick task 261030-oaf research). Owner kept the D-16 vibe-check fallback instead of pinning an older model or allowlisting the notice. Revisit on each Codex image bump (or if a non-code-mode current model appears): rerun the offline notice check from 261030-oaf-RESEARCH.md, and if clean, rerun the D-03 live review on a qualifying Dependabot PR. Not scheduled.
- **Dependabot rollup (#49-#52) BM iteration-8 items (2026-10-30, head `937aa76`):** (1) IN-02: `.github/scripts/ci-job-consistency.test.cjs:863` fixture still hardcodes the old actions/github-script v8 SHA (test passes; refresh the string in the next substantive commit). (2) IN-01: resolved 2026-10-30 -- PR #53 merged as `d5a4467`; the Review acceptance gate (run 41135525551 attempt 2) and the post-merge Release run 41137479745 (preflight + release jobs) passed under github-script v9. Item (1) not scheduled.
- **Pin the uv version installed by CI (BM SA-01, rollup head `937aa76`; owner decision pending):** the six `astral-sh/setup-uv` steps in `ci.yml` pass no `version`, so every run installs the newest uv; a uv release that changes `uv export`/lock behaviour could turn CI red with no repo change. Options: pin `version:` (Dependabot cannot bump it), use setup-uv v10's `version: latest-known` (checksum-verified, advances with action bumps), or accept. Pre-existing; not introduced by the rollup.
- **Codex F001 at PR #48 head 82b3411 (owner: "backlog F001; push and open the PR", 2026-10-30):** `--verify-boundary` run with a valid image but a missing host Codex `auth.json` prints the absolute home path and credential-file path in its JSON diagnostics (`tests/codex_review_run.py:4235`); contents are never shown. Redact with the runner's existing markers before printing. Low severity (local stdout; committed evidence is home-path-checked). Not scheduled.
- **vibe-check arch-001 at PR #48 head 82b3411 (owner: deferred, 2026-10-30):** `.github/scripts/codex-fallback.cjs:638` requires `acceptance-readiness.cjs` inside a function while readiness requires codex-fallback at load time — a hidden import cycle (works today; verified both load orders). Move `TRUSTED_AUTHORS`, `isRecognisedBot`, `ciIndependenceRuleApplies`, `CI_DEFINITION_PATHSPEC` and `REPO` into one shared trust module both scripts import; keep the parity test pointed at the same export. Not scheduled.
- **Card reasons label (found in the Phase 80 walkthrough, 2026-10-18):** the dashboard card's expandable list reads "Show N failure reasons" even when nothing failed (e.g. a Partial cycle with "0 failed" whose only rows are malformed-record skips). Reword the label so skip-only rows are not called failures; keep the row text and grade colors unchanged.
- **Refresh counts vs. scheduled cycles on a malformed record (kept out of PR #28 on 2026-10-18):** one malformed record (e.g. Sonarr `"series": null`) makes "Refresh counts" mark the instance disconnected and blank its counts, because `refresh_sonarr_counts`/`refresh_lidarr_counts` keep the coarse whole-instance guard, while a scheduled cycle now skips that record per item (per-item screening remains deferred; the shared release-date fix also benefits refresh). Decide whether refresh should skip per item too; if so, add a regression test for each app. **Resolved** 2026-10-30 (owner decision, Phase 86 `86-CONTEXT.md` D-02, extended to Radarr by D-02a): all three apps (Sonarr, Lidarr, Radarr) now skip a malformed record per item, keep the instance connected and log the skip, each with a regression test. Delivered in PR #54 (merge `b80c3e26cf9456dde7245350d7033f6feb94db0f`).
- **Pending Sonarr searches of a removed instance (Phase 81 deep review bugs-005, deferred 2026-10-20):** when a Sonarr instance is removed and a server is added under the same name, it gets a new stable ID. Searches still pending under the removed instance's ID are never checked again and stay pending. That isolation is intended: the new instance must not select or credit them. The open question is their lifecycle (leave them, or close them out some other way). Whatever is decided must keep identity isolation: no row is selected or credited by an ID other than its own.
- **Phase 81 deep-review deferrals (PR #29, owner-deferred 2026-10-21 as "refactor"):**
  - **Shared pending-outcome rule** (`triggarr/db.py:752`, Medium). Which outcomes count as pending (`'searched'`, `'partial'`) is written as a raw SQL literal in six places in `db.py`: the legacy-pending rule, both pending-cap queries, both pruning predicates and `get_trackable_entries`. The copies already differ on a missing outcome. The legacy rule and pruning use `COALESCE(outcome, 'searched')`, so a NULL counts as pending; the cap queries and `get_trackable_entries` compare `outcome` directly. That gap is latent: `outcome` defaults to `'searched'` and every insert sets it. Introduce one shared predicate or constant, and keep the NULL handling deliberate and tested. The next change to pending/terminal outcomes should do this rather than add a seventh copy.
  - **Atomic-write copies** (`triggarr/config.py:200`, Warning). `_atomic_text_write` is a fifth near-copy of the temp-file/fsync/rename sequence (also `_atomic_toml_write`, the v2.2 migration write, `save_state` and the reset-token writer), and the copies differ in fchmod timing and fd cleanup. The atomic-writes change-time rule above still applies (no mandatory consolidation). Consolidate only alongside a demonstrated defect or a change to these writers, with focused tests.

## Operator planning follow-up

After v2.12 closes, present [the review-workflow proposal](../../docs/bm-greptile-codex-blueprint.md) for owner confirmation. Do not enable the pilot, update BM for it, remove vibe-check, or change current acceptance requirements as part of this organization. It is not a v2.12 blocker or a product milestone.

After v2.12 also present [the CI reference-baseline plan](../../docs/ci-reference-baseline-plan.md) alongside the review blueprint. Goal: make Triggarr the model for other repositories, starting with tests of the shipped image, browser regressions, and version consistency. Owner-approved CLI submission was separately activated on 2026-10-18; follow [the active procedure](../../docs/owner-cli-acceptance.md), requiring explicit approval of the exact commit. All CI and reviewer changes remain deferred; preserve current checks and protected acceptance.

## Resolved in Phase 85 (2026-10-26 … 2026-10-27)

Items folded into Phase 85 from "Phase 83 carry-forward to Phase 85" and
"Quick 261026-s2v carry-forward to Phase 85" (D-15, D-16, D-17, D-18, D-13),
each resolved by the named plan and commit. Verified against the plans'
SUMMARY.md files by Plan 85-19; not re-verified against a pushed/merged head
(see `85-REVIEW-EVIDENCE.md`).

- **Checker/runner/schema grade their own PR** (WR-03 / ARCH-03 / impact-001) — resolved by Plan 85-13 (`fc34da2`): `audited_inputs_changed_in_diff` records which grader files changed, and a diff that changes one is cross-graded with the unchanged base-commit checker before it can report complete.
- **Raw Codex `.jsonl`/`.last.json` home-path redaction for future runs** (WR-04) — resolved by Plan 85-03 (`6ce9d49`): `_finalize_raw_outputs` redacts local absolute paths on every exit path before grading, and the overclaiming docstring is corrected. Already-committed raw evidence stays published as written (owner decision), per the contract's historical-evidence exception.
- **`--trusted` is operator-declared, not verified** (SA-01) — resolved by Plan 85-13 (`dcf0b13`): `verify_trust()` independently checks GitHub PR ownership (`gh pr view`) or, for a local checkpoint, every commit's own `commit`-prefixed reflog entry on this machine; the flag alone never establishes trust.
- **Planning-file (`*-PLAN.md`) classification** (SA-03) — resolved by Plan 85-16 (`695e7de`, `7cdb651`): `docs/review-classification-policy.md` classifies `*-PLAN.md` phase plan files as sensitive, and the Codex contract's fixed prompt (version 6) adds a second, positive diff that brings them into review scope despite the blanket `.planning/**/*.md` exclusion.
- **External SIGTERM/SIGHUP leaves Codex/pytest running** (round-6 WR-01, impact-1) **and post-kill drain is unbounded** (bugs-002/impact-2) — resolved by Plan 85-03 (`f17eae7`): a signal handler kills the tracked process group on SIGTERM/SIGHUP, and the post-kill output drain is bounded by `DRAIN_TIMEOUT_SECONDS`.
- **Approved-fallback definition for an INCOMPLETE/PENDING Codex pass** (round-7 WR-01) **and the two related wording gaps** (IN-01 wait/retry-later wording, IN-02 pilot step 4 missing Codex) — resolved by Plan 85-17 (`faa4387`, `e72e971`): the Codex contract's "Owner-approved fallback" section defines the schema (`codex-fallback.cjs`'s `FALLBACK_FIELDS`/`OWNER_DECISIONS`), both the contract and the checkpoint record now state verbatim that wait/retry-later blocks acceptance, and the pilot checklist's Routine BM workflow step 4 now requires the paired Codex review before approval. Dependabot PRs are not unblocked by this fix alone — see "moved to Phase 85.1" below for their actual Codex status.
- **`getpass.getuser()` silent redaction skip** (compliance-002) — resolved by Plan 85-03 (`6ce9d49`): `redact_local_paths()` now prints a warning naming the exception type instead of silently defaulting to no username substitution.
- **Empty directory left on `os.open()` failure** (rm-001) — resolved by Plan 85-03 (`6ce9d49`): `_write_evidence_copy` removes the directory it just created when the evidence file's `os.open()` fails.
- **Three hand-kept review-machinery lists drift guard** (arch-1) — resolved by Plan 85-16 (`d0b2b75`): `tests/test_review_machinery_lists.py` pins exact agreement between the classification policy's sensitive row, the Codex scope (`AUDITED_INPUTS`/`EXCLUDE_PATHSPECS`), and the acceptance checklist's Codex line, with majority-vote attribution naming whichever list drifted.
- **Null `exit_code` / trivial command still counts as evidence** — resolved by Plan 85-04 (`4a9a67a`): `TRIVIAL_COMMANDS` plus a null-exit-code check in the hollow-report guard reject a `commands_run` entry whose only command has no recorded exit code or is trivially uninformative (echo/pwd/true/etc).
- **Run the planchk-router plugin tests in CI** (quick 261026-s2v carry-forward; owner decision 2026-10-26) — resolved by Plan 85-11 (`8a5f48a`): `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` runs in `ci.yml`'s `test` job behind a Node >= 20 guard, by explicit file path (no directory recursion).

**Moved to Phase 85.1, not resolved here:** the isolated Codex review for
untrusted (bot and fork) PRs — part of the SA-01/D-07 carry-forward above —
is **not** delivered by Phase 85. Owner decision 2026-10-27 split it into
Phase 85.1 because its security boundary kept failing plan checks on paper
(`.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-CARRY-IN.md`).
Until Phase 85.1 ships, the interim rule applies (Plans 85-13/85-14/85-17):
`--untrusted` runs nothing and records an INCOMPLETE `untrusted-refused`
result; CI still runs in full; a per-PR owner-approved D-16 fallback is the
only way to satisfy acceptance for such a head; a diff that changes a Codex
grader file is cross-graded only by the base checker on `origin/main`, never
by an untrusted head's own code. D-07 for untrusted heads remains the goal,
delivered by Phase 85.1.

**Phase 85.1 outcome (owner exception, 2026-10-30):** the inspection-only
machinery merged in PR #48, but the post-merge live review (PR #52) is
INCOMPLETE on current Codex models, and the owner kept the D-16 fallback
(`85.1-REVIEW-EVIDENCE.md`, "Post-merge live run"). The interim rule above
therefore still governs bot/fork heads in practice, with `--untrusted` now
running the isolated review and recording INCOMPLETE instead of refusing.

## Still open after Phase 85

Items the owner did not fold into Phase 85 (D-15); unchanged from the prior
carry-forward record.

- **Card-template text-matching refactor** (quick WR-01 / bm IN-01). `cycle_grade.html` classifies reason rows by matching `outcome.py`'s rendered display strings instead of a structured "kind" field; correct for every row today but only coupled through wording. **Resolved** 2026-10-30 (Phase 86 pilot PR, `86-CONTEXT.md` D-03): `cycle_grade.html` now classifies reason rows by a structured `kind` field instead of matching display text; 86-05's divergence analysis found no reachable divergence for any input the application's own code produces, so the change has no visible difference. Delivered in PR #55 (merge `7f6b5d4b567c06ce9a4764b94352366ef008c22b`).
- **Craft-skill `code-reviewer` sticky accept pending.** The owner answered "Accept sticky (persist for bm-code-reviewer)" for the catalog's `code-reviewer` skill (`github.com/Jeffallan/claude-skills`, pinned at `1be15d8064f88fc25216442406d40add8fd23b53`, MIT, trust tier A), but it was never inserted — no local checkout exists at that pin. Needs a separate owner approval of the clone step plus cloning the third-party code at the pin before it can take effect.

### Phase 85 code review iteration 3 follow-ups (owner decision 2026-10-27)

Recorded, not fixed, by owner decision. Source: `85-REVIEW.md` iteration 3 (reviewed head `8bd286c`).

- **SA-04: a PR that changes the Codex runner can certify its own base cross-grade.** If a PR changes `tests/codex_review_run.py`, the changed runner can write its own "complete" `.base-status.json` with the right head and base, without ever running the unchanged base checker. Readiness cannot tell. Runner changes are already sensitive-class, and CI and owner acceptance are unaffected. Fix: make the base cross-grade independent of the runner being reviewed, e.g. readiness re-grades the Codex output with the base commit's checker itself (about half a day).
- **SA-05: the no-skip checks do not look inside reusable workflows or local actions.** A required job that calls a reusable workflow (job-level `uses:`) or a local action (`uses: ./...`) could hide a skip condition there. The pytest guard `tests/test_required_jobs_no_skip.py` forbids both in required jobs today, so this only matters if one is ever wanted. Fix at that point: extend the guard to read the called workflow or action, or document the boundary in `docs/review-classification-policy.md`.
- **IN-01:** `docs/os-scan-policy.md` says the scanned image ID is verified; the job only checks the checksum. Reword, or add a `docker load` plus image-ID check.
- **IN-02:** the `os-scan` job's checkout keeps the job token in `.git/config` while Trivy runs; add `persist-credentials: false`.
- **IN-03:** `acceptance-readiness.cjs` and `review-register.cjs` read and write the review registers in whatever repository the current directory is; pass `--repo` to `gh variable get/set`.
- **IN-04:** a failed `gh variable set` in `review-register.cjs` surfaces as a raw stack trace; wrap the write calls like the read calls.
- **IN-05:** the Docker build pulls an unpinned `hatchling` and an unhashed `uv`; pin them with hashes or record this as an accepted risk.
- **IN-06:** the Codex hollow-report guard accepts a report whose only command was something like `ls`; require a command naming the reviewed range, or soften the docstring.
- **IN-07:** readiness's CodeQL fallback match is unlikely to fire (filters on one app slug, takes only the newest run); require every matching run to succeed and match the app that actually posts them.
- **IN-08:** the readiness dry run uses the gate script at HEAD, not the pinned gate commit the acceptance job runs; load the pinned version, or test that the two are identical.
- **IN-09:** fallback records still accept hollow nested values (empty summary, findings with no id or severity, impossible dates, a confusing message for `pr: "5"`); tighten those checks.
- **IN-10:** the fallback `validate` command now requires `--base` to equal the Codex evidence's recorded base (done with WR-02, `63b0b3d`); it still does not compute the merge-base itself, so the operator must pass the right one.
- **IN-11:** `docs/owner-cli-acceptance.md` does not say readiness must run from the repository root after fetching both the PR head and main (it now runs `git merge-base`); add that line.
- **IN-12:** the fallback reviewer-name denylist misses run-together and model-only names (`ClaudeCode`, `BMcodereviewer`, `sonnet`, look-alike letters); also match names with separators removed, add model names, and reject non-ASCII names.

### Phase 85 code review iteration 4 accepted residual risk (owner decision 2026-10-27)

Accepted, not fixed. Source: `85-REVIEW.md` iteration 4 (reviewed head `eae6d34`); see `85-REVIEW-EVIDENCE.md` "Accepted residual risk".

- **WR-01:** `continue-on-error` on "Fail if tests failed" would swallow the no-skip guard's own CI failure and leave "CI ready" green; covered today by sensitive classification, BM + paired Codex review and exact-commit owner acceptance. Possible future hardening: move the gate logic into a tested script (or run the guard in a second required job without `set +e`).
- **WR-02:** hard-coded `RESULTS` (ci-ready gate) or `TEST_EXIT` ("Fail if tests failed") inputs would make the gate always see success; covered the same way. Possible future hardening: move the gate logic into a tested script whose inputs the guard pins exactly.

### Phase 85 code review iteration 5 follow-ups (recorded 2026-10-27)

Source: `85-REVIEW.md` iteration 5 (reviewed head `1f8e339`, status clean).

- **IN-14:** a job whose `name:` is an expression (`${{ 'CI ready' }}`, `format(...)`, a matrix value) evades the static "CI ready" uniqueness check yet publishes a "CI ready" check at run time; deliberate, sensitive-class edit (accepted class). Pairs with the deferred item below.
- **WR-03 readiness half (deferred in round 4):** `acceptance-readiness.cjs` picks the newest "CI ready" check by name only; make it accept only the run produced by `ci.yml`'s `ci-ready` job (workflow path + job), so a same-named check from another workflow cannot satisfy readiness.
- **Codex local trust vs worktree execution:** `tests/codex_review_run.py --trusted` local-checkpoint mode refuses any phase executed with BM parallel worktrees (plan commits arrive via `merge worktree-agent-…` reflog entries; worker reflogs are deleted). Either teach the runner to accept this machine's own worktree merges safely, or run phase checkpoints sequentially / by PR URL. Phase 85 used the PR-URL path (owner decision 2026-10-27).

### Phase 85 PR #36 Codex follow-ups (owner decision 2026-10-28)

Source: Codex by PR URL on `5a97e1f` (attempts a1/a2, both INCOMPLETE for diff size; owner chose a full vibe-check deep-review fallback). Recorded, not fixed on PR #36, so the reviewed head does not move.

- **Readiness dead end (a1 F001, medium, reproduced):** `acceptance-readiness.cjs` `codexStatusFor` returns blocked when the head-side checker says complete but the base checker says incomplete (grader changed in the diff), before `validateFallback` runs, while `codex-fallback.cjs validate` accepts the fallback for the same evidence. Treat base disagreement as incomplete and fall through to the fallback (or make the CLI refuse the same case). Same root as the deep-review pass-1 bugs-002/003 and arch-001 notes (two copies of the completeness rule).
- **Hollow-report guard (a2 F001, low, reproduced):** `tests/codex_report_status.py` accepts no-op-only command evidence such as `env true`, and can wrongly mark a legitimate compound inspection command starting with `echo` as hollow.
- **Codex scope vs PR size:** four attempts on two heads never finished the full PR diff (27 plans, tests, docs, `uv.lock`). Consider smaller phase PRs or a chunked Codex review mode.
- **IN-04 (BM iteration 8):** `test_post_kill_drain_keeps_partial_text_output` gives the child 1.0 s to print; raise to ~3 s if it flakes on CI.
- **FIXED on ci-traps (b0e1ee4), was: Before the first Dependabot github-actions PR (PR #36 fallback review, impact-001):** `.github/scripts/ci-job-consistency.test.cjs:564/592` match the full pinned `actions/checkout@d23441a…`/`docker/setup-buildx-action@f87e599…` strings; a Dependabot SHA bump makes `mutate()` fail and turns CI red. Anchor on a stable prefix or regex.
- **FIXED on ci-traps (3b3713b, pins now in `.github/tool-pins.env`), was: Before archiving the v2.13 milestone (arch-002/impact-002):** `tests/test_ci_followon_wiring.py` reads Trivy/actionlint pins from `.planning/phases/85-*/85-TOOL-PINS-AND-BASELINE.md` at import time; moving the phase dir breaks pytest collection on main. Move the pins to a tracked non-planning file.
- **Readiness vs pinned gate (arch-001):** add a test that `git show <review-acceptance.yml pin>:.github/scripts/review-acceptance.cjs` equals the working-tree file. The other 15 deferred fallback findings are listed with dispositions in `codex/5a97e1f98982-fallback.json`.
- **FIXED on archive-safe-fixtures, was: Same archive trap, phase 83:** `tests/test_codex_report_status.py:485` and `tests/test_codex_review_run.py:41` read recorded Codex evidence under `.planning/phases/83-paired-bm-codex-review-risk-based-depth/`; archiving the v2.13 milestone breaks them too. Move those fixtures under `tests/fixtures/` before archiving.
- **Next release (v2.13.x), UAT P5:** the release's CHANGELOG entry must state that Python wheel/sdist files are no longer attached to GitHub Releases (install with `pip install git+https://github.com/thejuran/triggarr@vX.Y.Z` or use the image) — Phase 85 D-14/CIMAINT-05. Record the result in `85-HUMAN-UAT.md` item 5. Also roll in open Dependabot PRs per the release rule (#41 updates shipped runtime deps).
- **SA-11 (BM iteration 11/12):** no test covers `main()` refusing a `--phase-dir` that does not exist (`tests/codex_review_run.py` parser.error path). Pre-existing gap; add a one-case test with the next change to the runner.

### Dependency rollup follow-ups (BM iteration 13, 2026-10-28)

- **SA-12 (owner call):** FastAPI 0.162 adds opt-in OpenTelemetry auto-configure. If a user's container environment sets `FASTAPI_OTEL_AUTO_CONFIGURE=true` plus an OTLP endpoint (e.g. a stack-wide compose `environment:` block), the web UI now fails at startup with a clear error; unset (the normal case) nothing changes and nothing is exported. Options: accept (current), ignore the variable in triggarr, or document telemetry export as unsupported. **Correction 2026-11-14 (v2.12.1 release review, BM WR-01 at `d06fab3`):** the startup-failure claim is wrong. FastAPI 0.162.0 and 0.162.4 catch the telemetry setup error and log a warning (`fastapi/telemetry/_runtime.py`, "Optional telemetry setup must not prevent application startup"). Checked on the locally built v2.12.1 image with both variables set: the web UI starts and answers requests, logs `FastAPI automatic telemetry configuration failed: ...`, and exports nothing. No owner decision is needed for startup safety; the only open choice is whether to document telemetry export as unsupported.
- **IN-11:** Starlette 1.10 deprecates its test client on `httpx` in favour of `httpx2`; a future Starlette release may break the auth tests. Tests only.
- **SA-03 instance:** the uv group jumped FastAPI 26 minor versions in one bump; consider a uv cooldown in `.github/dependabot.yml`.

### Phase 86 review-loop follow-ups (owner stopping rule, 2026-11-14)

Recorded, not fixed, by owner decision ("One more round, then stop", 2026-11-14 -- see
`86-PILOT-RECORD.md` "Added 2026-11-14, after code review iteration 2"): after that one
more batched fix round and its fresh BM + Codex re-review, only critical or warning
findings on the Phase 86 PR get fixed; everything below is a leftover info item, an
owner-ruling question, or a wording inconsistency, not a defect that blocked the PR.
Every item below was reproduced and still fails closed (or doesn't matter) at the
content that was actually merged. Unless noted otherwise, the file is the evidence
publication gate and its self-test
(`.planning/phases/86-pilot-reference-record/86-publication-gate.sh`,
`86-publication-gate-selftest.sh`).

- **BM iteration 3** (source: `86-REVIEW-phase-4066d538e12d.md`):
  - **IN-01:** a git flag that marks a file "assume unchanged" makes the gate's text
    search skip it, so a staged private detail in that file would pass. This needs a
    deliberate, unusual git command first; it isn't something a normal commit triggers.
  - **IN-02:** two of the gate's own operating rules aren't written down in its
    comments -- a match inside the evidence file itself can never be excused (the excuse
    would have to quote the pattern it's excusing), and when a reviewed file changes, the
    old hand-review entry for it must be replaced, not left beside the new one. Both rules
    are already enforced in the code; only the explanation is missing. The required
    vibe-check raised the same gap independently on the Phase 86 PR (filtered as a low
    note at pass 2, `86-REVIEW-EVIDENCE.md` "Vibe-check (RISK-02)").
  - **IN-03:** the gate's self-test checks three of its stated hand-review rules (an
    entry under the wrong heading, a basename-only path, a same-basename different file)
    for the credential-shape section only, not for the public-infrastructure section that
    shares the same code.
  - **IN-04:** the local-user-name check is a plain substring match, so an account whose
    name is also an ordinary word (for example an "admin" or CI-runner account) would
    block on ordinary prose; two self-test cases also need `zsh` or fail when run as an
    administrator account. Portability notes only -- the owner's own account name isn't a
    common word.
  - **IN-05:** the instructions don't say whether the automatic high-risk vibe-check
    still starts once Codex has already ended INCOMPLETE or is still pending.
  - **IN-06:** the adoption guide reuses the word "automatically" for two different
    things -- the retired practice of the owner running vibe-check on every "code"-class
    PR, and the new rule where the agent starts it by itself at a high-risk checkpoint --
    which could read as the same rule to a new reader.
  - **SA-01 (needs an owner ruling):** the gate's "public infrastructure" pattern only
    catches home-directory paths and one private-network product name; it doesn't check
    private IP address ranges, storage-volume paths, or other forms of the machine's own
    name (only its short host name). Options: widen the pattern, defer, or accept as is.
  - **SA-02 (needs an owner ruling):** the gate only scans review-evidence files; other
    tracked Phase 86 planning files (plans, summaries, context, research, validation) are
    published with no automated check at all. Options: extend the gate to the whole phase
    folder, defer, or accept as is.
- **BM iteration 4** (source: `86-REVIEW-phase-17eb05200e48.md`):
  - **IN-01:** when the gate blocks because a covered file isn't staged, its message
    only suggests staging it with `git add -f` -- the wrong direction for a file that
    should instead be deliberately withheld and moved out of the covered location.
  - **IN-02:** two short pointer sentences (one in `CLAUDE.md`, one in the CI
    reference-baseline plan's dated note) describe the high-risk vibe-check rule without
    repeating the untrusted-head exception; the full rule, which does state the
    exception, is elsewhere in the same document or is the pointer's own target, so a
    reader following the pointer isn't actually misled.
  - **IN-03:** the text doesn't say what happens after an untrusted (bot/fork) head's
    required vibe-check is recorded "pending" -- what ends that state, or what choices
    the owner has. See the "conservative reading" item below, which is the related
    owner-ruling gap this same finding points at.
  - **SA-01 (needs an owner ruling):** the gate's 32-character-hex credential-shape scan
    only matches lowercase hex, matching the Codex adversarial-review contract's own
    definition of the check; an uppercase or mixed-case key of the same length from some
    other service would still pass. Options: widen the check (and the contract's
    definition with it), defer, or accept as is.
- **BM iteration 5** (source: `86-REVIEW-phase-910e98853c41.md`):
  - **IN-01:** the case-insensitive name matching added in round 4 only folds plain
    ASCII letters; a local user or host name containing an accented letter, in the other
    letter case, would stop matching. Portability note only -- both local names on the
    owner's machine are plain ASCII.
  - **IN-02:** a file saved in a two-byte-per-character encoding (as some Windows tools
    write) has a NUL byte between letters, so none of the gate's four pattern checks
    would match it. Coverage-expansion note only -- everything this workflow writes is
    UTF-8.
- **BM iteration 6** (source: `86-REVIEW-phase-63a5b45b4a33.md`):
  - **IN-01:** the gate's "superseded older entry" rule (an older accepted hand-review
    line for the same path is skipped rather than blocking) is pinned by only one
    passing self-test case, in one of its two sections; three related behaviors (the same
    rule in the other section, an older entry beside a reason-less current-hash line, an
    older entry with a malformed hash) have no case of their own, so a later edit could
    loosen them without any self-test failing.
  - **IN-02 (same-hash check, one-line tightening available):** the "superseded" rule's
    own header comment says an older entry must carry "a different well-formed sha256",
    but the code never actually compares the older hash against the current one. The only
    place this matters is a reason-less line that already carries the *current* hash,
    next to a complete accepted entry for that same hash -- it now passes where the
    iteration-5 gate blocked it. No private detail can slip through this way, because a
    complete, reasoned entry for the exact current content is still required regardless.
    Fix is one line (`&& o != ENVIRON["H"]` on the comparison), or reword the comment to
    "any well-formed sha256" instead. The required vibe-check raised the same gap
    independently on the Phase 86 PR (filtered as a low note at pass 2,
    `86-REVIEW-EVIDENCE.md` "Vibe-check (RISK-02)").
  - **SA-01 (needs an owner ruling):** if a file is first recorded "rejected" in the
    hand-review section, then fixed and re-reviewed as "accepted", the gate keeps
    blocking until someone manually deletes or rewrites the old rejected line, and the
    error message doesn't point at that old line as the cause. Options: accept as is (the
    safest reading), let a rejected line be superseded the same way an accepted one is, or
    keep the block but name the conflicting line in the message.
- **Codex, carried to the Phase 86 PR's pushed heads** (dispositioned `nonblocking_debt`
  by the owner under this same stopping rule; source: `86-REVIEW-EVIDENCE.md` "Phase 86
  PR #59"):
  - **`codex:6ca643dcf210:a1:F001`** (medium; same item as Codex F002 at phase-review
    head `17eb05200e48`): finished Phase 86 plans still show the hand-review-entry
    wording from before the gate's hand-review format was finalized, and plan 86-01
    embeds the first version of both gate scripts. The plans are finished and aren't
    re-run, so this is drift in a historical record, not a live risk. Owner's
    disposition, verbatim: "record it as non-blocking debt" (2026-11-14).
  - **`codex:92b9daca2775:a1:F001`** (low; same item as Codex F001 at phase-review head
    `910e98853c41`): the 2026-10-30 home-path scrub left one literal tilde (`~`) path in
    the already-executed quick-task plan
    `.planning/quick/261026-s2v-activate-the-codex-routed-plan-checker-f/261026-s2v-PLAN.md:194`,
    which a Python subprocess wouldn't expand. The plan is finished and isn't re-run.
- **The high-risk vibe-check rule is restated in six documents** (source: the required
  vibe-check's pass-2 filtered low notes, `86-REVIEW-EVIDENCE.md` "Vibe-check
  (RISK-02)"): who starts the required vibe-check, when, and the untrusted-head exception
  are each stated in full in six separate places -- `CLAUDE.md`, `docs/review-checkpoint-record.md`,
  `docs/bm-greptile-codex-blueprint.md`, `86-PILOT-RECORD.md`, `docs/review-workflow-adoption.md`
  and `docs/ci-reference-baseline-plan.md`. Every copy agrees today, confirmed by this
  phase's own review loop, but a future edit could update one copy and miss another.
  Candidate fix: keep one canonical statement of the rule and have the other five point
  at it instead of restating it.
- **RISK-02's wording in REQUIREMENTS.md still says "recommends"** (found while filing
  this backlog, 2026-11-14): `REQUIREMENTS.md`'s RISK-02 requirement text says BM
  "explicitly recommends an additional vibe-check" at high risk, while the instructions
  this milestone actually adopted (`CLAUDE.md`, `docs/review-checkpoint-record.md`, per
  PILOT-03 decision 1) now say the vibe-check is required at high risk, not a
  recommendation the owner may decline. The owner has not separately ruled on whether to
  reword RISK-02 itself to match; it is left as originally written pending that decision.
- **The untrusted-head "conservative reading" was applied without its own owner ruling**
  (found while filing this backlog, 2026-11-14): fixing BM iteration 3's WR-01 (the
  automatic high-risk vibe-check had no stated exception for bot/fork/non-owner heads),
  Claude chose the conservative behavior -- on an untrusted head, record the required
  vibe-check as "pending" and ask the owner, rather than starting a tool-enabled review
  inside a checkout of that head. Iteration 4's IN-03 listed this as "the conservative
  reading the fix report already lists for the owner's confirmation," but the owner's
  2026-11-14 decisions only ruled on who starts the vibe-check on *trusted* heads
  ("Claude runs it"); no separate owner confirmation of the untrusted-head fallback
  itself is on record.
