---
phase: 70-presentation-discovery
plan: "01"
subsystem: documentation-critique
tags: [discovery, presentation, codex, cross-repo, critique]
dependency_graph:
  requires: [phase-68-FINDINGS.md, phase-69]
  provides: [70-CRITIQUE.md, 70-CODEX-REVIEW.md, 70-CONSISTENCY-AUDIT.md]
  affects: [phase-71-presentation-rewrite]
tech_stack:
  added: []
  patterns: [discover-dont-fix, codex-exec-adversarial-pass, cross-repo-audit]
key_files:
  created:
    - .planning/phases/70-presentation-discovery/70-CRITIQUE.md
    - .planning/phases/70-presentation-discovery/70-CODEX-REVIEW.md
    - .planning/phases/70-presentation-discovery/70-CONSISTENCY-AUDIT.md
  modified: []
decisions:
  - "codex exec --ask-for-approval flag does not exist in 0.133.0; used -c 'approval_policy=never' with stdin from /dev/null to defeat TTY block while keeping sandbox read-only"
metrics:
  duration: "~50 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
---

# Phase 70 Plan 01: Presentation Discovery Summary

**One-liner:** Hostile read of Triggarr's README/SECURITY/CONTRIBUTING + real codex exec adversarial pass + SeedSyncarr cross-repo divergence audit produced three cited, actionable gate artifacts for Phase 71.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Cynical-reader teardown (PDISC-01) | 38fa67f | 70-CRITIQUE.md (11 gripes, 3 D-08 lenses, direct citations) |
| 2 | Codex adversarial docs pass (PDISC-02) | 131f73a | 70-CODEX-REVIEW.md (6 findings: 3 HIGH, 3 MEDIUM, real codex run) |
| 3 | SeedSyncarr consistency audit (PDISC-03) | 8e6ba81 | 70-CONSISTENCY-AUDIT.md (11-signal divergence table) |

## What Was Built

### 70-CRITIQUE.md (PDISC-01)

Cynical r/selfhosted-reader teardown across three D-08 first-impression lenses. 11 gripes total (8 RESEARCH-pre-confirmed + 3 new):

- **Lens (a) Trustworthy?** — plain H1 + 2 badges (no release/license badge); screenshots stale (2026-04-14, predates v2.7 redesign); bug template version tops at v2.3 (current: v2.8.1); bug template omits Lidarr from App Type
- **Lens (b) Get it running in 5 min?** — pip install hardcodes v2.7.2 (actual: v2.8.1); Docker first-run sys.exit(1) behavior undocumented; no Quick Start section
- **Lens (c) Why this over alternatives?** — one-liner is feature-not-benefit-led; no Related Projects cross-link to SeedSyncarr; SECURITY.md omits v2.8/v2.8.1 hardening specifics

Every gripe cites a direct source location (README line, `.github/ISSUE_TEMPLATE/bug-report.yml`, `docs/screenshots/*.png` timestamps, SeedSyncarr README Related Projects section). Each gripe states a fix direction without writing the rewritten copy.

### 70-CODEX-REVIEW.md (PDISC-02)

Real codex exec run completed (exit 0). Invocation: `codex exec --sandbox read-only --ephemeral --color never -o $RAW -c 'approval_policy="never"' "<framing-prompt>" < /dev/null`. Model: gpt-5.5, reasoning: xhigh. Session ID: 019e8a1e-da78-7032-8349-dadd144e8d45.

6 findings surfaced by codex independently:
- **HIGH** — pip install cites `triggarr-2.7.2-py3-none-any.whl` vs actual v2.8.1 (seeded anchor confirmed present)
- **HIGH** — systemd unit `User=triggarr` + `TRIGGARR_CONFIG_DIR=/var/lib/triggarr` missing `StateDirectory=triggarr`; first start fails
- **HIGH** — SSRF claim overstates protection scope (`validate_arr_url()` only applied in settings POST handler, not TOML loading)
- **MEDIUM** — SECURITY.md "Credential Protection" implies at-rest secrecy; plaintext-on-disk caveat missing
- **MEDIUM** — tag-filtering fail-open behavior undocumented
- **MEDIUM** — Tailwind version mismatch between Dockerfile pin (v4.2.1) and committed CSS (v4.2.2)

