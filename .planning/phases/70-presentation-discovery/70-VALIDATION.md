---
phase: 70
slug: presentation-discovery
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-02
---

# Phase 70 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Phase nature:** This phase is **discover-don't-fix** — it produces three Markdown
> critique/audit artifacts (`70-CRITIQUE.md`, `70-CODEX-REVIEW.md`, `70-CONSISTENCY-AUDIT.md`)
> and writes NO product code. There are no testable I/O contracts, so the validation gates are
> **structural** (artifact exists + non-empty + correctly shaped) plus a **no-regression sanity
> check** (no source file outside the phase dir was modified; the existing test suite and ruff
> stay green because this phase touches no Python). This mirrors the Phase 68 discovery precedent,
> which likewise had no executable Nyquist tests.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — artifact-existence + shape checks (shell `test`/`grep`); existing pytest 7.x suite used only as a no-regression sanity net |
| **Config file** | none — no test infrastructure created or required |
| **Quick run command** | `test -s .planning/phases/70-presentation-discovery/<artifact>.md` (per artifact) |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` (sanity: must stay green — this phase touches no Python) |
| **Estimated runtime** | <1s per artifact check; ~existing-suite for the sanity net |

---

## Sampling Rate

- **After every task commit:** Run the per-artifact `test -s …` + the shape `grep` for that artifact.
- **After every plan wave:** Confirm all expected artifacts so far exist and are non-empty.
- **Before `/gsd:verify-work`:** All three artifacts exist + non-empty + correctly shaped; `git status` shows no modified file outside `.planning/phases/70-presentation-discovery/`; `uv run pytest tests/ -x -q` green and `uv run ruff check triggarr/ tests/` clean (no-regression sanity).
- **Max feedback latency:** <5 seconds (existence + shape checks are instant; the optional sanity suite is the only longer step).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 70-01-01 | 01 | 1 | PDISC-01 | — | N/A (critique artifact; no runtime behavior) | structural | `test -s .planning/phases/70-presentation-discovery/70-CRITIQUE.md && grep -q 'README' .planning/phases/70-presentation-discovery/70-CRITIQUE.md` | ❌ W0 (created by task) | ⬜ pending |
| 70-01-02 | 01 | 1 | PDISC-02 | — | N/A (codex findings artifact) | structural | `test -s .planning/phases/70-presentation-discovery/70-CODEX-REVIEW.md` | ❌ W0 (created by task) | ⬜ pending |
| 70-01-03 | 01 | 1 | PDISC-03 | — | N/A (consistency-audit artifact) | structural | `test -s .planning/phases/70-presentation-discovery/70-CONSISTENCY-AUDIT.md` | ❌ W0 (created by task) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: exact task/plan IDs are finalized by the planner; the requirement→artifact mapping above is the binding contract regardless of final IDs.*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* No test framework, stubs, or fixtures are
needed — the three artifact files are created by task execution itself, and verification is a
file-existence + shape check. The only "Wave 0" precondition is that the codex CLI is available
(`/opt/homebrew/bin/codex`, codex-cli 0.133.0, confirmed present) for the PDISC-02 task.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `70-CRITIQUE.md` covers all three D-08 first-impression lenses (trust / install-in-5-min / why-this-over-alternatives) and every gripe cites a specific README section or line | PDISC-01 | Content-quality judgement; no machine assertion can confirm "each gripe is cited + actionable" | Read the artifact; confirm three lens sections present and each gripe references a README §/line |
| `70-CODEX-REVIEW.md` findings are real (codex actually ran against README+SECURITY+CONTRIBUTING) and each row has severity + doc:line + claim + recommended correction | PDISC-02 | Requires confirming codex was invoked non-interactively and the table is populated, not stubbed | Confirm a provenance line (codex version/date) + a findings table with the required columns; spot-check ≥1 finding against the cited doc:line (e.g. the README pip-whl version mismatch) |
| `70-CONSISTENCY-AUDIT.md` enumerates SeedSyncarr divergences as signal · Triggarr state · SeedSyncarr state · recommended reconciliation, and flags the missing `Related Projects` section | PDISC-03 | Cross-repo comparison correctness is a judgement call | Read the artifact; confirm the divergence table and that the `Related Projects` gap (and badge/one-liner/section-ordering signals) are recorded |

---

## Validation Sign-Off

- [x] All tasks have a structural `<automated>` existence/shape check (no Wave 0 deps beyond codex-CLI presence)
- [x] Sampling continuity: every task has an automated structural verify (no 3-consecutive-task gap)
- [x] Wave 0 covers all MISSING references (none — no test infra needed)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter (structural-gate compliance for a no-code artifact phase)

**Approval:** approved 2026-06-02 (structural validation appropriate for a discover-don't-fix Markdown-artifact phase; mirrors Phase 68)
