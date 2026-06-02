# Phase 68: Code-track hostile-reader discovery - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

A skeptical-engineer pass over Triggarr's whole code surface — and the full git history — has run and produced a **single triaged findings artifact** that decides what the code-hardening phase (69) must fix. The pass runs the project's own tooling (ruff whole-tree, Shield = Semgrep SAST + gitleaks working-tree secrets + dependency audit, gitleaks over full git history) and skims the six highest-traffic entry-point files with hostile framing.

Covers CDISC-01..05. This phase **discovers and classifies only** — it writes no source fixes. Fixing fold-in findings is Phase 69 (CHARD-04). The fold-in/parked classification produced here is the gate that defines Phase 69's fix scope.
</domain>

<decisions>
## Implementation Decisions

### Findings artifact (D-01..D-03)
- **D-01:** The triaged findings artifact is a single structured Markdown file, `68-FINDINGS.md`, in this phase directory (`.planning/phases/68-code-track-hostile-reader-discovery/`). Committed with the phase.
- **D-02:** It has one section/table per discovery source — `ruff`, `Shield (Semgrep)`, `Shield (gitleaks working-tree)`, `Shield (dependency audit)`, `gitleaks (full history)`, `entry-point skim`. Each finding row carries: short description, `file:line` (or commit SHA for history hits), classification (`FOLD-IN` / `PARKED`), and a one-line rationale.
- **D-03:** Phase 69 consumes the `FOLD-IN` rows directly as its fix checklist (CHARD-04). So every FOLD-IN row must be specific enough to act on without re-investigation; every PARKED row must state why it's parked.

### Fold-in vs parked bar (D-04)
- **D-04:** A finding is **FOLD-IN** if it is **(a) launch-visible** — something a skeptical r/selfhosted engineer browsing the repo / README / `git log` would actually see and ding — **OR (b) any real security or secret exposure**, regardless of visibility. **PARK** pure-internal nitpicks (style the linter doesn't enforce, invisible debt, cosmetic items) with written rationale. This matches the spec's D-3 "launch-visible" bound while treating any genuine security/secret finding as always-fold-in. The config-knob UI debt (DEBT-03/06/07/08) is pre-parked by spec D-5 and must NOT be folded in even if surfaced.

### git-history secrets scan (D-05)
- **D-05:** Run gitleaks over the **full commit history** (13 milestones), honoring the existing `.gitleaksignore` (which allowlists 4 test-fixture files: `tests/test_auth_middleware.py`, `tests/test_auth_routes.py`, `tests/test_auth_integration.py`, `tests/test_auth_config.py`). Any hit **not** covered by that allowlist is treated as a potential real exposure and triaged **highest-priority** — the artifact records it FOLD-IN with a rotate-then-document remediation note (the repo is already public, so assume exposed). A clean result is **stated explicitly** in the artifact ("history scan clean, N commits scanned") rather than silently omitted.

### Entry-point skim depth (D-06)
- **D-06:** Skim each of the six entry-point files with "what would a skeptical engineer flag in ~2 minutes" framing — surface smells (bare `except`, secrets in log lines, obvious injection/SSRF, dead code, alarming `TODO`/`FIXME`, leaked internals in responses). Capture notes in the artifact. This is a **hostile-reader skim, not a full per-file correctness audit** — deep correctness analysis is the turingmind deep-review gate's job (it runs on Phase 69's diff), not this pass. Keeps Phase 68 lightweight and gating rather than duplicating deep review.

