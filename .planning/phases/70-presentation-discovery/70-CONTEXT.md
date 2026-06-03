# Phase 70: Presentation discovery - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

> **Discussion note:** Gray areas were presented for selection; the user declined to narrow
> them. Because this phase's scope is fully locked by the design spec (§3.2 / §4), the three
> PDISC requirements, and the strong Phase 68 discover-don't-fix precedent, the decisions below
> capture the spec-derived recommended defaults for each area. They are HOW-to-implement choices
> within fixed scope (no scope creep), low-risk, and consumed only by Phase 71 — re-litigate any
> of them at plan-phase time if needed.

<domain>
## Phase Boundary

A hostile reading of Triggarr's **presentation** has run and produced critique/audit artifacts
that drive (and gate) the Phase 71 rewrite. Three discovery activities:

1. **PDISC-01** — a framed cynical-reader ("r/selfhosted commenter") teardown of Triggarr's
   positioning, credibility, and first impression.
2. **PDISC-02** — a codex adversarial pass against the existing README + docs (technical-claims
   accuracy, broken/incomplete install/quickstart, unsupported assertions).
3. **PDISC-03** — a same-author cross-repo consistency audit against the sibling **SeedSyncarr**
   (`~/seedsyncarr`, github.com/thejuran/seedsyncarr): README structure, security-posture framing,
   badge style, and "what this is" one-liner — recorded as a list of divergences to reconcile.

This phase **discovers and critiques only** — it writes NO rewritten docs, screenshots, or
repo-metadata. Producing those is Phase 71 (PREW-01..07). The critique/audit artifacts produced
here are the gate that defines Phase 71's rewrite scope. This mirrors Phase 68's discover-don't-fix
boundary on the code track.

Covers PDISC-01, PDISC-02, PDISC-03.
</domain>

<decisions>
## Implementation Decisions

### Artifact structure (D-01..D-03)
- **D-01:** This phase produces **three focused critique artifacts**, one per PDISC requirement,
  all in this phase directory (`.planning/phases/70-presentation-discovery/`), committed with the
  phase:
  - `70-CRITIQUE.md` — the cynical-reader teardown (PDISC-01)
  - `70-CODEX-REVIEW.md` — the codex adversarial-pass findings against docs (PDISC-02)
  - `70-CONSISTENCY-AUDIT.md` — the SeedSyncarr cross-repo divergence list (PDISC-03)
- **D-02:** Three separate files (not one combined artifact) because each has a different natural
  shape — persona prose, a findings table, and a divergence-reconciliation list — and maps 1:1 to
  a requirement for clean traceability. (Phase 68 used a single `68-FINDINGS.md` because all its
  sources fed one fold-in/parked checklist; Phase 70's three sources feed three differently-shaped
  outputs, so they split.)
- **D-03:** Every actionable item in all three artifacts must be **specific enough for Phase 71 to
  rewrite against without re-investigation** — each teardown gripe and each divergence cites the
  specific README/doc section (or `file:line`) it concerns, and states the recommended direction
  of the fix. The three artifacts collectively ARE Phase 71's PREW-01/03/04/07 input.

### Codex pass mechanism & scope (D-04..D-05)
- **D-04:** PDISC-02 is run via the **direct `codex` CLI** (confirmed installed: codex-cli
  0.133.0), pointed at the *drafted docs themselves*, framed for: technical-claims accuracy,
  broken/incomplete install & quickstart instructions, and unsupported assertions. This is the
  **separate codex pass against docs** the spec calls for (D-6), distinct from the orchestrator's
  automatic per-phase codex *plan* review (D-9) — they are not the same invocation and one does
  not substitute for the other.
- **D-05:** In-scope docs for the codex pass: **README.md, SECURITY.md, CONTRIBUTING.md**, plus
  the install/quickstart path they describe (Docker compose, `TRIGGARR_CONFIG_DIR`, first-run
  setup). Findings captured in `70-CODEX-REVIEW.md` as a table: severity, doc/`file:line`, the
  claim or instruction at issue, and a recommended correction. (LICENSE and issue/PR templates are
  confirmed-present checks for Phase 71 PREW-04, not codex-claim targets.)

