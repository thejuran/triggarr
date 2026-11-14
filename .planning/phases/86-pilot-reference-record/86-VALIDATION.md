---
phase: 86
slug: pilot-reference-record
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-30
---

# Phase 86 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | Refresh-counts PR: `uv run pytest tests/test_refresh_counts.py tests/test_malformed_records_client_path.py -x -q`; card-template PR: `uv run pytest tests/test_outcome.py tests/test_app_cards.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~120 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the files touched (docs tasks: the task's grep/structure check). Task `<verify>` blocks use focused tests only; the full suite + ruff runs as the final-head gate inside the action with HEAD asserted on the pilot branch (86-02 Task 3, 86-04 Task 1, 86-05 Task 3, 86-06 Task 2, 86-10 Task 1)
- **After every plan wave:** Run the full suite command
- **Before `/bm:verify-work`:** Full suite must be green on each pilot PR's final head and on the Phase 86 PR
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

Filled in by the planner from the revised plans (2026-10-30); Status columns are updated by the executor, never pre-claimed. "File Exists ✅ (plan)" means the verify command is defined in the plan, not that it has run. Code tasks (Refresh-counts, card template) are TDD: the existing tests that pin the old behavior are rewritten first (red), then the fix (green). Docs tasks (pilot record, scorecards, PILOT-03 decision, adoption guide) are verified by grep for required sections and verbatim text (e.g. the D-15 bar present before the comparison results).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 86-01-01 | 01 | 1 | PILOT-02, PILOT-03 | T-86-02 | D-15 bar committed alone before any result | grep | grep for D-15 bar text, method/bar headings, commit subject | ✅ (plan) | ⬜ pending |
| 86-01-02 | 01 | 1 | PILOT-01 | — | scorecards cite committed records only; "not recorded" where absent | grep | grep for #48/#36/#44 sections, "not recorded", Sources: | ✅ (plan) | ⬜ pending |
| 86-01-03 | 01 | 1 | PILOT-01, PILOT-02 | T-86-03b | fail-closed publication gate re-check committed before any review artifact | bash self-test | `bash 86-publication-gate-selftest.sh 86-publication-gate.sh` prints `selftest: 23 passed, 0 failed` from bash and from zsh (clean, matching, unreadable/missing-file, empty-list cases; a 32-hex hit passes only with an accepted `- `<repo-relative path>`: not a credential -- <reason>` entry for its exact path in the single `## Credential-shape hand review` section of 86-REVIEW-EVIDENCE.md, and the negative cases (ordinary citation, entry outside the section, rejected, pending, conflicting, empty-reason, same-basename different-file, basename-only, duplicated section) all block); both files tracked; commit subject | ✅ (plan) | ⬜ pending |
| 86-02-01 | 02 | 2 | PILOT-01 | T-86-04 | RED: per-record skip for 3 apps + real-client boundary; envelope/HTTP guards | unit (TDD red) | focused pytest `-k "skipped_stays_connected or skips_non_object_record"` → 7 failed; `-k still_disconnects` → 6 passed; HEAD = pilot branch | ✅ (plan) | ⬜ pending |
| 86-02-02 | 02 | 2 | PILOT-01 | T-86-04, T-86-05, T-86-06 | GREEN: allow_non_object_records=True + _screen_queue; instance stays connected | unit | HEAD asserted on pilot branch; focused refresh/client-path pytest + ruff | ✅ (plan) | ⬜ pending |
| 86-02-03 | 02 | 2 | PILOT-01 | T-86-07 | final-head gate on H1, then restore phase checkout | unit (full) + git | full suite + ruff in action with HEAD = H1; verify: back on phase branch, clean, not pushed | ✅ (plan) | ⬜ pending |
| 86-03-01 | 03 | 3 | PILOT-02 | T-86-08, T-86-10, T-86-11b | three independent H1 reviews; Codex complete on H1 | file + json | H1 via `git show` of committed SUMMARY; pilot tip = H1; vibe/BM reports exist; status.json complete with inspected_head = H1 | ✅ (plan) | ⬜ pending |
| 86-03-02 | 03 | 3 | PILOT-02, PILOT-01 | T-86-09, T-86-11 | proof-based labels; publication gate before commit | grep + gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | checkpoint marker, result filled, commit subject, gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | ✅ (plan) | ⬜ pending |
| 86-03-03 | 03 | 3 | PILOT-02 | T-86-09 | owner tally decision verbatim | grep | grep "Owner tally decision (20" + commit subject | ✅ (plan) | ⬜ pending |
| 86-04-01 | 04 | 4 | PILOT-01, PILOT-02 | T-86-12, T-86-14 | batched revision; full gate with HEAD = H_final | unit | switch to pilot, assert HEAD/clean, focused pytest + ruff, switch back | ✅ (plan) | ⬜ pending |
| 86-04-02 | 04 | 4 | PILOT-01 | T-86-13, T-86-14b | fresh final-head evidence; publication gate | grep + gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | phase branch, findings table, commit subject, gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | ✅ (plan) | ⬜ pending |
| 86-05-01 | 05 | 5 | PILOT-01 | T-86-17 | RED: kind/skip_count pinned; equivalence tests pin current output | unit (TDD red) | test_outcome fails, test_app_cards passes, no removed card-test lines, divergence note exists | ✅ (plan) | ⬜ pending |
| 86-05-02 | 05 | 5 | PILOT-01 | T-86-17 | conditional owner scope decision on visible divergence | grep | note says "not needed" or holds verbatim owner decision | ✅ (plan) | ⬜ pending |
| 86-05-03 | 05 | 5 | PILOT-01 | T-86-15, T-86-16 | GREEN: template uses r.kind; rendering unchanged | unit + grep | HEAD = pilot branch, clean; focused pytest + ruff; no r.text classification | ✅ (plan) | ⬜ pending |
| 86-06-01 | 06 | 6 | PILOT-01 | T-86-18, T-86-20b | card first-head reviews recorded; publication gate | grep + file + gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | section exists, status/vibe files exist, phase branch, gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | ✅ (plan) | ⬜ pending |
| 86-06-02 | 06 | 6 | PILOT-01 | T-86-18, T-86-19 | batched revision + final-head evidence | unit + gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | switch to pilot, assert HEAD/clean, focused pytest + ruff, switch back, gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | ✅ (plan) | ⬜ pending |
| 86-07-01 | 07 | 7 | PILOT-01 | — | owner push decision recorded before push | grep | owner decisions log mentions push | ✅ (plan) | ⬜ pending |
| 86-07-02 | 07 | 7 | PILOT-01 | T-86-23, T-86-24, T-86-24c | push, non-acceptance checks green, per-head comments | gh + gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | comment URLs; one PR per branch; non-acceptance checks pass/skipping; gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | ✅ (plan) | ⬜ pending |
| 86-07-03 | 07 | 7 | PILOT-01 | T-86-21, T-86-22, T-86-24b | first PR accepted on exact head, merged by owner; second still open | gh + grep | refresh PR merged; card PR open; Merged: line | ✅ (plan) | ⬜ pending |
| 86-10-01 | 10 | 8 | PILOT-01 | T-86-30, T-86-31 | second branch merged with main once (no rebase); review round on H_merge and on each owner-approved fix head | git + file | branch/clean; H_merge read from scratch file is a two-parent merge with origin/main ancestor and a `commit (merge):` reflog entry; HEAD descends from H_merge with no further merges; HEAD = last `Reviewed head:`; current-head outputs exist | ✅ (plan) | ⬜ pending |
| 86-10-02 | 10 | 8 | PILOT-01 | T-86-30, T-86-33 | H_final pushed, not BEHIND, non-acceptance checks green, new comment; publication gate | gh + gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | not BEHIND; checks pass/skipping; comment marker for current head; gate re-check (`bash 86-publication-gate.sh`: gitleaks, 32-hex scan, public-infra grep; fails closed) | ✅ (plan) | ⬜ pending |
| 86-10-03 | 10 | 8 | PILOT-01 | T-86-32 | owner acceptance on H_final; owner merges | gh + grep | both pilot PRs merged; ≥2 Merged: lines | ✅ (plan) | ⬜ pending |
| 86-08-01 | 08 | 9 | PILOT-01 | — | five scorecards; backlog items settled | grep | no "filled in by 86-08"; ≥5 Sources:; MAINTENANCE item resolved | ✅ (plan) | ⬜ pending |
| 86-08-02 | 08 | 9 | PILOT-03 | — | recommendation applies fixed D-15 bar (incomplete comparison is not a pass) | grep | Decision 1/2 headings, FUT-03, RISK-02 | ✅ (plan) | ⬜ pending |
| 86-08-03 | 08 | 9 | PILOT-03 | — | owner PILOT-03 decisions verbatim | grep | no "pending" decisions; decision lines present | ✅ (plan) | ⬜ pending |
| 86-09-01 | 09 | 10 | PILOT-04 | — | adoption guide sections; no private infrastructure | grep | required headings; no local paths/username/hostname/tailnet | ✅ (plan) | ⬜ pending |
| 86-09-02 | 09 | 10 | PILOT-03 | — | STATE/ROADMAP/REQUIREMENTS hand-off consistent | grep | last_updated today; Phase 86 unchecked; no complete/await status; FUT-03 note | ✅ (plan) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements, plus one addition made in Wave 1: 86-01 Task 3 commits `86-publication-gate.sh` and its self-test before any review artifact exists, and every later publication-gate verify calls it. The tests to change already exist (`tests/test_refresh_counts.py`, `tests/test_malformed_records_client_path.py`, `tests/test_outcome.py`, `tests/test_app_cards.py`).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Owner PILOT-03 decisions recorded | PILOT-03 | Owner decision | Owner answers the recommendation; decision quoted in the pilot record |
| Exact-commit owner acceptance of each new pilot PR | PILOT-01 | Owner-only gate | Per `docs/owner-cli-acceptance.md` |
| Proof-based tally approved | PILOT-02 | Owner approves tally (D-09) | Owner reviews the comparison tally |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
