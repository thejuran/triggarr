---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-22T19:59:57Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - .claude/schemas/codex-review-findings.schema.json
  - docs/bm-review-baseline-2026-10-22.md
  - docs/buildomator-greptile-pilot.md
  - docs/codex-adversarial-review-contract.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - tests/codex_report_status.py
  - tests/test_app_cards.py
  - tests/test_codex_report_status.py
  - tests/test_codex_review_contract.py
  - tests/test_review_instructions.py
  - triggarr/templates/partials/cycle_grade.html
findings:
  critical: 2
  warning: 5
  info: 6
  total: 13
status: issues_found
---

# Phase 83: Code Review Report

**Reviewed:** 2026-10-22T19:59:57Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the Codex report completeness checker (`tests/codex_report_status.py`) and its tests, the output schema, the four review-process docs, the CLAUDE.md/contract drift-guard tests, and the quick-task card-label change (`cycle_grade.html` plus 10 new card tests).

All 125 tests in the four reviewed test modules pass. Ruff is clean, and the conventions tool reported no findings.

The main concern is the checker. Its only job is to make sure a malformed, partial or wrong Codex report is never counted as a complete review. Its schema check covers required and unexpected keys, a few enums and some integer fields. It does **not** check the types of most fields. I ran edge cases against `assess_report()`, and each of these returned `status: complete` with no reasons:

| Input mutation on the valid fixture | Result |
|---|---|
| `findings: null` or `findings: "none"` | complete, 0 findings |
| `coverage: null` or `coverage: "all"` | complete |
| `schema_version: "2"` (enum is `["1"]`) | complete |
| `summary: 5` (schema type is string) | complete |
| `verdict: "no-findings"` with 2 findings present | complete |
| `verdict: "findings"` with `findings: []` | complete |
| finding `id: 7` (int) | complete, `finding_count=2`, only 1 qualified ID |
| `line_start: true` | complete |
| `hypothesis: "   "` | complete |

The template change does what was decided (D-01 to D-04), and the new tests cover it. It classifies rows by matching the exact wording `outcome.py` produces, which is a fragile coupling, though when the wording drifts it falls back to the safer "failure reason" label.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Checker marks reports with wrong-typed or missing-value fields (including `findings: null`) as a complete review

**File:** `tests/codex_report_status.py:52-123, 133-135, 235-237`
**Issue:** `_check_schema` only validates nested items `if isinstance(findings, list)` / `if isinstance(commands_run, list)`. It never reports that `findings`, `commands_run`, `coverage`, `exclusions` or `limitations` are not arrays. It also never checks `schema_version` against its enum or the type of any string field. `_finding_consistency_and_ids` then returns `([], [], 0)` for a non-list `findings`. So a report with `"findings": null` and `"verdict": "findings"` gets `status: complete, finding_count: 0`. The owner checklist would then show "No findings" for a Codex run that produced none in a usable form. This is the false-clean outcome the module docstring and D-09 say can never happen ("a schema violation ... reported as a distinct reason"). Codex's `--output-schema` makes this unlikely in normal runs. But this checker is the gate that exists for when that constraint fails or the file is hand-edited or truncated into valid JSON, and right now it fails open.

Reproduced: `assess_report(json.dumps({**valid, "findings": None}), exit_code=0, ...)` returns `Assessment(status='complete', reasons=(), finding_count=0, ...)`.

`tests/test_codex_report_status.py` has no wrong-type case at all, so the suite passes despite this gap.

