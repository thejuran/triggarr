# Phase 76 — Adversarial Review Notes (codex)

> Audit trail of the orchestrator's codex adversarial-review pass over the plans.
> Rewrite 1/2 triggered by 2 high "No-ship" findings, both verified against live code.

## Round 1 — verdict: needs-attention (2 high, 2 medium)

### [HIGH-1] Stale cursor keys persist despite the "no-migration / overwritten on next save" claim — VERIFIED TRUE

QUEUE-03 / D-09 claimed leftover `missing_cursor`/`cutoff_cursor` keys in a pre-upgrade
`state.json` are harmless and overwritten on the next save. **False against the live merge.**

`state.py:143` — `_merge_defaults` does `{**_default_instance_state(), **instance_data}`.
`{**defaults, **loaded}` PRESERVES every key in `instance_data`, including unknown ones. So a
pre-upgrade instance dict carrying `missing_cursor: N` keeps that key in memory, and
`save_state` (`state.py:206`, `json.dump(state, ...)`) writes the whole dict back — stale
cursor keys included. They persist indefinitely; they are NOT overwritten away. The planned
back-compat test only asserts `missing_searched == []` + `missing_pass` survives, so it passes
while the stale keys live on.

**Fix:** strip `missing_cursor`/`cutoff_cursor` during load/merge (explicit one-time cleanup in
`_merge_defaults` or `load_state`), and add a pre-upgrade load→save round-trip test asserting
those keys are ABSENT from the saved state. Update QUEUE-03/D-09 plan language to describe an
active strip-on-load, not a passive "overwritten" claim.

### [HIGH-2] Plan 01 creates a broken runtime checkpoint before callers are rewired — VERIFIED TRUE

Plan 01 removes cursor fields from `_default_instance_state()` while leaving all six cycle call
sites reading `ist["missing_cursor"]` / `ist["cutoff_cursor"]` until Plan 02. Per-plan commits
mean a new/default instance running a search cycle AFTER Plan 01 but BEFORE Plan 02 would raise
`KeyError` (the scheduler intentionally does not swallow code-bug KeyErrors). Plan 01's
verification only runs the new prioritize/state tests, so the broken checkpoint can be marked
complete.

**Fix:** make every plan checkpoint runtime-safe. Either (a) keep cursor defaults in
`_default_instance_state()` until the call-site rewrite lands (move the field REMOVAL to the
same plan that rewires the 6 sites), or (b) collapse the state field-swap + 6 call-site rewires
into one non-breaking plan. At minimum Plan 01 must run the existing cycle tests if it changes
default runtime state.

### [MED-1] Pass-completion can fire on a zero-search batch

`pass_completed` is computed from eligible-coverage after pruning, guarding only the empty
eligible list — not an empty BATCH. With `batch_size == 0` (reachable via `hard_max`
proportional capping) and a pruned log already covering a now-tiny eligible set,
`prioritize_batch` can return `batch=[]` AND `pass_completed=True`; Plan 02 would then clear the
log + bump `*_pass` with zero searches. The OLD wrap logic required `and batch` (engine.py wrap
guard), so it never emitted zero-search pass events.

**Fix:** add pure + cycle tests for `batch_size <= 0` / zero-cap queues after prune; require
either `bool(batch)` in the pass-completion condition OR an explicit, documented+tested decision
that zero-search pass resets are intended. (Recommend requiring `batch` — match old behavior.)

### [MED-2] Sonarr composite-key correctness not proven at the real call sites

Plan 01 tests a standalone Sonarr key lambda; that doesn't prove `run_sonarr_cycle` wires BOTH
queues (missing + cutoff) correctly. Plan 02 leans on grep/read for the composite string and
only requires integration extensions for Radarr + one of Sonarr/Lidarr. A wrong key in either
Sonarr queue could collide same-series seasons or mishandle Specials while the pure unit test
still passes.