### Cross-repo consistency audit (D-06..D-07)
- **D-06:** PDISC-03 reads SeedSyncarr's **README.md, SECURITY.md, CONTRIBUTING.md, and its
  launch-hardening design spec** (`~/seedsyncarr/docs/superpowers/specs/2026-06-02-launch-hardening-design.md`)
  for the *target framing*, and records divergences in `70-CONSISTENCY-AUDIT.md` as a table:
  signal · Triggarr's current state · SeedSyncarr's state · recommended reconciliation.
- **D-07:** The audit is a **reconciliation of quality signals, not forced homogenization** (spec
  D-7). Align section ordering, honest security framing, badge style, and the "what this is"
  one-liner so the two repos read as one coherent serious author — but each project keeps its
  accurate identity ("what this is" stays true to each tool). Already-visible divergences to seed
  the audit (confirmed 2026-06-02): SeedSyncarr leads with a centered wordmark `<picture>` block
  and has `Quick Start` / `How It Works` / `Related Projects` sections; Triggarr leads with a plain
  `# Triggarr` H1 + badges, has a `Table of Contents` and a subsectioned `Security Model`, and has
  **no** `Related Projects` section (a concrete same-author cross-link gap).

### Teardown framing (D-08)
- **D-08:** PDISC-01 is written as a **single cynical "r/selfhosted commenter" persona**, but
  structured across the three first-impression questions that persona actually asks: (a) *is this
  trustworthy / a serious project?* (credibility, maturity signals, security posture), (b) *can I
  get it running in ~5 minutes?* (install/quickstart friction, prerequisites, first-run clarity),
  (c) *why this over the *arr apps' native search or a cron + curl?* (positioning / differentiation).
  Every gripe cites the specific README section or line it reacts to, so Phase 71 gets an
  actionable hit-list rather than vague vibes. Same hostile lens Phase 68 used and the sibling
  SeedSyncarr milestone used.

