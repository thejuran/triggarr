# Phase 85 — Negative demonstrations (CIMAINT-01, CIMAINT-04)

**Status: PENDING — performed during the Plan 85-19 hand-off, not by any plan.**

This file records the single prepared demonstration commit that proves, on the
real phase pull request, that CIMAINT-01's "Check image dependencies match
uv.lock" step and CIMAINT-04's `actionlint` job each turn `CI ready` red for
the specific reason they exist. Recipes: `docs/ci-negative-demonstrations.md`,
Recipes 4 and 5. The patch itself: `85-DEMO-NEGATIVE.patch` (this directory),
prepared and locally verified by this plan against `PHASE_HEAD`
`fbe6a3a4b5764960ce22e22f1fbe6f4ed600320f` — nothing in this patch has been
applied to any committed branch state, and nothing has been pushed.

## Owner go-ahead

**PENDING.** Recorded here only at the moment of the actual push, during the
Plan 85-19 hand-off — not inferred from this document, and not inferred from
any earlier go-ahead for a different push (Phase 82 D-10).

- Verbatim words: PENDING
- Date and time: PENDING
- The head the demo commit sits on: PENDING (will be the phase PR's head at
  that moment, after the normal end-of-phase push)

## Go-ahead request (to present at push time)

This proves on GitHub itself that the two new required checks actually block
a bad image and a bad workflow, not just that they exist. It is one
deliberately broken commit — built from the already-reviewed
`85-DEMO-NEGATIVE.patch` — pushed to the phase pull request's own branch,
after the normal end-of-phase push. It is never pushed to `main` and never
pushed as a tag. Nothing is published by this: the release workflow only
triggers on a push to `main` or on a version tag, and this is a pull-request
push.

Afterward, one restore push reverts it (`git revert --no-edit <demo
commit>`, keeping history, no force push). CI, the paired BM + Codex review,
and acceptance are then all redone on the restored head — none of that
evidence is carried over from the broken head or from any earlier head.

**Costs:** two extra CI runs (one on the negative head, one on the restored
head). Greptile may automatically review each of those two extra heads while
its free credits last; this is disclosed here, not treated as a reason to
decline (D-03).

The broken head's `review-acceptance` run will wait and will not be
approved.

**Recommendation:** go ahead. This is the minimum push that satisfies the
real-GitHub-run rule (Phase 82 D-07) for both CIMAINT-01 and CIMAINT-04.

