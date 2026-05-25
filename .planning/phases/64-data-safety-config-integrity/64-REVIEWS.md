---
phase: 64
slug: data-safety-config-integrity
review_date: 2026-05-25
reviewer: Codex (via /codex:adversarial-review)
verdict: needs-attention
target: working tree diff (4 PLAN.md + RESEARCH.md + PATTERNS.md + VALIDATION.md)
---

# Phase 64 — Cross-AI Review Feedback

> Adversarial review of phase 64 plans by Codex. Posture: challenge the chosen
> implementation, design choices, tradeoffs, and assumptions — not just defect
> review. Three findings, two high-severity and one medium.

---

## Verdict

**needs-attention**

> No-ship: Phase 64 would close a false data-bound invariant, its lock audit
> gate is invalid, and the diff deletes v2.7 verification evidence without an
> archive move.

---

## Findings

### F1 — [HIGH] SAFETY-01 is marked closable while the table can still exceed `max_history_rows`

**Location:** `.planning/phases/64-data-safety-config-integrity/64-04-PLAN.md:39-44`

**Finding:**
Plan 64-04 says it will close SAFETY-01 with documentation plus a resolved-row
soak test and explicitly makes no SQL change. That does not satisfy the roadmap
/ requirement wording that the `search_history` table never exceeds
`max_history_rows`: existing behavior preserves all `outcome='searched'` rows,
and the plan's own `must_haves` exempt pending rows. Under stalled tracking or
repeated dependency failures, pending entries can accumulate beyond the cap
while the plan still marks SAFETY-01 done.

**Why this matters (adversarial framing):**
The requirement says "never exceeds." The plan's contract says "never exceeds
for resolved rows." Those are different invariants. A real-world failure mode
exists: if the tracker stalls (Sonarr/Radarr unreachable for an extended
period), pending entries accumulate unboundedly while the resolved-row trim
keeps reporting "compliant." The plan is closing a weaker invariant than the
requirement promises.

**Codex's recommendation:**
> Do not close SAFETY-01 with resolved-row-only proof. Either narrow the
> requirement and roadmap text to resolved rows and add explicit pending-backlog
> bounds, or implement and test a total/pending row cap that preserves tracking
> semantics.

**Decision needed:**
Two valid paths forward:
- **A.** Narrow the requirement: edit REQUIREMENTS.md/ROADMAP.md so SAFETY-01
  explicitly applies to resolved rows, and add a new requirement (e.g.,
  `SAFETY-01b`) that bounds the pending backlog (e.g., reject inserts when
  pending count > `2 × max_history_rows`, or trim oldest pending after a TTL).
- **B.** Implement a total-row cap that preserves tracking semantics: keep the
  resolved-row trim, AND add a second trim that caps total rows by evicting
  the *oldest* pending rows when the table exceeds, say, `2 × max_history_rows`.
  This loses tracking for the evicted entries but bounds storage.

Path A is cleaner — the requirement language is what's actually broken. Path B
risks dropping tracking-eligible rows, which is a worse failure mode than the
unbounded growth this phase was trying to prevent.

---

### F2 — [HIGH] Working tree deletes shipped v2.7 phase evidence without archived copies

**Location:** `.planning/phases/63-header-favicon-icon/63-VERIFICATION.md:1-6` (representative)

**Finding:**
The diff deletes all phase 60-63 planning, validation, summary, review, and
verification files; this deleted verification report is representative. Codex
found no replacement under `.planning/milestones/v2.7-phases`, while the v2.7
audit still relies on per-phase VERIFICATION/VALIDATION evidence. Committing
this turns detailed acceptance and rollback evidence into summary-only trust,
which is planning data loss.

**Why this matters (adversarial framing):**
This is **not a phase 64 concern** — it is a pre-existing working-tree state
that predates this conversation. The deletions show up in `git status` because
a prior milestone-archival workflow removed the files but the archive move
itself was never committed. Codex correctly notes that this is reviewable
because committing phase 64 alongside an `add .` would silently land the
deletions too.

**Scope clarification:**
Phase 64's commit (`a5f3c7a`) staged only phase 64 files + STATE.md (verified
with `git diff --cached --stat` before commit). The v2.7 deletions remain
unstaged in the working tree. So phase 64 *did not* land the deletions — but
the working tree is still in a broken state that the next commit on this
branch must address before any clean state can be restored.

