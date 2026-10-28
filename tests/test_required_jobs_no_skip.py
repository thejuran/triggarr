"""Authoritative no-skip guard for the jobs behind GitHub required checks.

This is the authoritative check that no job backing a required check can be
skipped or neutralised. It loads the real ``ci.yml`` and
``review-acceptance.yml`` with a real YAML parser (PyYAML, with duplicate keys
rejected), so the parser decides what each key and value is. Spelling tricks a
line-based reader can miss (quoted or escaped keys, column-0 comments, flow
mappings, anchors, aliases, merge keys, tags) cannot hide a key from it.

The Node detector in ``.github/scripts/ci-job-consistency.cjs`` stays as a
secondary line of defence. Where the two disagree, this test is authoritative.

Required jobs:

- ``ci.yml``: every job in ``ci-ready``'s ``needs`` plus ``ci-ready`` itself.
- ``review-acceptance.yml``: every job in the workflow (the job is the check).

For each required job it asserts:

- no job-level ``if``, except ``ci-ready``'s exact ``always()``;
- no ``continue-on-error`` at job or step level, whatever its value;
- every step ``if`` is on the reviewed allowlist, keyed by job, step name and
  exact condition;
- no ``shell:`` on any step and no ``defaults:`` on the job or the workflow
  (a custom shell such as ``true {0}`` runs instead of the script, review
  iteration 4 CR-01);
- no reusable workflow (job-level ``uses:``) and no local action
  (``uses: ./...``), whose steps this guard cannot see (review SA-05);
- every job and step key is a string, and no key is a case variant of
  ``if``, ``continue-on-error``, ``uses``, ``steps``, ``shell`` or
  ``defaults``.

It also scans every workflow file and asserts that "CI ready" and "Review
acceptance" are each the check name (job ``name:``, or job id when it has no
name) of exactly one job, the one in ``ci.yml`` or ``review-acceptance.yml``
(review iteration 4 WR-03).

It also checks each workflow's parsed ``on:`` block against its reviewed
trigger contract (``CI_TRIGGER_CONTRACT`` and ``ACCEPTANCE_TRIGGER_CONTRACT``):
exactly the contracted triggers, branches and types, and no ``paths``,
``paths-ignore``, ``branches-ignore`` or ``tags-ignore`` in any spelling.

It also cross-checks the job sets, so a job dropped from a required check
fails: ``ci-ready``'s ``needs`` must equal ``ALL_JOBS`` from
``tests/test_ci_gate.py``, and ``review-acceptance.yml`` must hold exactly the
``acceptance`` job.

PyYAML follows YAML 1.1, so a bare ``on:`` key loads as ``True``;
``workflow_triggers`` accepts either spelling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.test_ci_gate import ALL_JOBS

REPO_ROOT = Path(__file__).parent.parent
CI_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ACCEPTANCE_PATH = REPO_ROOT / ".github" / "workflows" / "review-acceptance.yml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CI_TEXT = CI_PATH.read_text()
ACCEPTANCE_TEXT = ACCEPTANCE_PATH.read_text()

AGGREGATE_JOB = "ci-ready"
AGGREGATE_IF = "always()"
ACCEPTANCE_JOBS = frozenset({"acceptance"})
# review-acceptance.yml's reviewed trigger contract. Same branches and types as
# TRIGGER_CONTRACTS['review-acceptance.yml'] in ci-job-consistency.cjs, but
# stricter: types must be exactly these four (GitHub's default omits
# ready_for_review), whereas the Node detector only requires that they include
# them and accepts extras such as closed; a null pull_request: is also rejected
# here. Do not loosen this to match Node: where the two disagree, this guard wins.
ACCEPTANCE_TRIGGER_CONTRACT = {
    "pull_request": {
        "branches": ("main",),
        "types": ("opened", "ready_for_review", "reopened", "synchronize"),
    },
}
# ci.yml's reviewed trigger contract: exactly what ci.yml declares today. Same
# triggers and branches as TRIGGER_CONTRACTS['ci.yml'] in ci-job-consistency.cjs,
# but stricter: ci.yml sets no types:, so GitHub's default types apply, and any
# types: key is rejected here (Node accepts one that includes the defaults).
CI_TRIGGER_CONTRACT = {
    "push": {"branches": ("main",)},
    "pull_request": {"branches": ("main",)},
}
# Trigger keys that let a PR skip the workflow entirely. Mirrors
# TRIGGER_FILTER_KEYS in ci-job-consistency.cjs.
TRIGGER_FILTER_KEYS = frozenset({"paths", "paths-ignore", "branches-ignore", "tags-ignore"})
# Each required check name and the only (workflow file, job id) allowed to
# publish it (review iteration 4 WR-03).
REQUIRED_CHECK_OWNERS = {
    "CI ready": ("ci.yml", AGGREGATE_JOB),
    "Review acceptance": ("review-acceptance.yml", "acceptance"),
}
WATCHED_KEYS = frozenset({"if", "continue-on-error", "uses", "steps", "shell", "defaults"})

BROWSER_EVIDENCE_CONDITION = (
    "failure() && hashFiles('e2e-artifacts/credential/scan-complete.json') != '' && "
    "hashFiles('e2e-artifacts/pages/scan-complete.json') != ''"
)

# The only step-level conditions a required job may carry: (job, step name,
# exact condition). Mirrors STEP_IF_ALLOWLIST in ci-job-consistency.cjs. Each
# entry is an evidence upload, so the step carrying it must also be the only
# step of that name in its job, use actions/upload-artifact and have no run:
# (review WR-01: otherwise a gate step renamed to an allowlisted name, with
# the allowlisted condition, would stop running on success).
ALLOWLISTED_STEP_USES = "actions/upload-artifact@"
STEP_IF_ALLOWLIST = frozenset(
    {
        ("test", "Upload test evidence", "always()"),
        ("browser-e2e", "Upload browser failure evidence", BROWSER_EVIDENCE_CONDITION),
    }
)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys.

    Plain PyYAML keeps the last of two equal keys, so ``if: always()`` after
    ``if: false`` would hide the first value. Merge keys (``<<``) are left to
    PyYAML's normal merge handling.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, str | int | float | bool) and key is not None:
                raise yaml.constructor.ConstructorError(None, None, f"unhashable key {key!r}", key_node.start_mark)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_workflow(text: str) -> dict[Any, Any]:
    doc = yaml.load(text, Loader=_StrictLoader)  # _StrictLoader subclasses SafeLoader
    if not isinstance(doc, dict):
        raise ValueError("workflow is not a mapping")
    return doc


def workflow_triggers(doc: dict[Any, Any]) -> Any:
    """Return the ``on`` block, which PyYAML loads under the key ``True``."""
    present = [key for key in ("on", True) if key in doc]
    if len(present) != 1:
        raise ValueError("workflow must have exactly one on: key")
    return doc[present[0]]


def _step_label(index: int, step: dict[Any, Any]) -> str:
    name = step.get("name")
    return f'step {index} "{name}"' if isinstance(name, str) else f"step {index} (unnamed)"


def _key_problems(where: str, mapping: dict[Any, Any]) -> list[str]:
    problems = []
    for key in mapping:
        if not isinstance(key, str):
            problems.append(f"{where} has a non-string key {key!r}")
        elif key not in WATCHED_KEYS and key.lower() in WATCHED_KEYS:
            problems.append(f"{where} has a case variant of a watched key: {key!r}")
    return problems


def job_problems(job_id: str, job: Any, *, allowed_if: str | None) -> list[str]:
    """Problems that could let required job ``job_id`` be skipped or ignored."""
    prefix = f'required job "{job_id}"'
    if not isinstance(job, dict):
        return [f"{prefix} is not a mapping"]

    problems = _key_problems(prefix, job)
    if "defaults" in job:
        problems.append(f"{prefix} sets defaults: (a run.shell override can neutralise its run steps)")
    if "uses" in job:
        problems.append(f"{prefix} calls a reusable workflow (job-level uses: {job['uses']!r})")
    if "continue-on-error" in job:
        problems.append(f"{prefix} sets continue-on-error")
    if "if" in job:
        if allowed_if is None:
            problems.append(f"{prefix} has a job-level if: {job['if']!r}")
        elif job["if"] != allowed_if:
            problems.append(f"{prefix} if: must be exactly {allowed_if}, got {job['if']!r}")
    elif allowed_if is not None:
        problems.append(f"{prefix} if: must be exactly {allowed_if}, but it has none")

    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        return [*problems, f"{prefix} steps: is not a non-empty list"]

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            problems.append(f"{prefix} step {index} is not a mapping")
            continue
        label = _step_label(index, step)
        problems.extend(_key_problems(f"{prefix} {label}", step))
        uses = step.get("uses")
        if "uses" in step and (not isinstance(uses, str) or uses.startswith((".", "/"))):
            problems.append(f"{prefix} {label} uses a local or unreadable action: {uses!r}")
        if "continue-on-error" in step:
            problems.append(f"{prefix} {label} sets continue-on-error")
        if "shell" in step:
            problems.append(f"{prefix} {label} sets shell: {step['shell']!r}")
        if "if" not in step:
            continue
        if (job_id, step.get("name"), step["if"]) not in STEP_IF_ALLOWLIST:
            problems.append(f"{prefix} {label} if: not on the reviewed allowlist: {step['if']!r}")
            continue
        same_name = sum(1 for other in steps if isinstance(other, dict) and other.get("name") == step["name"])
        if same_name != 1:
            problems.append(f"{prefix} {label} allowlisted step name appears {same_name} times")
        if not isinstance(uses, str) or not uses.startswith(ALLOWLISTED_STEP_USES):
            problems.append(f"{prefix} {label} allowlisted step must use {ALLOWLISTED_STEP_USES}, got {uses!r}")
        if "run" in step:
            problems.append(f"{prefix} {label} allowlisted step must not have run:")
    return problems


def _load_problem(path_name: str, text: str) -> tuple[dict[Any, Any] | None, list[str]]:
    try:
        doc = load_workflow(text)
        workflow_triggers(doc)
    except (yaml.YAMLError, ValueError) as exc:
        return None, [f"{path_name} cannot be loaded: {exc}"]
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return None, [f"{path_name} jobs: is not a non-empty mapping"]
    problems = []
    for key in doc:
        if key == "defaults":
            problems.append(f"{path_name} sets workflow-level defaults: (run.shell can neutralise every run step)")
        elif isinstance(key, str) and key.lower() == "defaults":
            problems.append(f"{path_name} has a case variant of a watched key: {key!r}")
    return doc, problems


def _needs(job: Any) -> list[Any]:
    needs = job.get("needs") if isinstance(job, dict) else None
    if isinstance(needs, str):
        return [needs]
    return list(needs) if isinstance(needs, list) else []


def ci_problems(text: str) -> list[str]:
    doc, problems = _load_problem("ci.yml", text)
    if doc is None:
        return problems
    jobs = doc["jobs"]
    if AGGREGATE_JOB not in jobs:
        return [f'ci.yml aggregate job "{AGGREGATE_JOB}" not found']

    problems.extend(trigger_problems("ci.yml", workflow_triggers(doc), CI_TRIGGER_CONTRACT))
    needs = _needs(jobs[AGGREGATE_JOB])
    if sorted(map(str, needs)) != sorted(ALL_JOBS):
        problems.append(f"ci.yml {AGGREGATE_JOB} needs {needs!r} must be exactly {sorted(ALL_JOBS)!r}")

    for job_id in [*needs, AGGREGATE_JOB]:
        if job_id not in jobs:
            problems.append(f'ci.yml required job "{job_id}" not found')
            continue
        allowed_if = AGGREGATE_IF if job_id == AGGREGATE_JOB else None
        problems.extend(job_problems(job_id, jobs[job_id], allowed_if=allowed_if))
    return problems


def acceptance_trigger_problems(triggers: Any) -> list[str]:
    """Check review-acceptance.yml's parsed ``on:`` block against its contract.

    Uses the same branches and types as TRIGGER_CONTRACTS['review-acceptance.yml']
    in ci-job-consistency.cjs, but is stricter than the Node detector: types must
    match exactly (Node only requires that they include the contract's types and
    accepts extras), and a null ``pull_request:`` is rejected (Node reads it as an
    empty spec). Where the two disagree, this guard wins. It works on the
    PyYAML-parsed mapping, so a quoted key (``"paths":``) is the same key as a
    bare one and cannot hide a filter (review pass 2).
    """
    return trigger_problems("review-acceptance.yml", triggers, ACCEPTANCE_TRIGGER_CONTRACT)


def trigger_problems(path_name: str, triggers: Any, contracts: dict[str, dict[str, tuple[str, ...]]]) -> list[str]:
    """Check a workflow's parsed ``on:`` block against a trigger contract.

    ``contracts`` maps each allowed trigger to its required keys and their exact
    values. Any other trigger, any other key, and any filter key are problems.
    """
    prefix = f"{path_name} on:"
    if not isinstance(triggers, dict):
        return [f"{prefix} must be a mapping with exactly {sorted(contracts)!r}"]
    problems = []
    if set(triggers) != set(contracts):
        problems.append(f"{prefix} triggers {list(triggers)!r} must be exactly {sorted(contracts)!r}")
    for name, contract in contracts.items():
        if name not in triggers:
            continue
        spec = triggers[name]
        where = f"{prefix} {name}"
        if not isinstance(spec, dict):
            problems.append(f"{where} must be a mapping, got {spec!r}")
            continue
        for key in spec:
            if key in TRIGGER_FILTER_KEYS:
                problems.append(f"{where}.{key} lets a PR skip required jobs")
            elif key not in contract:
                problems.append(f"{where} has unsupported key {key!r}")
        for key, expected in contract.items():
            value = spec.get(key)
            exact = isinstance(value, list) and len(value) == len(expected)
            if not exact or sorted(map(str, value)) != sorted(expected):
                problems.append(f"{where}.{key} {value!r} must be exactly {list(expected)!r}")
    return problems


def acceptance_problems(text: str) -> list[str]:
    doc, problems = _load_problem("review-acceptance.yml", text)
    if doc is None:
        return problems
    problems.extend(acceptance_trigger_problems(workflow_triggers(doc)))
    if set(doc["jobs"]) != ACCEPTANCE_JOBS:
        problems.append(f"review-acceptance.yml jobs {list(doc['jobs'])!r} must be exactly {sorted(ACCEPTANCE_JOBS)!r}")
    for job_id, job in doc["jobs"].items():
        problems.extend(job_problems(str(job_id), job, allowed_if=None))
    return problems


def workflow_texts() -> dict[str, str]:
    """Every workflow file in .github/workflows, keyed by file name."""
    paths = [*WORKFLOWS_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yaml")]
    return {path.name: path.read_text() for path in sorted(paths)}


def required_check_name_problems(texts: dict[str, str]) -> list[str]:
    """Each required check name must be published by exactly its owning job.

    A job's check-run name is its ``name:``, or its id when it has no name.
    Names are compared after trimming and case-folding, so a near spelling
    also counts. A workflow that cannot be loaded fails the scan closed.
    """
    problems: list[str] = []
    publishers: dict[str, list[tuple[str, str]]] = {name: [] for name in REQUIRED_CHECK_OWNERS}
    wanted = {name.strip().casefold(): name for name in REQUIRED_CHECK_OWNERS}
    for filename, text in sorted(texts.items()):
        try:
            doc = load_workflow(text)
        except (yaml.YAMLError, ValueError) as exc:
            problems.append(f"{filename} cannot be loaded: {exc}")
            continue
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            name = job.get("name") if isinstance(job, dict) and "name" in job else job_id
            check = wanted.get(str(name).strip().casefold())
            if check is not None:
                publishers[check].append((filename, str(job_id)))
    for check, owner in REQUIRED_CHECK_OWNERS.items():
        if publishers[check] != [owner]:
            found = ", ".join(f"{f}:{j}" for f, j in publishers[check]) or "none"
            problems.append(f'check name "{check}" must be published only by {owner[0]}:{owner[1]}, found {found}')
    return problems


def _mutate(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"mutation anchor must occur exactly once: {old!r}"
    return text.replace(old, new)


# --- the real workflows pass ------------------------------------------------


def test_real_ci_workflow_has_no_skip_path() -> None:
    assert ci_problems(CI_TEXT) == []


def test_real_acceptance_workflow_has_no_skip_path() -> None:
    assert acceptance_problems(ACCEPTANCE_TEXT) == []


def test_bare_on_key_loads_as_true_and_is_still_found() -> None:
    doc = load_workflow(CI_TEXT)
    assert True in doc and "on" not in doc
    assert "pull_request" in workflow_triggers(doc)
    quoted = load_workflow(_mutate(ACCEPTANCE_TEXT, "\non:\n", '\n"on":\n'))
    assert "pull_request" in workflow_triggers(quoted)


# --- review pass 2: review-acceptance.yml's trigger contract -----------------

ACCEPTANCE_BRANCHES = "    branches: [main]\n"


@pytest.mark.parametrize(
    "key",
    ["paths", '"paths"', "'paths'", "paths-ignore", '"paths-ignore"', "branches-ignore", "'tags-ignore'"],
)
def test_acceptance_trigger_filter_in_any_spelling_is_rejected(key: str) -> None:
    mutated = _mutate(ACCEPTANCE_TEXT, ACCEPTANCE_BRANCHES, f'{ACCEPTANCE_BRANCHES}    {key}: ["triggarr/**"]\n')
    bare = key.strip("\"'")
    assert f"review-acceptance.yml on: pull_request.{bare} lets a PR skip required jobs" in acceptance_problems(
        mutated
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (ACCEPTANCE_BRANCHES, "    branches: [main, release]\n"),
        (ACCEPTANCE_BRANCHES, ""),
        (", ready_for_review]", "]"),
        ("    types: [opened, synchronize, reopened, ready_for_review]\n", ""),
        (", ready_for_review]", ", ready_for_review, closed]"),
    ],
)
def test_acceptance_trigger_branches_and_types_must_be_exact(old: str, new: str) -> None:
    problems = acceptance_problems(_mutate(ACCEPTANCE_TEXT, old, new))
    assert any(p.startswith("review-acceptance.yml on: pull_request.") and "must be exactly" in p for p in problems)


def test_acceptance_extra_trigger_or_unknown_key_is_rejected() -> None:
    extra = _mutate(ACCEPTANCE_TEXT, "\non:\n", "\non:\n  workflow_dispatch:\n")
    assert any(p.startswith("review-acceptance.yml on: triggers") for p in acceptance_problems(extra))
    renamed = _mutate(ACCEPTANCE_TEXT, "  pull_request:\n", "  pull_request_target:\n")
    assert any(p.startswith("review-acceptance.yml on: triggers") for p in acceptance_problems(renamed))
    unknown = _mutate(ACCEPTANCE_TEXT, ACCEPTANCE_BRANCHES, f"{ACCEPTANCE_BRANCHES}    branch: [dev]\n")
    assert "review-acceptance.yml on: pull_request has unsupported key 'branch'" in acceptance_problems(unknown)


# --- review pass 3: ci.yml's trigger contract ---------------------------------

CI_PUSH = "  push:\n    branches: [main]\n"
CI_PULL_REQUEST = "  pull_request:\n    branches: [main]\n"


def test_real_ci_workflow_triggers_match_the_contract() -> None:
    assert trigger_problems("ci.yml", workflow_triggers(load_workflow(CI_TEXT)), CI_TRIGGER_CONTRACT) == []


@pytest.mark.parametrize(("anchor", "trigger"), [(CI_PUSH, "push"), (CI_PULL_REQUEST, "pull_request")])
@pytest.mark.parametrize("key", ["paths", '"paths"', "'paths'", "paths-ignore", "branches-ignore", '"tags-ignore"'])
def test_ci_trigger_filter_in_any_spelling_is_rejected(anchor: str, trigger: str, key: str) -> None:
    mutated = _mutate(CI_TEXT, anchor, f'{anchor}    {key}: ["triggarr/**"]\n')
    bare = key.strip("\"'")
    assert f"ci.yml on: {trigger}.{bare} lets a PR skip required jobs" in ci_problems(mutated)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (CI_PUSH, "  push:\n    branches: [main, dev]\n", "ci.yml on: push.branches"),
        (CI_PULL_REQUEST, "  pull_request:\n", "ci.yml on: pull_request"),
        (CI_PULL_REQUEST, f"{CI_PULL_REQUEST}    types: [opened]\n", "ci.yml on: pull_request has unsupported key"),
        (CI_PUSH, "", "ci.yml on: triggers"),
        (CI_PUSH, f"{CI_PUSH}  workflow_dispatch:\n", "ci.yml on: triggers"),
    ],
)
def test_ci_trigger_contract_must_be_exact(old: str, new: str, expected: str) -> None:
    assert any(p.startswith(expected) for p in ci_problems(_mutate(CI_TEXT, old, new)))


# --- CR-01: continue-on-error in any spelling --------------------------------

FAIL_STEP = "      - name: Fail if tests failed\n"
CI_READY_NAME = "    name: CI ready\n"
ACCEPTANCE_NAME = "    name: Review acceptance\n"


@pytest.mark.parametrize(
    "key_line",
    [
        '"continue-on-error": true',
        "'continue-on-error': true",
        '"continue-on-erro\\x72": true',
        '"continue\\u002Don-error": true',
        "continue-on-error: ${{ true }}",
        "continue-on-error: false",
        "continue-on-error : true",
    ],
)
def test_step_continue_on_error_in_any_spelling_is_rejected(key_line: str) -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f"{FAIL_STEP}        {key_line}\n")
    assert 'required job "test" step 10 "Fail if tests failed" sets continue-on-error' in ci_problems(mutated)


@pytest.mark.parametrize("key_line", ["'continue-on-error': true", '"continue-on-erro\\x72": true'])
def test_aggregate_job_continue_on_error_is_rejected(key_line: str) -> None:
    mutated = _mutate(CI_TEXT, CI_READY_NAME, f"{CI_READY_NAME}    {key_line}\n")
    assert 'required job "ci-ready" sets continue-on-error' in ci_problems(mutated)


def test_acceptance_job_continue_on_error_is_rejected() -> None:
    mutated = _mutate(ACCEPTANCE_TEXT, ACCEPTANCE_NAME, f"{ACCEPTANCE_NAME}    'continue-on-error': true\n")
    assert 'required job "acceptance" sets continue-on-error' in acceptance_problems(mutated)


# --- CR-01: job-level and step-level if in any spelling -----------------------

LINT_HEADER = "  lint:\n"


@pytest.mark.parametrize(
    "if_line",
    ["if : false", "\"if\": github.run_attempt == '0'", "if: !!str false", "if:\n      github.run_attempt == '0'"],
)
def test_required_job_level_if_is_rejected(if_line: str) -> None:
    mutated = _mutate(CI_TEXT, LINT_HEADER, f"{LINT_HEADER}    {if_line}\n")
    assert any(p.startswith('required job "lint" has a job-level if:') for p in ci_problems(mutated))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("    if: always()\n    needs: [test", "    if: ${{ always() }}\n    needs: [test"),
        ("    if: always()\n    needs: [test", "    if: success() || failure()\n    needs: [test"),
        ("    if: always()\n    needs: [test", "    needs: [test"),
    ],
)
def test_aggregate_if_other_than_always_is_rejected(old: str, new: str) -> None:
    problems = ci_problems(_mutate(CI_TEXT, old, new))
    assert any(p.startswith('required job "ci-ready" if: must be exactly always()') for p in problems)


def test_acceptance_job_level_if_is_rejected() -> None:
    mutated = _mutate(ACCEPTANCE_TEXT, ACCEPTANCE_NAME, f'{ACCEPTANCE_NAME}    "if" : false\n')
    assert 'required job "acceptance" has a job-level if: False' in acceptance_problems(mutated)


@pytest.mark.parametrize(
    "replacement",
    [
        f"{FAIL_STEP}        if : github.run_attempt == '0'\n",
        f"{FAIL_STEP}        \"i\\x66\": github.run_attempt == '0'\n",
        "      -\n        name: Fail if tests failed\n        if : github.run_attempt == '0'\n",
        "      - {name: Skipper, if: \"github.run_attempt == '0'\", run: exit 0}\n" + FAIL_STEP,
        "      - {name: Skipper,\n         if: \"github.run_attempt == '0'\",\n         run: exit 0}\n" + FAIL_STEP,
    ],
)
def test_step_if_in_any_spelling_is_rejected(replacement: str) -> None:
    problems = ci_problems(_mutate(CI_TEXT, FAIL_STEP, replacement))
    assert any(p.startswith('required job "test" step') and "if: not on the reviewed allowlist" in p for p in problems)


GATE_STEP = "      - name: Require every mandatory job to succeed\n"


def test_step_if_from_merge_key_is_rejected() -> None:
    merged = "      - <<: {if: \"github.run_attempt == '0'\"}\n        name: Require every mandatory job to succeed\n"
    mutated = _mutate(CI_TEXT, GATE_STEP, merged)
    assert any(p.startswith('required job "ci-ready" step 0') and "allowlist" in p for p in ci_problems(mutated))


def test_step_if_from_anchor_and_alias_is_rejected() -> None:
    # The anchor sits in an unrelated job's env; the alias pulls its value into
    # the aggregate's only step.
    anchor = "      SKIP: &skip \"github.run_attempt == '0'\"\n      TRIVY_VERSION: "
    anchored = _mutate(CI_TEXT, "      TRIVY_VERSION: ", anchor)
    mutated = _mutate(anchored, GATE_STEP, f"{GATE_STEP}        if: *skip\n")
    assert any(p.startswith('required job "ci-ready" step 0') and "allowlist" in p for p in ci_problems(mutated))


def test_anchored_step_alias_reused_in_required_job_is_rejected() -> None:
    # The anchored step lives in the test job; the alias reuses it in ci-ready.
    noop = '      - &noop\n        name: Noop\n        if: "false"\n        run: exit 0\n'
    anchored = _mutate(CI_TEXT, FAIL_STEP, f"{noop}{FAIL_STEP}")
    mutated = _mutate(anchored, GATE_STEP, f"      - *noop\n{GATE_STEP}")
    problems = ci_problems(mutated)
    assert any(p.startswith('required job "test" step 10 "Noop"') for p in problems)
    assert any(p.startswith('required job "ci-ready" step 0 "Noop"') for p in problems)


def test_duplicate_if_key_cannot_hide_the_first_value() -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f'{FAIL_STEP}        if: "false"\n        if: always()\n')
    problems = ci_problems(mutated)
    assert len(problems) == 1
    assert problems[0].startswith("ci.yml cannot be loaded:") and "duplicate key 'if'" in problems[0]


def test_allowlisted_name_with_a_different_condition_is_rejected() -> None:
    mutated = _mutate(
        CI_TEXT,
        "      - name: Upload test evidence\n        if: always()\n",
        "      - name: Upload test evidence\n        if: success()\n",
    )
    assert any("if: not on the reviewed allowlist: 'success()'" in p for p in ci_problems(mutated))


# --- CR-01 (iteration 4): shell: and defaults: overrides ---------------------
# A custom shell template such as ``true {0}`` runs /usr/bin/true instead of
# the script, so a step "succeeds" without running. No workflow uses shell: or
# defaults: today, so every placement is forbidden.

SHELL_OVERRIDE = "true {0}"
GATE_ENV = "        env:\n          RESULTS: ${{ toJSON(needs) }}\n"


def test_ci_ready_job_level_defaults_shell_is_rejected() -> None:
    defaults = f"    defaults:\n      run:\n        shell: {SHELL_OVERRIDE}\n"
    mutated = _mutate(CI_TEXT, CI_READY_NAME, f"{CI_READY_NAME}{defaults}")
    assert any(p.startswith('required job "ci-ready" sets defaults:') for p in ci_problems(mutated))


def test_ci_ready_gate_step_shell_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, GATE_ENV, f"{GATE_ENV}        shell: {SHELL_OVERRIDE}\n")
    assert any(
        p.startswith('required job "ci-ready" step 0 "Require every mandatory job to succeed" sets shell:')
        for p in ci_problems(mutated)
    )


def test_fail_if_tests_failed_step_shell_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f"{FAIL_STEP}        shell: {SHELL_OVERRIDE}\n")
    assert any(
        p.startswith('required job "test" step 10 "Fail if tests failed" sets shell:') for p in ci_problems(mutated)
    )


@pytest.mark.parametrize("shell", ["bash", "sh"])
def test_even_a_builtin_step_shell_is_rejected(shell: str) -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f"{FAIL_STEP}        shell: {shell}\n")
    problems = ci_problems(mutated)
    assert any(p.startswith('required job "test" step 10 "Fail if tests failed" sets shell:') for p in problems)


def test_ci_workflow_level_defaults_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, "\njobs:\n", f"\ndefaults:\n  run:\n    shell: {SHELL_OVERRIDE}\n\njobs:\n")
    assert any(p.startswith("ci.yml sets workflow-level defaults:") for p in ci_problems(mutated))


def test_acceptance_workflow_level_defaults_is_rejected() -> None:
    mutated = _mutate(ACCEPTANCE_TEXT, "\njobs:\n", f"\ndefaults:\n  run:\n    shell: {SHELL_OVERRIDE}\njobs:\n")
    problems = acceptance_problems(mutated)
    assert any(p.startswith("review-acceptance.yml sets workflow-level defaults:") for p in problems)


def test_acceptance_job_defaults_and_step_shell_are_rejected() -> None:
    with_defaults = _mutate(
        ACCEPTANCE_TEXT, ACCEPTANCE_NAME, f"{ACCEPTANCE_NAME}    defaults:\n      run:\n        shell: bash\n"
    )
    assert any(p.startswith('required job "acceptance" sets defaults:') for p in acceptance_problems(with_defaults))
    with_shell = ACCEPTANCE_TEXT + f"        shell: {SHELL_OVERRIDE}\n"
    assert any(
        p.startswith('required job "acceptance" step') and "sets shell:" in p for p in acceptance_problems(with_shell)
    )


@pytest.mark.parametrize("key", ["Shell", "SHELL"])
def test_case_variant_of_step_shell_is_rejected(key: str) -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f"{FAIL_STEP}        {key}: {SHELL_OVERRIDE}\n")
    assert any("case variant of a watched key" in p for p in ci_problems(mutated))


def test_case_variant_of_job_defaults_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, CI_READY_NAME, f"{CI_READY_NAME}    Defaults:\n      run:\n        shell: bash\n")
    assert any("case variant of a watched key" in p for p in ci_problems(mutated))


def test_case_variant_of_workflow_defaults_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, "\njobs:\n", "\nDefaults:\n  run:\n    shell: bash\n\njobs:\n")
    assert any(p.startswith("ci.yml has a case variant of a watched key") for p in ci_problems(mutated))


# --- CR-02: comments and header spellings cannot hide a step or a job --------


def test_column_zero_comment_cannot_hide_a_ci_ready_step_if() -> None:
    mutated = CI_TEXT + "# reviewed\n        if: github.run_attempt == '0'\n"
    assert ci_problems(mutated) == [
        'required job "ci-ready" step 0 "Require every mandatory job to succeed" '
        "if: not on the reviewed allowlist: \"github.run_attempt == '0'\""
    ]


def test_column_zero_comment_cannot_hide_a_ci_ready_continue_on_error() -> None:
    mutated = CI_TEXT + "# reviewed\n        continue-on-error: true\n"
    assert any(
        p.startswith('required job "ci-ready" step 0') and "continue-on-error" in p for p in ci_problems(mutated)
    )


def test_column_zero_comment_cannot_hide_the_acceptance_gate_step_if() -> None:
    mutated = ACCEPTANCE_TEXT + "# end of gate\n        if: github.run_attempt == '0'\n"
    assert acceptance_problems(mutated) == [
        'required job "acceptance" step 1 (unnamed) if: not on the reviewed allowlist: "github.run_attempt == \'0\'"'
    ]


ACCEPTANCE_HEADER = "  acceptance:\n"


@pytest.mark.parametrize(
    "header",
    [
        "  acceptance: # gate\n",
        '  "acceptance":\n',
        "  'acceptance' :\n",
        "  ? acceptance\n  :\n",
    ],
)
def test_acceptance_header_spelling_cannot_hide_a_job_level_if(header: str) -> None:
    mutated = _mutate(ACCEPTANCE_TEXT, ACCEPTANCE_HEADER, f"{header}    if: github.run_attempt == '0'\n")
    assert acceptance_problems(mutated) == [
        'required job "acceptance" has a job-level if: "github.run_attempt == \'0\'"'
    ]


def test_reindented_jobs_block_cannot_hide_a_job_level_if() -> None:
    head, sep, body = ACCEPTANCE_TEXT.partition("\njobs:\n")
    reindented = "".join(f"  {line}" if line.strip() else line for line in body.splitlines(keepends=True))
    mutated = _mutate(head + sep + reindented, "    acceptance:\n", '    acceptance:\n      if: "false"\n')
    assert acceptance_problems(mutated) == ["required job \"acceptance\" has a job-level if: 'false'"]


def test_reindented_real_jobs_block_still_passes() -> None:
    head, sep, body = ACCEPTANCE_TEXT.partition("\njobs:\n")
    reindented = "".join(f"  {line}" if line.strip() else line for line in body.splitlines(keepends=True))
    assert acceptance_problems(head + sep + reindented) == []


def test_job_dropped_from_ci_ready_needs_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, "browser-e2e, os-scan, actionlint]", "browser-e2e, actionlint]")
    problems = ci_problems(mutated)
    assert len(problems) == 1 and problems[0].startswith("ci.yml ci-ready needs")


def test_ci_ready_needs_as_a_single_string_is_rejected() -> None:
    old = "    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint]\n"
    problems = ci_problems(_mutate(CI_TEXT, old, "    needs: test\n"))
    assert any(p.startswith("ci.yml ci-ready needs") for p in problems)


def test_acceptance_job_renamed_or_added_is_rejected() -> None:
    renamed = _mutate(ACCEPTANCE_TEXT, ACCEPTANCE_HEADER, "  acceptance-gate:\n")
    assert any(p.startswith("review-acceptance.yml jobs") for p in acceptance_problems(renamed))
    added = ACCEPTANCE_TEXT + "  extra:\n    runs-on: ubuntu-latest\n    steps:\n      - run: exit 0\n"
    assert any(p.startswith("review-acceptance.yml jobs") for p in acceptance_problems(added))


def test_missing_aggregate_job_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, "\n  ci-ready:\n", "\n  ci-ready-renamed:\n")
    assert ci_problems(mutated) == ['ci.yml aggregate job "ci-ready" not found']


@pytest.mark.parametrize("key", ["IF", "If", "Continue-On-Error", "USES"])
def test_case_variant_of_a_watched_step_key_is_rejected(key: str) -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f'{FAIL_STEP}        {key}: "false"\n')
    assert any("case variant of a watched key" in p for p in ci_problems(mutated))


def test_non_string_step_key_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f'{FAIL_STEP}        ? [if]\n        : "false"\n')
    problems = ci_problems(mutated)
    assert problems and all("cannot be loaded" in p or "non-string key" in p for p in problems)


# --- SA-05 (forbidden today): reusable workflows and local actions -----------


def test_required_job_calling_a_reusable_workflow_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, LINT_HEADER, f"{LINT_HEADER}    uses: ./.github/workflows/lint.yml\n")
    assert any(p.startswith('required job "lint" calls a reusable workflow') for p in ci_problems(mutated))


@pytest.mark.parametrize("uses", ["./.github/actions/setup", "../outside", "/abs/path"])
def test_required_step_using_a_local_action_is_rejected(uses: str) -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, f"      - uses: {uses}\n{FAIL_STEP}")
    assert any("uses a local or unreadable action" in p for p in ci_problems(mutated))


def test_acceptance_step_using_a_local_action_is_rejected() -> None:
    mutated = ACCEPTANCE_TEXT + "      - uses: ./.github/actions/gate\n"
    assert any("uses a local or unreadable action" in p for p in acceptance_problems(mutated))


# --- WR-01: an allowlisted (name, condition) pins the evidence upload step ----

BROWSER_GATE = "      - name: Require a complete browser-suite result\n"
BROWSER_UPLOAD = "      - name: Upload browser failure evidence\n"
BROWSER_IF = (
    "        if: >-\n"
    "          failure() &&\n"
    "          hashFiles('e2e-artifacts/credential/scan-complete.json') != '' &&\n"
    "          hashFiles('e2e-artifacts/pages/scan-complete.json') != ''\n"
)


def test_gate_renamed_to_the_allowlisted_upload_with_the_same_condition_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, BROWSER_GATE, BROWSER_UPLOAD + BROWSER_IF)
    problems = ci_problems(mutated)
    assert any("allowlisted step name appears 2 times" in p for p in problems)
    assert any("allowlisted step must not have run:" in p for p in problems)


def test_gate_renamed_to_the_allowlisted_upload_with_a_different_condition_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, BROWSER_GATE, BROWSER_UPLOAD + "        if: always()\n")
    assert any("if: not on the reviewed allowlist: 'always()'" in p for p in ci_problems(mutated))


def test_gate_renamed_and_real_upload_renamed_away_is_rejected() -> None:
    # The gate takes the upload's name and condition; the real upload is
    # renamed and loses its condition, so the name is unique again.
    swapped = _mutate(CI_TEXT, BROWSER_UPLOAD + BROWSER_IF, "      - name: Upload browser evidence\n")
    mutated = _mutate(swapped, BROWSER_GATE, BROWSER_UPLOAD + BROWSER_IF)
    problems = ci_problems(mutated)
    assert any("allowlisted step must use actions/upload-artifact@" in p for p in problems)
    assert any("allowlisted step must not have run:" in p for p in problems)


def test_test_job_gate_renamed_to_the_allowlisted_upload_is_rejected() -> None:
    mutated = _mutate(CI_TEXT, FAIL_STEP, "      - name: Upload test evidence\n        if: always()\n")
    assert any("allowlisted step name appears 2 times" in p for p in ci_problems(mutated))


# --- WR-03 (iteration 4): a required check name is published by one job only --
# Readiness picks the newest check run by name, and every workflow posts as the
# GitHub Actions app, so a second job named "CI ready" in any workflow file
# could stand in for the real one.

MIRROR_WORKFLOW = """name: Mirror
on:
  pull_request:
    branches: [main]