SECURITY.md hardening gaps (CSP nonces, session-secret rotation, `apikey=` rejection, Basic-auth control-char validation, session-secret startup check) added as Phase 71 notes — codex focused on install/quickstart and security-claim accuracy per the framing prompt.

Credential scrub: passed. No raw file in phase dir.

### 70-CONSISTENCY-AUDIT.md (PDISC-03)

11-signal SeedSyncarr divergence table with columns: signal · Triggarr current state · SeedSyncarr current state · recommended reconciliation · Phase 71 item.

**SeedSyncarr leads in presentation:**
- Centered wordmark with dark/light variants above the fold
- Screenshot above the fold (before any text)
- 4 badges (Release + License missing from Triggarr)
- Quick Start section at the top
- Related Projects section linking to Triggarr (Triggarr has no reciprocal link)
- Benefit-led one-liner

**Triggarr is AHEAD (D-07 reconciliation — SeedSyncarr has the gap):**
- Security reporting: GitHub GSVR vs email
- SECURITY.md: full threat model vs 5 bullet points
- Commit conventions: explicitly documented

SeedSyncarr working tree verified clean throughout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `--ask-for-approval never` flag does not exist in codex-cli 0.133.0**
- **Found during:** Task 2
- **Issue:** The RESEARCH.md-pinned flag `--ask-for-approval never` is not a valid codex exec option; exit code 2 with "unexpected argument" error.
- **Fix:** Used `-c 'approval_policy="never"'` (valid config override per `codex exec --help`) combined with `< /dev/null` to redirect stdin and defeat the TTY wait. This achieves the same effect: auto-approve read-only operations without interactive prompt, while keeping `--sandbox read-only` active.
- **Verification:** codex ran to exit 0 with `approval: never, sandbox: read-only` shown in session header. Real findings table produced with the seeded README:85 2.7.2 anchor.
- **Files modified:** None (workaround is in command flags only; 70-CODEX-REVIEW.md documents the actual command run)
- **Commit:** 131f73a (included in Task 2 commit with note in provenance)

**2. [Rule 3 - Output preservation] RAW temp file cleaned up before content captured**
- **Found during:** Task 2 (first attempt)
- **Issue:** The EXIT trap ran before the bash script captured the RAW file content, because the codex run was backgrounded and the script exited.
- **Fix:** Captured the RAW file content and copied to `/tmp/codex-review-final.txt` before the cleanup trap fired, by running the full script synchronously in the background and reading the persistent copy.
- **Verification:** `/tmp/codex-review-final.txt` contained 7 lines including the complete findings table.

## Known Stubs

None. All three artifacts contain real cited findings from direct file inspection (PDISC-01/03) and a real codex run (PDISC-02). No placeholder text, no "coming soon" entries.

## Threat Flags

None. This phase writes only Markdown critique artifacts; no runtime code, endpoints, or secrets handling was introduced. T-70-01 (credential scrub) and T-70-02 (tamper scope) mitigations confirmed applied.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| 70-CRITIQUE.md exists | FOUND |
| 70-CODEX-REVIEW.md exists | FOUND |
| 70-CONSISTENCY-AUDIT.md exists | FOUND |
| 70-01-SUMMARY.md exists | FOUND |
| Commit 38fa67f (Task 1) | FOUND |
| Commit 131f73a (Task 2) | FOUND |
| Commit 8e6ba81 (Task 3) | FOUND |
| No scratch files in phase dir | PASSED |
| No modifications outside phase dir | PASSED |
| SeedSyncarr working tree clean | PASSED |
| Ruff clean | PASSED |
| Credential scrub | PASSED |
