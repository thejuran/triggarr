---
phase: 84-codex-plan-checker-investigation
plan: "04"
subsystem: investigation
tags: [adoption-criteria, blind-comparison, evaluator-only, contamination-check, parity-check, d-12, d-13, d-14, d-15, d-17, d-18]
status: paused

# Dependency graph
requires:
  - phase: 84-codex-plan-checker-investigation (Plan 01)
    provides: "Route decision (hook), routed model (claude-gpt-6-astra[1m])"
  - phase: 84-codex-plan-checker-investigation (Plan 02)
    provides: "Matched-run harness, --permission-mode dontAsk + run-settings.json, Effort accepted: max"
  - phase: 84-codex-plan-checker-investigation (Plan 03)
    provides: "ORIGINAL-labelled, frozen, hashed Phase 81 input set at inputs/phase81-best/"
provides:
  - "Locked adoption criteria (84-ADOPTION-CRITERIA.md): D-12..D-18 verbatim, fixed scoring rules, matched-run settings, input label, resolved checker alias (sonnet), route (hook), effort (max), sha256-hashed and copied read-only into evaluator-only/ -- pending owner acknowledgment (Task 3 paused)"
  - "Evaluator-only answer keys (K1-K7 initial, R1-R4 revision) and a 26-line contamination-phrase list, isolated in a mode-700 directory"
  - "check_packet.py (stdlib, self-tested) -- contamination/forbidden-name check for the blind packet, with a Rule-1 fix for its own REVIEWER-BRIEF.md false-positive"
  - "A frozen, hash-manifested, contamination-clean blind packet (packets/blind-r1/, 133 files) with its driver prompt (packets/blind-r1-driver.txt) and a redacted copy of the two pre-cutoff sandbox runbook references"
  - "check_fallback_parity.py (stdlib, self-tested) -- confirms 'PARITY OK (route=hook)' for the live blind-r1 driver (no codex driver needed under route=hook)"
