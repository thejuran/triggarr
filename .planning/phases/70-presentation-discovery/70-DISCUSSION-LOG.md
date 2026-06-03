# Phase 70: Presentation discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 70-presentation-discovery
**Mode:** discuss (standard)
**Areas presented:** Artifact structure, Codex pass (PDISC-02), Cross-repo audit (PDISC-03), Teardown framing (PDISC-01)

---

> **Interaction note:** The four gray areas below were presented for multiSelect. The user
> declined to answer/select. Because Phase 70's scope is fully locked by the design spec (§3.2 / §4),
> the three PDISC requirements, and the strong Phase 68 discover-don't-fix precedent, each area was
> resolved with its spec-derived recommended default rather than re-prompting. All four are
> HOW-to-implement choices within fixed scope (no scope creep) and are consumed only by Phase 71.

## Artifact structure

| Option | Description | Selected |
|--------|-------------|----------|
| Three focused artifacts (one per PDISC) | `70-CRITIQUE.md` / `70-CODEX-REVIEW.md` / `70-CONSISTENCY-AUDIT.md` — 1:1 with PDISC-01/02/03, each its natural shape | ✓ |
| One combined critique file | Single `70-CRITIQUE.md` covering all three (Phase 68 style) | |

**Resolved (default):** Three separate files. Phase 68 used one file because all its sources fed
one fold-in/parked checklist; Phase 70's three sources produce three differently-shaped outputs
(persona prose, findings table, divergence list), so they split for clean 1:1 traceability.
**Notes:** Every actionable item must cite a specific README/doc section or `file:line` and state
the recommended fix direction — the three artifacts ARE Phase 71's PREW-01/03/04/07 input.

---

## Codex pass (PDISC-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Direct `codex` CLI against docs | codex-cli 0.133.0 installed; pass framed for claims accuracy / broken install / unsupported assertions | ✓ |
| Orchestrator `/codex:adversarial-review` skill | That skill reviews the *plan*, not the docs — distinct from PDISC-02 | |

**Resolved (default):** Direct `codex` CLI, scoped to README.md + SECURITY.md + CONTRIBUTING.md and
the install/quickstart path they describe. Findings → `70-CODEX-REVIEW.md` (severity, doc/file:line,
claim/instruction at issue, recommended correction).
**Notes:** Spec D-6 calls for a separate codex pass against the *docs*; spec D-9 keeps the per-phase
codex *plan* review separate. These are different invocations — one does not substitute for the other.

---

## Cross-repo audit (PDISC-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Read SeedSyncarr README+SECURITY+CONTRIBUTING + its launch-hardening spec; record divergences | Reconcile quality signals, preserve each project's identity (spec D-7) | ✓ |
| Shallow README-only badge/one-liner diff | Faster, but misses security-framing + section-ordering signals | |

**Resolved (default):** Full read of `~/seedsyncarr` README/SECURITY/CONTRIBUTING + its
`2026-06-02-launch-hardening-design.md`; divergences recorded in `70-CONSISTENCY-AUDIT.md` as
signal · Triggarr state · SeedSyncarr state · recommended reconciliation.
**Notes:** Reconciliation of quality signals, NOT forced homogenization. Seed divergences confirmed
2026-06-02: SeedSyncarr leads with a centered wordmark `<picture>` + has Quick Start / How It Works /
Related Projects; Triggarr leads with plain H1+badges, has a ToC + subsectioned Security Model, and
**no Related Projects section** (a same-author cross-link gap).

---

## Teardown framing (PDISC-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Single persona, 3 first-impression lenses | One "r/selfhosted commenter" across: trustworthy? · install-in-5-min? · why-this-over-alternatives? — each gripe cites a README line | ✓ |
| Single flat persona pass | One undifferentiated read; less actionable | |

**Resolved (default):** Single cynical persona structured across the three questions that persona
actually asks; every gripe cites the specific README section/line so Phase 71 gets an actionable
hit-list. Same hostile lens Phase 68 and the SeedSyncarr milestone used.

---

## Claude's Discretion

- Exact table column layout in each artifact (as long as items are specific + cited).
- Order the three activities run in (independent).
- Exact codex CLI flags/prompt wording for PDISC-02.
- Whether to add a per-artifact provenance header (codex version, date, commit).
- Whether `~/seedsync` (separate smaller repo) warrants a one-line note vs. canonical `~/seedsyncarr`.

## Deferred Ideas

- All actual rewriting (PREW-01/03/04/05/06/07) → Phase 71.
- Fresh Playwright screenshots (PREW-02) → milestone-end NAS walkthrough.
- GitHub repo-metadata application → maintainer applies Phase 71's drafted text in the web UI.
- Config-knob UI debt (DEBT-03/06/07/08), UI-01/02/03 → parked to v2 (spec D-5).
