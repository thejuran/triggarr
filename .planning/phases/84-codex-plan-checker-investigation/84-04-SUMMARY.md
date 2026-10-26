---
phase: 84-codex-plan-checker-investigation
plan: "04"
subsystem: investigation
tags: [adoption-criteria, blind-comparison, evaluator-only, contamination-check, parity-check, d-12, d-13, d-14, d-15, d-17, d-18]
status: complete

# Dependency graph
requires:
  - phase: 84-codex-plan-checker-investigation (Plan 01)
    provides: "Route decision (hook), routed model (claude-gpt-6-astra[1m])"
  - phase: 84-codex-plan-checker-investigation (Plan 02)
    provides: "Matched-run harness, --permission-mode dontAsk + run-settings.json, Effort accepted: max"
  - phase: 84-codex-plan-checker-investigation (Plan 03)
    provides: "ORIGINAL-labelled, frozen, hashed Phase 81 input set at inputs/phase81-best/"
provides:
  - "Locked, owner-acknowledged adoption criteria (84-ADOPTION-CRITERIA.md): D-12..D-18 verbatim, fixed scoring rules, matched-run settings, input label, resolved checker alias (sonnet), route (hook), effort (max), sha256-hashed and copied read-only into evaluator-only/ -- acknowledged by the owner at Record sha256 e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a (Task 3 complete)"
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
    - .planning/phases/84-codex-plan-checker-investigation/84-ADOPTION-CRITERIA.md (local only, git-excluded, never committed per D-16; Record sha256 e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a acknowledged by the owner; the file's own text was not edited to add an "Owner acknowledgment" section -- the acknowledgment is instead recorded in the separate evidence file below, per explicit continuation instruction, so the acknowledged hash is never altered by the act of recording acknowledgment of it)
    - .planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md (local only, git-excluded, never committed; acknowledged hash, UTC timestamp, owner's verbatim reply, the two accepted judgment calls, the three cosmetic issues left unedited by owner choice)
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
  - "Revision 4's §6 launch precondition is MET for every participating backend (Codex, Anthropic/ordinary arm, parent/orchestrator) on the basis of four dated owner attestations recorded verbatim in 84-ADOPTION-CRITERIA.md §6 item 2 (plan tiers; no separate API billing; Claude extra usage confirmed off after being briefly on) plus prior read-only evidence -- Plan 05 must re-check this immediately before its first run"
  - "Owner acknowledged revision 4 verbatim ('acknowledged') on 2026-10-26, accepting as written two orchestrator-presented judgment calls (the Codex proxy-internals limitation as disclosed-non-blocking against §6; 'no api billing' read as covering both accounts) and declining to request three listed cosmetic cleanups -- recorded in a separate, git-excluded 84-CRITERIA-ACK.md rather than inside 84-ADOPTION-CRITERIA.md itself, so the acknowledged Record sha256 is never altered by the act of recording the acknowledgment"

requirements-completed: ["PLANCHK-03"]

# Metrics
duration: "~25min (building Tasks 1-2, 2026-10-25) + four same-day revision rounds (2026-10-26) + Task 3 acknowledgment recorded (2026-10-26)"
completed: 2026-10-26
---

# Phase 84 Plan 04: Locked Adoption Criteria & Blind Packet (Owner-Acknowledged) Summary

**Built and verified the locked D-12..D-18 adoption-criteria record (through four owner-requested revisions), the withheld K1-K7/R1-R4 evaluator-only answer keys, and a frozen, hash-manifested, contamination-clean 133-file blind comparison packet with its driver prompt -- then recorded the owner's explicit acknowledgment of the final record before any comparison run, per binding rule 5.**

## Performance

- **Duration:** ~25 min (Tasks 1-2, 2026-10-25) + four revision rounds and the acknowledgment (2026-10-26)
- **Completed:** 2026-10-26T19:41:58Z (acknowledgment recorded)
- **Tasks:** 3 of 3 complete and verified (Task 1 auto, Task 2 auto, Task 3 checkpoint:human-verify -- owner replied "acknowledged" to revision 4)
- **Files modified (Triggarr tracked files):** 0 besides this SUMMARY.md -- every other deliverable is either the git-excluded `84-ADOPTION-CRITERIA.md`/`84-CRITERIA-ACK.md` or lives entirely outside the repo under `~/scratch/planchk-pilot/` (D-16/D-06)

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

### Task 3 — owner acknowledgment recorded; plan complete
Per binding rule 5, this was a real stop: the criteria, scoring rules, matched-run settings, route disclosure, and known limitations had to be presented to the owner in plain language and explicitly acknowledged (or revised and re-hashed) before any comparison run. No comparison run was started at any point, including during this final step.

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

**Revision 4 (2026-10-26):** The owner reviewed the revision-3 record and again declined to
acknowledge it, identifying three specific defects the orchestrator had flagged against revision 3,
plus one correction of the owner's own: (1) the process-census and restart evidence in §8 were
still sampled "immediately before launch and immediately after exit," not across the same
5-second-margin-inclusive window already required for the log offset and the `/healthz` counters;
(2) §6's Codex billing bullet asserted "no API-key path for the Codex backend in this gateway at
all ... by construction" — a certainty claim the read-only evidence does not actually support,
because every Codex-auth code path (`login`, `setup`, `doctor`, the `isAuthed()` readiness check)
forwards its real work to `claude-code-proxy`, a separately downloaded, compiled binary this
investigation has not inspected; (3) §6 had no precondition that blocks a run from launching when
subscription-only billing cannot be confirmed for every participating backend, only a requirement to
record usage as observational; (4) §8's session-id census bullet said a matching session id
"establishes exclusivity outright," which overstates what a session match actually proves.

All four were applied in place this session, inside the consolidated structure revision 3
established (one authoritative rule per section; no wording restored outside "Revision history"):
§8 now defines one **pre-window sample** and one **post-window sample**, used identically by all
four evidence types (log offset/inode/size, `/healthz` counters, `shim.pid`/`shim.pid.json`, and the
`claude` process census) — the "Restart" paragraph and the "Process census" bullet were both
rewritten to reference these same two named samples instead of "immediately before launch/after
exit." §6's Codex-backend bullet was rewritten from the "by construction" certainty claim to a
cited, read-only evidentiary statement ("subscription OAuth indicated by gateway source; proxy
behaviour unverified"), with a corrected `doctor`-vs-`setup` citation (this session's direct reading
of the installed model-gateway 0.51.2's `lib/commands.js` found that `ChatGPT auth: valid`, line
533, is printed by the `setup` command, not `doctor`, which instead prints `codex auth:
authenticated`, line 1153, from the same underlying `codexAuth` check) and a named **LIMITATION**
that the proxy binary (`raine/claude-code-proxy`, confirmed present at `~/.config/claude-code-proxy/`
via a directory listing only, mode 700, contents not read; no `apiKey`/`api_key`/`API_KEY` string
anywhere in the gateway's own `lib/*.js`, grepped this session) was never downloaded, decompiled, or
inspected, so its own billing/API-key behavior is unverified, not ruled out. §6 gained a new item 2,
"Launch precondition," a hard gate: no validation or scored run may launch unless subscription-only
billing is confirmed, by non-model-request evidence only (local config/credential metadata, help
text, or a dated owner attestation — never a model request, gateway request, or status/auth command
run merely to discover billing mode), for all three participating backends — the Codex arm, the
Anthropic/ordinary arm, and the parent/orchestrator sessions themselves (Anthropic) — with a
per-backend table. As first written, before any owner response, every row read "not confirmed —
BLOCKED." §8's session-id census bullet was corrected from "exclusivity is established outright" to:
a matching session id establishes only **session exclusivity** (no other session used the gateway in
the window) and never checker-specific attribution by itself — the within-session accounting already
required above (hook-spawn log, checker interval, model-id partition, reconciliation) still applies
in full even when the session id matches, and a `codex` line is attributed to the checker only when
that accounting ties it to a checker interval or hook-log spawn, never to the parent or another agent
by default. The rest of the record (§7 steps 2/5, §4's D-14 evidence map, §8's "Consequence"
paragraph) was checked for the same "session match ⇒ checker attribution" implication and needed no
correction — each already required the full §8 standard. No existing D-12..D-18 text, and no finding
(E1-E7, N1-N5), was altered or relabelled; every piece of wording this revision replaces is named,
under "revision 4," in "Revision history," and no earlier revision's wording was reintroduced as a
second, competing version. The read-only investigation this revision performed — reading
`lib/commands.js`/`lib/runtime.js` in the installed model-gateway 0.51.2, listing (never reading the
contents of) `~/.config/claude-code-proxy/`, and re-reading `~/.claude/model-gateway/shim.pid`/
`shim.pid.json` (PID `43968`, `startedAt` unchanged from revision 3's finding) — sent no gateway
request and started no `claude-code-proxy codex auth status`/`doctor`/`setup` invocation; those
commands were read as source, never executed, per binding rule 1.

**Owner attestations, same session, applied within revision 4 (not a fifth revision):** immediately
after seeing §6's new per-backend table, the owner supplied four dated statements, recorded verbatim
and in order in §6 item 2: (1) "I have claude max 20 and chatgpt pro." (2) "no api billing and extra
usage is on." (3) "extra usage is on claude but there is no guarantee there will be extra money but
do you think you need it I want to avoid" (4) "extra usage is off." Applied as received, the table's
status moved through three states, none deleted from the record: attestation 1 alone left every row
"not confirmed — BLOCKED" (plan tier only); attestation 2 resolved the API-billing question but
opened an account-ambiguous "extra usage is on," leaving every row "not confirmed — BLOCKED" because
which account was unstated; attestation 3 named the Claude account specifically (not ChatGPT) and
stated the owner's intent to avoid paid extra usage; attestation 4 confirmed that Claude extra usage
is now off. The final, current table reads: **Anthropic/ordinary arm and parent/orchestrator —
confirmed subscription-only** (attestations 1/2/4 plus the existing unset-env-var/Keychain-presence
evidence); **Codex — confirmed subscription-only on the gateway side** (attestations 1/2 plus the
gateway-source OAuth-only evidence), with the `claude-code-proxy` binary's own internals carried
forward as a disclosed, non-blocking limitation (§9) rather than as grounds to withhold confirmation
of the owner-attestable facts. **The §6 launch precondition is now MET for every participating
backend**, subject to two standing conditions recorded in the same section: Plan 05 must re-check the
attestation and the local env/credential evidence immediately before its first run (point-in-time
confirmation, not a standing one), and item 3's quota/rate-limit/`upstream-blocked` stop is
unaffected and still applies.

The record was re-hashed once, over its final state including both the structural fixes and the
attestation-driven §6/§9 updates (new `Record sha256:
e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a`, superseding
`35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93`), computed by the same
line-anchored method used in revisions 1-3 and independently cross-checked by a `head`-based
extraction (both agree). The locked copy at `evaluator-only/adoption-criteria.locked.md` was
refreshed (`chmod u+w`, byte-identical copy, `chmod a-w`; `cmp` confirms byte-identity), and Plan
04's Task 1 and Task 2 exact automated `<verify>` commands were both re-run against this final state
and both still exit 0 (Effort-equality check still passes: `max == max`; contamination/packet/parity
checks still pass, including the expected negative-path output inside each script's own
`--self-test`). No request of any kind — model, gateway, or status/auth command — was started at any
point during this revision; every billing-mode fact above is either owner attestation or the prior
read-only evidence from item 1. At this point the attestations had resolved §6's launch
precondition, which was a different step from acknowledging the full record as a whole — that
acknowledgment follows below.

**Owner acknowledgment (2026-10-26):** in direct reply to the orchestrator presenting revision 4 in
full, together with `Record sha256: e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a`,
and the orchestrator's explicit note that acknowledging accepts as written (a) the Codex
proxy-internals limitation (§6, §9) as a disclosed, non-blocking limitation against the §6 launch
precondition and (b) "no api billing" (owner attestation 2) read as covering both accounts, the
owner replied verbatim: **"acknowledged."** The orchestrator had also listed three cosmetic,
non-rule cleanups still present in the record (leftover "this replaces..." notes in §6 line ~291 and
§8 line ~502; the revision-4 history entry attributing defect identification to the owner rather than
the orchestrator; small revision annotations in §8); the owner acknowledged **without** requesting
them, so the record's text was **not** edited for these or for anything else — any edit, even one
confined to cosmetic wording, would require recomputing and re-presenting a new hash, which is not
what the owner's "acknowledged" reply addressed.

Before recording the acknowledgment, the hash and the locked copy were independently re-verified in
this session: the sha256 of the record's content up to (not including) the `Record sha256:` line
(line-joined with `\n`, no trailing newline) was recomputed with Python and matched
`e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a` exactly; `cmp` against
`/Users/julianamacbook/scratch/planchk-pilot/evaluator-only/adoption-criteria.locked.md` exited 0
(byte-identical), and that locked copy remains mode 444 (non-writable).

Per explicit continuation instruction, **`84-ADOPTION-CRITERIA.md` itself was not modified** to add
the plan's own "Owner acknowledgment" section (even though appending text after the `Record sha256:`
line would not change the hash — the plan's own action text notes the sha covers the criteria
content only). Instead, the acknowledgment is recorded in a separate, local, git-excluded evidence
file, `.planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md` (confirmed excluded
via the repo's existing `.git/info/exclude` `.planning/` pattern; `git status --short` shows nothing
for it), containing: the acknowledged record hash; the UTC timestamp this acknowledgment was
recorded (`2026-10-26T19:41:58Z`); the owner's verbatim word; the two accepted judgment calls; and
the three cosmetic issues left unedited by owner choice. See "Deviations from Plan" below for the
resulting mismatch against Task 3's own literal automated `<verify>` command, which greps
`84-ADOPTION-CRITERIA.md` for the string "Owner acknowledgment" and therefore fails as written.

No comparison run, validation run, or model/gateway request was started at any point while recording
this acknowledgment.

**Plan 05 obligations carried forward from the acknowledged record** (specified by the record, not
implemented in this plan):
1. **Hook spawn-log change (§8):** Plan 01's scratch `agent.spawn` hook must gain an append-only
   per-spawn log line (timestamp, subagent name, rewritten model, counter) before any run; the
   changed hook must itself be recorded and hashed before use.
2. **Billing precondition re-check (§6 item 2):** immediately before Plan 05's first run, re-confirm
   the owner's attestation is still current and re-check, read-only, the local env/credential
   evidence from §6 item 1 (the `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`CLAUDE_CODE_OAUTH_TOKEN`
   env vars still unset; the Keychain "Claude Code-credentials" entry still present) -- point-in-time,
   not a standing confirmation; if anything has changed, the precondition is unmet again rather than
   assumed to still hold. Item 3's quota/rate-limit/`upstream-blocked` stop applies independently and
   is unaffected.
3. **Margin-inclusive, combined pre/post samples (§8):** all four evidence types (`request-routes.jsonl`
   byte offset/inode/size; the shim's `/healthz` `served` counters; `shim.pid`/`shim.pid.json`
   `pid`/`startedAt`; the `claude` process census) must be captured at the same two named points --
   a pre-window sample taken at or before `started_at` − 5s, and a post-window sample taken at or
   after `finished_at` + 5s -- never "immediately at launch/exit" for any of them.
4. **Sequencing (§5):** full-loop validation + the 4 blind runs (batched only if every §8 exclusivity
   condition holds per run) → freeze (hash manifest, `chmod a-w`) → blind adjudication + owner
   spot-check → identical adjudicated feedback and a revised packet prepared and hashed for both arms
   → only then the 2 revision runs (same batching rule) → revision adjudication. No uninterrupted
   batch may span the blind and revision rounds.
5. **Run-budget ceiling (§5):** 2.0 hours maximum with no retries (6 scored attempts × 15 min + the
   one 30-min validation); 3.5 hours maximum if every scored attempt needs its one permitted retry
   (12 × 15 min + 30 min) -- there is no second retry.
6. **Full-loop validation, 30 min, 5 steps (§7):** one attempt, up to 30 minutes, never retried, never
   folded into D-12/D-13, never counted as one of the 6 scored attempts. "Complete" requires
   independent confirmation of all five steps: (1) the checker spawn (step 10) is actually reached;
   (2) the checker invocation is routed to Codex at the ATTRIBUTED tier per §8, not merely INDIRECT;
   (3) the checker returns a structured `## VERIFICATION PASSED` / `## ISSUES FOUND` result; (4) at
   least one full step-12 revision/recheck cycle completes, independently confirmed; (5) the
   post-bounce recheck (step 12.5) is separately reached and independently confirmed on the same
   terms as step 4 -- steps 4 and 5 are not interchangeable. `84-PILOT-EVIDENCE.md` E4/E5 stay
   recorded exactly as failed/incomplete attempts, never relabelled or superseded, even if this
   validation succeeds.

## Task Commits

No task-level code commits in Triggarr: every file Tasks 1-2 create or modify is either the git-excluded `84-ADOPTION-CRITERIA.md`/`84-CRITERIA-ACK.md` (never committed, per D-16) or lives entirely outside the repo under `~/scratch/planchk-pilot/` (D-06). Only this SUMMARY.md (now `status: complete`) is force-added and committed, per the plan's Task 3 protocol, so its commit timestamp — and therefore the acknowledgment-recording timestamp carried inside it — precedes any Plan 05 run. Commit message: `docs(84-04): record owner acknowledgment of adoption criteria rev 4`.

## Files Created/Modified

- `.planning/phases/84-codex-plan-checker-investigation/84-ADOPTION-CRITERIA.md` — locked criteria record, revised four times on 2026-10-26 per the owner's five (revision 1), three (revision 2), five-plus-consolidation (revision 3), then three-plus-one-correction (revision 4) requested changes; revision 3 restructured the record into D-12..D-18 verbatim plus nine single-authority sections (§2-§9) and a "Revision history" holding all superseded wording; revision 4 fixed §8's sampling (one shared pre-window/post-window sample for all four evidence types), §6's Codex billing certainty (replaced with cited evidence plus the proxy-binary limitation), added §6's hard launch precondition (initially BLOCKED on every row, then resolved to MET for every participating backend by four dated owner attestations recorded verbatim in §6), and corrected §8's session-id wording (session match ⇒ session exclusivity only, never checker attribution by default); `Record sha256: e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a` (supersedes `35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93`, which supersedes `24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`, which supersedes `f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`, which supersedes `3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69`); **this hash is now acknowledged by the owner** (2026-10-26); the file's own text was not edited to add the plan's "Owner acknowledgment" section (local only, never committed, per D-16)
- `.planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md` — the acknowledgment evidence record (local only, never committed, git-excluded)
- `/Users/julianamacbook/scratch/planchk-pilot/evaluator-only/` — answer keys, contamination phrases, the locked criteria's read-only copy (mode 700)
- `/Users/julianamacbook/scratch/planchk-pilot/harness/check_packet.py`, `check_fallback_parity.py` — contamination and route-parity checks (stdlib only)
- `/Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1/` — the frozen, 133-file blind comparison packet
- `/Users/julianamacbook/scratch/planchk-pilot/packets/blind-r1-driver.txt`, `blind-r1.sha256`, `blind-r1-drivers.sha256`, `blind-r1.check.txt`, `blind-r1.progress` — driver prompt and freeze/verification evidence
- `.planning/phases/84-codex-plan-checker-investigation/84-04-SUMMARY.md` — this file (partial; the only file this pause commits)

## ADOPTION-CRITERIA sha256: e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a

**This value is now acknowledged by the owner** (verbatim reply "acknowledged," 2026-10-26T19:41:58Z,
recorded in `.planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md`, local only,
git-excluded, never committed).

(Supersedes the revision-3 value `35cc8a51d3c881f7df0b110aabc4ed667143fe2431732aac5e961b68a0e3fa93`,
which superseded the revision-2 value `24ac86fa77b17fcf75c388faae7dfe1adf37a99e9b4c028eb4336c8892dd7796`,
which superseded the revision-1 value `f33e8101e7df4690889a2bcf8fe73af95a1ff28d0b0fe58bb4a619e700fa3b05`,
which itself superseded the 2026-10-25 value
`3ba93ce18d217542813bd8daad6c285b76fc82bd90fc6d9de1be36385e000e69` — none of the four prior values
was acknowledged by the owner; all four rounds of changes were requested before acknowledgment, and
only the final, fourth-revision value above was ever acknowledged.)

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

**4. [Explicit continuation instruction, not a Rule 1-3 auto-fix] `84-ADOPTION-CRITERIA.md` was not edited to add the plan's own "Owner acknowledgment" section, so Task 3's literal automated `<verify>` command fails as written**
- **Found during:** Task 3, recording the owner's acknowledgment.
- **Issue:** The plan's Task 3 `<action>`/`<how-to-verify>` text calls for recording "the owner's reply verbatim with UTC time under 'Owner acknowledgment' at the end of 84-ADOPTION-CRITERIA.md (after the sha line; the sha covers the criteria content only)," and Task 3's own automated `<verify>` greps for the literal string "Owner acknowledgment" inside `84-ADOPTION-CRITERIA.md`. The continuation prompt directing this session explicitly instructed the opposite: "Do NOT modify 84-ADOPTION-CRITERIA.md. Record the acknowledgment in a separate local evidence file ... .planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md ... instead." That explicit, more specific instruction from the spawning agent was followed, so the file was not touched and the plan's own `<verify>` grep for "Owner acknowledgment" in `84-ADOPTION-CRITERIA.md` returns no match.
- **Fix:** None applied — this is not a bug to auto-fix; it is a deliberate instruction overriding the plan's literal verify mechanics. The acknowledgment is fully and durably recorded, just in `84-CRITERIA-ACK.md` rather than appended to the criteria record. Ran the exact command Task 3's plan specifies and observed its real result below rather than claiming it passed.
- **Observed result of Task 3's own `<verify>` command, run exactly as written:** `grep -q "Owner acknowledgment" 84-ADOPTION-CRITERIA.md` → **no match, exit 1** (confirmed by running the full compound command: exit code `1`). The remainder of the command (`Record sha256:` extraction and the SUMMARY grep) was never reached because of the short-circuit on the first failed `grep`.
- **Cost if wrong:** Low for the acknowledgment's substance (the hash, timestamp, verbatim reply, and accepted judgment calls are all durably recorded in `84-CRITERIA-ACK.md`, independently re-verified against the record's hash and the locked copy before being written) but this `<verify>` command, if re-run unmodified by a future agent expecting a literal pass/fail signal from it, will report failure even though the owner has in fact acknowledged the record — a future reader must consult this SUMMARY and `84-CRITERIA-ACK.md`, not the plan's literal grep, to see that acknowledgment occurred.
- **Files modified:** None in `84-ADOPTION-CRITERIA.md` (deliberately unmodified); `84-CRITERIA-ACK.md` created instead.
- **Commit:** N/A (both files are local-only, git-excluded, never committed, per the continuation instruction and D-16).

---

**Total deviations:** 3 auto-fixed (Tasks 1-2, 1 Rule 1 bug in the check script's own pattern scope, 2 Rule 2 missing-critical-functionality additions — clean packet-internal wording and thorough redaction), plus 1 explicit-continuation-instruction deviation (Task 3, acknowledgment recorded in a separate file rather than inside the criteria record, per direct instruction from the spawning agent). None touch Triggarr; all are scoped to the scratch pilot and its packet or to the local acknowledgment evidence.
**Impact on plan:** The first three were necessary for the packet to actually satisfy its own stated purpose. The fourth means Task 3's own literal `<verify>` command, run unmodified, reports failure (exit 1) despite the owner having genuinely acknowledged the record — a materially important fact for whoever next reads this SUMMARY or re-runs that command.

## Issues Encountered

One not-a-bug issue beyond the three Task 1-2 auto-fixed deviations: Task 3's own automated `<verify>` command cannot pass as literally written, because it checks for text inside `84-ADOPTION-CRITERIA.md` that an explicit continuation instruction directed this session not to add. See Deviation 4 above for the full explanation and the actual (failing) result of running that command.

## User Setup Required

**No further setup required to close Task 3.** The owner reviewed the final (revision 4) locked adoption criteria in plain language, presented together with `Record sha256: e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a`, and replied **"acknowledged"** on 2026-10-26, without requesting further changes. That acknowledgment is recorded in `.planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md` (local, git-excluded, never committed). Plan 05 may proceed subject to the obligations listed below, none of which were implemented by this plan.

## Next Phase Readiness

- Tasks 1, 2, and 3 are all complete. Task 1 and Task 2's exact `<verify>` commands exit 0 (re-confirmed in this session against the final, acknowledged record). Task 3's own literal `<verify>` command exits 1 as run verbatim, because it checks `84-ADOPTION-CRITERIA.md` for "Owner acknowledgment" text that this session was explicitly instructed not to add there; the acknowledgment itself is real and durably recorded in `84-CRITERIA-ACK.md` (see Deviation 4). A continuation agent (or Plan 05) should treat Task 3 as complete on the basis of `84-CRITERIA-ACK.md` plus this SUMMARY, not on the basis of re-running Task 3's unmodified `<verify>` command against `84-ADOPTION-CRITERIA.md` and expecting exit 0.
- Before Plan 05's first run, re-verify `shasum -a 256 -c` on `packets/blind-r1.sha256` (excluding its last line) and `inputs/manifest.sha256` from their respective directories, and confirm `84-ADOPTION-CRITERIA.md`'s `Record sha256:` line is still `e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a` (unchanged since acknowledgment — any further change would require a fresh owner acknowledgment of the new hash).
- **New obligations for Plan 05, specified by the record but not implemented by this plan:**
  1. **Hook spawn-log change (§8, revision 3):** before any run, add an append-only per-spawn log line (timestamp, subagent name, rewritten model, counter) to the scratch `agent.spawn` hook from Plan 01 — a change to scratch code that must itself be recorded and hashed before use, required for §8's "within-session accounting" rule.
  2. **Sequencing (§5, revision 3):** full-loop validation + 4 blind runs → freeze → blind adjudication + owner spot-check → identical feedback/revised packet prepared and hashed → only then the 2 revision runs → revision adjudication — no uninterrupted batch may span the blind and revision rounds; within either batch, launching as a batch (rather than one at a time) is permitted only when every §8 exclusivity condition holds for each run in the batch.
  3. **Billing launch precondition (§6, revision 4):** before any validation or scored run, re-confirm the owner's attestation is still current and re-check, read-only, the local environment/credential presence from §6 item 1 (env vars still unset, Keychain entry still present); if anything has changed since this record's attestation, treat the precondition as unmet again rather than assuming it still holds. Item 3's quota/rate-limit/`upstream-blocked` stop is unaffected and still applies independently.
  4. **Margin-inclusive combined sampling (§8, revision 4):** every evidence-gathering step (log offset/inode/size, `/healthz` counters, `shim.pid`/`shim.pid.json`, the `claude` process census) must use the same two named pre-window and post-window samples (window start − 5s / end + 5s), never "immediately at launch/exit" sampling for any of the four.
  5. **Session-match ≠ checker attribution (§8, revision 4):** attribution of any `codex`-backend line to the checker specifically still requires the within-session accounting in §8 even when every line's session id matches the run's own session — a session match alone is never read as checker attribution.
  6. **Run-budget ceiling (§5):** 2.0 hours maximum with no retries; 3.5 hours maximum if every scored attempt needs its one permitted retry — there is no second retry.
  7. **Full-loop validation, 30 min, 5 steps (§7):** one attempt, never retried, never folded into D-12/D-13 or the 6 scored attempts; "complete" requires independent confirmation of all five steps defined in §7, with E4/E5 staying recorded as failed/incomplete regardless of this validation's own outcome.

---
*Phase: 84-codex-plan-checker-investigation*
*Completed: 2026-10-26 (owner acknowledgment of the locked adoption criteria recorded; plan complete)*

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

## Self-Check (Revision 4, 2026-10-26): PASSED

Re-verified after applying the orchestrator's three flagged fixes, the owner's own §8 correction,
and the owner's four dated billing attestations, all within this one revision:
- `grep -n "^Record sha256:" 84-ADOPTION-CRITERIA.md` → exactly one line, value
  `e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a`.
- Hash recomputed independently by two methods — Python `bytes.split(b'\n')` line-join up to the
  line starting `Record sha256:` (no trailing newline), and a `head -n`/`shasum` extraction dropping
  the one trailing newline byte — both agree with the recorded value, and both were re-run a second
  time after the structural fixes alone (producing the intermediate value
  `d3365a9d2ed83510a50f57367a74f444a0fc9f5d2304900be1f4487018a28360`, not recorded as the file's own
  `Record sha256:` line at any point, superseded in-session once the attestations were folded in)
  and a third time after the attestations were added, confirming the final value above.
- `grep -Ec "^Effort: (max|xhigh)$"` and `grep -Ec "^Route: (hook|fallback-agent)$"` both return
  exactly `1` (no accidental duplicate standalone lines introduced by the rewrite).
- `cmp 84-ADOPTION-CRITERIA.md evaluator-only/adoption-criteria.locked.md` → exit 0 (byte-identical;
  locked copy refreshed `chmod u+w` → copy → `chmod a-w` after the final content was in place).
- Plan 04 Task 1's exact `<verify>` command → exit 0 (Effort equality `max == max` still holds;
  D-12..D-18, `Input label:`, `Route: hook`, and the 64-hex-char `Record sha256:` line are all
  present).
- Plan 04 Task 2's exact `<verify>` command → exit 0 (`PACKET CLEAN`, `PARITY OK (route=hook)`,
  packet and driver shas still verify — this task does not read `84-ADOPTION-CRITERIA.md`'s content
  directly, so it was unaffected by the billing-section rewrite).
- Read-only source citations corrected or added this revision were independently confirmed by direct
  `Read`/`grep` of the installed model-gateway 0.51.2 plugin cache (`~/.claude/plugins/cache/
  eigenwise-toolshed/model-gateway/0.51.2/lib/`), with no gateway request, no `claude-code-proxy`
  invocation, and no `doctor`/`setup`/`login`/`status` command run: `setup`'s `ChatGPT auth: valid`
  at `commands.js` line 533 (confirmed distinct from `doctor`'s `codex auth: authenticated` at line
  1153, both reading the same `readiness.checks.codexAuth`); `login`'s proxy spawn at line 2475;
  `isAuthed()` at lines 285-287 (spawns the proxy binary with `codex auth status`, pattern-matches
  "account"); `PROXY_BIN`/`REPO` constants at lines 64/92; the module header's "owns the OAuth"
  sentence at lines 8-9; `runtime.js`'s credentials-path message at line 197; a directory listing
  (not a content read) of `~/.config/claude-code-proxy/` confirmed present with a mode-700 `codex`
  subdirectory; a `grep` of this gateway's own `lib/*.js` for `apiKey`/`api_key`/`API_KEY` returned
  no matches; `~/.claude/model-gateway/shim.pid`/`shim.pid.json` were re-read and still show PID
  `43968`, `startedAt` unchanged from revision 3's finding. The four owner attestations were recorded
  verbatim as given, in the order received, with no paraphrase or broadening, per the coordinator's
  explicit instruction; none was invented or assumed.
- No existing D-12..D-18 text, and no finding (E1-E7, N1-N5), was altered or relabelled. Every piece
  of wording this revision replaces (the "immediately before launch/after exit" sampling language,
  the "by construction" Codex billing certainty, the "exclusivity is established outright" sentence)
  is named, under "revision 4," in the rewritten "Revision history" section; the new §6 launch
  precondition and its attestation-driven resolution are recorded as additions, not as superseding
  any prior wording, since revision 3 had no equivalent gate.
- No comparison run, validation run, model request, or gateway request was started at any point
  during this revision, including while recording and applying the owner's billing attestations.
  `git status --short` (Triggarr repo root) shows no changes to `.planning/STATE.md`,
  `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`; the only modified tracked file is this
  SUMMARY.md (`84-ADOPTION-CRITERIA.md` itself is git-excluded per D-16, so it does not appear in
  `git status`).

## Self-Check (Task 3, 2026-10-26): PASSED — acknowledgment recorded, plan complete

Before recording the owner's acknowledgment:
- Re-extracted the `Record sha256:` line from `84-ADOPTION-CRITERIA.md` → exactly one match, value
  `e293d6e6ecabf24470e11e0528e0c849b8bc5cbdefea8c5651887298ffc2457a`.
- Independently recomputed the hash with Python (`bytes.split(b'\n')`, joining every line before the
  one starting `Record sha256:`, no trailing newline) → **matches exactly.**
- `cmp 84-ADOPTION-CRITERIA.md evaluator-only/adoption-criteria.locked.md` → **exit 0**
  (byte-identical); the locked copy's mode is `444` (non-writable), confirmed via `stat`.

After recording the acknowledgment:
- `.planning/phases/84-codex-plan-checker-investigation/84-CRITERIA-ACK.md` created (FOUND via
  direct read-back) with the acknowledged hash, UTC timestamp `2026-10-26T19:41:58Z`, the owner's
  verbatim word "acknowledged," the two accepted judgment calls, and the three cosmetic issues left
  unedited by owner choice.
- `git status --short` on the Triggarr repo root shows no entry for `84-CRITERIA-ACK.md` (confirmed
  git-excluded via the pre-existing `.git/info/exclude` `.planning/` pattern) — it will not be
  force-added or committed, per the continuation's explicit instruction.
- `84-ADOPTION-CRITERIA.md` was not modified (confirmed: its own `Record sha256:` line is unchanged
  from the value acknowledged, and the file was not opened with Edit/Write at any point in this
  session).

Task 1's exact `<verify>` command → re-run, **exit 0**.
Task 2's exact `<verify>` command → re-run, **exit 0** (`PACKET CLEAN`, `PARITY OK (route=hook)`,
packet/driver shas and parity self-tests still passing; the `CONTAMINATION`/`FORBIDDEN-NAME` lines
printed mid-run are the scripts' own expected negative-path self-test output, not failures).
Task 3's exact `<verify>` command → re-run verbatim as written in the plan, **exit 1** (the first
clause, `grep -q "Owner acknowledgment" 84-ADOPTION-CRITERIA.md`, finds no match because that text
was never added to the file, per the explicit continuation instruction documented in Deviation 4
above; the remainder of the compound command never executes due to the shell's `&&` short-circuit).
This exit-1 result is reported here exactly as observed — it is not reinterpreted as a pass, and the
acknowledgment's own validity does not depend on this specific command succeeding.

No run, model request, or gateway request was started at any point while performing this Task 3
closeout. `git status --short` (Triggarr repo root) shows no changes to `.planning/STATE.md`,
`.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md` — neither was touched by this plan, per the
continuation's explicit instruction; the only tracked-file change this plan makes is this
SUMMARY.md, about to be force-added and committed on its own.