**Fix:** require integration tests through `run_sonarr_cycle` for BOTH missing and cutoff with
same-series seasons including season 0, batch smaller than eligible count, asserting exact
`missing_searched`/`cutoff_searched` keys (`"123:0"`, `"123:1"`, `"123:2"`).

## Disposition

All four findings accepted. Rewrite 1/2 dispatched to `/gsd:plan-phase 76` with this critique
embedded. The two high findings are blocker-class (codex "No-ship") and gate execution.

## Round 2 — verdict: needs-attention (1 high + 1 medium, both NEW, introduced by the round-1 fixes)

codex confirmed the round-1 high/medium findings are RESOLVED against live code. Two new issues
from the revision:

### [HIGH-3] Plan 03 static guard would delete the tests that prove HIGH-1 — VERIFIED TRUE, FIXED
Plan 02 requires test_state.py to KEEP a pre-upgrade fixture writing missing_cursor/cutoff_cursor +
a load→save test asserting they're stripped. Plan 03's guard `! grep -rqE "missing_cursor|cutoff_cursor" tests/`
forbids those keys anywhere in tests/ — so a compliant executor would delete the very regression test
that keeps HIGH-1 fixed. **Fix applied directly:** scoped the Plan 03 cursor guard to EXCLUDE
tests/test_state.py, and added a companion gate requiring `grep -qE "missing_cursor" tests/test_state.py`
to HIT (the safety net must remain present). Updated truths, verify block, acceptance criteria,
verification, threat model T-76-08, and success criteria.

### [MED-3] PATTERNS.md still encoded the rejected round-1 assumption — VERIFIED TRUE, FIXED
76-PATTERNS.md:192-193 still said leftover cursor keys are "harmless and overwritten on next save" and
"Touch nothing in _merge_defaults" — contradicting the revised Plan 02 strip-pop, and PATTERNS.md is in
the plans' read_first. **Fix applied directly:** corrected that section to describe the active strip-on-load
(`merged.pop(...)`) and the load→save absence test, explicitly marking it as superseding the round-1 assumption.

## Disposition (round 2)
Both fixed directly (surgical doc/guard edits, no structural replan). This was rewrite 2/2.
Re-running codex (round 3) to confirm.

## Round 3 — verdict: needs-attention (1 high — incomplete propagation of the HIGH-1 correction)

codex confirmed the round-2 Plan-03 guard scoping is correct, but found the HIGH-1 correction was
only applied to ONE PATTERNS.md section — the same rejected "harmless/overwritten on next save"
guidance still lived in 6 other read_first/source-of-truth spots an executor would follow:
PATTERNS.md:255 + :312, RESEARCH.md:64/227/233/386, VALIDATION.md:69, plus VALIDATION.md:34's
unscoped `! grep _cursor` guard (conflicts with the v2.2-detector + _merge_defaults pop exceptions).

### [HIGH-4] Stale passive-overwrite guidance across read_first corpus — VERIFIED TRUE, FIXED
**Fix applied directly (rewrite 2/2 already consumed — this is a mechanical propagation of the
already-decided HIGH-1 correction, not new design):** updated all 7 spots to the active
strip-on-load design (`_merge_defaults` pops the legacy cursor keys; load→save test asserts
absence) and replaced VALIDATION.md's unscoped `_cursor` guard with the same scoped exception
model used in Plan 03 (state.py v2.2-detector + _merge_defaults pop allowed; tests/test_state.py
excluded + required to retain the regression). Verified by grep: no "overwritten/harmless/touch
nothing" guidance survives except inside explicit "this was WRONG, here is the correction" text;
no unscoped cursor guard remains.

## Disposition (round 3)
Fix applied directly — mechanical doc-sync of the HIGH-1 correction codex already validated in
round 2, no new design decision. Rewrite cap (2/2) is reached, so per the orchestrator contract
this is a user-pause point. Re-running codex once more to confirm the propagation is complete
before surfacing the decision.