**Decision needed:**
Independent of phase 64:
- Restore: `git checkout HEAD -- .planning/phases/60-foundation-header/ .planning/phases/61-stat-cards-app-cards/ .planning/phases/62-activity-rail-log-viewer/ .planning/phases/63-header-favicon-icon/`
- Or archive: `git mv` each phase dir into `.planning/milestones/v2.7-phases/` and update audit references.

This belongs in a separate "archive v2.7 milestone" task, not phase 64.

---

### F3 — [MEDIUM] SAFETY-05 route audit command fails against current code and does not prove lock coverage

**Location:** `.planning/phases/64-data-safety-config-integrity/64-03-PLAN.md:306-316`

**Finding:**
The plan tells the executor to count `_atomic_toml_write` within 8 lines after
each `search_lock` acquisition and expect at least 7. Running that command on
the current routes returns 5 because several valid writes are farther than 8
lines after the lock. This creates a false blocker and, worse, the grep
pattern still would not prove every `_atomic_toml_write` call is inside the
lock; it only counts nearby text matches.

**Why this matters (adversarial framing):**
The audit gate is **structurally wrong**, not just numerically wrong. A
line-distance heuristic on text cannot prove lexical scoping. A handler that
acquires the lock, does 20 lines of unrelated work, then writes the config,
*is* correctly locked — but the grep gate fails it. A handler that briefly
exits the `async with` block via an early return path and *then* writes the
config *is not* correctly locked — but the grep gate could still pass it. The
test is both over- and under-inclusive.

**Codex's recommendation:**
> Replace the grep with an explicit per-route checklist or a small AST /
> indentation-aware script that enumerates every `_atomic_toml_write` call and
> verifies it is dominated by `async with request.app.state.search_lock`.

**Decision needed:**
Three paths:
- **A. Explicit per-route checklist** — Plan enumerates each of the 8 (or 5)
  call sites by line number and the executor manually confirms each is inside
  a lock block. Concrete, auditable, but doesn't auto-detect drift.
- **B. AST script** — Write a small Python script using `ast` that walks every
  call to `_atomic_toml_write` and asserts the call's lexical ancestors
  include an `async with` on `request.app.state.search_lock`. Auto-detects
  drift, but adds tooling.
- **C. Trust the integration test** — Plan 64-03's TEST-03 already proves the
  lock serializes two concurrent PUTs. If TEST-03 passes, at least one path
  through the most-trafficked endpoint is provably locked. Drop the audit gate
  entirely and accept that future endpoints could regress without test
  coverage.

Path B is the strongest. Path A is acceptable if the executor is disciplined.
Path C is the most pragmatic but accepts ongoing drift risk.

---

## Reviewer Next Steps (from Codex)

- Fix the Phase 64 SAFETY-01 contract before execution.
- Replace the Phase 64-03 grep audit with a route-aware verification.
- Restore or properly archive the deleted v2.7 phase artifacts.

---

## Disposition for `/gsd:plan-phase 64 --reviews`

| Finding | Severity | Action |
|---------|----------|--------|
| F1 (SAFETY-01 contract) | HIGH | **Address in replan.** Decision required: narrow REQUIREMENTS.md/ROADMAP.md (Path A) or add pending-bound logic (Path B). |
| F2 (v2.7 evidence deletion) | HIGH | **Out of scope for phase 64.** Track as a separate "archive v2.7" task; do not modify phase 64 plans for this. |
| F3 (grep audit gate) | MEDIUM | **Address in replan.** Decision required: explicit checklist (A), AST script (B), or drop (C). Recommend B. |

---

*Reviewer:* Codex (OpenAI), `/codex:adversarial-review`
*Review date:* 2026-05-25
*Phase 64 commit at time of review:* `a5f3c7a`

---

## User Decisions (2026-05-25)

The orchestrator presented the three findings to the user with decision options.
The following selections are **canonical directives** for the `--reviews` replan
— the planner MUST honor them.

### F1 — Path A: Narrow the requirement

- **REQUIREMENTS.md is updated** (this commit): SAFETY-01 narrowed to resolved
  rows; SAFETY-01b added for pending-backlog bound (cap at `2 × max_history_rows`,
  reject inserts or evict oldest pending with logged warning).
