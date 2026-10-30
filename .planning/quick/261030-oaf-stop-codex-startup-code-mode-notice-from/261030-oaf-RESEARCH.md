# Quick Task 261030-oaf: Stop Codex startup code-mode notice from failing the untrusted-path event audit - Research

**Researched:** 2026-10-30
**Domain:** Codex CLI 0.153.4 feature flags and model metadata; `tests/codex_review_run.py` inspection-only argv
**Confidence:** HIGH (all key claims were reproduced against the pinned image in this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- The event audit (`audit_event_types` / `_new_disallowed_item`, ALLOWED_ITEM_TYPES / ALLOWED_EVENT_TYPES) MUST stay unchanged and fail-closed. No allowlisting of `error` items, and no exception for this notice text.
- Owner chose "Stop and ask": ship only the feature switch-off. If a local check shows the notice is still emitted with `code_mode` disabled, STOP and report to the owner — do not loosen the audit.

### Claude's Discretion
- Which exact `code_mode_*` flags to add (verify each name exists in the image's `codex features list`; `--strict-config` must still accept the argv).
- Whether the trusted-path argv gets the same flags (only if it shares DISABLED_FEATURES or it is free and consistent).
- Test shape, following the existing tests for DISABLED_FEATURES / audit_event_types.

### Deferred Ideas (OUT OF SCOPE)
- None listed.
</user_constraints>

## Summary — STOP CONDITION ALREADY MET

**Turning off `code_mode` does not stop the notice.** I checked this locally against the pinned image (`triggarr-codex-review:0.153.4`, id `sha256:59480ac5c502…`, codex-cli 0.153.4). I ran it with `--network none`, a fresh empty `CODEX_HOME`, no sign-in, and the runner's exact flags (`--sandbox read-only --ephemeral --skip-git-repo-check --ignore-user-config --ignore-rules --strict-config`). Codex emits the notice right after `thread.started`, before any network contact. So this offline check is a faithful reproduction of the live startup item [VERIFIED: local docker run]:

| Flags added | Notice emitted? |
|---|---|
| none | yes ("failed to spawn code-mode host … not found") |
| `--disable code_mode_host` (current runner) | yes ("code-mode host is disabled", the exact live text) |
| `--disable code_mode` | yes |
| `--disable code_mode --disable code_mode_host` | yes |
| all of `code_mode`, `code_mode_only`, `code_mode_interrupt`, `code_mode_prewarm`, `code_mode_host` | yes |
| `--disable code_mode_host -m gpt-6-astra` | yes |
| **`--disable code_mode_host -m gpt-5.5`** | **no** |
| **`--disable code_mode_host --disable code_mode -m gpt-5.5`** | **no** |

**Root cause (corrects the CONTEXT/evidence hypothesis):** code mode is not being switched on for the account from outside the image. The model's own metadata switches it on. The Codex binary ships with a built-in model catalog. In that catalog the default model `gpt-6-astra` (priority 1, the model the host check reported) and `gpt-5.6-sol/-terra/-luna` are marked `"tool_mode": "code_mode_only"`. `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini` and `gpt-5.2` are marked `"tool_mode": null` [VERIFIED: strings of /usr/local/bin/codex in the image]. Codex therefore tries to start code mode no matter what the `features.*` flags say. With the host disabled or missing, it then emits the fail-closed `error` item. `tool_mode` cannot be set as a config key: `-c tool_mode=…`, `-c tool_exposure=…` and `-c mcp_tool_exposure=…` are all rejected under `--strict-config` with "unknown configuration field" [VERIFIED].

Under the owner's locked "Stop and ask" rule, the planner should **not** ship the `--disable code_mode` change as the fix. The orchestrator should bring the following decision to the owner. The only lever found that removes the notice is choosing a model for the review container:

- **Option A (recommended to present):** pin `-m gpt-5.5` (a model with no code-mode marking) in `inspection_codex_argv()`. Effect: untrusted (Dependabot) reviews would run on an older model than the trusted path, which uses the host default `gpt-6-astra`. The audit stays unchanged. Risks: (1) a possible drop in review quality on dependency-bump diffs; (2) the pin needs revisiting each Codex bump; (3) the account's access to `gpt-5.5` through the signed-in path is unproven until a live run.
- **Option B:** keep things as they are. Every untrusted review ends INCOMPLETE, and the owner falls back to vibe-check.
- **Not viable:** (1) allowlisting `error`, which the owner forbade; (2) enabling `code_mode_host` and installing the host binary in the image, which widens the tool surface of an inspection-only review.

Disabling `code_mode` remains harmless defense in depth. It is a valid feature name and `--strict-config` accepts it. But it is not a fix, and adding it alone would leave the next live run INCOMPLETE for the same reason.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Inner Codex argv (flags/model) | Review harness (`inspection_codex_argv`) | Static gate in `verify_isolation_boundary` | Single argv builder; the boundary gate only checks a DISABLED_FEATURES subset and the schema path |
| Event audit | `audit_event_types` / `_new_disallowed_item` | `_probe_tool_use_reasons` (shares the classifier) | Locked, unchanged |
| Code-mode activation | Codex model metadata (in the binary) | `features.*` flags (cannot override it) | Proven by the table above |

## Findings by Question

### 1. DISABLED_FEATURES and its consumers [VERIFIED: codebase grep]
- Defined at `tests/codex_review_run.py:1420` (22 entries; `code_mode_host` at :1423).
- Only `inspection_codex_argv()` (:1467–1492) puts it on the command line (`--disable <f>` loop at :1489–1490). Both the untrusted review and the `--verify-boundary` probe (`verify_boundary_main` → `inspection_codex_argv()` at ~:4204) use it.
- `verify_isolation_boundary` (:1673–1675) statically requires that `set(DISABLED_FEATURES) ⊆ --disable values`. Adding entries keeps this consistent automatically. Adding `-m` does not affect it.
- **The trusted path does not share it.** `codex_argv()` (:505–521) passes no `--disable` and no `--ignore-user-config`, and uses the host's user config and default model. Leave it unchanged.
- Tests that pin it (`tests/test_codex_review_inspection.py`):
  - `REQUIRED_DISABLED_FEATURES` frozenset (:1008–1033) plus `test_disabled_features_cover_the_required_set_with_no_duplicates` (:1040–1045) assert exact **set equality**. Any new entry must be added there too.
  - `test_inspection_codex_argv_golden` (:1048–1068) asserts the **exact argv list**. A `-m` pin must be inserted there in the same position.
- Docs: `85.1-UNTRUSTED-BOUNDARY.md:55` lists "22 entries" by name. Update the count and list if entries change, and record a model pin there if adopted. `docs/`, `.github/` and `docker/codex-review/Dockerfile` contain no `code_mode` references. The contract doc does not list features. Changing the runner does not change the Dockerfile, so the image's dockerfile-sha256 label check is unaffected (no rebuild needed).

### 2. code_mode* features in the pinned image [VERIFIED: `codex features list` in image, `--network none`]
```
code_mode                 under development  false
code_mode_buffered_exec   removed            false
code_mode_host            stable             true
code_mode_interrupt       under development  false
code_mode_only            under development  false
code_mode_prewarm         under development  false
```
- `codex --disable code_mode features list` → exit 0. An unknown name (`code_mode_bogus_xyz`) → `Error: Unknown feature flag`, exit 1. Unknown names are rejected even without `--strict-config`.
- `codex exec --strict-config … --disable code_mode_host --disable code_mode … -` is accepted: it reaches `thread.started`/`turn.started`. `--strict-config` cannot be combined with `codex features` ("not supported for `codex features`"), so validate with `codex exec`, not `features list`.
- `code_mode_buffered_exec` is "removed" but still accepted; do not add it.

### 3. Recorded streams [VERIFIED: grep]
- 36 `*.jsonl` files exist under `.planning/`. **Only one** contains the notice: `16a719d720b3-untrusted-e2e-a1.jsonl`. All 11 trusted-path streams in the 85.1 `codex/` folder have **0** notices. The evidence note's claim that "the same notice appears in every trusted-path Codex stream recorded in this phase" does not hold for the recorded streams. The trusted streams also don't show `--disable` (their argv has none). The `.meta.json` files do not record argv or model.
- Related: live boundary **run 3**'s probe `error` event (stderr `error=code-mode host is disabled`) was attributed to "a blocked tool attempt". It is very likely this same startup notice. That means the premise of the backlog item "Probe scoring for `--verify-boundary --with-probes`" in `.planning/backlog/MAINTENANCE.md` is probably mistaken [ASSUMED: inferred from the identical text and timing; the run-3 probe transcript was deleted with its scratch dir].

### 4. Safe pre-merge proof
- **Credential-free proof (sufficient for the notice itself, because it is emitted before any network or sign-in):** run the exact new inner argv, offline, in the pinned image. Example for Option A (prints the event types; there must be no `"type":"error"` item):
  ```bash
  docker run --rm --network none -e CODEX_HOME=/tmp/ch --entrypoint sh triggarr-codex-review:0.153.4 -c \
   'mkdir -p /tmp/ch /tmp/w && echo hi | timeout 6 codex exec --sandbox read-only --ephemeral --skip-git-repo-check \
    --ignore-user-config --ignore-rules --strict-config -C /tmp/w <every --disable from DISABLED_FEATURES> -m gpt-5.5 \
    --json -o /tmp/l.json - 2>/dev/null'
  ```
  The executor should generate the flags from `inspection_codex_argv(cwd="/tmp/w", last_json="/tmp/l.json")` without its `--output-schema` pair (the schema is not mounted). It should not hand-type them. Expected: `thread.started`, `turn.started`, then exit 124 (no network), and no `item.completed` of type `error`.
- **Signed-in proof via existing machinery:** `uv run python tests/codex_review_run.py --verify-boundary --with-probes`. It uses `inspection_codex_argv()`, mounts the copied sign-in, and audits with the shared `_new_disallowed_item`. It does not require main HEAD (only live `--untrusted` runs refuse non-main). Caveats: (1) the probe prompt deliberately asks Codex to run scripts, so other `error` events can confound it; (2) it reports only "probe produced an unexpected event: error" without the message, and its transcript is deleted. A clean probe result is good corroboration (and it proves the account can use the pinned model), but a dirty one is ambiguous. It also needs a fresh image with the dockerfile label and the owner's authorization for a live run. Do not run it without that.
- The real proof remains the post-merge live run on a qualifying Dependabot PR (D-03).

### 5. Pitfalls
1. **Assuming the feature flag controls code mode.** It does not in 0.153.4; model metadata does. Verify with the offline matrix above, not with `features list`.
2. **Unknown feature names hard-fail** (`Unknown feature flag`, exit 1) whether or not `--strict-config` is set. Only add names present in the image list.
3. **Exact-set and golden-argv tests:** `REQUIRED_DISABLED_FEATURES` (set equality) and `test_inspection_codex_argv_golden` (exact list) must be updated in the same commit.
4. **Model pin drift:** a pinned slug can be removed in a future Codex bump, or flipped to `code_mode_only`. Recommend a test that pins the slug, plus a note next to the Codex version pin to recheck `tool_mode` on every bump.
5. **Regression pin for the audit:** add a test that feeds the recorded `error` item (verbatim from `16a719d720b3-untrusted-e2e-a1.jsonl` line 2) to `audit_event_types` and asserts `["inspection-only review used a tool: error"]`. This proves the audit was not loosened.
6. **"Extending this tuple is a sensitive review-machinery change"** (comment at :1418–1419). Any DISABLED_FEATURES or argv change goes through BM review plus the paired Codex pass. Classify it upward.

## Environment Availability

| Dependency | Available | Version |
|---|---|---|
| docker | yes | image `triggarr-codex-review:0.153.4` present (`59480ac5c502`) |
| codex in image | yes | 0.153.4 |
| uv / pytest | yes | the two pinning tests pass on the current tree |

No packages to install; package legitimacy audit not applicable.

## Validation Architecture
- Quick: `uv run pytest tests/test_codex_review_inspection.py -q -k "disabled_features or argv_golden or audit"`
- Full: `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/`
- New tests: golden argv including any model pin; the recorded `error` stream still fails the audit; DISABLED_FEATURES set (if changed).

## Security Domain
- Applies to V5 (input validation: the event-stream audit) and least privilege (tool surface). The fix must not widen the tool surface: no `code_mode_host` enable, no host binary. It must also not loosen ALLOWED_ITEM_TYPES. A model pin does not change the container boundary.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | The run-3 probe `error` was the same startup notice, not a blocked tool attempt | Q3 | The MAINTENANCE.md probe-scoring backlog item rests on a misdiagnosis |
| A2 | The signed-in account can use `gpt-5.5` from the container, and remote model metadata (`remote_models`) does not re-mark it `code_mode_only` online | Summary / Q4 | Option A still fails live; needs the `--with-probes` or post-merge confirmation |
| A3 | Review quality on `gpt-5.5` is acceptable for dependency-bump inspection | Summary | A product decision for the owner |

## Sources
- Local: `docker run … triggarr-codex-review:0.153.4` feature list, `--disable` acceptance and the offline notice matrix (2026-10-30)
- Local: model catalog strings in the image's `/usr/local/bin/codex` (`slug` → `tool_mode`), and the binary message "does not advertise Code Mode support … Disable `features.code_mode` and `features.code_mode_only`, or select a model whose metadata enables Code Mode"
- Codebase: `tests/codex_review_run.py` :505, :1420, :1467, :1494, :1530, :1673, :2014–2130, :4179; `tests/test_codex_review_inspection.py` :1008–1068; `85.1-UNTRUSTED-BOUNDARY.md` :55, :360–460; `85.1-REVIEW-EVIDENCE.md` :650–677; `.planning/backlog/MAINTENANCE.md` :13

**Valid until:** the next Codex version bump of the review image.
