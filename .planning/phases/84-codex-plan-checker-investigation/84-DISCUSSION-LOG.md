# Phase 84: Codex Plan-Checker Investigation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-23
**Phase:** 84-codex-plan-checker-investigation
**Areas discussed:** Runtime update gate, Recovering Phase 81 originals, Adoption criteria, PR shape and budget

---

## Runtime update gate

| Option | Description | Selected |
|--------|-------------|----------|
| Side-by-side install | Newer CLI installed separately, used only for the scratch session | |
| Stop and propose | Record unsupported, propose update, wait | |
| Update globally | Update the main Claude Code install | ✓ |

**User's choice:** Update globally. **Notes:** Claude still shows the exact target version and changelog before applying (no silent update).

| Option | Description | Selected |
|--------|-------------|----------|
| Only if hook fails | Pilot custom-checker fallback only if hook unsupported/unreliable | ✓ |
| Defer it | Record failure and stop | |
| Test both regardless | Pilot both routes | |

| Option | Description | Selected |
|--------|-------------|----------|
| Strongest available | Most capable Codex model at pilot time | ✓ |
| Same as code review | Match Phase 83 Codex model | |
| You decide | Claude picks | |

| Option | Description | Selected |
|--------|-------------|----------|
| Highest effort | Both checkers at max effort, matched | ✓ |
| BM defaults | Everyday behavior | |

---

## Recovering Phase 81 originals

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, read-only | Browse Time Machine snapshots read-only, copy to scratch, hash | ✓ |
| Ask me first | List snapshots, owner decides | |
| Don't use backups | Skip Time Machine | |

| Option | Description | Selected |
|--------|-------------|----------|
| Evidence-based | Pin cutoff from timestamps; all nine plans consistent | ✓ |
| Closest snapshot | Latest snapshot before findings date | |

| Option | Description | Selected |
|--------|-------------|----------|
| Labelled reconstruction | Record unavailable, then separately labelled reconstructed benchmark | ✓ |
| Record unavailable, stop | Pilot only | |
| Use another phase | Different phase with intact plans (scope change) | |

| Option | Description | Selected |
|--------|-------------|----------|
| Claude, owner spot-checks | Fresh blind Claude adjudicator; owner reviews summary + disputes | ✓ |
| Claude + Codex both score | Two adjudicators | |
| Claude only | Single adjudicator, no dispute flagging | |

---

## Adoption criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Beat ordinary checker | >=2 more of 7 than ordinary checker, FPs no worse | ✓ |
| Absolute threshold | >=5 of 7 | |
| Both | Strictest | |

| Option | Description | Selected |
|--------|-------------|----------|
| Cap them | <=1 FP per 2 real findings | ✓ |
| Informational only | Record only | |

**Must-haves (multi-select):** BM loop works end to end; Fails closed; Revision round holds up; Tolerable time/cost — all four selected.
**User's notes (verbatim):** "Select all four, with these qualifications: End-to-end loop: preserve BM's checker instructions, structured output, revision/recheck, post-bounce and resume behavior. Fail closed: unavailable routing or incomplete output stays visibly incomplete; no silent fallback. Revision quality: use independently adjudicated findings, including false positives. Keep blind first-pass results separate from the feedback-informed round. Time/cost: set limits before comparison; record actual duration and observable usage. Mark unavailable measurements as unknown. Also require proof of the routed backend/model, confirmation that other agents' models remain unchanged, and a tested way to disable the integration and restore ordinary checking. A model label alone isn't proof."

| Option | Description | Selected |
|--------|-------------|----------|
| Don't adopt; report | Mixed = not met; owner may still adopt | ✓ |
| Supplement, don't replace | Recommend running alongside | |

---

## PR shape and budget

| Option | Description | Selected |
|--------|-------------|----------|
| Ride in Phase 85's PR | Carry records into Phase 85 PR | |
| Stay local until needed | Records stay local, not pushed | ✓ |
| Exception: own PR | One-time docs-only PR | |

| Option | Description | Selected |
|--------|-------------|----------|
| Separate dir outside repo | e.g. ~/scratch/planchk-pilot | ✓ |
| Session scratchpad | Ephemeral | |

| Option | Description | Selected |
|--------|-------------|----------|
| 2 each, disclose spread | 2 blind runs + 1 revision run per checker | ✓ |
| 1 each | | |
| 3 each | | |

| Option | Description | Selected |
|--------|-------------|----------|
| 30 min, stay in plan | | |
| 15 min | Tighter cap | ✓ |
| No time cap, record it | | |

**Notes:** Phase-wide constraint of staying within the ChatGPT subscription (no paid overage) carried into CONTEXT D-18 from the recommended option's framing — confirm at planning if the owner intended otherwise.

---

## Claude's Discretion

- Scratch directory layout and packet assembly mechanics
- Timestamp sources for the cutoff (must be cited)
- Hook implementation details within blueprint constraints

## Deferred Ideas

- Activating any Codex plan-checker integration in Triggarr (separate owner approval)
- Blind comparison on another phase (not chosen)