- **ROADMAP.md Phase 64 is updated** (this commit): SAFETY-01b added to
  `Requirements:` line; SC1 narrowed to resolved rows; SC1b added; SC6 added
  for AST audit (see F3 below); `Plans: TBD` (replan in progress).
- **Planner directive:**
  1. Update Plan 64-04 (or split into 64-04a/04b) to cover both SAFETY-01
     (resolved-row trim — already implemented; doc + soak test as before) AND
     SAFETY-01b (pending-row cap — NEW production code in `triggarr/db.py`
     `insert_search_entry` plus a new test that inserts `2 × max_history_rows + 1`
     pending entries and asserts either rejection or eviction).
  2. The plan must add SAFETY-01b to its `requirements:` frontmatter list.
  3. Choose the simpler of the two pending-bound mechanisms: rejecting new
     inserts when pending count is at the cap is preferable to evicting old
     pending, because eviction loses tracking semantics (the original concern
     in the Open Question that drove deferral). Reject + log a WARNING with
     the rejected entry's identifier.
  4. The bound is `2 × max_history_rows`, not `max_history_rows`, to allow
     headroom for transient tracking backlog during normal operation.

### F3 — Path B: AST-verified lock coverage

- **ROADMAP.md SC6 is updated** (this commit): explicit AST audit requirement.
- **Planner directive:**
  1. Update Plan 64-03 Task 1: replace the line-distance grep audit with an
     AST-based audit script. The script lives in `tests/audit_lock_coverage.py`
     (or similar — planner picks the canonical location) and:
     - uses Python's `ast` module to walk `triggarr/web/routes.py`
     - finds every `Call` whose target resolves to `_atomic_toml_write` (or
       a known wrapper)
     - asserts each call's lexical ancestor chain includes an `AsyncWith` node
       whose `items` reference `request.app.state.search_lock` (or
       `app.state.search_lock` accessed via a `Request`)
     - exits 0 when every call is covered; exits 1 with a clear list of
       uncovered call sites
  2. The audit script runs in two places:
     - as a pytest test: `tests/test_audit_lock_coverage.py::test_all_config_writes_locked`
     - as a one-shot CLI check the executor can invoke during plan verification
  3. The mutation sanity check (temporarily replacing a lock with `nullcontext`)
     still has value as a meta-test that the AST audit *itself* catches the
     drift — keep it, but now its proof is "AST audit fails" rather than
     "grep count drops." The post-revert verification gate (grep count == 8)
     stays because it's cheap and a useful redundancy.
  4. The acceptance criteria must include `pytest tests/test_audit_lock_coverage.py -x exits 0` AND verify the AST script reports zero uncovered sites.

### F2 — Defer

- **No working-tree changes for v2.7 deletions.** The 60-63 directory
  deletions are pre-existing carryover from a prior milestone cleanup. Phase
  64's `--reviews` replan does NOT address them.
- **Tracked as a separate task** (not yet filed): "Archive v2.7 milestone
  evidence under `.planning/milestones/v2.7-phases/`" — to be inserted via
  `/gsd:add-todo` or `/gsd:phase --insert` as appropriate before v2.8 ships.
- **Planner directive:** ignore F2 entirely. Do not modify phase 64 plans for
  this finding. Do not stage or restore any 60-63 files.

---

## Replan Scope Summary

For the `--reviews` planner pass:

| What changes | What stays |
|--------------|------------|
| Plan 64-04 expanded (or split) to cover both SAFETY-01 (existing) and **SAFETY-01b (NEW: pending cap in db.py + test)** | Plans 64-01 and 64-02 unchanged (they pass adversarial review) |
| Plan 64-03 Task 1: grep audit replaced with **AST audit script + pytest test** | Plan 64-03 Tasks 2-3 mostly unchanged (TEST-03 itself is unaffected) |
| `requirements:` frontmatter on the SAFETY-01b plan adds the new ID | All other `requirements:` lines unchanged |
| Phase requirement set grows from 5 to 6 (adds SAFETY-01b) | All four threat-model entries stay |
| Coverage gate now expects 6 IDs covered, not 5 | TDD types, wave structure mostly unchanged (64-01/03/04 in wave 1; 64-02 in wave 2 depending on 64-01) |

The two unchanged plans (64-01, 64-02) explicitly do not need rework. The
planner should preserve them and only edit 64-03 and 64-04.
