# Phase 84: Codex Plan-Checker Investigation - Pattern Map

**Mapped:** 2026-10-23
**Files analyzed:** 14 (4 in-repo phase-dir evidence artifacts; 6 scratch-pilot artifacts outside the repo; 4 supporting fixtures/harness pieces)
**Analogs found:** 9 / 14 (strong or partial); 5 have no in-repo analog (flagged below, with the RESEARCH.md-cited external spec as the only available reference)

## Scope note

This phase ships **no Triggarr application code**. "Files" below are (a) evidence-record markdown/JSON inside the git-excluded phase directory `.planning/phases/84-codex-plan-checker-investigation/`, and (b) artifacts for the scratch pilot at `~/scratch/planchk-pilot/` — **outside this repo**, per D-06. Per CONTEXT.md's "Claude's Discretion," exact scratch file names/layout are the planner's/executor's call; the file list below follows RESEARCH.md's concrete skeleton and the blueprint's packet/evidence requirements as the most probable shape, and the planner should treat names as illustrative, not locked.

All analogs below come from this repository's own Phase 83 tooling (`tests/codex_review_run.py`, `tests/codex_report_status.py`, `docs/codex-adversarial-review-contract.md`, `docs/review-checkpoint-record.md`, `.planning/phases/83-.../83-REVIEW-EVIDENCE.md`, `83-DEMONSTRATIONS.md`) — exactly the precedent `84-CONTEXT.md`'s "Established Patterns" and "Don't Hand-Roll" sections point to.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `84-RUNTIME-VERDICT.md` (in-repo, PLANCHK-01) | config/evidence record | batch (one-shot verification write) | `84-RESEARCH.md` §"Runtime support for `agent.spawn`" (this phase's own research doc) + `83-REVIEW-EVIDENCE.md`'s per-head evidence sections | role-match |
| `84-HASH-MANIFEST.md` (in-repo, PLANCHK-03 D-08/D-09) | evidence record / file-I/O | batch (hash + provenance) | `docs/codex-adversarial-review-contract.md` `AUDITED_INPUTS` sha256 pattern; `84-RESEARCH.md`'s own sha256 table for `81-01..07-PLAN.md` | exact (same hashing discipline, same repo) |
| `84-COMPARISON-REPORT.md` (in-repo, PLANCHK-03 matched runs + adjudication) | evidence record / test-report | batch | `83-REVIEW-EVIDENCE.md`, `83-DEMONSTRATIONS.md` | exact (same per-checkpoint markdown-record convention) |
| `84-CLOSEOUT.md` (in-repo, criterion 4: investigated vs. deferred) | evidence record | batch | `83-VERIFICATION.md` / `83-HUMAN-UAT.md` "Summary"/"Gaps" structure | role-match |
| `84-pilot/<run>.meta.json` + `.status.json` + `.jsonl`/output per matched run | evidence record / file-I/O | batch, one record per run | `tests/codex_review_run.py` output-suffix convention (`.prompt.txt`/`.meta.json`/`.jsonl`/`.last.json`/`.status.json`); `.planning/phases/83-.../codex/<head12>-<label>-a<attempt>.*` | exact |
| matched-run harness script (e.g. `run_matched_checker.py`) | utility/test harness | batch, subprocess invocation with timeout | `tests/codex_review_run.py` (whole file) | exact (same problem: wrap a `claude`/`codex` CLI call, enforce a wall-clock ceiling, write provenance, never silently pass) |
| `~/scratch/planchk-pilot/.claude/plugins/planchk-router/.claude-plugin/plugin.json` | config | config | none in this repo | no analog |
| `~/scratch/planchk-pilot/.claude/plugins/planchk-router/hooks/hooks.json` | config (hook registration) | event-driven | none in this repo | no analog |
| `~/scratch/planchk-pilot/.claude/plugins/planchk-router/hooks/register.js` (the `agent.spawn` hook) | middleware | event-driven | none in this repo (no JS mods-hook code anywhere in Triggarr) | no analog — use `84-RESEARCH.md`'s cited skeleton + code.claude.com docs |
| `~/scratch/planchk-pilot/.claude/settings.json` (isolated pilot settings) | config | config | partial: `--settings <file>` flag pattern cited in `84-RESEARCH.md` "Matched-run mechanics" | no analog |
| blind packet assembly (frozen Phase 81 plans + context/research/patterns/validation, copied into scratch) | file-I/O / data snapshot | batch (freeze + copy + redact) | `docs/codex-adversarial-review-contract.md` "Raw output storage" + `redact_local_paths()` in `tests/codex_review_run.py` | partial |
| known-defective plan fixture (for pilot exercise "a known-defective plan") | test fixture | batch | `.planning/phases/81-.../81-0N-PLAN.md` (structural reference for a valid plan's shape — the fixture must deliberately violate it) | partial |
| adjudicator session scoping (`--settings`/`--add-dir` for the blind-scoring session) | config | request-response (one-shot `claude -p`) | `84-RESEARCH.md` "Matched-run mechanics" / "Blind adjudicator session (D-11)" | partial (spec-only, no repo code) |
| secret/path redaction pass before any evidence is written to the phase dir | utility (transform) | transform | `redact_local_paths()`, `tests/codex_review_run.py:309` | exact |
| non-silent incomplete-status check for each evidence artifact | utility (validation) | transform | `assess_report()` / `Assessment` dataclass, `tests/codex_report_status.py:58,305` | exact |

## Pattern Assignments

### `84-RUNTIME-VERDICT.md` (evidence record, PLANCHK-01)

**Analog:** `83-REVIEW-EVIDENCE.md` (per-head evidence-section convention) + this phase's own `84-RESEARCH.md` (binary/doc citation discipline it already modeled).

**Structure to copy** — one bounded section per claim, each ending in an explicit, binary verdict word, never a hedge:

`84-RESEARCH.md` lines 113-161 (`### Runtime support for agent.spawn (PLANCHK-01, D-01)`) already demonstrates the exact shape this record should reuse: a `[VERIFIED: ...]`/`[CITED: ...]` provenance tag on every claim, a direct quoted excerpt of the evidence (binary strings, doc prose), and a one-line "Conclusion for D-01" that commits to one of `verified-present` / `verified-absent` / `update-required` — matching the evidence-map check in `84-RESEARCH.md` line 523 (`grep -q "agent.spawn" <evidence-file>` + an explicit state word). Reuse that exact pattern; do not write prose that never commits to one of the three states.

**Commit-identity table pattern** (for recording before/after Claude Code version per D-02, if an update happens):
`docs/review-checkpoint-record.md` lines 33-39 ("### Commit identities" table) — copy the table shape (`| Field | Value |`) with rows `Installed version (before)`, `Target version (proposed)`, `Changelog items shown to owner`, `Owner go-ahead (quote)`, `Installed version (after)`, `Hook re-verified on updated runtime (yes/no + evidence)`.

**Non-silent-negative discipline** (shared pattern, see below): if the hook turns out unsupported after the update, the verdict must say so in the same explicit place a positive result would go — never omit the section.

---

### `84-HASH-MANIFEST.md` (evidence record, PLANCHK-03 D-08/D-09)

**Analog:** `docs/codex-adversarial-review-contract.md` lines 57, 61-64 (`AUDITED_INPUTS` sha256-and-commit-state check) and `84-RESEARCH.md` lines 341-349 (the sha256 table this research already produced for `81-01..07-PLAN.md`).

**Core pattern to copy** — a manifest row per input file with: path, sha256, mtime, provenance (git-tracked / never-tracked-filesystem / Time-Machine-recovered), and an explicit "cutoff satisfied: yes/no" column citing the D-09 timestamp evidence (`84-RESEARCH.md` lines 355-368 gives the exact three-source triangulation and the recommended conservative cutoff `2026-10-19 22:34:01 -0400` to cite per row).

```
# from 84-RESEARCH.md:341-349, reuse verbatim as manifest seed rows, recomputed at execution time:
dfeb54c5937136e7143574ab4d0b14feab0f80d106e215010e571377ba557fb2  81-01-PLAN.md
096a065550f1643f756b3d6b7f1cb0212dbee85952ad537199de02cd3f7f2b14  81-02-PLAN.md
...
```

**Validation before trusting a hash:** `tests/codex_review_run.py` lines 57-65 (`AUDITED_INPUTS` + the "refuses to start if ... has uncommitted changes" check described in `docs/codex-adversarial-review-contract.md` line 57, step 0) is the pattern for "recompute and compare before relying on a previously recorded hash" — the manifest must be recomputed at the moment each matched run actually consumes a file, not trusted from this research pass alone (RESEARCH.md's own caveat, line 351).

**Explicit-unavailable branch (D-10):** if the 81-08/81-09 gap cannot be closed (Time Machine still blocked — see `84-RESEARCH.md` lines 370-384), the manifest must carry an explicit row stating `UNAVAILABLE — reason: Full Disk Access blocked (tmutil/ls both "Operation not permitted")`, in the same table, not a silent omission — matching the "never report a missing input as clean" discipline in `docs/codex-adversarial-review-contract.md`'s Failure rule (line 93) and `tests/codex_report_status.py`'s docstring (lines 7-10: "a missing report ... is never described as anything else").

---

### `84-COMPARISON-REPORT.md` (evidence record, PLANCHK-03 matched runs + adjudication)

**Analog:** `83-REVIEW-EVIDENCE.md` (per-checkpoint record) and `83-DEMONSTRATIONS.md` (recipe-by-recipe expected/observed/evidence-line structure).

**Core pattern** — `83-DEMONSTRATIONS.md`'s per-recipe shape (Input → Command run → Expected → Observed (verbatim JSON/output) → Evidence-record line) is the template for each of the 2+2+1+1 matched runs (D-17: 2 ordinary + 2 Codex-routed blind runs, 1 ordinary + 1 Codex-routed revision-round run). Example to copy almost verbatim (`83-DEMONSTRATIONS.md` lines 18-33, Recipe 1):

```markdown
### Run: ordinary BM checker, blind pass, attempt 1
- **Input:** <frozen plan snapshot path>, <model>, <effort>
- **Command run:** <exact claude -p invocation>
- **Expected / Observed:** <checker's structured BLOCKER/WARNING output, verbatim>
- **Duration / usage:** <wall-clock, token/turn counts if available>
- **Evidence-record line:** `<checker>: <N> findings, <M> of 7 answer-key defects matched, duration Xs`
```

**Adoption-criteria scoring table** — reuse the "Commit identities"/"Classification" table-and-JSON-block pattern from `docs/review-checkpoint-record.md` lines 33-47, adapted to D-12 through D-15's bar (defects matched / false-positive ratio / D-14 checklist / "met" or "not met, mixed counts as not met").

**False-positive adjudication discipline:** `docs/codex-adversarial-review-contract.md` line 44 ("Separate reproduced defects ... from unverified hypotheses") and the schema's `reproduced`/`reproduction_command`/`hypothesis` fields (`.claude/schemas/codex-review-findings.schema.json` lines 94-96, 133-141) are the direct structural analog for D-11's "checks false positives as carefully as hits, with reproduction evidence per verdict" — copy that same reproduced/hypothesis split into the adjudicator's scoring record rather than inventing a new one.

---

### `84-CLOSEOUT.md` (evidence record, success criterion 4)

**Analog:** `83-HUMAN-UAT.md`'s `Summary` block (total/passed/issues/pending/skipped/blocked counts, lines 24-29) and `83-VERIFICATION.md`'s closeout framing.

**Core pattern:**
```yaml
## Summary
total: <N investigated items>
investigated: <N, each with evidence pointer>
deferred: <N, each with reason>
unavailable: <N, each with reason>
```
Followed by one subsection per PLANCHK-0X requirement, each stating either "Investigated — see `84-RUNTIME-VERDICT.md`/`84-COMPARISON-REPORT.md` §X" or "Deferred/Unavailable — reason: ...", matching the phase boundary's own instruction ("Closeout separates what was actually investigated ... from what was deferred or not run") and D-15 ("mixed result counts as not met... explain what fell short").

---

### Matched-run harness script (e.g. `run_matched_checker.py`)

**Analog:** `tests/codex_review_run.py` (entire file, 745 lines) — same problem shape: wrap a CLI session (`claude -p` here instead of `codex exec`), enforce D-18's 15-minute ceiling, write immutable provenance/output files, never silently pass on timeout or failure.

**Imports / stdlib-only pattern** (`tests/codex_review_run.py:30-45`):
```python
import argparse, contextlib, getpass, hashlib, json, os, re, shlex, shutil, signal, subprocess, sys, tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
```
Copy this discipline: no third-party dependency for the harness, matching `84-RESEARCH.md`'s "Standard Stack" conclusion that only `subprocess`/`json`/`hashlib`/`pathlib` are needed.

**Timeout-with-process-group-kill pattern** (`tests/codex_review_run.py:106-146`, `run_command()`/`_kill_group()`):
```python
def _kill_group(proc: subprocess.Popen) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)

def run_command(argv, *, start_new_session=False, input=None, timeout=None, check=False, **kwargs):
    # start_new_session=True: `uv run`/`claude` spawns a child of its own;
    # killing only the direct child on timeout would leave it running.
    ...
    except subprocess.TimeoutExpired as exc:
        _kill_group(proc)
        exc.stdout, exc.stderr = proc.communicate()
        raise
```
Directly reusable for D-18's 15-minute (`timeout=900`) ceiling on `claude -p` — `84-RESEARCH.md`'s own "Code Examples" section (lines 442-457) already sketches this same call with `timeout=900` and a `status = "incomplete_timeout"` branch; wire it through this exact `run_command`/`_kill_group` shape instead of a bare `subprocess.run(..., timeout=...)`, since a bare call only kills the direct child, not a `claude`-spawned grandchild.

**Validated-run dataclass pattern** (`tests/codex_review_run.py:153-190`, `ReviewRun`):
```python
@dataclass(frozen=True)
class ReviewRun:
    head: str
    base: str
    label: str
    attempt: int
    ...
    def __post_init__(self) -> None:
        # raise ValueError with a plain-word reason for every malformed field
    @property
    def out_base(self) -> Path:
        return REPO_ROOT / self.phase_dir / "codex" / f"{self.head[:12]}-{self.label}-a{self.attempt}"
```
Adapt the same shape for a `MatchedRun` dataclass keyed by `(checker: Literal["ordinary","codex"], round: Literal["blind","revision"], attempt: int)`, writing to `84-pilot/<checker>-<round>-a<attempt>.*` — mirrors the Phase 83 `codex/<head12>-<label>-a<attempt>.*` naming exactly.

**Output-suffix / "never overwrite, claim atomically" pattern** (`tests/codex_review_run.py:89, 94-96`, plus the atomic-claim rule in `docs/codex-adversarial-review-contract.md` line 65):
```python
OUTPUT_SUFFIXES = (".prompt.txt", ".meta.json", ".jsonl", ".last.json", ".status.json", ".pytest.txt")
```
Copy this suffix set (renamed for this harness: `.prompt.txt`, `.meta.json`, `.jsonl`, `.last.json`/`.result.json`, `.status.json`, `.routes.jsonl` for the gateway-metadata correlation) and the `O_CREAT|O_EXCL` atomic-claim behavior described in the same doc line, so two runs with the same checker/round/attempt can't silently clobber each other.

**Path/secret redaction before anything is written to the (git-excluded but still local) phase dir** (`tests/codex_review_run.py:309`, `redact_local_paths()`):
```python
def redact_local_paths(text: str, *, worktree: Path, scratch: Path) -> str:
    # Replace local absolute paths (worktree, scratch, repo, tmp, home,
    # pytest-of-<user>) with neutral markers before the text is ever stored.
```
Apply the same transform to anything the harness captures that might contain the operator's home-directory path, the scratch-pilot path, or (per global CLAUDE.md) any gateway auth token — never store those raw in `84-pilot/*.jsonl`.

**Error handling / non-silent-incomplete pattern** (`docs/codex-adversarial-review-contract.md` lines 62, 91-94, the "Failure rule"):
> On a non-zero exit code, a timeout, or an incomplete checker result, retry once automatically on the same SHA (attempt 2) ... If attempt 2 is also incomplete, record ... INCOMPLETE/PENDING with the reasons in plain words and ask the owner to choose.

Copy this one-retry-then-ask-the-owner rule verbatim for D-07's "unavailable gateway/model and incomplete output must show as incomplete with an explicit error (no silent pass, no silent fallback to Claude)."

---

### Gateway-metadata correlation check (part of the harness, PLANCHK-02 proof-of-routing)

**Analog:** `tests/codex_report_status.py` — same problem shape (assess a JSON artifact against required fields and emit exactly one of two status words, never anything softer).

**Core pattern** (`tests/codex_report_status.py:58-70`, `Assessment` dataclass + docstring lines 7-10):
```python
@dataclass(frozen=True)
class Assessment:
    status: Literal["complete", "incomplete"]
    reasons: tuple[str, ...]
    ...
```
> The only two status words this module ever emits are "complete" and "incomplete" -- a missing, failed, skipped, stale, or wrong-commit report is never described as anything else (D-09).

Reuse this exact two-word-status discipline for the gateway-routing proof (`84-RESEARCH.md` lines 234-258, the `request-routes.jsonl` `agentId`-correlation check): the check must emit `routed`/`not-routed` (or `complete`/`incomplete`), never a softer "probably routed" — matching D-14's "a model label alone is not proof" bar.

**jq correlation command** (already fully specified in `84-RESEARCH.md` lines 434-439, "Code Examples" — use verbatim):
```bash
jq -c --arg aid "<agent_id>" 'select(.agentId == $aid)' ~/.claude/model-gateway/logs/request-routes.jsonl
# Expect: {"backend":"codex","model":"gpt-6-astra", ... ,"agentId":"<agent_id>", ...}
```

---

### `register.js` (the `agent.spawn` hook) — no in-repo analog

No JS mods-hook code exists anywhere in this Python/FastAPI repo; there is nothing to copy a pattern *from* inside Triggarr. The only available reference is the external, already-cited skeleton in `84-RESEARCH.md` lines 274-282:

```js
export function register(on) {
  on('agent.spawn', { subagentType: 'bm:bm-plan-checker' }, async ($, e, next) => {
    return next({ ...e, model: 'claude-gpt-6-astra[1m]' }); // recheck live catalog at pilot time (D-04)
  });
}
```
Treat this as a spec to verify (per `84-RESEARCH.md` Assumption A2: confirm the matcher key is actually `subagentType` via `claude plugin validate`, not `agentType`), not a proven-working snippet — it has not been live-exercised anywhere, in this repo or elsewhere in this research.

---

## Shared Patterns

### Evidence discipline: never report missing/incomplete/unavailable as clean
**Source:** `docs/codex-adversarial-review-contract.md` line 93 (Failure rule); `tests/codex_report_status.py` docstring lines 7-10 ("the only two status words ... never described as anything else")
**Apply to:** `84-RUNTIME-VERDICT.md`, `84-HASH-MANIFEST.md`, `84-COMPARISON-REPORT.md`, `84-CLOSEOUT.md`, every matched-run output, the gateway-routing check.
```
A missing, failed, skipped, stale, or wrong-commit report is never described as anything else.
```

### Immutable, suffix-keyed raw output; atomic claim of the output name
**Source:** `tests/codex_review_run.py:89` (`OUTPUT_SUFFIXES`), `docs/codex-adversarial-review-contract.md` line 65 (atomic `O_CREAT|O_EXCL` claim), lines 69-80 ("Raw output storage")
**Apply to:** every `84-pilot/<checker>-<round>-a<attempt>.*` artifact. None of these files are ever edited after being written; a retry gets the next attempt number, never an overwrite.

### Secret/path redaction before anything leaves the operator's machine or is written to a (even git-excluded) file
**Source:** `tests/codex_review_run.py:309` (`redact_local_paths`); `docs/codex-adversarial-review-contract.md` lines 80-89 (gitleaks + 32-hex-char key grep before `git add -f`); global CLAUDE.md "never log sensitive data ... never hardcode secrets"
**Apply to:** the matched-run harness, `84-HASH-MANIFEST.md`, `84-COMPARISON-REPORT.md`, the gateway-metadata correlation output (model-gateway's `request-routes.jsonl` lines never contain a token, but confirm before quoting a line verbatim into a markdown record).
```python
def redact_local_paths(text: str, *, worktree: Path, scratch: Path) -> str: ...
```

### Subprocess wall-clock ceiling via process-group kill, not a bare `timeout=`
**Source:** `tests/codex_review_run.py:106-146`
**Apply to:** the matched-run harness's `claude -p` / `codex exec` invocations (D-18's 15-minute ceiling).

### `.planning/` stays local; nothing from this phase is `git add -f`'d (D-16)
**Source:** `.git/info/exclude` (`.planning/` excluded repo-wide) contrasted with `docs/codex-adversarial-review-contract.md` lines 80-89's documented `git add -f` carve-out that *other* phases (81, 83) deliberately use
**Apply to:** every file this phase writes. The default (do nothing) already satisfies D-16 — do not run `git add -f` against `84-*` files, unlike Phase 83's `codex/` evidence, which was deliberately force-added.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `~/scratch/planchk-pilot/.claude/plugins/planchk-router/.claude-plugin/plugin.json` | config | config | No Claude Code plugin manifest authored anywhere in this repo; use the file-layout skeleton in `84-RESEARCH.md` lines 264-273 and validate with `claude plugin validate` at execution time. |
| `~/scratch/planchk-pilot/.claude/plugins/planchk-router/hooks/hooks.json` | config (hook registration) | event-driven | Same — no mods `hooks.json` anywhere in Triggarr. |
| `~/scratch/planchk-pilot/.claude/plugins/planchk-router/hooks/register.js` | middleware | event-driven | No JS mods-hook code anywhere in this Python repo; the only reference is the external skeleton quoted above (not proven working). |
| `~/scratch/planchk-pilot/.claude/settings.json` (isolated pilot settings) | config | config | No isolated-settings-file precedent in this repo; `84-RESEARCH.md`'s `--settings`/`--permission-mode` flag citations are the only guidance. |
| blind-packet assembly mechanics (what gets copied, in what order, with what exclusions) | file-I/O / data snapshot | batch | Partially analogous to `codex_review_run.py`'s redaction/storage discipline, but no prior phase has assembled a *reviewer-facing input packet* with deliberate exclusions (answer key, later findings) — this is genuinely new; follow the blueprint's explicit inclusion/exclusion list (`docs/bm-greptile-codex-blueprint.md` lines 255, 259, 261) directly, since it is more complete than any code analog here. |

## Conventions

Derived with the shared `gsd-tools.cjs verify conventions --derive` module (repo-wide; a scope limited to `tests/` returned `no-app-files` since the module does not treat `.py` test/tooling files as "app files" for this derivation):

| Axis | Dominant | Share | Entropy | Status |
|---|---|---|---|---|
| file-name casing | camel | 77.4% | 0.609 | named contract |
| identifier casing | (mixed: camel/Pascal/CONSTANT) | 43.2% | 0.784 | contested hotspot |
| export style | — | insufficient data (0 samples) | — | insufficient data |
| import style | — | insufficient data (0 samples) | — | insufficient data |

Two Python-specific axes the same run also reported, directly relevant if the matched-run harness is committed inside this repo (e.g. `tests/run_matched_checker.py`) rather than kept entirely external per D-06: **py-wildcard-import** — dominant `explicit`, share 100%, named contract (never use `from x import *`); **py-import-relativity** — dominant `absolute`, share 100%, named contract (absolute imports only, matching `tests/codex_review_run.py`'s own `from __future__ import annotations` + absolute-import style).

**Contested hotspots (author's choice):** the repo-wide file-name/identifier-casing numbers above are pulled from a mixed scan (this repo's Python app/test code alongside JS/TS material under `.claude/` plugin caches and worktrees) and are not this phase's own signal either way — this phase adds no JS/TS identifiers of its own. The project's own prototype intentional-contested split is the CJS<->SDK dual resolver in the installed BM plugin tooling: `bin/lib/**` is CJS (`module.exports`/`require`), `sdk/src/**` is ESM (`export`/`import`) — each half is internally consistent per-directory, contested only when compared repo-wide. The same rule applies here: if the scratch-pilot `register.js` is authored, match whatever module style `hooks.json`'s own loader expects (check `claude plugin validate` output) rather than importing a style from elsewhere in this repo; if a harness script lands inside Triggarr's own `tests/`, match that directory's existing absolute-import, explicit-import Python style instead.

## Metadata

**Analog search scope:** `tests/` (codex review harness + its tests), `docs/` (codex-adversarial-review-contract.md, review-checkpoint-record.md, review-classification-policy.md, bm-greptile-codex-blueprint.md), `.planning/phases/83-paired-bm-codex-review-risk-based-depth/` (REVIEW-EVIDENCE, DEMONSTRATIONS, HUMAN-UAT, VERIFICATION, codex/ subdir), `.claude/schemas/codex-review-findings.schema.json`, `.git/info/exclude`.
**Files scanned:** 15 (read in full or by targeted range); repo-wide convention derivation run separately via the shared tool.
**Pattern extraction date:** 2026-10-23
