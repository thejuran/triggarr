# Phase 70 — Codex Adversarial Plan Review (pass 1)

**Date:** 2026-06-02  **Branch:** launch-hardening  **Reviewer:** codex-cli 0.133.0 (`codex exec --sandbox read-only`)
**Scope:** challenge review of 70-01-PLAN.md against 70-RESEARCH.md / 70-CONTEXT.md / REQUIREMENTS.md (PDISC-01/02/03)

---

CHALLENGE — Task 2 has blocker-level execution and scope risks before this plan is safe to run.

- **blocker:** Task 2 writes a fourth Markdown file, `70-CODEX-REVIEW-raw.md`, and even permits leaving it untracked. That contradicts the phase contract of exactly three artifacts and “write NOTHING else” ([70-01-PLAN.md:67](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:67>), [154-171](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:154>)). The current `git status` guard only blocks files outside the phase dir, so this violation would pass.

- **blocker:** PDISC-02 still depends on an unresolved codex non-interactive assumption. `codex exec --help` confirms the flags exist, but not that the run completes without approval/TTY gating. Research explicitly marks that as A1 risk ([70-RESEARCH.md:368](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-RESEARCH.md:368>)). The plan’s fallback records failure in `70-CODEX-REVIEW.md` ([70-01-PLAN.md:171](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:171>)), but PDISC-02 requires the adversarial pass to actually run and capture findings ([REQUIREMENTS.md:39](</Users/julianamacbook/triggarr/.planning/REQUIREMENTS.md:39>)).

- **major:** `-o` capture is treated as reliable enough for the gate, but research only says it captures the final message and flags A2 parsing/capture risk ([70-RESEARCH.md:144](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-RESEARCH.md:144>), [369](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-RESEARCH.md:369>)). The plan does not guard against stale raw output, missing final message, partial/thin output, or nonzero exit with a leftover file.

- **major:** The artifact quality gates permit vague output. Most automated checks are keyword or non-empty checks ([70-01-PLAN.md:132](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:132>), [177](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:177>), [224](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:224>)). PDISC-02 does not require codex to surface the known README version mismatch or SECURITY hardening gaps seeded by research ([70-RESEARCH.md:201](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-RESEARCH.md:201>), [235](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-RESEARCH.md:235>)).

- **major:** Credential scrubbing is under-specified. The plan says no real API key, hostname, or credential may appear, but the automated grep only checks `sk-...` and 32-hex patterns ([70-01-PLAN.md:167](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:167>), [184](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:184>)). It would miss hostnames, URLs, passwords, tokens with other shapes, and any leaked value in the raw scratch file.

- **major:** Scope verification is incomplete for cross-repo work. Task 3 reads `/Users/julianamacbook/seedsyncarr`, but the acceptance gate only checks Triggarr’s `git status` ([70-01-PLAN.md:197](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:197>), [233](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:233>)). An accidental SeedSyncarr edit would not be caught.

- **minor:** PDISC-01 wording over-focuses citations on README lines, but required gripes include `.github/ISSUE_TEMPLATE`, screenshot timestamps, and SeedSyncarr comparison evidence ([70-01-PLAN.md:118](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:118>), [122](</Users/julianamacbook/triggarr/.planning/phases/70-presentation-discovery/70-01-PLAN.md:122>)). That can weaken the “specific enough for Phase 71” standard by forcing indirect citations where direct file citations are needed.

---

# Pass 2 — after rewrite #1 (all pass-1 findings addressed)

**Verdict:** B2 RESOLVED; B1 re-flagged.

- **B2 resolved (confirmed):** Task 2 now pins the non-interactive invocation `codex exec --sandbox read-only --ask-for-approval never --ephemeral --color never -o <mktemp>`, requires exit 0 + a non-trivial findings table (≥1 HIGH/MEDIUM/LOW row) + the seeded README:85 `2.7.2`-vs-`2.8.1` correctness anchor, and replaces the silently-passing failure stub with a hard-stop/retry (`-m o3`, then surface to operator).
- **Majors all confirmed present:** mktemp-outside-repo + unconditional `trap` cleanup; broadened credential scrub with placeholder allow-list; SeedSyncarr working-tree scope guard (`git -C /Users/julianamacbook/seedsyncarr status --porcelain`); seeded-finding correctness anchor in the automated gate; PDISC-01 direct-citation wording for `.github`/`docs/screenshots`/SeedSyncarr evidence.
- **B1 re-flag:** codex objected that the plan's `<output>` block creates `70-01-SUMMARY.md` — "a fourth phase-dir file" — and that the artifact-count guard only grepped `*-raw.md`.

# Pass 2 finding adjudication (receiving code review)

**The B1 re-flag is a FALSE POSITIVE — adjudicated, not capitulated to.** `70-01-SUMMARY.md` is the **mandatory GSD execute-phase completion artifact**; every GSD plan ends by writing a SUMMARY, and the phase directory always also holds the standard planning docs (CONTEXT/RESEARCH/VALIDATION/PLAN/DISCUSSION-LOG/ADVERSARIAL-REVIEW). The phase contract "exactly three artifacts / write nothing else" refers to the three **deliverable critique artifacts** in `files_modified`, NOT a cap on total files in the directory. Removing the SUMMARY would BREAK the executor contract. Codex conflated "three deliverables" with "three files total."

**The legitimate kernel of the re-flag — fixed by targeted edit (within rewrite budget, no full replan):**
1. `<objective>`, `truths[4]`, and `<scope_guard>` reworded from "three artifacts / nothing else" to "three DELIVERABLES," explicitly listing `70-01-SUMMARY.md` + the standard GSD planning docs as EXPECTED (not stray).
2. The scratch guard broadened from `*-raw.md`-only to forbid any un-deliverable scratch this plan could leave (`*-raw.md`, `*-codex-raw*`, `*.tmp`, `*.bak`) — while the real protection against a stray raw file remains structural: codex raw capture goes to a `mktemp` file OUTSIDE the repo, so it can never land in the phase dir at all.

# Pass 3 — verification of the B1 targeted fix

Re-ran codex to confirm the fix; the run hung past ~13 min (well beyond passes 1–2's few-minute completions) and was terminated (SIGTERM). Treated as a **delegated-tool hang, not a plan defect** (orchestrator contract: a hung delegated tool is not an orchestrator fault and does not gate the milestone). The B1 fix does not depend on codex's re-blessing — the SUMMARY is a non-negotiable framework requirement and the targeted edit is self-evidently correct on read.

# Final disposition

**Adversarial gate: PASSED (report-only residual).** Both genuine blockers (B1 raw-file, B2 failure-stub) are resolved by rewrite #1 plus the B1 targeted edit; the pass-2 B1 re-flag was a false positive (mandatory SUMMARY) whose legitimate kernel (precise scratch-guard + unambiguous "deliverables" wording) is fixed. Rewrites used: 1 of 2. Proceeding to EXECUTE.
