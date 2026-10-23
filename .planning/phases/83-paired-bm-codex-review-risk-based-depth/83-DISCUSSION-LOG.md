# Phase 83: Paired BM + Codex Review & Risk-Based Depth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-22
**Phase:** 83-paired-bm-codex-review-risk-based-depth
**Areas discussed:** BM target version, Who runs Codex, Where evidence lives, Demo PRs & classification

---

## BM target version

| Option | Description | Selected |
|--------|-------------|----------|
| v5.0.3, latest | Newest reviewer/fixer behavior; more variables change at once | ✓ (after clarification) |
| v4.9.3, conservative | The version the blueprint assessed; fewer changes | |
| Assess both, decide at gate | Compare both at the gate | |

**User's choice:** The first answer was "i think one came out today". Claude rechecked: v5.0.3 was published 2026-10-22, and the "2 days old" wording in the option was wrong. The owner then confirmed "Yes, v5.0.3".

| Question | Options | Selected |
|----------|---------|----------|
| v5.0.1 model-tier change | Accept but record / Pin old models | Accept but record |
| Settings list | Only code_review standard / Also enable specialist lanes | Also enable specialist lanes |
| Gate surprise | Stop and bring to owner / Fill gaps via instructions | Stop and bring to owner |
| Which lanes | Security+a11y+code-review / Whatever v5.0.3 offers, all on / Let gate propose | Whatever v5.0.3 offers, all on |

**Notes:** The owner chose a broader settings change than the blueprint suggested.

---

## Who runs Codex

| Option | Description | Selected |
|--------|-------------|----------|
| Claude runs it automatically | Read-only Codex after each BM review; owner involved only on failure | ✓ |
| BM asks me to run it | Owner runs Codex each time | |
| Claude runs, I run on high-risk | Hybrid | |

**User's choice:** The first answer was a question: "doesn't BM have a mode that asks for codex?" Claude checked v5.0.3. `/bm:review --codex` covers plans only, and the code-review workflow has no Codex option. The owner then chose "Claude runs it automatically".

| Question | Options | Selected |
|----------|---------|----------|
| Prompt | Fixed template only / Template + Claude's risk notes | Fixed template only |
| Findings | Claude triages, fixes, shows you / Show me before any fix | Claude triages, fixes, shows you |
| Failure | One retry, then ask me / Ask me immediately | One retry, then ask me |

---

## Where evidence lives

| Question | Options | Selected |
|----------|---------|----------|
| Record | PR comment + durable repo copy / PR comment only / Repo files only | PR comment + durable repo copy |
| Raw output | Full raw + summary / Summary only | Full raw + summary |
| At approval | One checklist message / Links to each report | One checklist message |

---

## Demo PRs & classification

| Question | Options | Selected |
|----------|---------|----------|
| Docs PR | One small separate docs PR / Wait for natural one / Demo within phase PR | Other: "no docs only PR -- start the phase on a new branch and save the PR for the end" |
| High risk | Phase 83's own PR if assessed high / A Phase 85 CI change | Phase 83's own PR if assessed high |
| Quick task | Small backlog item / Phase 83 sub-task | Small backlog item |
| Classify | Claude classifies, owner overrides / Owner classifies | Claude classifies, owner overrides |

**Follow-up:**
- Branch: the options were to keep `ci-review-workflow` or cut a new phase branch. The owner answered: "2 - i meant one branch/PR per phase not milestone".
- Docs demo: the options were carry forward as a gap, dry-run, or drop it from REVIEW-08. The owner answered: "3 - no more docs only PRs the PR is prepped on branch at the end of a phase". This is an approved scope change: REVIEW-08's ordinary-docs-PR demonstration is removed.

---

## Claude's Discretion

- Wording and layout of the checkpoint comment, checklist message and Codex template
- Where the template and policy text live, and how `CLAUDE.md` references them
- `codex exec` invocation details (read-only, SHA-bound)
- Order of the review-path demonstrations

## Deferred Ideas

- Phase 85 ACCEPT-03's ordinary-docs-PR case needs revisiting under the no-docs-only-PRs rule
- `/bm:review --codex` for plans
- Extending the acceptance gate to require BM/Codex reports (PILOT-03/FUT-03)
