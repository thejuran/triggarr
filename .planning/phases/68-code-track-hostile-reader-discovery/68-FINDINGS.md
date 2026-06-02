# Phase 68 — Code-track hostile-reader discovery: FINDINGS

> **This file (`68-FINDINGS.md`) is the AUTHORITATIVE discovery artifact for Phase 68.**
> Its [`## Fold-In Summary`](#fold-in-summary) section is the fix checklist that **Phase 69 (CHARD-04)**
> consumes directly, without re-investigation. The GSD per-plan `68-01-SUMMARY.md` is execution
> bookkeeping, **not** a discovery deliverable — when the two disagree, this file wins.

This artifact is the product of a deliberate *"this is on Reddit and a skeptical r/selfhosted engineer
is reading the repo, the README, and `git log`"* hostile pass over Triggarr's whole code surface, its
launch-visible self-hosting surface (Docker / compose / entrypoint / templates / htmx / middleware / CI),
and its **full git history across all refs**. This phase writes **no source code** — it runs read-only
discovery tools and records + triages their output.

---

## Scan Provenance

| Field | Value |
|-------|-------|
| Run date | 2026-06-02 |
| Branch | `launch-hardening` |
| Repo | Triggarr (`ghcr.io/thejuran/triggarr`) |
| gitleaks version | `8.30.1` |
| semgrep version | `1.136.0` |
| pip-audit version | `pip-audit 2.10.0` |
| uv version | `uv 0.10.2 (a788db7e5 2026-02-10)` |
| **All-refs commit count** (`git rev-list --count --all`) | **1036** |
| HEAD commit count (`git rev-list --count HEAD`) | 1026 |
| ruff ruleset | `E, F, I, UP, B, SIM` (line-length 120, target py311 — from `pyproject.toml`) |

> **The history section cites the ALL-REFS count (1036), not the HEAD count (1026).** On this repo the two
> differ by 10 commits, so an all-refs scan must state the all-refs figure to be honest about coverage.

---

## Schema (read before classifying anything)

### Classification bar (LOCKED — 68-CONTEXT.md D-04)

- **FOLD-IN** if **(a) launch-visible** — something a skeptical r/selfhosted engineer browsing the repo /
  README / `git log` would actually see and ding — **OR (b) any real security or secret exposure**,
  regardless of visibility.
- **PARK** pure-internal nitpicks (style the linter doesn't enforce, invisible debt, cosmetic items) —
  with written rationale.
- **NARROWED HARD RULE (F-5):** the config-knob **UI-exposure** debt — *"the setting EXISTS in the model
  but is NOT exposed in the settings UI"* — (DEBT-03 history cap, DEBT-06 drain timeout, DEBT-07 request
  timeout, DEBT-08 page size; UI-01/02/03 auth-page pixel verification) **MUST NOT** be folded in even if a
  tool surfaces it. Record it PARKED with rationale *"spec D-5: UI-exposure debt, invisible to launch
  reader, parked to v2."*
- **TIEBREAKER (F-5):** an *independent* security / secret / runtime-correctness / launch-visible finding
  that merely happens to touch the same file or setting as a pre-parked knob still applies the D-04 bar
  normally and **CAN** be FOLD-IN. Only the UI-exposure debt *itself* is forced PARKED.

### Source classification matrix (F-8)

- **FOLD-IN sources:** any security finding, any secret exposure, any runtime-correctness defect, any
  user-visible failure (crash, wrong result, broken install/quickstart, leaked internals in a response).
- **PARKED sources** (unless they produce a visible failure): pure style the linter does not enforce,
  import-ordering (ruff `I`), pyupgrade modernization (ruff `UP`) with no behavior change, test-only cleanup.
- **AMBIGUOUS:** if a finding does not cleanly fall into either bucket, it requires a written one-sentence
  *"why a Reddit reviewer would notice"* justification **before** it may be marked FOLD-IN. With no such
  justification it is PARKED.

### FOLD-IN row schema (every FOLD-IN row carries all of these — F-6/F-9)

| Field | Meaning |
|-------|---------|
| **ID** | Stable `P68-FI-NNN` (zero-padded, assigned sequentially across all sources) |
| **Source** | `ruff` / `semgrep` / `gitleaks` / `pip-audit` / `skim` |
| **Locator** | `file:line` OR commit SHA (history hits) |
| **Rule/Advisory** | ruff rule code / semgrep rule ID / CVE-or-advisory ID / gitleaks rule |
| **Severity** | tool severity or assessed severity |
| **Evidence** | sanitized — **never** the raw secret value |
| **Rationale** | applies the D-04 bar + the source matrix |
| **Remediation** | concrete fix Phase 69 applies |
| **Verify cmd** | command Phase 69 runs to confirm the fix |

### PARKED row schema (lighter)

| Field | Meaning |
|-------|---------|
| **Source** | which discovery source surfaced it |
| **Locator** | `file:line` or summary scope |
| **Classification** | `PARKED` |
| **Rationale** | one-line written reason it is parked |

### Tool contract (F-2 + F-3)

Structured JSON output is the contract; capture it, then classify rows from it. **All four tools use a
NON-ZERO exit code to mean "findings exist," NOT "the command failed."** A finding-exit-code is
**SUCCESS-WITH-FINDINGS** (capture + classify). A genuine failure (tool-not-found, flag rejected, parse
error, crash) is a **DISCOVERY FAILURE**, recorded separately in the section's `Discovery status:` line —
a discovery failure on a required source **FAILS** the phase gate.

---

## ruff

*Discovery status:* _(pending — populated in Task 2)_

| ID | Source | Locator | Rule | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|------|----------|----------|-----------|-------------|------------|
| _(empty — populated in Task 2)_ | | | | | | | | |

---

## Shield (Semgrep)

*Discovery status:* _(pending — populated in Task 2)_

| ID | Source | Locator | Rule | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|------|----------|----------|-----------|-------------|------------|
| _(empty — populated in Task 2)_ | | | | | | | | |

---

## Shield (gitleaks working-tree)

*Discovery status:* _(pending — populated in Task 2)_

| ID | Source | Locator | Rule | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|------|----------|----------|-----------|-------------|------------|
| _(empty — populated in Task 2)_ | | | | | | | | |

---

## Shield (dependency audit)

*Discovery status:* _(pending — populated in Task 2)_

| ID | Source | Locator (pkg@ver) | Advisory/CVE | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|-------------------|--------------|----------|----------|-----------|-------------|------------|
| _(empty — populated in Task 2)_ | | | | | | | | |

---

## gitleaks (full history)

*Discovery status:* _(pending — populated in Task 3)_

| ID | Source | Locator (commit SHA) | Rule | Severity | Evidence (redacted) | Rationale | Remediation | Verify cmd |
|----|--------|----------------------|------|----------|---------------------|-----------|-------------|------------|
| _(empty — populated in Task 3)_ | | | | | | | | |

---

## public-surface inventory

*Discovery status:* _(pending — populated in Task 4)_

_(empty — populated in Task 4: each launch-visible non-Python surface item either skimmed or carries an
explicit not-present / covered-by / out-of-scope line)_

---

## entry-point skim

*Discovery status:* _(pending — populated in Task 4)_

_(empty — populated in Task 4: hostile ~2-min surface skim of the six entry-point files with the extended
smell list, file:line anchors for anything flagged)_

| ID | Source | Locator | Rule/smell | Severity | Evidence | Rationale | Remediation | Verify cmd |
|----|--------|---------|-----------|----------|----------|-----------|-------------|------------|
| _(empty — populated in Task 4)_ | | | | | | | | |

---

## Fold-In Summary

> **This is Phase 69's CHARD-04 fix checklist.** Every `P68-FI-NNN` that appears as FOLD-IN in a source
> section above appears here exactly once, with the same rich metadata. One-to-one, no gaps, no duplicates.

*Discovery status:* _(pending — consolidated in Task 5)_

| ID | Source | Locator | Rule/Advisory | Severity | Remediation | Verify cmd |
|----|--------|---------|---------------|----------|-------------|------------|
| _(empty — consolidated in Task 5)_ | | | | | | |

---

## Cross-check against CONCERNS.md

*Discovery status:* _(pending — populated in Task 5)_

_(empty — populated in Task 5: reconcile discovery findings against `.planning/codebase/CONCERNS.md`; for
each relevant catalogued item note whether this pass re-confirmed it; confirm the two curated known items —
`.orchestrator.json` gitignore gap and SAFETY-03 — are recorded and in the Fold-In Summary)_
