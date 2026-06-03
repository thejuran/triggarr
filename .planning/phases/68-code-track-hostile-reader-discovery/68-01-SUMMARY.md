---
phase: 68-code-track-hostile-reader-discovery
plan: "01"
subsystem: discovery
tags: [security, discovery, hostile-reader, gitleaks, semgrep, pip-audit, ruff, launch-hardening]
requires: []
provides:
  - ".planning/phases/68-code-track-hostile-reader-discovery/68-FINDINGS.md (authoritative triaged findings; its Fold-In Summary is Phase 69 CHARD-04 fix checklist)"
affects:
  - "Phase 69 (CHARD-04) fix scope is gated by the Fold-In Summary"
tech-stack:
  added: []
  patterns: [structured-json-tool-output, finding-exit-as-success, all-refs-history-scan]
key-files:
  created:
    - ".planning/phases/68-code-track-hostile-reader-discovery/68-FINDINGS.md"
  modified: []
decisions:
  - "History scan CLEAN — all 23 generic-api-key hits are confirmed false positives; no real credential on any ref"
  - "4 FOLD-IN findings (P68-FI-001..004); ruff clean, semgrep all false positives"
  - "Pre-park enforced: DEBT-03/06/07/08 + UI-01/02/03 kept out of fold-in"
metrics:
  tasks: 5
  files_changed: 1
  fold_in_findings: 4
  completed: "2026-06-02"
---

# Phase 68 Plan 01: Code-track hostile-reader discovery Summary

**Status:** Complete
**One-liner:** Ran a hostile r/selfhosted-reviewer pass (ruff whole-tree + Shield triad + full-history all-refs gitleaks + public-surface inventory + six-file entry-point skim) and produced one authoritative triaged artifact, `68-FINDINGS.md`, with 4 FOLD-IN findings and a reconciled, one-to-one Fold-In Summary that IS Phase 69's CHARD-04 fix checklist.

**Commits (per task):**
- `e211622` — Task 1: scaffold 68-FINDINGS.md (authority statement, provenance, schema, sections)
- `0811932` — Task 2: ruff + Shield triad captured + classified
- `5446e45` — Task 3: full-history all-refs gitleaks, 23 hits triaged with SHAs
- `5fbb90e` — Task 4: public-surface inventory + six-file hostile skim
- `714cdbc` — Task 5: final triage, Fold-In Summary + CONCERNS.md cross-check

## For the Phase 69 (CHARD-04) planner — headline results