### Claude's Discretion
- Exact table column layout within each artifact (as long as D-03's "specific + cited" bar is met).
- Order in which the three activities run (they are independent; PDISC-03 needs SeedSyncarr read,
  PDISC-02 needs codex — neither blocks the other).
- Exact codex CLI flags/prompt wording for the PDISC-02 pass (as long as scope = D-05 docs and the
  framing = technical-claims/broken-instructions/unsupported-assertions).
- Whether to capture a short provenance header (codex version, date, commit) per artifact —
  encouraged for reproducibility, not mandated.
- Whether `~/seedsync` (the *separate* smaller repo, github.com/thejuran/seedsync) is worth a
  one-line cross-link note; the canonical sibling for PDISC-03 is `~/seedsyncarr`.
</decisions>

<specifics>
## Specific Ideas

- Framing throughout is the **same hostile "this is on Reddit, a skeptical r/selfhosted engineer
  is reading it" lens** the sibling SeedSyncarr launch-hardening milestone used and that Phase 68
  applied to the code track. Findings are judged by what that reader would actually notice in the
  first 30 seconds, not by abstract completeness.
- The **actual driver** (spec D-7) is same-author coherence: a viewer hopping between Triggarr and
  SeedSyncarr (both `thejuran`) should see consistent README structure, security-posture framing,
  and honest positioning. The most concrete seed divergence found during discussion: Triggarr has
  no `Related Projects` section linking to SeedSyncarr, while SeedSyncarr's README has one — a
  trivially-fixable but high-signal same-author gap for Phase 71.
- Codex "has historically caught real README issues for this maintainer" (spec §3.2) — so the
  PDISC-02 pass is expected to surface genuine signal, not be a formality.
- This phase treats the existing presentation as a **draft to tear apart, not assumed-good** (D-6).
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone design (authoritative scope)
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — the source design spec. §3.2
  (presentation track: hostile take first, content surface to harden, same-author cross-repo
  consistency), D-6 (hostile take before rewrite), D-7 (cross-repo consistency target), D-9 (the
  per-phase codex *plan* review is separate from the PDISC-02 docs pass). §5 (definition of done,
  item 3 & 4 = the presentation hostile take and the consistency audit).
- `.planning/REQUIREMENTS.md` — PDISC-01/02/03 requirement text + success criteria; and the
  Phase 71 PREW-01..07 items these artifacts feed (so the critique is shaped to be actionable).

### Triggarr presentation surface under critique (the subject of this phase)
- `README.md` — 277 lines; sections: Table of Contents, Features, Screenshots, Install
  (Docker/Standalone), Configuration Reference, Security Model, Development. Highest-stakes target.
- `SECURITY.md` — vulnerability-reporting policy + threat-model note; to be reconciled in Phase 71
  with v2.8/v2.8.1 hardening (PREW-03) — note any current divergence in the codex/teardown passes.
- `CONTRIBUTING.md`, `LICENSE`, `.github/` (issue templates `bug-report.yml`/`feature-request.yml`/
  `config.yml`, `pull_request_template.md`) — community-health files; presence/accuracy is a
  same-author seriousness signal.
- `docs/screenshots/dashboard.png`, `history.png`, `settings.png` — current screenshots dated
  2026-04-14 (stale; replaced via Playwright at the Phase 71 walkthrough, PREW-02). Note staleness
  in the teardown, do NOT recapture here.

### Sibling repo (target framing for PDISC-03)
- `~/seedsyncarr/README.md` — sections: Quick Start, Features, How It Works, Installation,
  Configuration, Screenshots, Related Projects, Contributing, Security, License, Usage Examples.
  Leads with a centered wordmark `<picture>` block. The consistency target.
- `~/seedsyncarr/SECURITY.md`, `~/seedsyncarr/CONTRIBUTING.md` — security-posture + community-health
  framing to align against.
- `~/seedsyncarr/docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — SeedSyncarr's own
  launch-hardening spec; read for the *intended* target framing both repos are converging toward.

### Standing codebase context
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/STRUCTURE.md` — to ground "is this a
  real presentation tell or an established project convention".
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **codex CLI** confirmed installed (`/opt/homebrew/bin/codex`, codex-cli 0.133.0) — PDISC-02 runs
  against it directly; no tool gap.
- **SeedSyncarr checkout** present and current at `~/seedsyncarr` (git remote
  github.com/thejuran/seedsyncarr) with README/SECURITY/CONTRIBUTING and its launch-hardening spec
  at the mirror path — PDISC-03 reads it directly, no clone needed.
- **Phase 68 artifact pattern** (`68-FINDINGS.md` in phase dir, consumed by next phase) is the
  precedent for how a discovery phase hands a structured artifact to its paired hardening phase.
- **`triggarr/changelog.py`** present — the in-app changelog source Phase 71 (PREW-06) will update;
  not touched here, but note in critique if the codex pass flags a changelog/version-claim mismatch.

### Established Patterns
- This is a **discover-don't-fix** phase (same contract as Phase 68): the output is critique
  artifacts only; all rewriting is deferred to Phase 71. No README/SECURITY/CONTRIBUTING edits in
  this phase.
- Disjoint from the code track (Phase 68/69 touched Python; Phase 70 touches Markdown/docs critique
  only) — no file coupling.

### Integration Points
- The three artifacts (`70-CRITIQUE.md`, `70-CODEX-REVIEW.md`, `70-CONSISTENCY-AUDIT.md`) are the
  sole interface to Phase 71. Their actionable items map to PREW-01 (README), PREW-03 (SECURITY.md),
  PREW-04 (community-health), PREW-05 (repo metadata text), PREW-07 (cross-repo signal
  reconciliation). PREW-02 (screenshots) is handled separately at the walkthrough.
- SECURITY.md reconciliation target for Phase 71: v2.8/v2.8.1 hardening = CSP nonces, session-secret
  rotation on password change, `apikey=` query rejection, Basic-auth control-char validation,
  session-secret startup checks (per spec §3.2 and STATE.md v2.8.1 record).
</code_context>

<deferred>
## Deferred Ideas

- **All actual rewriting** — README rewrite (PREW-01), SECURITY.md reconciliation (PREW-03),
  community-health fixes (PREW-04), repo-metadata copy (PREW-05), release notes + in-app changelog
  (PREW-06), cross-repo signal reconciliation edits (PREW-07) — is **Phase 71**, not this phase.
- **Fresh screenshots** (PREW-02) — captured via Playwright at the milestone-end NAS walkthrough,
  not in Phase 70 and not in Phase 71's body. The teardown only *notes* current screenshot staleness.
- **GitHub repo-metadata application** — Phase 71 drafts copy-paste text (PREW-05); the maintainer
  applies it in the GitHub web UI (cannot be done from the session).
- Config-knob UI debt (DEBT-03/06/07/08), UI-01/02/03 pixel verification — parked to v2 (spec D-5),
  invisible to a launch reader; not a presentation-discovery concern.
</deferred>

---

*Phase: 70-presentation-discovery*
*Context gathered: 2026-06-02*
