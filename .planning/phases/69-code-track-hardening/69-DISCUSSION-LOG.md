# Phase 69: Code-track hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 69-code-track-hardening
**Areas discussed:** SAFETY-03 refactor shape, starlette CVE bump strategy, .gitleaksignore fix approach, CHARD-01 audit breadth

---

## Discussion flow

Phase 69 is tightly specified — Phase 68's `68-FINDINGS.md → ## Fold-In Summary` already provides a
concrete remediation **and** a verify command for all four FOLD-IN findings (P68-FI-001..004 →
CHARD-01..04). The four gray areas below were presented for optional interactive deep-dive. The user
elected **"Use recommended defaults"**: lock the implementation choices from the findings-artifact
recommendations + design-spec preferences without an interactive per-area dive. Decisions recorded in
CONTEXT.md (D-01..D-10) reflect those recommended defaults.

---

## SAFETY-03 refactor shape (P68-FI-003 / CHARD-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Shared `_run_one_cycle` helper | Extract a helper both the scheduled `job()` and manual `search_now` call; share counter + lock. | ✓ |
| Route `search_now` through `make_search_job` | Reuse the whole APScheduler-job wrapper for manual searches. | |

**Choice:** Shared `_run_one_cycle(app, app_name, instance_name)` helper (CONTEXT D-01).
**Notes:** Spec §3.1 + the SAFETY-03 risk-mitigation row explicitly prefer "extract a shared helper
used by both paths." Routing through `make_search_job` was rejected so the manual path doesn't inherit
scheduler-job wrapper semantics (job_id provenance, scheduler logging) — only the cycle+counter+lock
core. Refactor is a mechanical extraction, not a counter-logic redesign (D-03).

---

## starlette CVE bump strategy (P68-FI-002 / CHARD-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Raise the `fastapi` pin | Let fastapi pull a resolved starlette ≥1.0.1 (single transitive owner). | ✓ |
| Direct `starlette>=1.0.1` constraint | Add an explicit starlette pin in pyproject.toml. | (fallback) |

**Choice:** Raise the `fastapi` pin; direct starlette constraint only as fallback (CONTEXT D-05).
**Notes:** The starlette 0.x→1.x major is a breakage-risk gate — confirm via the full test suite +
ruff, not just the audit (D-06). Surface breakage during execution rather than pinning around it.

---

## .gitleaksignore fix approach (P68-FI-001 / CHARD-04)

| Option | Description | Selected |
|--------|-------------|----------|
| 8.x fingerprint entries in `.gitleaksignore` | Convert bare paths to `commitSHA:filepath:rule:line` fingerprints in the existing file. | ✓ |
| `gitleaks.toml` `[allowlist] paths` block | Move the allowlist into a new gitleaks.toml regex block. | |

**Choice:** Convert to 8.x fingerprint entries in the existing `.gitleaksignore` (CONTEXT D-07).
**Notes:** Minimizes new config surface — the file already exists and is honored by default. Fingerprints
generated from a real gitleaks run, not hand-fabricated (D-08). Tuning `generic-api-key` for doc-prose
is optional, not required.

---

## CHARD-01 audit breadth (P68-FI-004)

| Option | Description | Selected |
|--------|-------------|----------|
| `.orchestrator.json` only | Ignore the one confirmed gap and stop. | |
| Active audit-and-close sweep | Ignore `.orchestrator.json` + sweep untracked & tracked-cruft, close whatever is open. | ✓ |

**Choice:** Active audit-and-close (CONTEXT D-09/D-10).
**Notes:** CHARD-01 is explicitly "audit-and-close, not a fixed checklist." Sweep `git status --porcelain`
(untracked-but-not-ignored) + `git ls-files` (accidentally-tracked editor cruft), record the result so
the requirement is demonstrably met, not assumed.

---

## Claude's Discretion

- Exact name/location/internal structure of the `_run_one_cycle` helper (D-01 semantics hold).
- Exact test method names + fixtures (D-04 increment+reset assertions exist; no existing test removed/skipped).
- Specific fastapi version chosen (resolved starlette ≥1.0.1, suite green).
- Order the 4 findings are fixed (largely independent).

## Deferred Ideas

- Config-knob UI debt (DEBT-03/06/07/08), UI-01/02/03 pixel verification — pre-parked spec D-5, MUST NOT fold in.
- Tuning gitleaks `generic-api-key` for planning-doc prose — optional, not required.
- Presentation/docs hardening — Phase 70/71.
