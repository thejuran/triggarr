# Phase 86: Pilot & Reference Record - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-30
**Phase:** 86-Pilot & Reference Record
**Areas discussed:** Which PRs count, Vibe-check comparison, What to measure, Retirement bar & guidance

---

## Which PRs count

| Option | Description | Selected |
|--------|-------------|----------|
| Mix | Strongest existing post-83 PRs + 1-2 new PRs from authorized backlog | ✓ |
| Existing PRs only | Only merged post-83 PRs; product-logic and UI categories become gaps | |
| New PRs only | Fresh scorecard from day one; slowest | |

| New pilot PR candidate | Selected |
|------------------------|----------|
| Refresh-counts fix (state/error-path) | ✓ |
| Card-label template (UI) | ✓ |
| SA-12 OpenTelemetry startup | |
| uv version pin | |

**Refresh-counts behavior:** Skip that record (keep the instance connected, log the skip) ✓. Not chosen: Skip + show a dashboard warning.
**PR shape:** Separate PRs per fix (a recorded pilot-only exception to one-PR-per-phase) ✓. Not chosen: everything in the Phase 86 PR.
**Existing PRs:** #48, #36, #44 ✓. Not chosen: #48 and #44 only; #48, #36, #53.
**Notes:** Every post-83 PR so far changed CI/review machinery, not product code, so the new PRs supply the product-logic and UI coverage.

---

## Vibe-check comparison

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh, same first head | On the Refresh-counts PR, vibe-check and BM + Codex independently review the same pre-fix head | ✓ |
| Reuse #48 as-is | Vibe-check only saw the head after five fix rounds, so a weak comparison | |
| Both | Fresh comparison plus #48 as a secondary point | |

**Substantial enough:** Yes, Refresh-counts is enough (recorded as moderate size) ✓. Not chosen: also run a comparison on the Phase 86 PR.
**Judging:** Proof-based (confirmed only with a failing test or reproduction; the owner approves the tally) ✓. Not chosen: majority of reviewers.

---

## What to measure

| Question | Selected | Alternative |
|----------|----------|-------------|
| Missing data on old PRs | Mark "not recorded" | Estimate from timestamps |
| Owner effort | Count decisions/approvals asked per PR | Count + owner's rough minutes |
| Usage/cost | Wall-clock time + tool-reported usage only | Add dollar estimates |
| Later-found miss window | Until Phase 86 PR acceptance | Also through the next release |

---

## Retirement bar & guidance

| Option | Description | Selected |
|--------|-------------|----------|
| No unique catches | Recommend retiring only if vibe-check found no proven defect BM + Codex missed | ✓ |
| No unique serious catches | Minor unique catches don't count | |
| Keep it unless clearly redundant | Retire only if nothing unique AND noticeably more owner time | |

**Guide:** For the owner's other repos, at `docs/review-workflow-adoption.md` ✓. Not chosen: generic, for any maintainer.
**Carried forward (not re-asked):** bot/fork vibe-check fallback (85.1 exception); RISK-02 high-risk vibe-check recommendation (Phase 83).

## Claude's Discretion

- Scorecard file name/format and table layout; order of the two new PRs; guide wording; how multi-round records are condensed (every number traceable to a committed record).

## Deferred Ideas

- SA-12 and SA-01 as pilot PRs (they stay in the backlog); dollar-cost estimates; owner self-reported minutes; tracking misses past Phase 86 acceptance.
