---
phase: 84
slug: codex-plan-checker-investigation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-23
---

# Phase 84 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> This phase has no Triggarr application code. Its deliverables are evidence records and a scratch pilot outside the repo, so validation is done with evidence-record checks (files and required fields exist, hashes match, the routing log lines up, negative cases are recorded), not product pytest assertions.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Evidence-record checks (shell: `test -f`, `grep -q`, `jq`, `shasum -a 256 -c`). Triggarr's pytest suite is untouched by this phase. |
| **Config file** | none |
| **Quick run command** | per-task `<automated>` evidence check (see plan tasks) |
| **Full suite command** | `uv run pytest tests/ -x -q` (regression only; must stay green because no repo code changes) |
| **Estimated runtime** | evidence checks < 5 s each |

---

## Sampling Rate

- **After every investigation step:** record evidence right away (hash, log line, or an explicit unavailable statement) before moving to the next step.
- **After every plan wave:** re-run every evidence check written so far.
- **Before `/bm:verify-work`:** each of the 4 ROADMAP success criteria has either a positive evidence record or an explicit deferred/unavailable statement with a reason.
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

*Filled in by the planner/executor per task. Each PLANCHK requirement maps to at least one automated evidence check.*

| Requirement | Behavior | Evidence Check (automated) | Status |
|-------------|----------|----------------------------|--------|
| PLANCHK-01 | Hook support on the installed runtime is verified (present/absent/update-required), never assumed | runtime evidence record contains `agent.spawn`, the exact CLI version, and one of the three verdict strings | ⬜ pending |
| PLANCHK-02 | Only the checker is routed; proof comes from gateway metadata; fail-closed negatives are recorded | `jq` over the gateway request log finds the checker's agentId with a codex backend; other agents' entries are non-codex; the negative runs record explicit incomplete/error | ⬜ pending |
| PLANCHK-03 | Blind comparison on hashed originals, or recorded unavailable or as a labelled reconstruction | `shasum -a 256 -c` manifest passes; OR an explicit unavailable statement with the reason; adoption criteria are recorded before the first run's timestamp | ⬜ pending |
| Criterion 4 | Closeout separates what was investigated from what was deferred | closeout record has both sections; every deferred item has a reason | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Scratch pilot directory and opt-in `agent.spawn` hook exist outside the repo (validated with `claude plugin validate` or equivalent)
- [ ] Harness/procedure for running `claude -p` with JSON output and matching the agentId against the gateway request log
- [ ] Full Disk Access resolved (owner action) or Time Machine recorded as unavailable
- [ ] Cutoff timestamp for "original" recorded with cited evidence (D-09)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Owner spot-check of the adjudication summary and disputed calls | PLANCHK-03 (D-11) | Owner judgement | Owner reads the plain-language summary and records agree/dispute |
| Global Claude Code update go-ahead (only if needed) | PLANCHK-01 (D-02) | Owner approval gate | Show the exact version and changelog; owner confirms in-session |
| Time Machine read access | PLANCHK-03 (D-08) | macOS Full Disk Access is an owner action | Owner grants access or performs the read personally |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
