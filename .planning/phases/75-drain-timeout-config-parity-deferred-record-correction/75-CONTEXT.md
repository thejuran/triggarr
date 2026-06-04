# Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring the settings UI to full config-knob parity by exposing the graceful-shutdown
drain timeout (`shutdown_drain_timeout`) as a persisted config field with a settings-UI
numeric input and documented env-override precedence, AND correct the stale deferred
record so it matches shipped reality (DEBT-07/08/03 already shipped; DEBT-06 now shipped).

Requirements: CFG-03, CFG-04, DOCS-01.

In scope: the `shutdown_drain_timeout` config field, its settings-UI input + help text,
the POST-handler parse/persist wiring, the scheduler refactor that reads the configured
value at shutdown time (env override on top), and the DOCS-01 record correction across
the four documentation surfaces. Out of scope: any new shutdown behavior beyond honoring
a configurable timeout; Tracks A and B (already shipped this milestone, disjoint code).
</domain>

<decisions>
## Implementation Decisions

> **Finite-only contract (adversarial-pass correction, 2026-06-03):** D-01, D-03, D-04,
> and D-06 below carry the FINITE-ONLY contract added after the codex adversarial pass.
> `float()` parses `"nan"`/`"inf"`/`"-inf"` WITHOUT raising, and a non-finite value SURVIVES
> a `max(value, 1.0)` clamp (`max(nan, 1.0) == nan`, `max(inf, 1.0) == inf`). Without an
> explicit finite guard, an `inf` would mean `asyncio.timeout(inf)` never bounds the drain
> (waits until SIGKILL — drain effectively disabled) and a `nan` would time out immediately
> (drain effectively disabled) — closing the "nan/inf disables the drain" vector the
> adversarial pass found. Every surface that produces a drain value is therefore finite-only.

### Config field (CFG-03)
- **D-01:** Add `shutdown_drain_timeout: float = Field(default=60.0, ge=1.0, allow_inf_nan=False)`
  to `GeneralConfig` in `triggarr/models/config.py`, mirroring the bounded-field pattern of
  `max_consecutive_failures: int = Field(default=5, ge=1, le=100)` (config.py:134). The
  `ge=1.0` bound defends against a typo (e.g. `0`) disabling the drain — same defensive
  intent as the existing bounded knobs. `allow_inf_nan=False` rejects a non-finite
  (inf/nan/-inf) config/TOML value at construction: confirmed in the project venv that
  `Field(ge=1.0)` ALONE accepts `+inf` (Pydantic v2 default `allow_inf_nan=True`; `ge=1.0`
  rejects `nan` but NOT `inf`), so `allow_inf_nan=False` is load-bearing — it closes the
  "a TOML/config inf disables the drain" vector. No upper bound on the model field itself;
  the form-parse clamp (D-03) supplies a practical UI ceiling.

### Settings-UI input + parse/persist (CFG-03, CFG-04)
- **D-02:** Add a numeric input to `triggarr/templates/settings.html` mirroring the
  existing `request_timeout` / `page_size` / `max_consecutive_failures` inputs
  (settings.html:46-74). Render its current value via a `{{ shutdown_drain_timeout }}`
  context var, populated in the GET handler's render dict alongside the sibling fields
  (routes.py:438-446) and the settings render at routes.py:319-style block.
- **D-03 (parse helper — discussed):** Add a `safe_float(value, default, minimum, maximum)
  -> float` helper to `triggarr/web/validation.py`, mirroring `safe_int`'s signature and
  clamp semantics (validation.py:179), and parse the drain timeout with it:
  `safe_float(form.get("shutdown_drain_timeout"), 60.0, 1.0, 3600.0)` in the settings POST
  handler (routes.py:542-548 block). Rationale: the field is a genuine `float`; `safe_int`
  would truncate (the existing `request_timeout` float field is parsed via `safe_int` —
  a wrinkle we are NOT propagating to a brand-new float knob). One small, tested helper
  preserves honest float semantics (e.g. accepts `1.5`). The `3600.0` UI ceiling is a
  practical clamp, not a model constraint. **Finite-only:** after coercion `safe_float`
  guards `math.isfinite(n)` BEFORE clamping and returns `default` for a non-finite value
  (`"nan"`/`"inf"`/`"-inf"`) exactly as it does for a malformed string — because `float("nan")`
  parses without raising and `max(nan, 1.0) == nan` means the clamp does NOT neutralize it.
  So the helper returns a finite, bounded value or the default; it never returns nan/inf.

