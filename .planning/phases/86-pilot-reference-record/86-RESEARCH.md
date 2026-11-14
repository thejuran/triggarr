# Phase 86: Pilot & Reference Record - Research

**Researched:** 2026-10-30
**Domain:** Process/evidence recording for an existing review workflow (BM + Codex + vibe-check + GitHub acceptance), plus two small, low-risk product changes (engine state logic, UI template) used as pilot PRs.
**Confidence:** HIGH — nearly every claim below is sourced directly from this repository's own code, docs, committed evidence, and `gh pr view` output, not from general knowledge.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Pilot set (PILOT-01)
- **D-01:** The pilot set has five PRs. Three already merged after Phase 83 and two are new:
  - **#48** (Phase 85.1, large, security-sensitive)
  - **#36** (Phase 85, large; its Codex pass was INCOMPLETE because of the PR's size and the owner approved the vibe-check fallback, which counts as evidence of how the workflow fails on very large PRs)
  - **#44** (small fix: Phase 85 follow-up)
  - **New: Refresh-counts fix** (state/error-path logic, product code)
  - **New: Card-template structured reason kind** (UI template)
- **D-02:** Refresh-counts behavior (owner decision): when one Sonarr or Lidarr record is malformed, "Refresh counts" **skips that record**, keeps the instance connected and logs the skip, matching what scheduled cycles already do. No new dashboard warning. Add a regression test for each app (Sonarr and Lidarr). This settles the open "Refresh counts vs. scheduled cycles" item in `.planning/backlog/MAINTENANCE.md`.
- **D-03:** The card-template PR is the backlog's "Card-template text-matching refactor": `cycle_grade.html` stops classifying reason rows by matching `outcome.py`'s display text and uses a structured kind field instead. Visible text and grade colors are unchanged. Record it honestly as a UI-template change with no visible difference. The pilot's "UI or security-sensitive" category is also covered by #48 (security-sensitive).
- **D-04:** **Each new fix ships as its own PR**, cut from `main`, so each gets a clean per-PR scorecard. This is a deliberate, recorded exception to one-PR-per-phase, for pilot PRs only. The Phase 86 records, scorecards and adoption guide ship in the Phase 86 PR (branch `phase-86-pilot-reference-record`, which also carries the held planning commits). Each pilot PR goes through the full current process: classification, BM review plus the paired Codex pass, a RISK-01 note, routine vibe-check where required, the checkpoint comment, and exact-commit owner acceptance.
- **D-05:** Categories are covered as follows: small fix (#44), state/error-path logic (Refresh-counts), UI (card template), security-sensitive (#48), larger change (#36, #48). Write down any category that turns out not to fit the evidence as a gap rather than stretching a PR to fill it.

#### Vibe-check comparison (PILOT-02)
- **D-06:** The fresh comparison runs on the **Refresh-counts PR**. Vibe-check and BM + Codex each review the **same first head, before any fixes, independently**: neither sees the other's output. Compare what each caught. Routine vibe-check is still owed on that PR's final head where the current process requires it.
- **D-07:** Refresh-counts counts as "substantial" for PILOT-02 because it changes real state/error-path logic in two apps, with tests. Record its size honestly as moderate.
- **D-08:** #48 is **not** used as the comparison. Its vibe-check ran only on the final head, after five BM/Codex fix rounds, so it cannot show what vibe-check would catch independently. If #48's vibe-check result is cited at all, state that limitation.
- **D-09:** **Proof-based judging.** A finding counts as a *confirmed consequential defect* only if a failing test or a reproduction demonstrates it. Every other finding is labeled *false positive* or *unproven*, with the reason. The owner approves the tally, not the code (the owner does not adjudicate code).

#### What to measure (PILOT-01)
- **D-10:** For each pilot PR and each reviewer (BM, Codex, vibe-check, Greptile when it ran), record: confirmed consequential defects, false positives, later-found misses, revision rounds, review time, observable usage/cost, and owner effort.
- **D-11:** For the existing PRs (#48, #36, #44), fill in only what the committed records prove (findings, dispositions, rounds). Mark missing review time, usage and owner effort as **"not recorded"**. Never estimate or rebuild them from timestamps.
- **D-12:** Owner effort on new PRs is the **number of decisions or approvals Claude brought to the owner** on that PR, logged as they happen. No self-reported minutes.
- **D-13:** Usage/cost is **wall-clock time plus whatever usage or token counts each tool actually prints**. If a tool reports nothing, say so. No dollar estimates.
- **D-14:** A later-found miss counts if a later review round, another reviewer, CI or production finds it **before the Phase 86 PR is accepted**. State this cutoff, and that it is short for the newest PRs.

#### Retirement bar (PILOT-03), set before results
- **D-15:** The bar is fixed now, before any comparison result exists. Recommend **retiring routine vibe-check only if, on the fresh comparison and across the pilot, vibe-check found no proven defect (D-09) that BM + Codex missed.** If it found one, recommend keeping routine vibe-check, or keeping it for the risk level where it made the unique catch. The owner makes the final decision; the bar shapes Claude's recommendation only.
- **D-16:** These two things stay whatever PILOT-03 decides: bot/fork PRs keep the vibe-check fallback (Phase 85.1 owner exception, D-16 of that phase), and BM still recommends an extra vibe-check at high risk (RISK-02, Phase 83).
- **D-17:** The second PILOT-03 decision is left to the end of the phase: does BM/Codex completion stay a manual owner check, or is the acceptance gate extended to require those reports? Claude brings a recommendation with the evidence. Recording the owner's decision completes the requirement. If the owner chooses extension, it is scheduled as FUT-03 and not built in this phase unless the owner pulls it in.

#### Adoption guide (PILOT-04)
- **D-18:** Write it as `docs/review-workflow-adoption.md` in this repository, for the owner's other projects (e.g. SeedSyncarr). It separates GitHub-enforced requirements from instruction-enforced ones and lists what not to copy blindly. No private infrastructure details: the repo is public, so follow the 2026-10-21 published-history rule.

### Claude's Discretion
- Scorecard format and where it lives inside the phase directory (e.g. `86-PILOT-RECORD.md`), and the per-PR table layout.
- The order of the two new PRs, and the exact wording of the adoption guide.
- How #36's and #48's multi-round records are condensed into scorecard rows, as long as each number traces back to a committed record.

### Deferred Ideas (OUT OF SCOPE)
- SA-12 (opt-in FastAPI OpenTelemetry auto-configure can fail startup) and SA-01 (pin CI's uv version): considered as pilot PRs and not chosen. They stay in `.planning/backlog/MAINTENANCE.md` with their decisions still pending.
- Dollar-cost estimates and self-reported owner minutes: not collected (D-12, D-13).
- Tracking later-found misses past Phase 86 acceptance (e.g. through the next release): not in scope (D-14).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PILOT-01 | 3-5 representative PRs run under the paired workflow, drawn from authorized work (small fix, state/error-path logic, UI/security-sensitive, larger change); per-PR, per-reviewer metrics recorded; any unfillable category recorded as a gap. | D-01's pilot set (#48/#36/#44 + 2 new) fully evidenced below: exact checkpoint-comment contents extracted via `gh pr view`/committed evidence for #48/#36/#44; exact code locations, existing tests, and the reuse-vs-build pattern (`_screen_queue`) fully scoped for the Refresh-counts fix; exact template/outcome.py construction sites and the ~20+90 existing tests protecting the card-template refactor. |
| PILOT-02 | At least one substantial pilot PR gets a recorded side-by-side vibe-check vs. paired-workflow comparison on the same head, independently, in addition to routine vibe-check. | Pattern 3 (Architecture Patterns) gives the exact sequencing needed to keep vibe-check and BM+Codex independent on the Refresh-counts PR's first head, and explicitly documents why PR #48 cannot substitute (D-08) and why the routine vibe-check on the final head is a separate, still-required step (D-06). |
| PILOT-03 | Owner's decisions recorded: retire routine vibe-check? keep BM/Codex completion as a manual owner check or extend the acceptance gate (→ FUT-03)? | D-15's bar (quoted verbatim in `<user_constraints>` above) is ready to paste into the pilot record before the comparison runs; D-09's proof-based judging rule is the mechanical test for "found no proven defect BM+Codex missed"; the existing checkpoint-record/PR-comment format is the reuse target for recording both decisions — no new tooling needed. |
| PILOT-04 | Reusable adoption guidance distinguishing instruction-enforced from GitHub-enforced requirements, listing what not to copy blindly. | Live GitHub configuration extracted directly (`gh api .../rulesets/14805779`, `.../environments`, `greptile.json`): required checks (`CI ready`, `CodeQL`, `Review acceptance`), the `review-acceptance` protected environment, Greptile's optional/free-tier config — ready inputs for `docs/review-workflow-adoption.md`'s GitHub-enforced-vs-instruction-enforced split (D-18). Repository confirmed public (`gh api repos/thejuran/triggarr --jq '{visibility, private}'`), so the published-history/no-private-infra rule applies. |
| FUT-03 (deferred, not built this phase) | Automated acceptance-gate enforcement of BM/Codex report presence, scheduled only if the owner chooses it under PILOT-03. | Not researched further — explicitly out of scope unless the owner pulls it in during the PILOT-03 decision (D-17). |
</phase_requirements>

## Summary

Phase 86 is almost entirely a documentation/process phase: it runs the review machinery Phases 82/83/85/85.1 already built, on real PRs, and writes down what happened. Only two small product changes need to be built: (1) make `refresh_sonarr_counts`/`refresh_lidarr_counts` skip one malformed record instead of disconnecting the whole instance, reusing the exact per-item screening helper (`_screen_queue`) that scheduled cycles already use; and (2) replace `cycle_grade.html`'s text-matching reason classification with a structured field, with zero visible change. Both are fully scoped by reading the existing code: the exact call sites, the exact existing tests that currently assert the *old* (soon-to-be-wrong) behavior, and the exact shared helpers to reuse are all identified below.

The rest of the phase is: (a) extracting per-reviewer evidence that already exists in committed checkpoint records and `gh pr view` output for PRs #48, #36, #44 — done below, with exact numbers; (b) running the existing BM+Codex+vibe-check pipeline on the two new PRs with one added twist — an independent, same-first-head comparison between vibe-check and BM+Codex on the Refresh-counts PR, which requires deliberate sequencing to avoid contaminating the comparison the way PR #48's vibe-check (run only after 5 fix rounds) could not be used for one; and (c) writing two reference documents (a pilot record and an adoption guide) using formats and conventions this repository already has (the checkpoint-record template, the classification JSON, the GitHub-enforced/instruction-enforced distinction already made explicit throughout `.planning/REQUIREMENTS.md`).

Every "owner decision" gate in this phase is a real human-in-the-loop checkpoint, not a formality: owner acceptance, merge, the PILOT-02 vibe-check-vs-paired comparison tally, and both PILOT-03 decisions must be the owner's own words, per `docs/owner-cli-acceptance.md`'s authorization boundary and this repository's standing "never merge or approve acceptance autonomously" rule.

**Primary recommendation:** Treat this phase as five sequential autonomous-with-checkpoints workstreams — (1) pilot-record skeleton with the D-15 bar quoted verbatim, written *before* anything else; (2) Refresh-counts PR (code + the PILOT-02 comparison); (3) card-template PR; (4) scorecards for all five PRs; (5) PILOT-03 decision + adoption guide — and reuse existing evidence/templates at every step rather than inventing new formats.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Refresh-counts per-record skip (D-02) | API / Backend (`triggarr/search/engine.py` search logic) | Database/Storage (`triggarr/state.py` in-memory `AppState`, no SQL involved) | Pure in-process state mutation inside the single-process daemon's engine module; no HTTP boundary crossed, no persistence beyond the existing `state.json` write-through already covered by `triggarr/state.py`. |
| Card-template structured kind (D-03) | Frontend Server (SSR) — Jinja2 template rendered server-side by FastAPI (`triggarr/templates/partials/cycle_grade.html`) | API / Backend (`triggarr/search/outcome.py` supplies the render-ready dict) | htmx + server-rendered Jinja2, no client-side JS logic for this classification; the "kind" field is produced backend-side and consumed template-side. |
| Pilot evidence recording, scorecards, comparison, adoption guide (PILOT-01..04) | — (process/documentation, not an application tier) | — | These are records about the review process, not application capabilities; they live in `.planning/` and `docs/`, not in the running app. |

## Standard Stack

No new libraries, frameworks, or runtime dependencies are introduced by this phase. Both code changes reuse existing in-repo helpers (`_screen_queue`, `CycleTally`) and existing template/render infrastructure (Jinja2, already a project dependency). `/bm:plan-phase` should not budget time for dependency research here.

**Installation:** None required.

## Package Legitimacy Audit

Not applicable — this phase installs no external packages. No `slopcheck`/registry verification was run because there is nothing to verify.

## Architecture Patterns

### Pattern 1: Per-item malformed-record screening (`_screen_queue`) — reuse, do not reinvent

**What:** `triggarr/search/engine.py:156` (`_screen_queue`) is the shared helper every scheduled cycle (`run_radarr_cycle`, `run_sonarr_cycle`, `run_lidarr_cycle`) already uses to skip one malformed record per queue stage, log it once, and tally the skip — rather than aborting the whole queue. [VERIFIED: codebase, `triggarr/search/engine.py:156-213`]

**When to use:** Any place that currently wraps a filter/dedup/tag step in a broad `except (AttributeError, KeyError, TypeError)` that treats *one bad record* as a whole-instance failure. This is exactly `refresh_sonarr_counts` (engine.py:1981), `refresh_lidarr_counts` (engine.py:2108), and `refresh_radarr_counts` (engine.py:1859) today.

**The scheduled-cycle pattern to replicate** (from `run_sonarr_cycle`, `engine.py:1365-1399`):
```python
# Source: triggarr/search/engine.py:1365-1399 (run_sonarr_cycle, missing-queue chain)
missing_episodes = _screen_queue(missing_episodes, app_label="Sonarr", queue="missing", tally=tally)
missing_episodes = filter_monitored(missing_episodes)
missing_episodes = _screen_queue(
    missing_episodes, app_label="Sonarr", queue="missing", tally=tally, date_fields=("airDateUtc",)
)
missing_episodes = filter_sonarr_episodes(missing_episodes)
if scope.missing_tag_id is not None:
    missing_episodes = _screen_queue(
        missing_episodes, app_label="Sonarr", queue="missing", tally=tally,
        nested_key="series", tags_at=("series", "tags"),
    )
    missing_episodes = filter_by_tag(missing_episodes, scope.missing_tag_id, _sonarr_tags)
missing_episodes = _screen_queue(
    missing_episodes, app_label="Sonarr", queue="missing", tally=tally,
    key_fields=("seriesId", "seasonNumber"), nested_key="series",
)
missing_seasons = deduplicate_to_seasons(missing_episodes)
```
`_screen_queue` is called once per stage, immediately before the filter step that would otherwise raise on a malformed field — so a record the queue would never dispatch anyway (unmonitored, out-of-tag-scope) is never counted against a field nothing reads.

**The gap in `refresh_*_counts` today:** these functions call `filter_monitored`/`filter_sonarr_episodes`/`filter_by_tag`/`deduplicate_to_seasons` directly on the raw fetch, with no `_screen_queue` calls at all, wrapped in one broad `try/except (AttributeError, KeyError, TypeError)` around the *entire* filter/tag phase (`engine.py:1964-1976` for Radarr, `2091-2103` for Sonarr, `2211+` for Lidarr) that marks the whole instance disconnected on any single bad record. [VERIFIED: codebase, read directly]

**Critical implementation detail — `_screen_queue`'s `tally` parameter is not optional.** Its signature is `tally: CycleTally` (required, not `CycleTally | None`), and it unconditionally calls `tally.record_malformed(...)`. `refresh_*_counts` functions do not carry a `CycleTally` today — they pass `tally=None` into the sibling helper `_resolve_tag_scope`, which *does* accept `CycleTally | None` (engine.py:798, guarded with `if tally is not None`). Two ways to close this gap:
1. **Recommended, minimal diff:** instantiate a throwaway `CycleTally()` locally inside each `refresh_*_counts` function, pass it to `_screen_queue` calls, and discard it when the function returns (never call `.to_record()`, never persist it). This gets correct per-item skip-and-log behavior (via `_screen_queue`'s own call to `_log_malformed_skip`, `engine.py:196`) with **zero signature changes** to the shared helper used by all three scheduled cycles. Matches D-02's "no new dashboard warning" — nothing from this throwaway tally is ever surfaced.
2. Loosen `_screen_queue`'s `tally` type to `CycleTally | None` (mirroring `_resolve_tag_scope`) and guard the `record_malformed` call. This touches a helper shared by all six scheduled-cycle queues and is unnecessary for this fix's scope — flagged as the less-preferred option.

### Pattern 2: Structured "kind" discriminator for card reason rows

**What:** `triggarr/templates/partials/cycle_grade.html:18-28` currently classifies each reason row into three buckets (`malformed`, `unevaluated`, `other`) by matching `r.text` against literal strings that `triggarr/search/outcome.py`'s `cycle_view()` produces (e.g. `r.text.endswith('— malformed data') or r.text.endswith('skipped')`, `r.text.startswith('Missing queue not evaluated: ')`). This is exactly the backlog's "Card-template text-matching refactor" item. [VERIFIED: codebase, both files read directly]

**Minimal structured shape that keeps visible output identical:** `cycle_view()` (outcome.py:219-351) already constructs each reason as a dict literal at five distinct call sites: a fetch-error row (line 260), one row per failure reason (line 275), one row per unevaluated queue (line 291), one row per malformed queue — or the legacy aggregate fallback (lines 306/314), and the eligible-not-dispatched backstop row (line 335). Add a `"kind"` key at each of these five construction sites with one of these literal values, then switch the template's three-way branch from text matching to `r.kind`:

| Construction site (outcome.py line) | Proposed `kind` value | Template bucket (cycle_grade.html) |
|---|---|---|
| fetch-error row (260) | `"fetch_failed"` | `other` |
| failure-reason row (275) | `"failure"` | `other` |
| unevaluated-queue row (291) | `"unevaluated"` | `unevaluated` |
| malformed-by-queue row (306) | `"malformed"` | `malformed` |
| legacy aggregate malformed fallback (314) | `"malformed"` | `malformed` |
| eligible-not-searched backstop (335) | `"eligible_not_searched"` | `other` |

```python
# Proposed, illustrative — not yet in the codebase (Claude's discretion, D-03)
reasons.append({"text": _truncate(text), "count": 1, "kind": "malformed"})
```
```jinja2
{# cycle_grade.html, replacing the text-matching conditions at lines 20-27 #}
{% if r.kind == 'unevaluated' %}
  {% set ns.unevaluated = ns.unevaluated + 1 %}
{% elif r.kind == 'malformed' %}
  {% set ns.malformed = ns.malformed + 1 %}
  {% set ns.malformed_total = ns.malformed_total + r.skip_count %}
{% else %}
  {% set ns.other = ns.other + 1 %}
{% endif %}
```
**Bonus fix available in the same diff (optional, same spirit as D-03, not required by it):** line 24's `ns.malformed_total + (r.text.split(' ')[0] | int(0))` re-derives the skipped-record count by parsing the leading number out of the display text — a second, independent instance of coupling template logic to display-string shape. Since the refactor already touches every malformed-row construction site, consider adding a numeric `"skip_count"` field there too (distinct from the existing `"count"` field, which means something else — the `&times;N` repeat-count multiplier) so the template reads a number directly instead of re-parsing text it just received. This is **not required to satisfy D-03** (which only asks for the classification mechanism, not the count extraction) but removes a second fragile text-coupling in the same four lines at near-zero marginal cost. Flag as a proposal, not a locked requirement.

**Why this is the right shape:** the template only ever needs exactly the three buckets it already branches on (`ns.malformed`, `ns.unevaluated`, `ns.other`) to choose a summary label (lines 30-37); a richer taxonomy than these five source values would over-engineer a problem the template doesn't need solved more granularly. [Claude's discretion, D-03's "Specific Ideas" note]

### Pattern 3: Review-pipeline sequencing for the PILOT-02 same-head comparison (D-06)

This is a process pattern, not a code pattern — but getting its sequencing wrong invalidates the entire PILOT-02 success criterion.

```
Refresh-counts PR, first head (H1) — before any fix
        │
        ├──► BM code review (standard) ──► paired Codex pass (read-only, exact H1)
        │         (Claude runs both automatically per Phase 83 D-06; triage but DO NOT fix yet)
        │
        └──► vibe-check deep-review on H1, independently
                  (stock /vibe-check:deep-review invocation; no Codex findings fed into its
                   prompt/framing; Claude does not open the Codex .last.json before invoking
                   vibe-check, and does not summarize Codex's findings to it)
                        │
                        ▼
        Record both reviewers' findings on H1 into the comparison table, BEFORE triage-fixing
        anything — apply D-09 proof-based judging (confirmed only if a failing test or a
        reproduction demonstrates it; everything else is false_positive/unproven) to every
        finding from BOTH reviewers at this point
                        │
                        ▼
        One batched revision fixing confirmed defects (standard D-08 triage flow) ──► new head (H_final)
                        │
                        ▼
        Routine vibe-check (standing "code" class rule) + fresh BM review + fresh paired Codex
        pass on H_final — this is the PR's ordinary acceptance evidence, separate from the
        PILOT-02 comparison, which already concluded at H1
```

**Why order matters:** D-08 explicitly disqualifies PR #48's vibe-check as comparison evidence because it ran only on the final head, after five BM/Codex fix rounds — by then vibe-check could only confirm or miss defects BM+Codex had *already found and the owner had already seen*, which proves nothing about independent coverage. The Refresh-counts PR's comparison is only valid if vibe-check's assessment of H1 happens with zero exposure to what BM/Codex found at H1. Concretely: do not read the Codex `.last.json` or BM's `REVIEW.md` findings list before invoking `/vibe-check:deep-review`, and do not pass either into vibe-check's prompt. The existing Codex contract (D-07, Phase 83: "Claude adds no risk notes or framing" when invoking Codex) already establishes this discipline one direction; this phase needs the same discipline applied in the other direction, toward vibe-check.

**Routine vibe-check is still owed separately (D-06's second sentence):** the "code" classification's standing rule (routine vibe-check while the owner keeps it) still applies to this PR's *final* head, independent of the PILOT-02 comparison that already happened at H1. Two vibe-check runs on two different heads of the same PR is the correct, intended outcome here — not a redundancy to eliminate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-item malformed-record skip in refresh counts | A new skip/log/count mechanism specific to the refresh path | `_screen_queue` (`engine.py:156`), already used by all 6 scheduled-cycle queues | It already does exactly this (skip, log once per reason/batch, tally), and D-02 explicitly asks for behavior that "matches what scheduled cycles already do." |
| Classifying card reason rows | A rich new `ReasonKind` enum/class hierarchy | A plain string `"kind"` literal matching exactly the 3 Jinja branches that already exist | The template only needs 3 buckets; a richer taxonomy solves nothing the template asks for (Pattern 2 above). |
| Per-PR evidence/metrics tables | A new metrics schema, scorecard tool, or dashboard | The existing checkpoint-record template (`docs/review-checkpoint-record.md`) and its already-populated PR comments for #48/#36/#44 | The template already has every column PILOT-01 needs (reviewer, findings, dispositions, depth, SHAs); this phase's own CONTEXT leaves the exact scorecard layout to Claude's discretion but doesn't need a new format. |
| Owner-effort tracking | A new instrumentation/logging system | A running tally of "decisions brought to the owner" logged inline in the PR checkpoint comment as they happen (D-12) | D-12 is explicit: count decisions/approvals as logged, not minutes or tooling. |
| The vibe-check-vs-paired comparison itself | New comparison tooling, a diffing script, or a scoring rubric beyond what's specified | D-09's proof-based judging rule (confirmed only with a failing test or reproduction) plus a plain table | The decision rule is already fully specified (D-09); building tooling around it would be process overhead the phase's own "Claude's Discretion" section doesn't ask for. |

**Key insight:** every mechanism this phase needs — the per-record skip, the checkpoint-record format, the classification JSON, the proof-based judging rule — already exists in this repository from Phases 79/80/82/83/85. The work is applying these mechanisms honestly to real evidence, not building new ones.

## Common Pitfalls

### Pitfall 1: Radarr has the identical coarse guard, but D-02 names only Sonarr/Lidarr
**What goes wrong:** `refresh_radarr_counts` (`engine.py:1859-1978`) has the byte-for-byte identical pattern — one `try/except (AttributeError, KeyError, TypeError)` around the whole filter/tag phase (lines 1964-1976) that marks the instance disconnected on any single malformed record. There is already a passing test that pins this exact old behavior: `tests/test_refresh_counts.py::test_refresh_radarr_counts_malformed_tag_data_returns_none` (asserts `result is None`, `connected is False`). D-02's locked text says "when one Sonarr or Lidarr record is malformed" and "add a regression test for each app (Sonarr and Lidarr)" — Radarr is not named.
**Why it happens:** the backlog item this decision resolves (`.planning/backlog/MAINTENANCE.md`, "Refresh counts vs. scheduled cycles on a malformed record") itself only ever named Sonarr/Lidarr, likely because nobody had checked whether Radarr shared the bug when that backlog entry was filed. The 86-CONTEXT.md code-context section explicitly flagged this as something to verify during research ("check whether it has the same coarse guard") — it does.
**How to avoid:** this is a locked-decision scope question, not Claude's discretion to silently extend or silently ignore. Surface it explicitly during planning/execution (see Open Questions below) rather than either (a) quietly fixing Radarr too, which would exceed D-02's literal scope, or (b) leaving an inconsistency nobody wrote down.
**Warning signs:** if the final PR only touches `refresh_sonarr_counts`/`refresh_lidarr_counts` and the existing Radarr test is left completely untouched, that's consistent with D-02's literal wording — but then the pilot record (or `.planning/backlog/MAINTENANCE.md`) must explicitly note the resulting Radarr/Sonarr+Lidarr inconsistency as a known, written-down gap, not silence.

### Pitfall 2: An existing test already documents the exact behavior D-02 changes — it must be rewritten, not just supplemented
**What goes wrong:** `tests/test_malformed_records_client_path.py::test_refresh_counts_unchanged_for_non_object_record` has this exact docstring today: *"Out of scope for PR #28 and recorded as a follow-up: Refresh counts keeps its strict fetch, so a null record still marks the instance unreachable there, and it does so without raising."* It asserts `state["lidarr"]["Default"]["connected"] is False` after feeding a `None` record through `refresh_lidarr_counts`. This is the literal follow-up D-02 resolves — it is not a new test to add, it is an existing passing test whose assertion is about to become wrong.
**Why it happens:** the fix touches multiple test files (`tests/test_refresh_counts.py` and `tests/test_malformed_records_client_path.py`), and it's easy to add new regression tests in one file while missing that an existing test in a different file pins the old behavior.
**How to avoid:** before implementing, grep both files for every test whose name or docstring references "malformed," "returns_none," or "non_object_record" for Sonarr/Lidarr (and Radarr, pending Pitfall 1's resolution) and classify each as "must flip to new behavior" vs. "still correct" (e.g., fetch-phase `httpx.HTTPError` tests, which are unrelated to this fix, stay unchanged).
**Warning signs:** `uv run pytest tests/test_refresh_counts.py tests/test_malformed_records_client_path.py -x -q` reports a failure in a test that predates this phase's work.

### Pitfall 3: Adding the `"kind"` field breaks ~20 existing exact-dict-equality test assertions
**What goes wrong:** `tests/test_outcome.py` has roughly 20 assertions of the exact shape `assert {"text": "...", "count": N} in view["reasons"]` or `assert view["reasons"] == [{"text": "...", "count": N}]` — dict equality with no `"kind"` key. Adding `"kind"` to every reason dict in `cycle_view()` will make every one of these fail, because Python dict equality requires identical keys, not a subset match.
**Why it happens:** the planner may scope this as "modify the template + add a kind field" without accounting for the fact that `outcome.py`'s own unit tests (as opposed to the full-route rendering tests in `test_app_cards.py`) assert the *exact* dict shape `cycle_view()` returns.
**How to avoid:** this refactor's test work is mostly **editing existing assertions to add `"kind": "..."` to each expected literal**, not writing new tests. `tests/test_app_cards.py`'s ~90 full-route rendering tests (which assert on rendered HTML text, not the intermediate dict) should need **zero changes** if the refactor is done correctly — they are the regression suite proving "visible output identical" (D-03).
**Warning signs:** `uv run pytest tests/test_outcome.py -x -q` shows failures immediately after adding the field but before updating its assertions (expected, TDD-red step); `uv run pytest tests/test_app_cards.py -x -q` showing ANY failure after the refactor is the real signal something is visibly different.

### Pitfall 4: Treating PR #48's vibe-check as PILOT-02 comparison evidence
**What goes wrong:** PR #48 (the richest, most recent existing evidence) has a well-documented vibe-check run (`/vibe-check:deep-review`, 13 raised/2 reported/11 filtered, 0 critical/0 warning) that looks like good comparison material at a glance.
**Why it happens:** it's the most complete, most recently-written evidence available, and tempting to reuse.
**How to avoid:** D-08 is explicit and locked: "#48 is not used as the comparison. Its vibe-check ran only on the final head, after five BM/Codex fix rounds, so it cannot show what vibe-check would catch independently. If #48's vibe-check result is cited at all, state that limitation." Cite it only as general pilot-set color (e.g., in the PILOT-01 scorecard row for #48), never as PILOT-02 comparison data.

### Pitfall 5: Forgetting the model-change caveat when comparing across heads/phases
**What goes wrong:** BM's `sonnet`/`haiku` tiers moved to Claude Sonnet 5.5/Haiku 5.5 as part of the same v5.0.3 update that turned on `workflow.code_review` (Phase 83 D-02). Any comparison that spans before/after that update (e.g., citing Phase 81 or earlier reviews alongside Phase 83+ reviews) is comparing different models and different settings simultaneously.
**Why it happens:** easy to read two review reports side by side and attribute a difference in finding quality purely to "the paired workflow vs. vibe-check" when the underlying model also changed.
**How to avoid:** 86-CONTEXT's own "Specific Ideas" section requires this note "wherever older and newer review results are compared." All five pilot PRs (#48, #36, #44, and the two new ones) post-date the Phase 83 D-02 model change, so this mainly matters if the pilot record or adoption guide cites *any* pre-Phase-83 review evidence for contrast — flag it there if so.

## Code Examples

### The exact three existing refresh-count functions needing the fix
```python
# Source: triggarr/search/engine.py — current coarse guard (identical pattern x3)
# refresh_radarr_counts: engine.py:1859-1978 (except block at 1964-1976)
# refresh_sonarr_counts: engine.py:1981-2105 (except block at 2091-2103)
# refresh_lidarr_counts: engine.py:2108-2221+ (except block at 2211+)
try:
    scope = await _resolve_tag_scope(...)
    # ... filter/tag/dedup chain, called directly on raw data, no _screen_queue ...
except (AttributeError, KeyError, TypeError) as exc:
    logger.warning("{App}: Count refresh data fault ({etype}) -- treating as disconnected", ...)
    _mark_unreachable(ist)          # <-- whole instance marked disconnected
    _clear_faulted_scoped_counts(ist, scope, instance_config, ...)
    return None
```

### `_screen_queue`'s actual signature (what the fix must satisfy)
```python
# Source: triggarr/search/engine.py:156-166
def _screen_queue(
    items: list,
    *,
    app_label: str,
    queue: str,
    tally: CycleTally,          # <-- required, not Optional
    key_fields: tuple[str, ...] = (),
    nested_key: str | None = None,
    tags_at: tuple[str, ...] | None = None,
    date_fields: tuple[str, ...] = (),
) -> list[dict]:
```

### The existing test whose docstring is the literal follow-up item (must be rewritten)
```python
# Source: tests/test_malformed_records_client_path.py:273-286
async def test_refresh_counts_unchanged_for_non_object_record(tmp_path):
    """Out of scope for PR #28 and recorded as a follow-up: Refresh counts keeps
    its strict fetch, so a null record still marks the instance unreachable
    there, and it does so without raising."""
    fake = _FakeArr({"missing": [_GOOD["lidarr"], None]})
    ...
    await refresh_lidarr_counts(client, state, "Default", config, make_settings())
    ...
    assert state["lidarr"]["Default"]["connected"] is False   # <-- this must become True
```

### The five reason-construction sites in `outcome.py` that need a `"kind"` key
```python
# Source: triggarr/search/outcome.py:260, 275, 291, 306/314, 335
reasons.append({"text": _truncate(f"Couldn't reach {app_label} ({fetch_error})"), "count": 1})     # kind="fetch_failed"
reasons.append({"text": _truncate(text), "count": count})                                           # kind="failure"
reasons.append({"text": _truncate(f"{label} queue not evaluated: {reason}"), "count": 1})            # kind="unevaluated"
reasons.append({"text": _truncate(text), "count": 1})   # malformed-by-queue / legacy fallback         # kind="malformed"
reasons.append({"text": _truncate(text), "count": 1})   # eligible-not-searched backstop              # kind="eligible_not_searched"
```

### The checkpoint-record evidence already on GitHub for PR #44 (model for new PRs' scorecards)
```
# gh pr view 44 --comments (checkpoint comment, verified 2026-10-30)
BM review:    standard depth, complete — 0 critical, 0 warning, 1 new info (IN-05)
Codex:        complete, attempt 1, 0 findings, verdict "no-findings"
Greptile:     not run on this head (optional)
CI:           all required jobs success (run 40761276419); Review acceptance passed (attempt 2)
Review time / usage / owner effort: not recorded anywhere in the committed evidence
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `refresh_*_counts` aborts the whole instance (disconnected, counts cleared) on one malformed record | Scheduled cycles (`run_*_cycle`) skip just that record via `_screen_queue`, keep going | Phase 80 (scheduled cycles only) → Phase 86 extends it to refresh counts (D-02) | "Refresh counts" and scheduled cycles will finally agree on malformed-record handling; closes a Phase 80-era gap explicitly deferred at the time ("Refresh counts vs. scheduled cycles," `.planning/backlog/MAINTENANCE.md`). |
| Card reason-row classification by matching `outcome.py`'s rendered display text | Structured `"kind"` field read directly | Phase 86 (D-03) | Decouples the template's grouping logic from exact wording of display strings — a future wording change to `outcome.py`'s text no longer risks silently breaking the card's summary-label logic. |
| Vibe-check and BM+Codex evaluated independently only by happenstance (never deliberately on the same frozen first head) | PILOT-02 deliberately runs both on the same first head, before fixes, with explicit non-contamination discipline | Phase 86 (D-06) | First methodologically sound reviewer-coverage comparison in this project; PR #48's methodology (final-head-only vibe-check) is explicitly disqualified as a precedent (D-08). |

**Deprecated/outdated:** none — no library or tool version is changing in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The proposed `"kind"` literal values (`fetch_failed`/`failure`/`unevaluated`/`malformed`/`eligible_not_searched`) and the optional `"skip_count"` field are a reasonable concrete shape, not the only valid one | Architecture Patterns, Pattern 2 | Low — 86-CONTEXT.md explicitly leaves this to Claude's discretion; any shape that lets the template branch correctly and keeps visible text identical satisfies D-03. |
| A2 | Instantiating a throwaway, never-persisted `CycleTally()` inside each `refresh_*_counts` function is the lowest-risk way to reuse `_screen_queue` without changing its shared signature | Architecture Patterns, Pattern 1 | Low-medium — if a future reviewer prefers loosening `_screen_queue`'s `tally` parameter to `Optional` instead, that's a slightly larger diff touching a helper shared by all 6 scheduled-cycle queues; functionally equivalent either way. |

**If this table is empty:** N/A — two low-risk discretionary proposals are listed above; nothing safety-, compliance-, or decision-critical was assumed without verification.

## Open Questions

> **RESOLVED 2026-10-30 (Q1):** the owner chose to include Radarr (CONTEXT D-02a). Plan the fix and regression tests for all three apps and rewrite `test_refresh_radarr_counts_malformed_tag_data_returns_none`. Q3 is answered by CONTEXT D-04 (cut each pilot PR branch from `main`). Q2 follows the recommendation below.

1. **Does the Refresh-counts fix extend to `refresh_radarr_counts`, given it has the byte-identical coarse guard and D-02's locked text names only Sonarr/Lidarr?**
   - What we know: Radarr's `refresh_radarr_counts` has the identical whole-instance-disconnect pattern (verified by reading `engine.py:1964-1976`), and an existing test (`test_refresh_radarr_counts_malformed_tag_data_returns_none`) currently pins that old behavior.
   - What's unclear: whether the owner, when making D-02, was aware Radarr shares the bug (the backlog item it resolves never mentioned Radarr either), or deliberately scoped the fix to match the backlog wording.
   - Recommendation: the planner should either (a) confirm scope with the owner before/during execution (since this is a locked-decision boundary, not Claude's discretion), or (b) implement exactly Sonarr+Lidarr per D-02's literal text and explicitly record the resulting Radarr inconsistency as a known, written-down gap in the pilot record and/or `.planning/backlog/MAINTENANCE.md` — never silently extend or silently ignore it.

2. **Exact owner-effort counting granularity for D-12.**
   - What we know: D-12 says owner effort is "the number of decisions or approvals Claude brought to the owner on that PR, logged as they happen."
   - What's unclear: whether a single multi-part checkpoint message (e.g., the acceptance checklist, which bundles several status lines into one ask) counts as one decision or several.
   - Recommendation: count each distinct yes/no or choice the owner had to make (e.g., "approve this exact commit" = 1; "fix all defects vs. accept as-is" = 1; a RISK-02 vibe-check recommendation response = 1), and state the counting rule once in the pilot record so all five PRs' owner-effort numbers are comparable.

3. **Where exactly do the two new pilot PR branches get cut from, relative to the current `phase-86-pilot-reference-record` branch?**
   - What we know: D-04 requires each new fix to ship as its own PR "cut from main" — an explicit, recorded exception to the project's normal one-PR-per-phase rule. The Phase 86 PR itself (carrying records/scorecards/adoption guide) is the already-existing `phase-86-pilot-reference-record` branch.
   - What's unclear: nothing structurally — this is confirmed by D-04's own text — but the plan should make explicit that these are three separate branches/PRs, not sub-branches of the phase branch, so execution doesn't accidentally nest them.
   - Recommendation: `git checkout main && git pull && git checkout -b <refresh-counts-branch-name>` (and likewise for the card-template fix), each opened and merged independently before the Phase 86 PR's own scorecards reference their final head SHAs.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `codex` CLI | Paired Codex pass on both new PRs (Phase 83 D-06/D-07) | ✓ | 0.153.4 | Owner-approved fallback (vibe-check) per `docs/codex-adversarial-review-contract.md` if Codex stays INCOMPLETE after one retry |
| `docker` | Nothing new in this phase (the untrusted-head review container from Phase 85.1 is not needed — both new PRs are trusted, owner-authored) | ✓ | 29.4.3 | N/A |
| `gh` CLI | Opening/pushing the two new PRs, posting checkpoint comments, owner acceptance transport | ✓ | 2.86.0 | None needed |
| `uv` / `pytest` | TDD for both code changes | ✓ | uv 0.12.17 | None needed |
| `node` | `.cjs` script tests unaffected by this phase's changes (no `.github/scripts/**` files touched by either new PR) | ✓ | v25.9.0 | Not expected to be needed unless scope grows |
| `vibe-check:deep-review` skill | Routine vibe-check + the PILOT-02 comparison | ✓ (listed in available skills) | — | None needed |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — everything required is present.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio (`asyncio_mode = "auto"`), pytest-cov 7.1.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_refresh_counts.py tests/test_malformed_records_client_path.py -x -q` (Refresh-counts fix) / `uv run pytest tests/test_outcome.py tests/test_app_cards.py -x -q` (card-template fix) |
| Full suite command | `uv run pytest tests/ -x -q` (≈3270+ tests as of the most recent recorded full run, Phase 85.1 PR #48) |

### Phase Requirements → Test Map
| Req / item | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| D-02 (Refresh-counts, Sonarr) | malformed record skipped, instance stays connected, correct eligible/searchable counts for the surviving records | unit | `uv run pytest tests/test_refresh_counts.py::test_refresh_sonarr_counts_malformed_cutoff_data_returns_none tests/test_refresh_counts.py::test_refresh_sonarr_counts_malformed_missing_data_returns_none -x -q` | ✅ exists, but **assertions must be rewritten** (currently pin the old `connected is False` behavior) |
| D-02 (Refresh-counts, Lidarr) | same, Lidarr; plus the client-path non-object-record case | unit | `uv run pytest tests/test_malformed_records_client_path.py::test_refresh_counts_unchanged_for_non_object_record -x -q` | ✅ exists, **must be rewritten** (docstring literally says this is the follow-up) — no existing malformed-filter-phase test for Lidarr beyond this one; add one mirroring the Sonarr pair |
| D-02a (Refresh-counts, Radarr) | same as Sonarr/Lidarr (resolved: owner included Radarr, CONTEXT D-02a) | unit | `uv run pytest tests/test_refresh_counts.py::test_refresh_radarr_counts_malformed_tag_data_returns_none -x -q` | ✅ exists; **must be rewritten** — owner decided 2026-10-30 (CONTEXT D-02a) that Radarr is included |
| D-03 (card-template kind field) | `cycle_view()`'s reason dicts carry `"kind"`; template branches on it; visible HTML text/colors unchanged | unit + integration | `uv run pytest tests/test_outcome.py -x -q` (unit, dict-shape — **~20 assertions need an added `"kind"` key**) + `uv run pytest tests/test_app_cards.py -x -q` (integration, rendered HTML — **must show zero changes**) | ✅ both exist |
| PILOT-01/02/03/04 | process/documentation requirements | structural/manual | grep for required sections (e.g., the D-15 bar text verbatim in the pilot record; `docs/review-workflow-adoption.md` existing with GitHub-enforced/instruction-enforced sections) — not pytest-covered | N/A — these are documents, not code |

### Sampling Rate
- **Per task commit:** the relevant quick-run command above for whichever file was touched.
- **Per PR/wave merge:** `uv run pytest tests/ -x -q` (full suite) + `uv run ruff check triggarr/ tests/`.
- **Phase gate:** full suite green on each new PR's final head before that PR's owner acceptance; full suite green on the Phase 86 PR itself before `/bm:verify-work`.

### Wave 0 Gaps
None — both `tests/test_refresh_counts.py` and `tests/test_outcome.py`/`tests/test_app_cards.py` already exist with directly relevant (if currently wrong-asserting) tests, and the test framework is already fully configured. The unusual TDD shape here is **editing existing tests that assert the old behavior** before writing the fix, rather than creating new test files from nothing — call this out explicitly in the plan so it isn't mistaken for skipping the red step.

## Security Domain

`security_enforcement` is absent from `.planning/config.json` — treated as enabled per the standing rule, though this phase's actual new-code surface is small and low-risk.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | Unchanged — neither new PR touches auth code. |
| V3 Session Management | No | Unchanged. |
| V4 Access Control | No | Unchanged. |
| V5 Input Validation | Yes | Both changes are about handling malformed *upstream* (Radarr/Sonarr/Lidarr) API data safely. The established, correct pattern is already in place: `_malformed_reason`/`_screen_queue` validate structurally (dict-ness, JSON-int-ness, nested-dict-ness, list-ness) before any field is read, never coerce, and log only sanitized counts/IDs (never raw exception text in a user-facing surface) — reuse it as-is. |
| V6 Cryptography | No | Unchanged — no secrets, tokens, or crypto touched by either new PR. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| A malformed upstream API record (null, wrong type, non-dict nested object) crashing or wedging a feature | Denial of Service (availability) | Already mitigated by `_screen_queue`'s per-item structural screening; the Refresh-counts fix *extends* this existing mitigation to a path that currently lacks it — it does not introduce a new threat surface. |
| Template logic silently drifting from the data it renders (the exact bug class D-03 fixes) | Tampering (of displayed information, not of data) | Structured discriminator fields instead of string pattern-matching on display text — the general fix this phase applies narrowly to one template. |

This phase's review-process work (checkpoint records, adoption guide) involves no application code and no new attack surface; `CLAUDE.md`'s absolute security rules (no secrets in logs, SecretStr discipline, parameterized queries, no `innerHTML`/`| safe`) are unaffected because neither new PR touches secret handling, HTML templates with unescaped user content, or SQL.

## Sources

### Primary (HIGH confidence — direct repository read)
- `triggarr/search/engine.py` — `_screen_queue`, `_malformed_reason`, `refresh_radarr_counts`/`refresh_sonarr_counts`/`refresh_lidarr_counts`, `run_sonarr_cycle`'s screening chain, `_resolve_tag_scope`, `_TagScope` (read in full relevant ranges)
- `triggarr/search/outcome.py` — `CycleTally`, `cycle_view`, `grade_cycle` (read in full)
- `triggarr/state.py` — `LastCycleRecord`, `AppState` (malformed counters)
- `triggarr/templates/partials/cycle_grade.html` (read in full)
- `tests/test_refresh_counts.py`, `tests/test_malformed_records_client_path.py`, `tests/test_outcome.py`, `tests/test_app_cards.py` — existing coverage for both fixes (read relevant sections and ran `grep`/`wc -l` counts)
- `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md` — full per-head evidence for PR #48, including the durable checkpoint comment and the post-merge live-run outcome
- `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW-EVIDENCE.md` — Phase 85 pre-push verification record for PR #36
- `gh pr view 44/36/48 --comments` and `--json ...` — live GitHub evidence for all three existing pilot PRs (checkpoint comments, CI results, merge timestamps)
- `gh api repos/thejuran/triggarr/rulesets/14805779`, `.../environments`, `greptile.json` — live GitHub-enforced configuration (required checks, `review-acceptance` environment, Greptile config)
- `docs/bm-greptile-codex-blueprint.md`, `docs/buildomator-greptile-pilot.md`, `docs/review-checkpoint-record.md`, `docs/review-classification-policy.md`, `docs/codex-adversarial-review-contract.md`, `docs/owner-cli-acceptance.md` — the review process this phase runs, unchanged
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` § Phase 86, `.planning/STATE.md`, `.planning/backlog/MAINTENANCE.md`, `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-CONTEXT.md` — locked decisions and standing rules
- `.planning/phases/86-pilot-reference-record/86-CONTEXT.md` — this phase's locked decisions (D-01..D-18)
- Local tool checks: `codex --version` (0.153.4), `docker --version` (29.4.3), `gh --version` (2.86.0), `uv --version` (0.12.17), `node --version` (v25.9.0)

### Secondary / Tertiary
None used — every claim in this document traces to a primary source above.

## Metadata

**Confidence breakdown:**
- Code-level findings (Refresh-counts fix, card-template refactor): HIGH — verified by directly reading the exact files and line ranges, cross-checked against existing tests.
- Existing-PR evidence (#48, #36, #44): HIGH — sourced from committed checkpoint records and live `gh pr view` output, not reconstructed or estimated.
- Process/sequencing guidance (PILOT-02 comparison discipline, review pipeline steps): HIGH — derived directly from the locked decisions in 86-CONTEXT.md and the governing docs (`docs/review-checkpoint-record.md`, `docs/codex-adversarial-review-contract.md`), not from external best practice.
- Proposed `"kind"` field shape: MEDIUM — a sound, minimal proposal consistent with the template's actual needs, but explicitly left to Claude's discretion by 86-CONTEXT.md, so it is a recommendation rather than a verified-only-one-right-answer fact (see Assumptions Log A1).

**Research date:** 2026-10-30
**Valid until:** This research is tied to the current state of `main` (head `05b24fe` at research time) and the current BM/Codex/vibe-check tooling versions recorded above. Re-verify the engine.py line numbers and test assertions if `main` moves significantly before planning/execution begins (e.g., if another PR touches `engine.py`, `outcome.py`, or `cycle_grade.html` first).