**Fix:** Do generic type and enum validation driven by the schema, without adding a dependency (`jsonschema` is not installed):
```python
_JSON_TYPES = {"string": str, "array": list, "object": dict, "boolean": bool, "integer": int, "null": type(None)}

def _type_ok(value, spec) -> bool:
    types = spec.get("type")
    if types is None:
        return True
    types = types if isinstance(types, list) else [types]
    for t in types:
        py = _JSON_TYPES[t]
        if t == "integer" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False

def _validate(value, spec, path, reasons):
    if not _type_ok(value, spec):
        reasons.append(f"schema: {path} has wrong type"); return
    if "enum" in spec and value not in spec["enum"]:
        reasons.append(f"schema: {path} {value!r} not in {spec['enum']}")
    if isinstance(value, dict) and spec.get("type") == "object":
        props = spec.get("properties", {})
        for f in spec.get("required", []):
            if f not in value: reasons.append(f"schema: {path} missing {f}")
        for k, v in value.items():
            if k not in props: reasons.append(f"schema: {path} unexpected field {k}")
            else: _validate(v, props[k], f"{path}.{k}", reasons)
    if isinstance(value, list) and "items" in spec:
        for i, item in enumerate(value):
            _validate(item, spec["items"], f"{path}[{i}]", reasons)
```
Replace `_check_schema` with a recursive walk of this kind. Add tests for `findings: null`, `findings: "x"`, `coverage: null`, `schema_version: "2"`, `summary: 5` and `line_start: True`, each expecting `incomplete`.

### CR-02: A finding with a non-string `id` is counted but dropped from the qualified IDs, so it cannot be dispositioned

**File:** `tests/codex_report_status.py:145-147, 162`
**Issue:** `_finding_consistency_and_ids` runs `continue` when `fid` is not a `str`. That skips the duplicate check, the reproduced/hypothesis check and the qualified-ID creation. Nothing in `_check_schema` flags the wrong type of `id`, so the report stays `complete`. Reproduced: with `findings[0]["id"] = 7`, the result is `status=complete, finding_count=2, qualified_ids=1`. The checkpoint-record disposition table and the owner checklist are keyed on qualified IDs. A real Codex finding (possibly a critical one) disappears from the disposition flow while the report still reads "complete". Its reproduced/hypothesis consistency is also never checked.
**Fix:** Treat a missing or non-string `id` as a schema violation that makes the report incomplete, and never skip a finding silently:
```python
fid = finding.get("id")
if not isinstance(fid, str) or not fid.strip():
    reasons.append(f"finding at index {idx} has no valid id")
    continue
```
CR-01's recursive validation would also catch this. Add a test where `id=7` expects `incomplete` and checks that `finding_count == len(qualified_ids)` on every complete result.

## Warnings

### WR-01: Contradictory `verdict` and `findings` are accepted as complete

**File:** `tests/codex_report_status.py:69-72, 230-239`
**Issue:** `verdict: "no-findings"` with two findings, and `verdict: "findings"` with `findings: []`, both come back `complete`. A summary built from `verdict` would say "no findings" while findings exist, or the other way round.
**Fix:** After schema validation, add:
```python
if isinstance(findings, list):
    if verdict == "no-findings" and findings:
        reasons.append("verdict says no-findings but findings are listed")
    if verdict == "findings" and not findings:
        reasons.append("verdict says findings but none are listed")
```

### WR-02: CLI crashes with a traceback (no JSON assessment) on a non-UTF-8 or directory report path

**File:** `tests/codex_report_status.py:288-289`
**Issue:** `report_path.read_text(encoding="utf-8") if report_path.exists()` raises `UnicodeDecodeError` on invalid bytes (reproduced with `\xff\xfe`) and `IsADirectoryError` if the path is a directory. The contract (step 6) expects this command to produce the `.status.json` assessment. Instead it produces a Python traceback and no `status`/`reasons` payload. That breaks the promise that every failure gets a plain-language reason. The docstring of `assess_report` says it "never raises on malformed input", but the CLI wrapper does.
**Fix:**
```python
try:
    report_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else None
except (OSError, UnicodeDecodeError) as exc:
    report_text = None
    read_error = f"unreadable report: {type(exc).__name__}"
```
Prepend `read_error` to the reasons, so the run still prints JSON and exits 1.

### WR-03: The checkpoint record says BM re-review keeps no history, which contradicts the verified baseline and BM's own workflow

