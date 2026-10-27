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
