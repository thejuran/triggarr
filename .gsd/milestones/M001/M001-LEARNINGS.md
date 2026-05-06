---
phase: completion
phase_name: milestone learnings extraction
project: Triggarr
generated: 2026-05-06T00:04:44Z
counts:
  decisions: 3
  lessons: 4
  patterns: 4
  surprises: 3
missing_artifacts:
  - human documentation UAT decision for README/SECURITY/TODO
  - /deep-review result or explicit human deferral
---

# M001 Learnings: Portable Config Directory & Documentation Refresh

### Decisions

- **Keep Docker/default `/config` behavior unchanged while documenting absolute `TRIGGARR_CONFIG_DIR` for standalone installs.** Runtime `/config` references were intentional defaults/backward compatibility, so S01 proved the contract with tests and probes instead of changing production path code.
  Source: S01-SUMMARY.md/Key decisions

- **Move secure-cookie forwarded-proto trust to the Uvicorn/ASGI boundary.** Runtime cookie-setting code uses `request.url.scheme`; only Uvicorn proxy-header processing constrained by `TRUSTED_PROXY_IPS` may translate trusted forwarded-proto headers.
  Source: DECISIONS.md/D001-D002

- **Represent unresolved human docs UAT and `/deep-review` as needs-attention instead of approval.** Agent-created packets, tests, and stale-claim scans are preparation and diagnostics only; they do not count as human acceptance.
  Source: S06-HUMAN-UAT-GATE.md/Gate Record

### Lessons

- **Import-time path constants require environment setup before import.** `CONFIG_DIR`, `CONFIG_PATH`, and `STATE_PATH` freeze when their modules are imported, so tests and operational probes must set `TRIGGARR_CONFIG_DIR` before importing Triggarr modules.
  Source: S01-SUMMARY.md/Patterns established

- **Mechanical verification and release approval are different gates.** Focused tests, full pytest, lint, stale-claim scans, and docs guardrails can prove mechanics, but human UAT and `/deep-review` remain unresolved until a human records a decision.
  Source: S05-SUMMARY.md/Known Limitations

- **Historical GSD artifact inconsistencies can block milestone closure even when slices are marked complete.** S02 was complete with a residual pending task; milestone completion required repairing canonical task state and replacing the placeholder summary with a real evidence trail.
  Source: S06-S02-SUPERSESSION.md/Canonical Supersession

- **Unsafe documentation wording can be superseded by a later security decision.** The stale S02/T04 wording around direct `X-Forwarded-Proto` handling was not applied; S04/D001/D002 established the safer ASGI/Uvicorn trust-boundary model.
  Source: S06-S02-SUPERSESSION.md/Superseded S02/T04 Wording

### Patterns

- **Use focused boundary tests plus fresh temp-directory probes for startup/path contracts.** The combination proves helper-level behavior, import/startup wiring, and real config/state/db co-location without unnecessary production code changes.
  Source: S01-SUMMARY.md/Patterns established

- **Add docs-accuracy tests for high-risk operator/security claims.** README TOML examples and External-auth/secure-cookie trust-boundary text are executable documentation surfaces, not just prose.
  Source: S04-SUMMARY.md/Patterns established

- **Use canonical supersession artifacts when a previous slice summary is stale.** Validators should be pointed to authoritative task summaries, later assessments, decisions, and tests instead of relying on placeholder artifacts.
  Source: S06-S02-SUPERSESSION.md/Canonical Evidence Chain

- **Encode unresolved human/release gates in machine-readable verification artifacts.** `T04-VERIFY.json` intentionally marks the human gate as not passed so automation cannot confuse mechanical pass with release approval.
  Source: S06-SUMMARY.md/What Happened

### Surprises

- **The configurable-config-directory TODO described already-shipped behavior.** The runtime audit found no production hardcoded `/config` defect; the main gap was stale docs/backlog text and missing proof.
  Source: S01-SUMMARY.md/What Happened

- **The original S02 closeout produced a blocker placeholder instead of usable slice evidence.** Downstream validation had to rely on S02 task summaries plus S04/S06 supersession until the completion retry repaired S02 state.
  Source: S06-S02-SUPERSESSION.md/Historical Blocker Treatment

- **A milestone can be mechanically complete while still not release-ready.** M001 passed focused/full/lint/operational verification, but the human docs UAT and `/deep-review` gates remain unresolved and keep release validation at needs-attention.
  Source: S06-VALIDATION-EVIDENCE.md/Validation Recommendation
