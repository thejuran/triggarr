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
- no reusable workflow (job-level ``uses:``) and no local action
  (``uses: ./...``), whose steps this guard cannot see (review SA-05);
- every job and step key is a string, and no key is a case variant of
  ``if``, ``continue-on-error``, ``uses`` or ``steps``.

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
CI_TEXT = CI_PATH.read_text()
ACCEPTANCE_TEXT = ACCEPTANCE_PATH.read_text()

AGGREGATE_JOB = "ci-ready"
AGGREGATE_IF = "always()"
ACCEPTANCE_JOBS = frozenset({"acceptance"})
WATCHED_KEYS = frozenset({"if", "continue-on-error", "uses", "steps"})

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


def acceptance_problems(text: str) -> list[str]:
    doc, problems = _load_problem("review-acceptance.yml", text)
    if doc is None:
        return problems
    if set(doc["jobs"]) != ACCEPTANCE_JOBS:
        problems.append(f"review-acceptance.yml jobs {list(doc['jobs'])!r} must be exactly {sorted(ACCEPTANCE_JOBS)!r}")
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
