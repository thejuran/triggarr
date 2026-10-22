---
phase: 83
slug: paired-bm-codex-review-risk-based-depth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-22
---

# Phase 83 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> This is a process/instruction phase: every ROADMAP success criterion is "(Instruction-enforced)".
> Evidence means demonstration artifacts, with an explicit positive case and, where ROADMAP calls for it, a deliberate negative case. See `83-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None for phase behaviors (process/instruction phase); existing pytest is a regression guard only |
| **Config file** | n/a |
| **Quick run command** | `uv run ruff check triggarr/ tests/` plus file/grep assertions per task |
| **Full suite command** | `uv run pytest tests/ -x -q` (confirms no application-code drift) |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's grep/file assertions (acceptance_criteria)
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Per checkpoint (push):** Full demonstration cycle (BM review → Codex pass → risk note → evidence comment bound to the exact head SHA)
- **Before `/bm:verify-work`:** Full suite green and every requirement's evidence artifact present
- **Max feedback latency:** 60 seconds (automated parts)

---

## Per-Task Verification Map

To be filled by the planner/executor from PLAN.md task IDs. The requirement-to-evidence mapping is:

| Requirement | Evidence | Positive Case | Negative Case | Status |
|-------------|----------|---------------|---------------|--------|
| REVIEW-01 | Baseline doc + before/after `.planning/config.json` diff + `/bm:version` output | Update only after a recorded owner approval of the exact version and settings list | Without a recorded approval, no update or settings change happens (described stop) | ⬜ pending |
| REVIEW-02 | Codex report per BM review path (phase execution, quick, explicit review, review after fixes) | One demonstration per path | BM cannot invoke Codex → explicit pending request, never "clean" | ⬜ pending |
| REVIEW-03 | Locally constructed missing/stale/wrong-SHA report | — | Reported as incomplete | ⬜ pending |
| REVIEW-04 | Codex `--output-schema` JSON from a real run | All required fields present | Missing field fails schema validation | ⬜ pending |
| REVIEW-05 | Depth fields in the checkpoint record | requested = actual | >50-file downgrade reported verbatim | ⬜ pending |
| REVIEW-06 | Pre-re-review snapshots + refreshed evidence on the new head | Two dated snapshots, two head-bound records | Earlier-head evidence never cited for a later head | ⬜ pending |
| REVIEW-07/08 | Classification policy doc + CLAUDE.md diff | Ordinary-docs and sensitive-docs PRs classified with rationale | Upward reclassification reasoning shown | ⬜ pending |
| RISK-01/02 | Risk section of the checkpoint record | High-risk checkpoint records a vibe-check recommendation and the owner's decision | Below high → recorded as not demonstrated, never claimed passed | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Baseline record for REVIEW-01 (created first, before any BM change)
- [ ] Fixed Codex adversarial-review prompt/contract doc
- [ ] Codex findings output schema JSON (every REVIEW-04 field)
- [ ] Review-classification policy doc
- [ ] REVIEW.md snapshot/archive convention before each re-review

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Owner approves the exact BM version and settings list | REVIEW-01 | Owner decision gate | Present baseline + target assessment; record the owner's explicit approval before the update |
| Owner records vibe-check decision at a high-risk checkpoint | RISK-02 | Owner decision | Present the risk note; record the owner's decision against the head SHA |
| Owner acceptance of the phase PR | all | Exact-commit owner acceptance is unchanged | Per `docs/owner-cli-acceptance.md`; never inferred or self-approved |

---

## Validation Sign-Off

- [ ] All tasks have an automated assertion or a listed manual verification
- [ ] Sampling continuity: no 3 consecutive tasks without an automated check
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
