# .planning/ format for the Roadmaps page

The Roadmaps page (http://localhost:8088 on the MacBook, `maguffynas:8096` for the GitHub-only copy) builds every card and detail view from three files in a repo's `.planning/` folder. This guide says what it reads and how to write those files so the page stays accurate.

Anything not described here is ignored, so extra sections and notes are fine.

**Golden rule: `STATE.md` is the source of truth for where a project is right now. `ROADMAP.md` describes the plan. When the two disagree, the page shows a red "Planning files disagree" box and believes `STATE.md`.**

---

## STATE.md (required)

A repo without `.planning/STATE.md` does not appear on the page at all.

### Front matter (top of the file)

```yaml
---
milestone: v2.12
milestone_name: Search Correctness & Trustworthy Feedback
status: "Phase 80 executed — PR #28 open, in review (not merged or deployed)"
stopped_at: "Phase 80 executed; PR #28 in review, awaiting push"
last_updated: "2026-10-18T16:40:00Z"
last_activity: 2026-10-18 -- PR #28 review fixes committed
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 19
  completed_plans: 19
  percent: 80
---
```

| Key | Shown as | Rule |
|---|---|---|
| `milestone`, `milestone_name` | Card heading, detail title | The milestone being worked on now. Must match the 🔨 milestone in ROADMAP.md. |
| `status` | Coloured status badge | One line, see vocabulary below. |
| `stopped_at` | "Stopped at" box, card summary | Where work paused, in a sentence. |
| `last_updated` | "Updated … ago", card sort order | **Update it every time STATE.md is edited.** If the file was saved more than a day after this date, the page warns that the front matter is stale. |
| `last_activity` | Under the status KPI | Optional. |
| `progress.*_plans` | "Plans" KPI | Optional. |
| `progress.percent` | Card bar, **only** when ROADMAP.md has no active-milestone phase list | Optional. |

**Status vocabulary.** The badge colour comes from words in `status`:

- `planning`, `discussing`, `ready` → amber outline
- `executing`, `in progress`, `verifying`, `in review` → solid amber
- `blocked`, `paused`, `on hold` → red
- `complete`, `shipped`, `done` → green
- `Awaiting next milestone` / `Between milestones` → grey "Between milestones"; the card shows the last milestone as shipped (100%) plus the next one

To mark the current phase as finished, the status must say `complete`, `merged`, `shipped`, `deployed`, `verified` or `done`. It must not also say `in review`, `open`, `blocked` or `not merged`.

### Body sections

```markdown
**Current focus:** PR #28 (Phase 80) review and merge; Phase 81 next

## Current Position

Phase: 80 (cycle-robustness) — EXECUTED, IN REVIEW
Plan: 5 of 5 complete
Status: Phase 80 executed — PR #28 open, in review

## Operator Next Steps

- Push the review-fix checkpoint and re-review PR #28
- Then Phase 81

## Deferred Items

| Kind | Item | Status |
|------|------|--------|
| Follow-up | Refresh counts skips malformed records | Deferred |
```

- `Phase:` must **start with the phase number** (`80`, `119.1`). The page uses it to highlight the current phase and its plans.
- Next steps: the first three `- ` bullets are shown. A single `Next action: …` line also works.
- Deferred Items rows appear under "Backlog & deferred".

---

## ROADMAP.md

### 1. Milestones list (history bar + planned milestones)

```markdown
## Milestones

- ✅ v2.11 Never-Searched-First Search Queue -- Phase 76 (shipped 2026-06-04)
- 🔨 v2.12 Search Correctness & Trustworthy Feedback -- Phases 77-81 (in progress)
- 📋 v2.13 Reliability -- planned
```

- `✅` = shipped. Put the **ship date as YYYY-MM-DD** at the end; it places the bar on the timeline.
- `🔨` (or `🚧`, or the words `in progress`) = the active one. Exactly one.
- `📋` = agreed but not started. It shows under "Upcoming milestones" unless a fuller section below describes it.
- Start each entry with the version (`v2.12`) so the page can match it with STATE.md's `milestone`.

### 2. Active milestone phase list (card progress)

```markdown
### 🔨 v2.12 Search Correctness & Trustworthy Feedback (Phases 77-81, in progress)

- [x] **Phase 77: Secret & Reset-Token Log Hygiene** - Reset token never reaches the viewer
- [x] **Phase 78: Honest Cycle Outcomes** - Each cycle grades Success/Partial/Failed
- [ ] **Phase 80: Cycle Robustness** - A malformed record can't wedge a cycle
- [ ] **Phase 81: Correct Sonarr Grab Attribution** - Grabs credit exactly once
```

- The heading needs `🔨`/`🚧`/`in progress`. The phase list is everything under it until the next heading or `<details>`.
- Each line: `- [ ]` or `- [x]`, then `Phase N:` (bold optional), the name, then ` - ` or ` — ` and a one-line description.
- **Tick `[x]` only when the phase is actually finished** (merged / verified). An executed-but-in-review phase stays `[ ]`. If you tick it early, the page counts it as in review and flags the mismatch.
- Add `(INSERTED)` for inserted phases and `dropped` for dropped ones (they are left out of the count).
- Shipped milestones' phase lists can sit inside `<details>` blocks; they are not counted.
- **Without this section the card has no phase count**, and falls back to `progress.percent` from STATE.md.

### 3. Current phase detail (plans list)

```markdown
### Phase 81: Correct Sonarr Grab Attribution

**Goal**: Grabs credit the matching series+season exactly once

- [ ] 81-01-PLAN.md — schema migration for grab ownership
- [ ] 81-02-PLAN.md — attribution engine
```

The heading number must equal STATE.md's `Phase:` number. Plan lines are `- [ ] <id>-PLAN.md — text`.

### 4. Upcoming milestones (the "what's next" view)

Use one section per agreed future milestone, in order:

```markdown
## Next milestone: Reliability

**Goal:** Keep searching and saved state correct through failed writes and partial startup.

1. [ ] **State/config consistency.** Write validated settings before removing an instance. Done when: …
2. [ ] **Resource lifecycle.** Close resources opened during failed startup. Done when: …

## Following milestone: Authentication Safety (conditional)

**Activation:** Reliability is complete and a real need is demonstrated.

**Goal:** …

1. [ ] **Session expiry.** …
```

- Heading: `## Next milestone: <name>`, `## Following milestone: <name>`, or `Future` / `Upcoming` / `Later` / `Planned milestone:`. Text between "milestone" and the colon is allowed (`## Next milestone after v2.12: Reliability`). A version may lead the name (`v2.13 Reliability`).
- `**Goal:**` line → shown under the title.
- `(conditional)` in the heading or an `**Activation:**` line → shown dashed with "Starts when: …".
- Scope items: numbered (`1.`) or bulleted (`-`), optional `[ ]`/`[x]`, then a **bold title**, then the detail. Bold lead-ins called Goal, Scope, Done when, Sequence or Activation are not treated as items.
- The first two upcoming milestones also appear on the card as "Next: A → B".

### 5. Backlog

```markdown
## Backlog

### 999.4: Recheck the braces/karma dev-test advisory
### Phase 999.9: Keep: State/config consistency
```

Each `###` heading under `## Backlog` becomes a backlog tile. A leading `Keep:`, `Narrow:`, `Retired:` or `Deferred:` becomes its status.

### Milestone sequence (optional)

A section whose heading contains "milestone sequence", with numbered bold lines (`1. **Reliability — in progress** short text`), renders as a row of milestone tiles.

---

## REQUIREMENTS.md (optional)

```markdown
- [x] **LOGSEC-01**: Reset token never appears in the in-app log viewer.

| Requirement | Phase |
|---|---|
| LOGSEC-01 | Phase 77 |
```

IDs must look like `ABC-01`. The table maps each one to a phase.

---

## Checklist after any planning update

1. STATE.md front matter: `milestone`, `status`, `stopped_at` and **`last_updated`** reflect today.
2. STATE.md `Phase:` starts with the current phase number.
3. ROADMAP.md: exactly one 🔨 milestone, and it is the same version as STATE.md's `milestone` (or none, if STATE says "Awaiting next milestone").
4. Phase ticks match STATE.md: nothing is ticked that STATE still calls in review.
5. Agreed future milestones are written as `## Next milestone:` / `## Following milestone:` sections, or as 📋 lines in the Milestones list.
6. Open the page: no red "Planning files disagree" box.