### Scheduler wiring + precedence (CFG-04 — the one real decision)
- **D-04 (wiring approach — discussed):** Local-resolve at shutdown start. Refactor
  `_read_shutdown_drain_timeout` in `triggarr/search/scheduler.py` (currently scheduler.py:58)
  to accept the configured default and apply the env override on top:
  `def _read_shutdown_drain_timeout(configured: float = 60.0) -> float:` — read
  `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT`; if unset, use `configured`; if set, the env value
  wins (coerce, falling back to `configured` on malformed input). **Finite-only:** BEFORE
  the `>=1.0` clamp, guard the resolved value with `math.isfinite` — a non-finite resolved
  value (env `nan`/`inf`/`-inf`, OR a non-finite `configured` value) is treated as malformed
  and falls back to a finite default (`configured` if finite, else 60.0). Then return
  `max(value, 1.0)` so the `>=1.0` clamp applies to BOTH sources. The helper NEVER returns
  nan/inf, so `asyncio.timeout(drain)` always receives a finite bound. (75-01's
  `allow_inf_nan=False` already makes a non-finite CONFIGURED value unreachable from the
  model; the helper guards it anyway as defense in depth, since it is the single choke point
  that feeds `asyncio.timeout` and is also called directly in tests.)
- **D-05:** At the top of the shutdown-drain block (scheduler.py:~605), compute one local:
  `drain = _read_shutdown_drain_timeout(app.state.settings.general.shutdown_drain_timeout)`.
  Replace ALL ~6 references to the module constant `_SHUTDOWN_DRAIN_TIMEOUT` in the shutdown
  path (scheduler.py:611, 618, 634, 648, 656 + the logging sites) with this local. The
  module-level `_SHUTDOWN_DRAIN_TIMEOUT = _read_shutdown_drain_timeout()` import-time
  constant (scheduler.py:81) is RETAINED as a no-arg call (env-unset → 60.0) so the two
  existing constant tests stay green for free; the shutdown PATH simply no longer references
  it. This removes the import-time-staleness footgun: the configured value is read from
  `app.state.settings` at shutdown time, where settings is already in scope (the block
  already reads `app.state.search_lock_holder` / `app.state.search_lock`).
- **D-06:** Precedence is **config default, env overrides** (12-factor: an explicit env
  override beats a persisted file). This PRESERVES the documented env knob for ops who
  already set `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` — no silent behavior change for existing
  deployments — and adds the UI path for everyone else. The `>=1.0` clamp applies to BOTH
  sources, and the **finite guard** (D-04) applies to the resolved value from either source:
  a non-finite env value (`nan`/`inf`/`-inf`) OR a non-finite configured value falls back to
  a finite default before clamping, so neither precedence source can disable or unbound the
  drain. A malformed (non-float) env value falls back to the configured default.

### DOCS-01 record correction (all four surfaces — discussed)
- **D-07:** Correct the **STATE.md deferred table** (`.planning/STATE.md`): DEBT-07
  (request timeout), DEBT-08 (page size), DEBT-03 (search-history cap) were mis-recorded as
  parked but are already shipped as both config fields (config.py:128-130) AND settings
  inputs; DEBT-06 (drain timeout) is now shipped here. (Note: GSD's complete-milestone may
  rewrite STATE.md at archive; the durable record is the roadmap/milestone audit, so treat
  this as in-flight bookkeeping correctness.)
- **D-08:** Update **README / settings docs**. README already documents the env var
  (README.md:86, 95, 140) — add the new config-field / settings-UI path and the
  config-default-vs-env-override precedence note. Do not remove the existing
  `stop_grace_period > drain` deployment guidance.
- **D-09:** Add an **in-app changelog entry** to `CHANGELOG.md` (repo root — the source
  `read_changelog()` renders into the in-app changelog modal, triggered by the
  `changelog-badge` in base.html:31). Entry covers the drain-timeout knob; per spec §5,
  the v2.10 entry also covers the password-recovery flow (Track A) and Refresh-counts
  (Track B) shipped this milestone.
- **D-10:** Add **field help text** to the settings.html drain-timeout input documenting
  the precedence (config value is the default; `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` overrides
  it when set; `>=1.0` enforced). Spec §4.2/§4.3 require this — it is the most-seen doc
  surface.

### Claude's Discretion
- Exact `safe_float` clamp ceiling beyond the agreed `3600.0` UI bound, and whether the
  helper coerces `int`-like strings (it should, via `float()`).
- Whether `_SHUTDOWN_DRAIN_TIMEOUT` module constant is deleted outright or kept as an
  unreferenced default constant (functional requirement: shutdown path reads config, not
  import-time state). NOTE: the revised plans RETAIN it as a no-arg call so the two existing
  constant tests (`test_shutdown_timeout_default_is_60s`, `test_shutdown_timeout_env_var_override`)
  stay green for free — recommended (cheaper).
- Exact CHANGELOG.md section wording and ordering; exact settings.html input placement
  among the General fields.
- Test file organization (extend existing scheduler/config/routes test modules vs. new file).

</decisions>

<specifics>
## Specific Ideas

- Mirror `max_consecutive_failures` for the bounded config field; mirror `request_timeout`
  for the settings.html numeric input markup; mirror the `safe_int` form-parse pattern but
  via the new `safe_float`.
- The env-override precedence is the single substantive design decision — the spec calls it
  out as "the one real decision" (§4.3).