affects: [84-05, 84-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Longest-match-first literal-string redaction (host/IP/user categories only, never the original value) over sanitized external runbook references, with a residual-token grep as a post-redaction self-check"
    - "Content-hash (not path) matching against a frozen-inputs manifest to distinguish a verified original input (phrase hit = INFO) from a newly-authored packet file (phrase hit = failure) in the same contamination scan"

key-files:
  created:
    - .planning/phases/84-codex-plan-checker-investigation/84-ADOPTION-CRITERIA.md (local only, git-excluded, never committed per D-16; Owner acknowledgment section still PENDING)
    - /Users/julianamacbook/scratch/planchk-pilot/evaluator-only/ (mode 700; answer-key-initial.md, answer-key-revision.md, contamination-phrases.txt, adoption-criteria.locked.md)
    - /Users/julianamacbook/scratch/planchk-pilot/harness/check_packet.py
    - /Users/julianamacbook/scratch/planchk-pilot/harness/check_fallback_parity.py
    - /Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1/ (frozen, 133 files)
    - /Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1-driver.txt
    - /Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1.sha256
    - /Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1-drivers.sha256
    - /Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1.check.txt
    - /Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1.progress
  modified: []

key-decisions:
  - "Input label carried forward verbatim: ORIGINAL (from 84-HASH-MANIFEST.md)"
  - "Checker invocation alias resolved live: sonnet (bm-sdk query resolve-model bm-plan-checker, model_profile balanced) -- matches 84-RESEARCH.md's expectation"
  - "Route: hook (carried from 84-RUNTIME-VERDICT.md); no fallback-agent driver or --agents-file needed; blind-r1-driver.txt is used byte-for-byte by both arms"
  - "Effort: max (carried from 84-PILOT-EVIDENCE.md's 'Effort accepted: max', string-equality-checked against the criteria record)"
  - ".planning/REQUIREMENTS.md and /Users/julianamacbook/Cowork/mediaserver/v5test-results.md (+ v5test-results/) recorded UNAVAILABLE in the packet README rather than substituted with a wrong-era copy -- the latter also postdates the cutoff and falls inside the actual manual-review window"

requirements-completed: []

# Metrics
duration: "~25min (building Tasks 1-2 this session; exact session start not separately timestamped)"
completed: 2026-10-25
---

# Phase 84 Plan 04: Locked Adoption Criteria & Blind Packet (Paused at Owner Acknowledgment) Summary

**Built and verified the locked D-12..D-18 adoption-criteria record, the withheld K1-K7/R1-R4 evaluator-only answer keys, and a frozen, hash-manifested, contamination-clean 133-file blind comparison packet with its driver prompt -- paused before any comparison run, per binding rule 5, for the owner's explicit acknowledgment of the criteria.**

## Performance

- **Duration:** ~25 min (Tasks 1-2 this session)
- **Completed (this session):** 2026-10-25T18:58:15Z
- **Tasks:** 2 of 3 complete and verified (Task 1 auto, Task 2 auto); Task 3 (checkpoint:human-verify, gate=blocking) reached and paused -- awaiting the owner's reply, no comparison run started
- **Files modified (Triggarr tracked files):** 0 besides this SUMMARY.md -- every other deliverable is either the git-excluded `84-ADOPTION-CRITERIA.md` or lives entirely outside the repo under `~/scratch/planchk-pilot/` (D-16/D-06)

## Accomplishments

### Task 1 — Evaluator-only answer keys and the locked criteria record
- Created `/Users/julianamacbook/scratch/planchk-pilot/evaluator-only/` at mode 700 and wrote `answer-key-initial.md` (K1-K7, the blueprint's 7 evaluator-only reproduction checks verbatim-in-substance plus the credit rule), `answer-key-revision.md` (R1-R4, the 4 later revision-round findings), and `contamination-phrases.txt` (26 lowercase, finding-specific phrases; confirmed no "name reuse"/"stable identity" line, since those distinctions must remain discussable in the packet).
- Wrote `84-ADOPTION-CRITERIA.md`: D-12, D-13, D-14 (all seven bullets), D-15, D-17, D-18 copied verbatim from `84-CONTEXT.md`; the fixed scoring rules (hit/real-finding/false-positive definitions, the D-12 mean-and-floor bar, the D-13 FP-cap formula, per-D-14-item evidence sources, answer-key-validity handling, D-15's "any unmet item -> not met", D-17's run order and one-retry rule, D-18's harness ceiling and doctor-state check); the matched-run settings (parent alias opus, checker alias **sonnet** resolved live via `bm-sdk query resolve-model bm-plan-checker`, Route: hook, Effort: max copied from and string-equal to `84-PILOT-EVIDENCE.md`'s "Effort accepted: max", shared settings file, fresh session/packet per run, blind adjudicator); the Input label (ORIGINAL, carried from `84-HASH-MANIFEST.md`); and known limitations (BM-4.9.1-vs-5.0.3 checker version, the `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` prerequisite, E4/E5's 900s-ceiling shortfall, the agentId-absent correlation method) carried forward rather than re-discovered.
- Computed and recorded `Record sha256: 3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69` over the record's content, then copied the file byte-identically into `evaluator-only/adoption-criteria.locked.md` and `chmod a-w` it.
- Ran the task's exact automated `<verify>` command: **exit 0.**

### Task 2 — Blind packet assembly, contamination check, driver prompt, route parity
- Wrote `harness/check_packet.py` (stdlib only): content-hash-against-manifest classification (frozen original -> phrase hit is INFO; anything else -> phrase hit or forbidden-name match fails), a 4-case `--self-test` (forbidden phrase present/absent, forbidden-name file, and — after the Rule 1 fix below — a clean `REVIEWER-BRIEF.md`), all passing.
- Assembled `packets/blind-r1/` as a project-shaped tree: `triggarr/`+`tests/`+`CLAUDE.md`+`docs/PLANNING-FORMAT.md`+the approved design spec (`docs/superpowers/specs/2026-10-08-search-correctness-design.md`, no amendments found referenced anywhere) from the frozen source snapshot `98e01b6bf884`; the pre-cutoff `.planning/ROADMAP.md`; `.planning/phases/81-correct-sonarr-grab-attribution/` containing exactly the 9 ORIGINAL-labelled plans plus `81-CONTEXT/RESEARCH/PATTERNS/VALIDATION/DISCUSSION-LOG.md` (14 files); redacted copies of the two pre-cutoff sandbox runbook references (`SANDBOX-sonarr-v5.md`, `RUNBOOK-sonarr-v5-test.md` — both mtimes predate the cutoff); `REVIEWER-BRIEF.md` (the blueprint's reproduction-instructions paragraph minus its hidden-defects sentence, plus the design-distinctions sentence rephrased as "Reviewers must consider these distinctions"); and a `README.md` recording the redaction log (HOST=92, IP=1, USER=14, SECRET=0, counts only) and the two inputs recorded UNAVAILABLE rather than substituted (`.planning/REQUIREMENTS.md`; the mediaserver's `v5test-results.md`/`v5test-results/`, which postdates the cutoff and falls inside the actual 2026-10-20 20:19:46-21:57:02 manual-review window).
- Wrote `packets/blind-r1-driver.txt`: a single `Agent(subagent_type="bm:bm-plan-checker", model="sonnet", description="Verify Phase 81 plans", prompt=<BM step-10 checker template filled for Phase 81>)` call, with the mechanically-comparable `subagent_type:`/`model:`/`description:`/`prompt:` line format the plan requires; confirmed exactly one `subagent_type:` line and one `model:` line, and zero contamination-phrase hits.
- Froze the packet (`chmod -R a-w`), wrote `packets/blind-r1.sha256` (133 file rows + the driver's own row) and `packets/blind-r1-drivers.sha256`; `shasum -a 256 -c` on both verifies clean (133/133 OK).
- Wrote `harness/check_fallback_parity.py` (stdlib only): route-aware parity check (hook: driver-identity only; fallback-agent: body/frontmatter/driver-line-shape parity, all four self-test cases — planted body diff, model-line retained, one-word prompt diff, correct set — passing). Live run against the actual `84-RUNTIME-VERDICT.md`/drivers prints `PARITY OK (route=hook)`; appended to `packets/blind-r1.check.txt` after `PACKET CLEAN`.
- Ran the task's exact automated `<verify>` command: **exit 0.**

### Task 3 — paused at the owner-acknowledgment checkpoint
Not yet executed. Per binding rule 5, this is a real stop: the criteria, scoring rules, matched-run settings, route disclosure, and known limitations above must be presented to the owner in plain language and explicitly acknowledged (or revised and re-hashed) before any comparison run. No comparison run has been started. See the CHECKPOINT REACHED section returned alongside this summary.

**Revision 1 (2026-10-26):** The owner reviewed the record and declined to acknowledge the
2026-10-25 version, requesting five changes before freezing: (1) a separate, one-attempt,
30-minute full-loop validation exercise outside the scored-run budget, without loosening the
end-to-end requirement; (2) a per-arm effective-settings disclosure instead of trusting the shared
"Effort: max" flag name alone; (3) an explicit statement that usage is observational, with only
wall-clock ceilings and run counts actually enforced; (4) a classification of session/timing
correlation as indirect routing evidence, with a defined standard for unambiguous attribution; (5)
final, pinned scoring rules for duplicate findings, additional-finding buckets, the false-positive
denominator, and incomplete-run scoring. All five were applied to `84-ADOPTION-CRITERIA.md` this
session (five new sections added: "Full-loop validation (separate from comparison budget)",
"Effective settings per arm", "Routing attribution standard", "Usage", "Scoring rules (final)",
plus a "Revision log" section); no existing D-12..D-18 text, the original "Scoring rules (fixed
before any run)" section, or the "Matched-run settings" section was deleted. The record was
re-hashed (new `Record sha256: f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`,
superseding `3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69`), the locked copy at
`evaluator-only/adoption-criteria.locked.md` was refreshed (`chmod u+w`, byte-identical copy,
`chmod a-w`; `cmp` confirms byte-identity), and Task 1's and Task 2's exact automated `<verify>`
commands were both re-run and both still exit 0 (Effort-equality check still passes: `max == max`;
contamination/packet/parity checks still pass). The investigation into item 2 (reading
`lib/request-worker.js` in the installed model-gateway 0.51.2, read-only) and item 4 (reading
`dispatchRequestIdentity()` in the same file) surfaced two concrete, citable findings now recorded
in the criteria: the harness's shared `--effort max` flag is logged as `effort: "max"` on every
codex-arm request but as `effort: null` on the one recorded ordinary-arm run, because
model-gateway's own anthropic-passthrough log call (line 2345) never passes an `effort` argument at
all; and the `x-claude-code-agent-id` header the runtime already sends is read by
`dispatchRequestIdentity()` but that function is only invoked on the `auto`-dispatch branch, never
on the direct hook-routed or anthropic-passthrough paths this comparison uses — which is why
`agentId` has been uniformly absent from every route-log line this phase has produced. Still no
comparison run, validation run, or gateway request was started; the owner has not yet acknowledged
this revised record. See the CHECKPOINT REACHED section returned alongside this summary.

**Revision 2 (2026-10-26):** The owner reviewed the revision-1 record and again declined to
acknowledge it, requesting a second set of clarifications before freezing: (1) state whether a
successful 30-minute full-loop validation can satisfy the D-14 end-to-end must-have despite
E4/E5's recorded timeouts, with E4/E5 preserved exactly as failed/incomplete attempts (never
relabelled, never superseded) and the validation never counted toward D-17's scored runs; (2)
apply the identical routing-proof standard to that validation, defining Option 2's observation
window and the evidence establishing exclusive use of the routed Codex model concretely enough
that absence of competing requests in an incomplete log is explicitly insufficient; (3) distinguish
requested effort, logged effort, and verified effective effort (unknown values stay unknown) and
frame the whole benchmark as a comparison of two configured systems, not an equal-effort model
comparison. All three were applied to `84-ADOPTION-CRITERIA.md` this session: a framing statement
was added near the top of the record and restated in "Effective settings per arm"; the "Full-loop
validation" section gained an addendum stating that a validation meeting every required step
satisfies D-14's end-to-end item notwithstanding E4/E5, a required fifth "complete" step for the
post-bounce recheck (step 12.5, no longer interchangeable with step 4's step-12 recheck from this
revision onward — resolved by direct re-reading of
`~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/plan-phase.md`'s step 12.5, which runs
unconditionally after the revision loop whenever bounce is activated, not as an alternative path to
step 12), and resume recorded as N/A per `84-PILOT-EVIDENCE.md` E6; a new three-way
requested/logged/verified-effective-effort table was appended to "Effective settings per arm"
(both arms read "Unknown" in the verified-effective column, for different, disclosed reasons); and
a new "Option 2 for the validation and every scored codex run" subsection was appended to "Routing
attribution standard," defining the observation window from the harness's own `started_at`/
`finished_at`/`duration_s` fields plus a stated margin, and the required completeness/exclusivity
evidence (byte-offset/line-count capture before launch and after exit, per-line session-id
attribution over the full window rather than a pre-filtered one, a process census, and the
orchestrating/other-session caveat). This revision's read-only investigation into the installed
model-gateway 0.51.2 source (`lib/request-worker.js`, `lib/commands.js`) found a real, citable
per-backend request counter (`served: counters`, incremented at lines 2112/2251/2320/2344, exposed
only via the shim's own `GET /healthz` endpoint) that `model-gateway doctor`'s own printed CLI text
never surfaces (`doctor()` only logs `health?.models`, a model-list count, never `health.served`) —
recorded as a disclosed, read-only source finding, not something this revision sent a request to
verify. The record was re-hashed (new `Record sha256:
24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`, superseding
`f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`), the locked copy at
`evaluator-only/adoption-criteria.locked.md` was refreshed (`chmod u+w`, byte-identical copy,
`chmod a-w`; `cmp` confirms byte-identity), and Task 1's and Task 2's exact automated `<verify>`
commands were both re-run and both still exit 0 (Effort-equality check still passes: `max == max`;
contamination/packet/parity checks still pass). No existing text from revision 1 or the original
record was deleted; where new text differs from or extends it (the step-4 "step 12 or 12.5"
wording, the original per-arm effort table), the new text states explicitly which wording governs.
Still no comparison run, validation run, or gateway request was started; the owner has not yet
acknowledged this twice-revised record. See the CHECKPOINT REACHED section returned alongside this
summary.

**Revision 3 (2026-10-26):** The owner reviewed the revision-2 record and again declined to
acknowledge it, this time asking that the record be **consolidated into one authoritative set of
rules**, with every piece of superseded wording confined to the "Revision history" section, plus
five substantive changes: (1) relax routing exclusivity so that individually-attributable,
demonstrably-unrelated non-codex gateway traffic no longer voids attribution by itself, and require
within-session accounting (the parent and any other agent inside the test's own session) rather
than relying on session-id match alone; (2) align evidence-window sampling with the full window
including its 5-second margins (samples taken exactly at child launch/exit do not cover the
margins), and require independent process-start evidence — not `served`-counter agreement alone —
against a gateway restart; (3) resolve "fixed run counts" vs. "one retry per incomplete run" into
an explicit stated maximum; (4) restate the no-paid-API-overage constraint as hard, not
observational, and define concretely how it is checked read-only for both arms; (5) require the
full blind round (runs, freeze, adjudication, owner spot-check, feedback/packet preparation) to
complete before any revision run starts, rather than permitting an uninterrupted batch across both
rounds.

All five were applied, and the record was restructured end-to-end this session:
`84-ADOPTION-CRITERIA.md` is now organized as D-12..D-18 verbatim plus a "How these are applied"
pointer list, followed by nine authoritative, present-tense sections (§2 Matched-run settings, §3
Effort, §4 Scoring rules, §5 Run budget and sequencing, §6 Billing, §7 Full-loop validation, §8
Routing attribution standard, §9 Known limitations) and a "Revision history" that names, under each
prior revision, exactly which wording that revision's text superseded — there is no remaining
"both are kept, for the audit trail" / "this section governs where they differ" layering anywhere
in the body. The budget arithmetic resolves to the owner's own stated numbers: **2.0 hours maximum
with no retries** (6 scored attempts × 15 min + 30 min validation), **3.5 hours maximum if every
scored attempt needs its one retry** (12 × 15 min + 30 min). The billing section states the
no-overage constraint as hard and cites concrete, read-only, non-secret findings from this session:
the Codex backend has no API-key path in this gateway at all (ChatGPT OAuth only, per `commands.js`
line 533's `ChatGPT auth: valid` and the `login`/`doctor` flow); the ordinary arm's
`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`CLAUDE_CODE_OAUTH_TOKEN` env vars are confirmed unset
and a Keychain "Claude Code-credentials" entry exists (attributes only, never the secret), recorded
as "most likely subscription, not confirmed" rather than guessed. The routing section's new
"Restart" rule cites a real, live-confirmed mechanism found by reading
`lib/process-supervision.js`/`lib/commands.js` in the installed model-gateway 0.51.2: the shim
already writes `~/.claude/model-gateway/shim.pid.json` (`{pid, command, startedAt}`) on every start,
with `startedAt` captured via `ps -ww -p <pid> -o pid=,ppid=,lstart=,args=` — read this session,
read-only, confirming the current shim PID (`43968`) and its `startedAt`/live `ps -o lstart` agree
exactly (`Mon Oct 12 17:44:56 2026`), with no gateway request sent. The record was re-hashed (new
`Record sha256: 35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93`, superseding
`24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`), computed by the same
line-anchored method used in revisions 1 and 2 and cross-checked by a second, independent
`head`-based extraction (both methods agree). The locked copy at
`evaluator-only/adoption-criteria.locked.md` was refreshed (`chmod u+w`, byte-identical copy,
`chmod a-w`; `cmp` confirms byte-identity), and Plan 04's Task 1 and Task 2 exact automated
`<verify>` commands were both re-run and both still exit 0 (Effort-equality check still passes:
`max == max`; contamination/packet/parity checks still pass). No existing D-12..D-18 text and no
finding (E1-E7, N1-N5) was altered or relabelled; every piece of text this revision's consolidation
replaces is named, under its originating revision, in "Revision history." Still no comparison run,
validation run, or gateway/model request was started at any point during this revision. This
revision also newly specifies (for Plan 05, not executed now): the scratch `agent.spawn` hook must
gain an append-only per-spawn log line (timestamp, subagent name, rewritten model, counter) before
any run, and the record's §5 sequencing (full-loop validation + 4 blind runs → freeze → blind
adjudication + owner spot-check → identical feedback/revised packet prepared and hashed → only then
the 2 revision runs → revision adjudication) must be followed, with no uninterrupted batch spanning
the blind and revision rounds. The owner has not yet acknowledged this third revision. See the
CHECKPOINT REACHED section returned alongside this summary.

## Task Commits

No task-level code commits in Triggarr: every file Tasks 1-2 create or modify is either the git-excluded `84-ADOPTION-CRITERIA.md` (never committed, per D-16) or lives entirely outside the repo under `~/scratch/planchk-pilot/` (D-06). Only this SUMMARY.md (partial, `status: paused`) is force-added and committed now, per the pause protocol, so its commit timestamp — and therefore the criteria's lock timestamp recorded inside it — precedes any Plan 05 run.

## Files Created/Modified

- `.planning/phases/84-codex-plan-checker-investigation/84-ADOPTION-CRITERIA.md` — locked criteria record, revised three times on 2026-10-26 per the owner's five (revision 1), three (revision 2), then five-plus-consolidation (revision 3) requested changes; revision 3 restructures the record into D-12..D-18 verbatim plus nine single-authority sections (§2-§9) and a "Revision history" holding all superseded wording, `Record sha256: 35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93` (supersedes `24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`, which supersedes `f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`, which supersedes `3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69`), Owner acknowledgment section still pending (local only, never committed)
- `/Users/julianamacbook/scratch/planchk-pilot/evaluator-only/` — answer keys, contamination phrases, the locked criteria's read-only copy (mode 700)
- `/Users/julianamacbook/scratch/planchk-pilot/harness/check_packet.py`, `check_fallback_parity.py` — contamination and route-parity checks (stdlib only)
- `/Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1/` — the frozen, 133-file blind comparison packet
- `/Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1-driver.txt`, `blind-r1.sha256`, `blind-r1-drivers.sha256`, `blind-r1.check.txt`, `blind-r1.progress` — driver prompt and freeze/verification evidence
- `.planning/phases/84-codex-plan-checker-investigation/84-04-SUMMARY.md` — this file (partial; the only file this pause commits)

## ADOPTION-CRITERIA sha256: 35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93

(Supersedes the revision-2 value `24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`,
which superseded the revision-1 value `f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`,
which itself superseded the 2026-10-25 value
`3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69` — none of the three prior values
was acknowledged by the owner; all three rounds of changes were requested before acknowledgment.
This line will be updated again if the owner requests further changes; it is finalized only once
the owner's "acknowledged" reply is recorded in `84-ADOPTION-CRITERIA.md`'s "Owner acknowledgment"
section.)

## Decisions Made

See `key-decisions` in the frontmatter above. Headline: every value needed by Plan 05 (checker alias, route, effort, input label) was resolved live from this session's own evidence or carried forward from Plans 01-03's records — none was assumed or chosen to fit an anticipated result.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `check_packet.py`'s own forbidden-name pattern `*REVIEW*` would always reject the packet's required `REVIEWER-BRIEF.md`**
- **Found during:** Task 2, Step D (first contamination-check run against the assembled packet)
- **Issue:** The plan's Step A forbidden-name list (`*SUMMARY*`, `*REVIEW*`, `*VERIFICATION*`, `*UAT*`, ...) is meant to catch later review/revision artifacts (e.g. a stray deep-review note), but `*REVIEW*` also matches the packet's own deliberately-included `REVIEWER-BRIEF.md` — a file Step B explicitly instructs creating and Task 2's own `<verify>`/`<acceptance_criteria>` require to exist. As written, the check could never pass on a conforming packet.
- **Fix:** Added a narrow, named exemption (`REVIEWER-BRIEF.md` only) to the forbidden-name check, with the reasoning recorded inline in the script. Added a dedicated self-test case confirming a clean `REVIEWER-BRIEF.md` passes.
- **Cost if wrong:** If this exemption were instead hiding a real leak, a `REVIEWER-BRIEF.md` containing K1-K7/R1-R4 wording would still be caught by the separate acceptance-criteria check (`grep` for K/R wording) and by the phrase-contamination scan (REVIEWER-BRIEF.md's own content is still scanned for phrases, only its *filename* is exempted from the forbidden-name list) — confirmed clean in this execution.
- **Files modified:** `harness/check_packet.py`.
- **Commit:** N/A (scratch file, not committed).

**2. [Rule 2 - Missing critical functionality] The packet's own `README.md` tripped the contamination check it was meant to satisfy**
- **Found during:** Task 2, Step D (first contamination-check run)
- **Issue:** My first draft of `README.md` (required by the acceptance criteria: "a redaction log with counts exists in packets/blind-r1/README") used the literal phrases "PLANCHK-03 blind comparison" and "the blind packet" — both on the contamination-phrase list, since they are investigation-process terms that should not reach a checker session.
- **Fix:** Rewrote the two sentences in neutral language ("an independently-adjudicated, two-arm comparison... (two separate model configurations)", "this packet") with no loss of information; re-ran the contamination check, now clean.
- **Cost if wrong:** Low — this is the executor's own newly-authored file, not a frozen original, so it was correctly treated as fully subject to the contamination check; the fix only changes wording, not the redaction log's actual counts or the unavailable-inputs record.
- **Files modified:** `packets/blind-r1/README.md` (before freezing; refrozen after the fix).
- **Commit:** N/A (scratch file, not committed).

**3. [Rule 2 - Missing critical functionality] Thorough redaction of the two sandbox runbook references before freezing the packet**
- **Found during:** Task 2, Step B (sandbox-runbook copy)
- **Issue:** The plan requires redacting "private hostnames, IPs, usernames and any credential-like strings" from the two runbook files before they enter a packet that a Codex-routed (external-backend) checker will read in Plan 05. The source files contain a real NAS hostname, a real personal seedbox domain, a real username, a real LAN IP, and several internal container hostnames.
- **Fix:** Wrote a longest-match-first literal-string redaction script (ordered to avoid partial-match collisions, e.g. `nyx.usbx.me` before `jules1651`), applied it, then ran a residual-token grep over the redacted output confirming zero remaining occurrences of every identified private token before the files entered the frozen packet. Logged counts only (HOST=92, IP=1, USER=14, SECRET=0), never the original values, per the plan's own instruction and this project's CLAUDE.md ("never log sensitive data").
- **Cost if wrong:** High if missed — an unredacted leak would send the owner's real infrastructure topology, personal domain and username to an external LLM backend via model-gateway. Mitigated by the explicit residual-token verification step before freezing, not just trusting the redaction script's own reported counts.
- **Files modified:** `packets/blind-r1/sandbox-runbook/SANDBOX-sonarr-v5.md`, `RUNBOOK-sonarr-v5-test.md` (new, redacted copies only — the originals at `/Users/julianamacbook/Cowork/mediaserver/` were never modified).
- **Commit:** N/A (scratch files, not committed).

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug in the check script's own pattern scope, 2 Rule 2 missing-critical-functionality additions — clean packet-internal wording and thorough redaction). None touch Triggarr; all are scoped to the scratch pilot and its packet. Each was verified against the task's own automated `<verify>` command (all passing, exit 0) before being relied on.
**Impact on plan:** All three were necessary for the packet to actually satisfy its own stated purpose (a clean, non-leaking, checker-ready comparison input) rather than merely appearing to.

## Issues Encountered

None beyond the three auto-fixed deviations above, all resolved within this plan using the plan's own granted decision authority (Rule 1/Rule 2).

## User Setup Required

**Yes — this is why execution is paused.** See the CHECKPOINT REACHED section returned alongside this summary: the owner must review the **three-times-revised, now consolidated** locked adoption criteria (revision 3, 2026-10-26) in plain language and reply "acknowledged" (or request further changes, which are only permitted at this point) before Plan 05 runs any comparison or the full-loop validation exercise.

## Next Phase Readiness

- Tasks 1-2 are complete and independently verified (both tasks' exact `<verify>` commands exit 0, re-confirmed after revision 1, revision 2, and now revision 3); Task 3 cannot proceed without the owner's explicit acknowledgment of the **consolidated** `84-ADOPTION-CRITERIA.md` (`Record sha256: 35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93`).
- A continuation agent should re-verify `shasum -a 256 -c` on `packets/blind-r1.sha256` (excluding its last line) and `inputs/manifest.sha256` from their respective directories, confirm `84-ADOPTION-CRITERIA.md`'s `Record sha256:` line is unchanged from this revision (or apply any newly requested changes, re-hash, and re-present), then present the checkpoint to the owner (or process the owner's recorded reply if already given) and complete Task 3.
- Blocker: Task 3, and all of Plan 05 (including the new full-loop validation exercise), cannot proceed without the owner's recorded acknowledgment (or further requested changes, re-hashed and re-presented) of the locked criteria.
- **New obligations for Plan 05, specified by revision 3 but not implemented now:** (i) before any run, add an append-only per-spawn log line (timestamp, subagent name, rewritten model, counter) to the scratch `agent.spawn` hook from Plan 01 — this is a change to scratch code, must itself be recorded and hashed before use, and is required for §8's "within-session accounting" rule; (ii) follow §5's mandatory sequencing (full-loop validation + 4 blind runs → freeze → blind adjudication + owner spot-check → identical feedback/revised packet prepared and hashed → only then the 2 revision runs → revision adjudication) — no uninterrupted batch may span the blind and revision rounds, and within either batch of runs, launching as a batch (rather than one at a time) is permitted only when every §8 exclusivity condition holds for each run in the batch.

---
*Phase: 84-codex-plan-checker-investigation*
*Paused: 2026-10-25 (mid-execution, awaiting owner acknowledgment of the locked adoption criteria)*

## Self-Check: PASSED

Verified file existence (all FOUND):
- `.planning/phases/84-codex-plan-checker-investigation/84-ADOPTION-CRITERIA.md`
- `/Users/julianamacbook/scratch/planchk-pilot/evaluator-only/answer-key-initial.md`, `answer-key-revision.md`, `contamination-phrases.txt`, `adoption-criteria.locked.md`
- `/Users/julianamacbook/scratch/planchk-pilot/harness/check_packet.py`, `check_fallback_parity.py`
- `/Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1-driver.txt`, `blind-r1.sha256`, `blind-r1-drivers.sha256`, `blind-r1.check.txt`, `blind-r1.progress`
- `/Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1/REVIEWER-BRIEF.md`, `README.md`

Verified commit exists: `git log --oneline --all | grep -q 390534d` → FOUND.

Verified STATE.md/ROADMAP.md/REQUIREMENTS.md untouched: `git status --short -- .planning/STATE.md .planning/ROADMAP.md .planning/REQUIREMENTS.md` → empty.

Verified Task 1's exact `<verify>` command → exit 0 (re-run before writing this summary).
Verified Task 2's exact `<verify>` command → exit 0 (re-run before writing this summary).
Verified `shasum -a 256 -c` on `packets/blind-r1.sha256` (excluding its last line, from inside `packets/blind-r1`) → 133/133 OK.
Verified `check_packet.py --self-test` and `check_fallback_parity.py --self-test` → both `SELF-TEST PASS`.

## Self-Check (Revision 1, 2026-10-26): PASSED

Re-verified after applying the owner's five requested changes:
- `grep -n "^Record sha256:" 84-ADOPTION-CRITERIA.md` → exactly one line, value
  `f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`.
- Hash recomputed independently by two methods (Python `bytes.split(b'\n')` line-join up to the
  line starting `Record sha256:`, and a `sed`-based extraction) → both agree with the recorded
  value. The same method, applied to a reconstruction of the pre-revision file, reproduces the
  known-good superseded hash `3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69`,
  confirming the hashing method itself (an earlier attempt using Python's plain `bytes.find()`
  instead of a line-start match collided with this revision's own "Revision log" section, which
  mentions the superseded hash by name — caught before trusting it, corrected to the line-anchored
  method before writing the final value).
- `cmp 84-ADOPTION-CRITERIA.md evaluator-only/adoption-criteria.locked.md` → exit 0 (byte-identical;
  locked copy is `chmod a-w`).
- Task 1's exact `<verify>` command → exit 0 (Effort equality `max == max` still holds).
- Task 2's exact `<verify>` command → exit 0 (`PACKET CLEAN`, `PARITY OK (route=hook)`, packet and
  driver shas still verify).
- No comparison run, validation run, or gateway/model request was started at any point during this
  revision. `git status --short` shows no changes to `.planning/STATE.md`, `.planning/ROADMAP.md`,
  or `.planning/REQUIREMENTS.md`.

## Self-Check (Revision 2, 2026-10-26): PASSED

Re-verified after applying the owner's three requested clarifications:
- `grep -n "^Record sha256:" 84-ADOPTION-CRITERIA.md` → exactly one line, value
  `24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`.
- Hash recomputed independently by two methods: Python `bytes.split(b'\n')` line-join up to the
  line starting `Record sha256:` (no trailing newline), and a `head -n`/byte-trim extraction
  (`head -n 603 file | head -c $((N-1))`, dropping exactly the one trailing newline byte `head -n`
  leaves after the blank line that precedes `Record sha256:`) → both agree with the recorded
  value, `24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`.
- `cmp 84-ADOPTION-CRITERIA.md evaluator-only/adoption-criteria.locked.md` → exit 0 (byte-identical;
  locked copy refreshed `chmod u+w` -> copy -> `chmod a-w`).
- Task 1's exact `<verify>` command → exit 0 (Effort equality `max == max` still holds; the
  `Effort: max` line text is unchanged from revision 1).
- Task 2's exact `<verify>` command → exit 0 (`PACKET CLEAN`, `PARITY OK (route=hook)`, packet and
  driver shas still verify; the self-test diagnostic lines the command prints internally — e.g. the
  planted-failure cases inside `check_packet.py --self-test` and `check_fallback_parity.py
  --self-test` — are expected negative-path output, not failures of the command itself).
- No existing D-12..D-18 text, no original "Scoring rules (fixed before any run)" text, no
  revision-1 section text, and no revision-1 "Revision log" entry was deleted; every new addition
  (the top-of-record framing statement, the "Full-loop validation" addendum, the three-way effort
  table, and the "Option 2" subsection) states explicitly which wording governs where it overlaps
  with earlier text, per binding rule 8.
- The two new, read-only source citations added this revision (`lib/request-worker.js`'s `served`
  counters at lines 1076/2085/2112/2251/2320/2344; `lib/commands.js`'s `fetchShimHealth()`/`doctor()`
  at lines 734-736/1146-1161) were confirmed by direct `Read`/`grep` of the installed model-gateway
  0.51.2 plugin cache in this session — no request was sent to the shim or the gateway to test them.
- No comparison run, validation run, or gateway/model request was started at any point during this
  revision. `git status --short` (Triggarr repo root) shows no changes to `.planning/STATE.md`,
  `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`, and no other tracked file.

## Self-Check (Revision 3, 2026-10-26): PASSED

Re-verified after consolidating the record into one authoritative rule set per the owner's
instruction:
- `grep -n "^Record sha256:" 84-ADOPTION-CRITERIA.md` → exactly one line, value
  `35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93`.
- Hash recomputed independently by two methods: Python `bytes.split(b'\n')` line-join up to the
  line starting `Record sha256:` (no trailing newline), and an independent `head -n`-based
  extraction (`head -n $((LINE-1))` then dropping the one trailing newline byte) → both agree with
  the recorded value.
- `grep -Ec "^Effort: (max|xhigh)$"` and `grep -Ec "^Route: (hook|fallback-agent)$"` both return
  exactly `1` (no accidental duplicate standalone lines introduced by the rewrite).
- `cmp 84-ADOPTION-CRITERIA.md evaluator-only/adoption-criteria.locked.md` → exit 0 (byte-identical;
  locked copy refreshed `chmod u+w` → copy → `chmod a-w`).
- Plan 04 Task 1's exact `<verify>` command → exit 0 (Effort equality `max == max` still holds;
  D-12..D-18, `Input label:`, `Route: hook`, and the 64-hex-char `Record sha256:` line are all
  present).
- Plan 04 Task 2's exact `<verify>` command → exit 0 (`PACKET CLEAN`, `PARITY OK (route=hook)`,
  packet and driver shas still verify — this task does not read `84-ADOPTION-CRITERIA.md`'s content
  directly, so it was unaffected by the rewrite, and re-running it confirms nothing else in the
  pilot was disturbed).
- The new read-only, non-secret source citations added this revision were independently confirmed
  this session, with no gateway request or child `claude` session started: `~/.claude/model-gateway/
  shim.pid` (`43968`) and `shim.pid.json` (`startedAt: "Mon Oct 12 17:44:56 2026"`) were read
  directly; a `ps -p 43968 -o pid=,lstart=` cross-check returned the identical `lstart` value; the
  `writePidRecordAsync`/`processInfoSync` call sites were read in
  `lib/process-supervision.js` (lines 49-87, 276-281) and `lib/commands.js` (line 2187); the
  Codex-backend OAuth-only auth path was read in `commands.js` (`login`, `ChatGPT auth: valid` at
  line 533) and confirmed present via a directory listing (not a content read) of
  `~/.config/claude-code-proxy/`; `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/
  `CLAUDE_CODE_OAUTH_TOKEN` presence (not value) was checked via `printenv` and found unset; a
  macOS Keychain entry named "Claude Code-credentials" was confirmed to exist via `security
  find-generic-password` with no `-w` flag (attributes only, the secret was never retrieved); the
  `request-routes.jsonl` append-only write site (`lib/request-worker.js` line 1150) and its path
  definition (`runtime.js` line 32) were read to confirm no internal rotation/truncation logic.
  `/healthz` was not queried, per binding rule 1.
- No existing D-12..D-18 text, and no finding (E1-E7, N1-N5) in `84-PILOT-EVIDENCE.md`, was altered
  or relabelled. Every piece of wording this revision's consolidation replaces is named, under its
  originating revision, in the rewritten "Revision history" section — there is no remaining
  "both are kept, for the audit trail" / "this section governs where they differ" layering in the
  body.
- No comparison run, validation run, or gateway/model request was started at any point during this
  revision. `git status --short` (Triggarr repo root) shows no changes to `.planning/STATE.md`,
  `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`; the only modified tracked file is this
  SUMMARY.md (`84-ADOPTION-CRITERIA.md` itself is git-excluded per D-16, so it does not appear in
  `git status`).