**File:** `docs/review-checkpoint-record.md:131`
**Issue:** The record says `/bm:code-review <N> --fix --auto` "overwrites `REVIEW.md` in place ... it has no built-in history". `docs/bm-review-baseline-2026-10-22.md:53, 68, 86, 230, 238` documents (with line citations) that each iteration backs up `REVIEW.md`/`REVIEW-FIX.md` to `*.iterN.md` before overwriting. The installed `bm/5.0.3/workflows/code-review-fix.md:270-272` confirms this (`cp "${REVIEW_PATH}" "${REVIEW_PATH%.md}.iter${ITERATION}.md"`). This is a sensitive operational procedure doc. A false claim about how evidence is kept will confuse whoever reconciles `.iterN.md` files against the `REVIEW-<head12>.md` snapshots, and it undercuts trust in the baseline.
**Fix:** Change the wording to: "BM's `--auto` loop keeps per-iteration `*.iterN.md` backups, but they are named by iteration rather than head SHA and are not committed. Before any re-review, also snapshot by head SHA:" and keep the `cp` step.

### WR-04: The classification policy does not rank `sensitive` against `code`, but the record requires a single "most consequential" class

**File:** `docs/review-classification-policy.md:15-19, 41`
**Issue:** "Mixed changes" says a PR follows "its most consequential class" and `classification` is "the single most consequential class". It only says ordinary-docs is the least consequential. `sensitive` and `code` require different things: sensitive asks for vibe-check only when risk is high, while code requires routine vibe-check and CI. This phase's own PR is mixed sensitive + code (it touches `.claude/schemas/**` and policy docs plus `triggarr/templates/partials/cycle_grade.html` and tests). Classifying it `sensitive` would, read literally, drop the routine vibe-check the owner still requires for application code.
**Fix:** Add: "When both `sensitive` and `code` are present, the PR must meet the union of both rows' requirements (routine vibe-check and CI from `code`, plus RISK-01/RISK-02 from `sensitive`). Record `classification` as `code` and list both in `classes_present`." Alternatively, define an explicit order.

### WR-05: Raw Codex event streams are committed to a public repo, with pattern-based gitleaks as the only safeguard

**File:** `docs/codex-adversarial-review-contract.md:46-52`
**Issue:** The full, unedited `.jsonl` stream (every command Codex ran and its output) is force-added (`git add -f`) to the public repository. `--sandbox read-only` restricts writes, not reads. Codex can still `cat` files outside the detached worktree, such as a dev `config.toml` or shell environment, and those outputs land in the stream. gitleaks only catches known secret shapes. Radarr/Sonarr API keys are 32-character hex strings with no prefix and are commonly missed. CLAUDE.md's security rule says "No API keys in logs". The fixed prompt never tells Codex to stay inside the worktree or avoid reading credentials.
**Fix:** Add this sentence to the fixed prompt: "Do not read files outside the working directory or any credential/config file." Bump the template version. Before committing, also grep the raw files for the configured instance API keys (for example `rg -F -f <(local key list)`, kept out of the repo), or commit only `.last.json`/`.status.json` and keep `.jsonl` local or as a CI artifact.

## Info

### IN-01: Template classifies reason rows by matching the wording `outcome.py` generates

**File:** `triggarr/templates/partials/cycle_grade.html:18-28`
**Issue:** The `startswith('Missing queue not evaluated: ')` / `endswith('— malformed data')` / `endswith('skipped')` checks duplicate the strings built in `triggarr/search/outcome.py:291, 303-313`. The view layer is re-deriving domain categories that `cycle_view` already knows. A wording change in `outcome.py` silently changes the label. The fallback goes to "failure reason" (the safe direction), and `test_app_cards.py` would catch it, so this is a maintainability issue rather than a live defect.
**Fix:** Have `cycle_view` emit `"kind": "failure" | "unevaluated" | "malformed" | "eligible"` on each reason row, or emit precomputed `detail_label` fields, and branch on those in the template.

### IN-02: "Skipped records" label count comes from a different field than the rows