- DOCS-01 is a record-correction, not new feature work: DEBT-07/08/03 are demonstrably
  already shipped (config.py:128-130 + settings.html inputs), so the deferred table is
  factually wrong and must be corrected to match reality.
- Finite-only hardening (adversarial pass): every drain-value-producing surface
  (`GeneralConfig.shutdown_drain_timeout` field, `safe_float`, `_read_shutdown_drain_timeout`)
  rejects non-finite input so `asyncio.timeout` is always given a finite bound.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design spec (source of truth — read first)
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §4 (Track C —
  DEBT-06 Drain-Timeout Settings Knob): §4.1 problem, §4.2 design, §4.3 precedence (the one
  real decision), §4.4 tests. Also §5 (Cross-Track Close — docs deliverable + walkthrough),
  §7 (all decisions resolved; "DEBT-06 precedence: config default, env overrides ✅").

### Planning state
- `.planning/STATE.md` — milestone v2.10 shape, v2.10 phasing rationale (Track C is one
  small phase 75), and the Deferred Items table that D-07 corrects.
- `.planning/ROADMAP.md` Phase 75 — goal, success criteria (3 criteria), requirements
  (CFG-03, CFG-04, DOCS-01).

### Codebase integration points (full paths)
- `triggarr/models/config.py` §`GeneralConfig` (config.py:122-136) — where D-01 adds the
  field; pattern anchor `max_consecutive_failures` (config.py:134).
- `triggarr/search/scheduler.py` — `_read_shutdown_drain_timeout` (scheduler.py:58-75),
  module constant `_SHUTDOWN_DRAIN_TIMEOUT` (scheduler.py:81), shutdown-drain usage sites
  (scheduler.py:611, 618, 634, 648, 656 + logging). D-04/D-05 refactor target.
- `triggarr/templates/settings.html` (settings.html:46-74) — existing numeric inputs to
  mirror for D-02/D-10.
- `triggarr/web/routes.py` — settings GET render dict (routes.py:438-446), settings POST
  parse/persist (routes.py:542-548). D-02/D-03 wiring target.
- `triggarr/web/validation.py` — `safe_int` (validation.py:179) is the pattern for the new
  `safe_float` (D-03).
- `CHANGELOG.md` (repo root) — in-app changelog source via `triggarr/changelog.py`
  `read_changelog()` (changelog.py:32, 40); rendered into base.html changelog modal
  (base.html:102-108). D-09 target.
- `README.md` (README.md:86, 95, 140) — existing drain/env docs to extend for D-08.

No external (non-repo) specs — all requirements captured in the design spec and decisions above.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `safe_int(value, default, minimum, maximum)` (validation.py:179) — direct template for
  the new `safe_float` helper (same signature shape, same clamp idiom; `safe_float` ADDS a
  `math.isfinite` guard before the clamp).
- `max_consecutive_failures: int = Field(default=5, ge=1, le=100)` (config.py:134) —
  bounded-field pattern to mirror for `shutdown_drain_timeout` (the new field ADDS
  `allow_inf_nan=False`).
- settings.html numeric inputs `request_timeout` / `page_size` / `max_consecutive_failures`
  (settings.html:46-74) — markup template for the new input.
- `_read_shutdown_drain_timeout()` (scheduler.py:58) already encapsulates env-read +
  clamp; refactor it to accept a `configured` default rather than rewrite from scratch, and
  add the `math.isfinite` finite guard before the clamp.
- `read_changelog()` + `CHANGELOG.md` + base.html changelog modal — existing in-app
  changelog plumbing; D-09 is just a new CHANGELOG.md section, no code change.

### Established Patterns
- Settings round-trip: GET render dict → settings.html `{{ var }}` → POST `safe_*` parse →
  atomic TOML persist (write-then-rename) → reload on next view. Drain timeout joins this
  flow identically to the sibling `general.*` fields.
- Shutdown drain already reads `app.state.*` at shutdown time (lock holder, lock), so
  reading `app.state.settings.general.shutdown_drain_timeout` there is consistent — no new
  state-access pattern introduced.
- `asyncio.timeout()` (Python 3.11+) is the established drain primitive (WR-01,
  scheduler.py:634); D-05 only swaps the timeout VALUE source, not the mechanism. The
  finite-only contract guarantees the swapped-in value is always a finite bound.

### Integration Points
- Config model ↔ settings GET render ↔ settings.html input ↔ settings POST parse ↔ TOML
  persist (the standard config-knob loop).
- Scheduler shutdown block ↔ `app.state.settings.general.shutdown_drain_timeout` ↔
  `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env override (the precedence wiring, D-04/D-05/D-06).
- DOCS-01 touches non-code artifacts (STATE.md, README.md, CHANGELOG.md) + one code
  surface (settings.html help text).
</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Tracks A and B are already shipped this
milestone; the milestone-end NAS walkthrough exercising all three tracks is the
orchestrator's milestone-end step, not this phase's work.)
</deferred>

---

*Phase: 75-drain-timeout-config-parity-deferred-record-correction*
*Context gathered: 2026-06-03*
