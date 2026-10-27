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
  exact condition.

PyYAML follows YAML 1.1, so a bare ``on:`` key loads as ``True``;
``workflow_triggers`` accepts either spelling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
CI_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ACCEPTANCE_PATH = REPO_ROOT / ".github" / "workflows" / "review-acceptance.yml"
CI_TEXT = CI_PATH.read_text()
ACCEPTANCE_TEXT = ACCEPTANCE_PATH.read_text()

AGGREGATE_JOB = "ci-ready"
AGGREGATE_IF = "always()"

BROWSER_EVIDENCE_CONDITION = (
    "failure() && hashFiles('e2e-artifacts/credential/scan-complete.json') != '' && "
    "hashFiles('e2e-artifacts/pages/scan-complete.json') != ''"
)

# The only step-level conditions a required job may carry: (job, step name,
# exact condition). Mirrors STEP_IF_ALLOWLIST in ci-job-consistency.cjs.
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
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_workflow(text: str) -> dict[Any, Any]:
    doc = yaml.load(text, Loader=_StrictLoader)  # noqa: S506 -- _StrictLoader subclasses SafeLoader
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


def job_problems(job_id: str, job: Any, *, allowed_if: str | None) -> list[str]:
    """Problems that could let required job ``job_id`` be skipped or ignored."""
    prefix = f'required job "{job_id}"'
    if not isinstance(job, dict):
        return [f"{prefix} is not a mapping"]

    problems: list[str] = []
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
        if "continue-on-error" in step:
            problems.append(f"{prefix} {label} sets continue-on-error")
        if "if" in step and (job_id, step.get("name"), step["if"]) not in STEP_IF_ALLOWLIST:
            problems.append(f"{prefix} {label} if: not on the reviewed allowlist: {step['if']!r}")
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
    return doc, []


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

    for job_id in [*_needs(jobs[AGGREGATE_JOB]), AGGREGATE_JOB]:
        if job_id not in jobs:
            problems.append(f'ci.yml required job "{job_id}" not found')
            continue
        allowed_if = AGGREGATE_IF if job_id == AGGREGATE_JOB else None
        problems.extend(job_problems(job_id, jobs[job_id], allowed_if=allowed_if))
    return problems


def acceptance_problems(text: str) -> list[str]:
    doc, problems = _load_problem("review-acceptance.yml", text)
    if doc is None:
        return problems
    for job_id, job in doc["jobs"].items():
        problems.extend(job_problems(str(job_id), job, allowed_if=None))
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