### Claude's Discretion
- Exact table column layout within `68-FINDINGS.md` (as long as D-02's fields are present).
- Order in which the tools are run.
- Which specific ruff rule violations (if any surface) are worth a row vs a summary count.
- Whether to capture a short "scan provenance" header (tool versions, commit range, date) — encouraged for reproducibility but not mandated.
</decisions>

<specifics>
## Specific Ideas

- Framing throughout is **"this is on Reddit and a skeptical r/selfhosted engineer is reading it"** — the same hostile lens the sibling SeedSyncarr launch-hardening milestone used. Findings are judged by what that reader would actually notice, not by abstract completeness.
- The one material way Triggarr's situation is riskier than pre-launch SeedSyncarr: it is **already public with a long history**, so a leaked secret in an old commit is already exposed. The full-history gitleaks scan (D-05) is the direct response to that.
- Known curated items the spec already commits Phase 69 to fixing (so they are expected to appear FOLD-IN or be noted as already-known): `.orchestrator.json` not git-ignored (repo hygiene), and SAFETY-03 (manual search bypasses the consecutive-failure counter — `# TODO` at `scheduler.py:~325`). The discovery pass should confirm/locate these, not re-litigate them.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone design (authoritative scope)
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` — the source design spec. §3.1 (code track: discovery + curated known items), D-3 (launch-visible bound), D-4 (curated subset), D-5 (parked config-knob debt), D-8 (the exact discovery toolchain). The fold-in/parked bar (D-04 above) operationalizes spec D-3.
- `.planning/REQUIREMENTS.md` — CDISC-01..05 requirement text + success criteria; the parked v2 items (DEBT-03/06/07/08, UI-01..03) that must NOT be folded in.

### Standing codebase concerns (input to the pass, not a substitute for it)
- `.planning/codebase/CONCERNS.md` — v2.8 source audit; already documents SAFETY-03, DEBT-03/06/07/08 with file:line pointers. The discovery pass should reconcile its findings against this (don't re-discover what's already catalogued; do find what isn't).
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/STRUCTURE.md` — codebase conventions/layout to judge "is this a real smell or an established pattern".

### Existing scan config
- `.gitleaksignore` — the 4 test-fixture allowlist entries the history scan (D-05) honors.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Project tooling is already wired:** `ruff` (config in `pyproject.toml`, rules E/F/I/UP/B/SIM, line-length 120), `pytest` (965 tests). Discovery uses `uv run ruff check triggarr/ tests/`.
- **Discovery toolchain confirmed available on this machine:** gitleaks 8.30.1, semgrep (installed), Shield plugin 0.3.1, pip-audit. No tool is missing — no gray area premised on absent tooling.
- **`.gitleaksignore`** already exists with 4 test-fixture allowlist entries — the history scan extends, not replaces, this.
- **`.planning/codebase/CONCERNS.md`** is a ready-made catalogue of known debt with file:line pointers — use as a cross-check so the pass spends its effort finding NEW issues.

### Established Patterns
- Error handling convention (per CLAUDE.md + CONVENTIONS): `httpx.HTTPError` + `pydantic.ValidationError` catches, no bare `except:`. A bare-except smell in an entry-point file would be a genuine FOLD-IN finding.
- Secrets: `SecretStr` everywhere; `.get_secret_value()` only at HTTP-client init; loguru redacting sink. Any raw secret in a log line or response would be a high-priority FOLD-IN.

### Integration Points
- Output (`68-FINDINGS.md`) is the sole interface to Phase 69 — its `FOLD-IN` rows ARE Phase 69's CHARD-04 fix checklist. No code is touched in this phase.
- The six skim targets: `triggarr/web/routes.py`, `triggarr/search/scheduler.py`, `triggarr/config.py`, `triggarr/db.py`, `triggarr/auth.py`, `triggarr/startup.py`.
</code_context>

<deferred>
## Deferred Ideas

- Config-knob UI debt (DEBT-03 history cap, DEBT-06 drain timeout, DEBT-07 request timeout, DEBT-08 page size) — pre-parked by spec D-5; invisible to a launch reader. Must NOT be folded in even if the pass surfaces them. Tracked in REQUIREMENTS.md v2.
- UI-01/02/03 pixel-exact auth-page verification — out of scope (behind first-run setup, not launch-visible).
- Actual fixing of any fold-in finding — Phase 69 (CHARD-04), not this phase.
</deferred>

---

*Phase: 68-code-track-hostile-reader-discovery*
*Context gathered: 2026-06-02*
