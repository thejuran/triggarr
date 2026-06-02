# Phase 68 Plan — Adversarial Review (codex, round 1)

**Date:** 2026-06-02
**Reviewer:** codex (gpt-5.3-codex) via /codex adversarial review
**Verdict:** FAIL — 1 BLOCKER + 5 HIGH. Plan rewritten in round 2 to address.

## Summary

The plan has the right high-level discovery shape, but several operational assumptions are loose enough to make the pass unsound. The most serious risk is the full-history gitleaks step: the command/count contract does not prove all refs were scanned. The second class is capture quality: tools need explicit structured-output and exit-code handling so findings become usable rows. The artifact also needs stronger metadata and deterministic classification rules so Phase 69 can consume FOLD-IN rows without re-running discovery.

## Findings by Severity

### BLOCKER

**F-1 [BLOCKER] Full-history gitleaks command/count is not tight enough**
- `68-01-PLAN.md` lines 145-153; D-05.
- The plan runs `gitleaks detect --source . --log-opts=--all` but reports `N` via `git rev-list --count HEAD` — a HEAD-only count, not all refs. Artifact could claim an all-ref scan with a mismatched count. With gitleaks 8.30.1 the current CLI form is `gitleaks git . --log-opts="--all"`; `--log-opts` needs the quoted `="--all"` value form.
- **Remediation:** Use `gitleaks git . --log-opts="--all" --no-banner`. Change count to `git rev-list --count --all`. Capture exact command + exit code in provenance. Fail the phase if gitleaks rejects the flag or emits findings without commit SHAs.

### HIGH

**F-2 [HIGH] Shield invocation named but not operationally specified**
- Make the fallback commands the primary contract, or add an explicit Shield contract: exact invocation, expected component outputs, how to split into the three sections, clean-vs-finding exit statuses. Record the exact invocation used.

**F-3 [HIGH] Finding-producing exit codes + plain-text output can break classification**
- ruff/Semgrep/gitleaks/pip-audit all use non-zero exit codes to mean "findings exist," not "command failed"; an autonomous executor could abort before writing rows. Plain text makes IDs hard to map.
- **Remediation:** Require structured capture: `ruff check ... --output-format json`, `semgrep --json`, `gitleaks ... --report-format json --redact`, `pip-audit --format json`. Finding-exit-codes must be captured + classified; genuine tool/command failures recorded separately as discovery failures.

**F-4 [HIGH] Public self-hosting surface is outside the six-file skim**
- The six-file skim omits Dockerfile, entrypoint.sh, `__main__.py`, web middleware, templates, static/htmx, compose/install files — high-traffic launch-visible surfaces a self-hosted reviewer inspects (Docker layer secrets, env-var leakage, shell entrypoint mistakes, template/htmx XSS, auth/middleware edges).
- **Remediation:** Add a "public surface inventory" before the skim: enumerate Docker/compose/entrypoint, CLI entry points, web middleware/auth hooks, templates/static/htmx, config/TOML parsing. For each present item, include in the skim OR record an explicit "not present / covered by source X" line.

**F-5 [HIGH] Absolute pre-park rule can override real security findings**
- D-04 says any real security/secret exposure is FOLD-IN regardless of visibility, but the hard rule says DEBT-03/06/07/08 MUST NOT fold in. Ambiguous when a real finding touches the same file/setting as a pre-parked UI-knob issue.
- **Remediation:** Narrow the hard rule to the exact pre-parked shape: "the setting exists but is not exposed in the UI." Add tiebreaker: independent security/secret/correctness/launch-visible findings on the same files/settings still apply D-04 normally; only the UI-exposure debt itself is forced PARKED.

**F-6 [HIGH] Fold-In Summary drops metadata Phase 69 needs**
- Description + `file:line-or-SHA` is not enough to fix scanner findings without re-running discovery. Dependency findings need package/version/CVE/fixed-version; Semgrep needs rule ID/severity/CWE; gitleaks needs SHA/file/rule/fingerprint; ruff needs rule code.
- **Remediation:** Require stable fields in source sections AND Fold-In Summary: ID, source, locator, rule/advisory, severity, sanitized evidence, rationale, concrete remediation, verification command.

### MEDIUM

**F-7 [MEDIUM]** Extend the Task 4 smell list with config/TOML parsing, template/htmx escaping, Docker/build-context secrets, auth/session middleware, shell/process arg env leakage — same time-box, explicit categories.

**F-8 [MEDIUM]** Add a source-specific tiebreaker matrix: security/secret/runtime-correctness/user-visible-failure = FOLD-IN; pure style/import-order/pyupgrade/test-only = PARKED unless it creates a visible failure; ambiguous needs a written "why a Reddit reviewer would notice" sentence.

**F-9 [MEDIUM]** Assign stable IDs (`P68-FI-001`) to every FOLD-IN row; same ID in source section + summary; add a verification step that confirms one-to-one presence.

### LOW

**F-10 [LOW]** The `<output>` asks for `68-01-SUMMARY.md` but files_modified lists only `68-FINDINGS.md` — contradicts the single-artifact contract. Resolve (SUMMARY.md is GSD's per-plan execution summary, expected; clarify 68-FINDINGS.md is the authoritative discovery artifact).

## Verdict

**FAIL.** Fix F-1 (gitleaks command/count), F-2/F-3 (Shield + structured-output + exit-code handling), F-4 (public-surface inventory), F-5 (DEBT pre-park tiebreaker), F-6 (stable-ID checklist with scanner metadata) before execution.