**If declined:** CIMAINT-01 and CIMAINT-04's GitHub failure cases are
recorded as not demonstrated on GitHub — local evidence only (see "Local
verification" below), the same way Phase 82's pill-loop and pill-disabled
gate-enforcement demonstrations were waived rather than passed.

## Expected failures

| Job / check | Expected failure text | Source |
|---|---|---|
| `docker` ("Check image dependencies match uv.lock" step) | `version mismatch: idna lock 3.15 image 3.4` | Recipe 4 |
| `image-smoke`, `browser-e2e`, `os-scan` | reported **skipped** (each `needs: [docker]`, directly or transitively) | Recipe 4 |
| `actionlint` | `property "missing" is not defined in object type {} [expression]` (on `.github/workflows/demo-actionlint-negative.yml:11:24`) | Recipe 5 |
| `CI ready` | `Mandatory jobs did not succeed` (lists `docker` and `actionlint`, plus the skipped downstream jobs) | both recipes |

No other test failed when the mutations were applied in the local
verification worktree (see below) — `uv run --locked --extra dev pytest
tests/ -q --ignore=tests/test_acceptance_docs.py
--ignore=tests/test_review_checkpoint_record.py` stayed at **2541 passed**
both before and after the mutations, and `node --test
.github/scripts/*.test.cjs
.claude/plugins/planchk-router/test/planchk-router.test.mjs` stayed at **326
passed, 0 failed** both before and after. No test enumerates all files under
`.github/workflows/`, so the new demo workflow's presence did not trip any
other check locally. This expected-failures list is therefore believed
complete, pending the real CI run.

## Local verification (this plan, no push)

Performed in a detached temporary worktree (`git worktree add --detach`) at
`PHASE_HEAD` `fbe6a3a4b5764960ce22e22f1fbe6f4ed600320f`, so the main worktree
never changed branch or files.

- `uv sync --locked --extra dev`: succeeded.
- Clean baseline (unmodified worktree), ~86s wall-clock:
  - `uv run --locked --extra dev pytest tests/ -q
    --ignore=tests/test_acceptance_docs.py
    --ignore=tests/test_review_checkpoint_record.py` — **2541 passed**,
    85.84s. (The two ignored files belong to same-wave Plan 85-17, which may
    hold intentionally failing RED doc-guard tests at `PHASE_HEAD`; they are
    unrelated to this plan's Dockerfile/workflow mutations.)
  - `node --test .github/scripts/*.test.cjs
    .claude/plugins/planchk-router/test/planchk-router.test.mjs` — **326
    passed, 0 failed**, ~0.49s.
- Both mutations applied exactly as in Recipes 4 and 5.
- Dockerfile diff: exactly one added line
  (`RUN pip install --no-cache-dir --no-deps "idna==3.4"`), confirmed by `git
  diff -- Dockerfile`.
- `actionlint .github/workflows/demo-actionlint-negative.yml` (actionlint
  1.7.12): exit 1, output `property "missing" is not defined in object type
  {} [expression]` at line 11, column 24 — the exact expected text.
- With both mutations applied: the same pytest command — **2541 passed**,
  84.72s (no change in count); the same node command — **326 passed, 0
  failed**, ~0.51s (no change in count). No demo-induced test failure found.
- Worktree removed (`git worktree remove --force`); back in the main
  worktree, `git apply --check
  .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMO-NEGATIVE.patch`
  succeeded, and `git status --porcelain` showed no change to any tracked
  file (the new patch file itself sits under `.planning/`, which is
  gitignored for untracked files; it only appears with `git status
  --porcelain --ignored=traditional`).
- `git ls-remote --heads origin 'demo/*'` printed nothing — no demonstration
  branch exists on the remote. Nothing was pushed and no PR was created by
  this plan.

**Setup failures:** none. `uv sync --locked --extra dev` and both baseline
commands passed on the first attempt in the unmodified worktree.

## Evidence — negative head

**PENDING**, filled in during the Plan 85-19 hand-off after the owner's
go-ahead and the actual push.

| Field | Value |
|---|---|
| PR number | PENDING |
| PR head SHA (demo commit) | PENDING |
| PR base SHA | PENDING |
| Tested SHA (`github.sha` / checkout HEAD) | PENDING |
| Reconciliation (tested SHA vs. PR head/base) | PENDING |
| Run URL | PENDING |
| Run ID | PENDING |
| Run attempt | PENDING |
| `docker` job conclusion + quoted failure line | PENDING |
| `image-smoke` job conclusion | PENDING |
| `browser-e2e` job conclusion | PENDING |
| `os-scan` job conclusion | PENDING |
| `actionlint` job conclusion + quoted failure line | PENDING |
| `CI ready` job conclusion + quoted failure line | PENDING |
| Greptile run on this head? | PENDING |

## Restore push

**PENDING**, filled in during the Plan 85-19 hand-off.

| Field | Value |
|---|---|
| Restore commit (`git revert --no-edit <demo commit>`) | PENDING |
| Pushed to | PENDING (same PR branch; never a force push) |
| Confirmation the revert is a plain revert, not a squash or rewrite | PENDING |

## Fresh review on the restored head

**PENDING**, filled in during the Plan 85-19 hand-off. None of this is
carried over from the negative head or any earlier head (T-85-57a).

| Field | Value |
|---|---|
| CI run (restored head) | PENDING |
| BM code review | PENDING |
| Paired Codex pass outcome | PENDING |
| Checkpoint record comment URL | PENDING |
| Owner acceptance (`review-acceptance`) | PENDING (requested only after the above are all recorded) |

---

*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Prepared (no push): 2026-10-27*