jobs:
  mirror:
    name: CI ready
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""


def test_real_workflows_publish_each_required_check_name_once() -> None:
    assert required_check_name_problems(workflow_texts()) == []


def test_workflow_scan_covers_every_workflow_file() -> None:
    assert {"ci.yml", "review-acceptance.yml", "release.yml"} <= set(workflow_texts())


@pytest.mark.parametrize("filename", ["mirror.yml", "mirror.yaml"])
def test_ci_ready_job_in_another_workflow_is_rejected(filename: str) -> None:
    texts = {**workflow_texts(), filename: MIRROR_WORKFLOW}
    problems = required_check_name_problems(texts)
    assert any(p.startswith('check name "CI ready"') and f"{filename}:mirror" in p for p in problems)


def test_unnamed_job_whose_id_is_the_check_name_is_rejected() -> None:
    mirror = MIRROR_WORKFLOW.replace("  mirror:\n    name: CI ready\n", '  "CI ready":\n')
    texts = {**workflow_texts(), "mirror.yml": mirror}
    assert any(p.startswith('check name "CI ready"') for p in required_check_name_problems(texts))


def test_second_ci_ready_name_inside_ci_yml_is_rejected() -> None:
    texts = {**workflow_texts(), "ci.yml": _mutate(CI_TEXT, "  lint:\n", "  lint:\n    name: CI ready\n")}
    assert any(p.startswith('check name "CI ready"') for p in required_check_name_problems(texts))


def test_ci_ready_name_moved_off_the_aggregate_job_is_rejected() -> None:
    texts = {**workflow_texts(), "ci.yml": _mutate(CI_TEXT, CI_READY_NAME, "    name: CI gate\n")}
    assert any(p.startswith('check name "CI ready"') for p in required_check_name_problems(texts))


def test_review_acceptance_job_in_another_workflow_is_rejected() -> None:
    mirror = MIRROR_WORKFLOW.replace("name: CI ready", "name: Review acceptance")
    texts = {**workflow_texts(), "mirror.yml": mirror}
    assert any(p.startswith('check name "Review acceptance"') for p in required_check_name_problems(texts))


def test_unloadable_workflow_fails_the_scan_closed() -> None:
    texts = {**workflow_texts(), "broken.yml": "jobs: [\n"}
    assert any(p.startswith("broken.yml cannot be loaded") for p in required_check_name_problems(texts))