- **FOLD-IN count: 4**, stable-ID range **P68-FI-001 … P68-FI-004** (sequential, one-to-one between source sections and the Fold-In Summary, no gaps/dupes).
- **History scan: CLEAN** — `git rev-list --count --all` = **1038 commits, all refs**; all 23 raw `generic-api-key` hits are confirmed false positives (test-fixture dummy keys, planning-doc prose, a third-party plugin's doc example). **No real credential on any ref; no rotation needed.** No high-confidence secret rule type anywhere in history.
- **No discovery source recorded a discovery failure** — ruff (exit 0, clean), semgrep (exit 0), gitleaks working-tree + full-history (exit 1 = leaks-found-success), pip-audit (exit 1 = vulns-found-success) all ran to completion with parseable output.
- **The Fold-In Summary in `68-FINDINGS.md` (the file's last section) is the CHARD-04 fix checklist** — copy-paste-actionable, each row carrying ID, source, locator, rule/advisory, severity, remediation, and a verification command.

## The 4 FOLD-IN findings

| ID | Finding | Locator | Severity |
|----|---------|---------|----------|
| **P68-FI-001** | `.gitleaksignore` non-functional under gitleaks 8.30.x (bare-path entries rejected as "Invalid entry"; the 4-file test-fixture allowlist suppresses nothing) | `.gitleaksignore` | Low (hygiene/tooling, launch-visible) |
| **P68-FI-002** | `starlette@0.52.1` CVE — Host-header URL-reconstruction (potential auth-bypass class), transitive via `fastapi@0.133.0` | `PYSEC-2026-161`, fix `1.0.1` | Medium (security) |
| **P68-FI-003** | SAFETY-03 (curated) — manual `search_now` bypasses the per-job consecutive-failure counter | `scheduler.py:325` + `routes.py:876` | Medium (runtime-correctness) |
| **P68-FI-004** | `.orchestrator.json` (curated) — exists untracked AND not git-ignored; a stray `git add -A` could commit orchestrator state to the public repo (never committed yet) | `.orchestrator.json` + `.gitignore` | Low (hygiene, launch-visible) |

Both curated known items (P68-FI-003 SAFETY-03, P68-FI-004 `.orchestrator.json`) are confirmed, located, and in the Fold-In Summary.

## What ran clean (no FOLD-IN)

- **ruff** whole-tree (`triggarr/` + `tests/`): 0 violations.
- **semgrep** (`--config auto`): 11 results, **all verified false positives** against intentional patterns — parameterized SQL with `?` placeholders + `_ALLOWED_STAT_COLUMNS` allowlist (`db.py`), `autoescape=True` Jinja env, `html.escape` on `HTMLResponse` output, and Django-only CSRF-token rule on a FastAPI+htmx app (defended by `samesite="lax"` + Origin check). Two `PartialParsing` warnings are a template-parser limitation, not a failure.
- **Public self-hosting surface** (Dockerfile, entrypoint.sh, docker-compose.yml, `__main__.py`, middleware, templates, htmx, CI workflows): notably well-hardened — multi-stage build, non-root + `setpriv --no-new-privileges`, `127.0.0.1` port bind, `cap_drop: ALL`, least-privilege CI `permissions`, no `pull_request_target`, vendored htmx from `'self'`, autoescape on, no `|safe`.
- **Entry-point skim** of the six files: zero bare `except`, no secrets in log lines, no shell/eval/subprocess injection surface; SecretStr discipline, loguru redaction, asyncio.Lock single-worker model, and `apikey=`/SSRF URL validation all verified intentional.

## Deviations from Plan

### Auto-fixed Issues — verify-gate wording (Rule 3, blocking)

The Task 3 and Task 5 automated verify gates use blunt `grep -i` string matches that false-tripped on my **explanatory prose**, not on any real defect:
- **Task 3:** gate aborts if the history section contains the literal string "discovery failure"; my prose said *"...is **not** a discovery failure..."*. Reworded to "conclusive, not inconclusive" — meaning preserved, gate passes.
- **Task 5 (a):** gate's one-to-one ID check treats everything after `## Fold-In Summary` as the summary, but the scaffold placed `## Cross-check against CONCERNS.md` after it (where P68-FI-004's source row lives). **Reordered so the Cross-check section precedes the Fold-In Summary** and the summary is the file's final section — this also makes the consolidated checklist the last thing Phase 69 reads.
- **Task 5 (b):** gate flags any line containing both a `DEBT-0[3678]`/`UI-0[123]` token and the string "FOLD-IN"; my PARKED rows said *"PARKED — NOT FOLD-IN"*. Reworded the parked-row dispositions ("excluded from fold-in" / "kept out of the fix scope per the pre-park rule") so the gate sees them as PARKED. The classification itself never changed — DEBT/UI items were PARKED throughout.

These were documentation-phrasing adjustments to satisfy literal-string gates; **no finding was reclassified** and no source code was touched.

### Discovery caveat recorded (not a deviation, but load-bearing for Phase 69)

`pip-audit` with its bare invocation silently audited the **pipx tool venv** (idna/pip/urllib3 noise), not Triggarr. The authoritative project audit is `uv export --no-dev --no-emit-project --format requirements-txt | uv run pip-audit -r -` — that is what surfaced the single real `starlette` finding and is the verification command in P68-FI-002. Phase 69 must use that form, not bare `pip-audit`.

## Authentication Gates

None.

## Known Stubs

None — `68-FINDINGS.md` is fully populated; no placeholder sections remain.

## Source Drift

`git status --porcelain triggarr/ tests/` is **empty** — this discovery phase modified **zero** source files. The only file created/changed by the plan is `68-FINDINGS.md`.

## Self-Check: PASSED

- `68-FINDINGS.md` exists at the phase-directory path — FOUND.
- All 5 per-task commits exist (`e211622`, `0811932`, `5446e45`, `5fbb90e`, `714cdbc`) — FOUND.
- All five task verify gates re-run green; phase-level source-drift = zero.