**File:** `triggarr/templates/partials/cycle_grade.html:32-33`
**Issue:** The rows come from `malformed_by_queue`, but the label count and the gate use `malformed_skipped`. They agree for engine-written state (`outcome.py:176`). For a tampered or hand-edited `state.json` (which `cycle_view` explicitly guards against), `malformed_by_queue={"missing": 2}` with `malformed_skipped=0` falls through to "Show 1 failure reason". Mismatched values would show a count that disagrees with the rows.
**Fix:** Compute the label count in `cycle_view` from the rows actually rendered (sum of per-queue counts, or the legacy aggregate).

### IN-03: `test_never_reports_clean` is tautological

**File:** `tests/test_codex_report_status.py:319-339`
**Issue:** It only asserts that the word "clean" never appears. The implementation has no code path that could emit it, so the test cannot fail on a real regression. A meaningful guard would be "every malformed scenario yields `incomplete`", which is what CR-01 shows is false.
**Fix:** Replace it with a parametrized list of malformed and type-violating reports, each asserting `status == "incomplete"`, plus an invariant check that `finding_count == len(qualified_ids)` whenever the status is `complete`.

### IN-04: `--attempt` accepts zero or negative values

**File:** `tests/codex_report_status.py:268`
**Issue:** `--attempt 0` or `--attempt -3` produces qualified IDs such as `codex:<head>:a-3:F001`, which do not match the `a1`/`a2` convention used in the checkpoint record.
**Fix:** Use a `type=` validator that requires `>= 1`.

### IN-05: Whitespace-only `reproduction_command`/`hypothesis` and `bool` integers pass

**File:** `tests/codex_report_status.py:98-101, 155-158`
**Issue:** `not finding.get("hypothesis")` treats `"   "` as present, and `isinstance(True, int)` lets `line_start: true` and `exit_code: true` pass the integer checks (both reproduced).
**Fix:** Use `not (value or "").strip()` and `isinstance(v, int) and not isinstance(v, bool)`.

### IN-06: Failure rule allows a third attempt, but the record template only allows 1 or 2

**File:** `docs/codex-adversarial-review-contract.md:56`, `docs/review-checkpoint-record.md:86`
**Issue:** After attempt 2 the owner may choose "retry later", which would be attempt 3. The checkpoint template's `Attempts | 1 | 2` and the storage naming give no guidance for it.
**Fix:** Change the template to `Attempts | N (1, 2, or owner-approved retry)` and say that owner-approved retries keep incrementing `a<attempt>`.

## Set aside (needs ruling)

### SA-01: Red "Failed" cycle whose only rows are unevaluated queues is labelled "Show N detail(s)"

**Where:** `triggarr/templates/partials/cycle_grade.html:28-31`
**Why excluded:** This follows decision D-04 ("unevaluated is not a failure"), and no test covers the Failed-grade version of it. That makes it a product-wording call rather than a code defect.
**Effect if left as is:** A user sees a red "Failed · 0 accepted, 0 failed" headline above a neutral "Show 1 detail" disclosure. The row inside may be "Missing queue not evaluated: malformed data (KeyError)", which is the actual cause of the failure. The neutral label may make the user less likely to open it.
**Needs:** Owner ruling on whether a Failed-grade card with only unevaluated rows should still say "detail(s)", or should use a failure label.

### SA-02: Changed files in the diff range that were not in the review scope

**Where:** `CLAUDE.md` (commit 719359a), `docs/owner-cli-acceptance.md:15`
**Why excluded:** Both changed in `6f3841aa..HEAD` but were not in the provided file list. Both are sensitive under the new classification policy (agent instructions and acceptance policy).
**Effect if left as is:** The acceptance-procedure change (write dispositions before presenting the run, Greptile optional) and the CLAUDE.md review wiring have not had this BM pass. `tests/test_review_instructions.py` only checks that strings are present in CLAUDE.md.
**Needs:** A ruling on whether to add them to this review's scope or cover them in the paired Codex pass.

---

_Reviewed: 2026-10-22T19:59:57Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
