# Triggarr maintenance

Updated 2026-10-27. Small ongoing work and change-time rules; not a separate development milestone. Confirm existing implementation and current need before acting.

## Change-time rules

- **Atomic writes (former 999.8):** preserve atomic replacement, secret-file permissions, cleanup and durability. Fix demonstrated defects with focused tests; no mandatory consolidation of all writers/public APIs.
- **URL validation (former 999.11):** ship migration/recovery and a regression test alongside any future rule that rejects a previously supported configuration. Do not prebuild a generic migration framework or weaken validation.
- Preserve changelog escaping and its tests, and ordinary login/setup/settings usability and accessibility checks.

## Small follow-ups

- Revalidate the README screenshot and CI action-runtime tasks in [TODO.md](../../TODO.md). Close already-delivered work rather than repeating it; update only remaining discrepancies.
- Recheck the old v2.9 Retry-Connection button behavior and bug-report version options; fix confirmed user-facing problems while touching those areas. URL-validation deduplication is optional local cleanup, not its own plan.
- **Card reasons label (found in the Phase 80 walkthrough, 2026-10-18):** the dashboard card's expandable list reads "Show N failure reasons" even when nothing failed (e.g. a Partial cycle with "0 failed" whose only rows are malformed-record skips). Reword the label so skip-only rows are not called failures; keep the row text and grade colors unchanged.
- **Refresh counts vs. scheduled cycles on a malformed record (kept out of PR #28 on 2026-10-18):** one malformed record (e.g. Sonarr `"series": null`) makes "Refresh counts" mark the instance disconnected and blank its counts, because `refresh_sonarr_counts`/`refresh_lidarr_counts` keep the coarse whole-instance guard, while a scheduled cycle now skips that record per item (per-item screening remains deferred; the shared release-date fix also benefits refresh). Decide whether refresh should skip per item too; if so, add a regression test for each app.
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

## Still open after Phase 85

Items the owner did not fold into Phase 85 (D-15); unchanged from the prior
carry-forward record.

- **Card-template text-matching refactor** (quick WR-01 / bm IN-01). `cycle_grade.html` classifies reason rows by matching `outcome.py`'s rendered display strings instead of a structured "kind" field; correct for every row today but only coupled through wording.
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
- **Same archive trap, phase 83:** `tests/test_codex_report_status.py:485` and `tests/test_codex_review_run.py:41` read recorded Codex evidence under `.planning/phases/83-paired-bm-codex-review-risk-based-depth/`; archiving the v2.13 milestone breaks them too. Move those fixtures under `tests/fixtures/` before archiving.
