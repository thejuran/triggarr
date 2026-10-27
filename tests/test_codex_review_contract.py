"""Drift guard for the Codex adversarial review contract and its output schema."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CONTRACT = REPO_ROOT / "docs" / "codex-adversarial-review-contract.md"
SCHEMA = REPO_ROOT / ".claude" / "schemas" / "codex-review-findings.schema.json"

TOP_LEVEL_FIELDS = [
    "schema_version",
    "inspected_head_sha",
    "inspected_base_sha",
    "pr_url",
    "scope",
    "verdict",
    "summary",
    "coverage",
    "exclusions",
    "commands_run",
    "findings",
    "limitations",
    "review_complete",
    "incomplete_reasons",
]

FINDING_FIELDS = [
    "id",
    "severity",
    "title",
    "file",
    "line_start",
    "line_end",
    "trigger",
    "execution_path",
    "consequence",
    "evidence",
    "suggested_fix",
    "reproduced",
    "reproduction_command",
    "hypothesis",
]


def _load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _extract_fixed_prompt() -> str:
    """Return the first fenced block after the '## Fixed prompt (version 6)' heading."""
    text = CONTRACT.read_text(encoding="utf-8")
    heading = "## Fixed prompt (version 6)"
    idx = text.index(heading)
    after = text[idx + len(heading) :]
    match = re.search(r"```(?:[^\n]*)\n(.*?)```", after, re.DOTALL)
    assert match, "no fenced block found after the fixed-prompt heading"
    return match.group(1)


def _walk_objects(node):
    """Yield every object-typed schema node, including nested items/properties."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from _walk_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_objects(item)


def test_schema_top_level_fields() -> None:
    schema = _load_schema()
    assert sorted(schema["required"]) == sorted(TOP_LEVEL_FIELDS)
    assert schema["additionalProperties"] is False


# Durable Codex completeness (owner 2026-10-22): schema v2 states
# completeness structurally instead of in free text.
def test_schema_version_two_completeness_fields() -> None:
    schema = _load_schema()
    props = schema["properties"]
    assert props["schema_version"]["enum"] == ["2"]
    assert props["review_complete"]["type"] == "boolean"
    assert props["incomplete_reasons"]["type"] == "array"
    assert props["incomplete_reasons"]["items"]["type"] == "string"
    assert props["limitations"]["type"] == "array"


def test_schema_finding_fields() -> None:
    schema = _load_schema()
    finding_schema = schema["properties"]["findings"]["items"]
    assert sorted(finding_schema["required"]) == sorted(FINDING_FIELDS)
    assert finding_schema["additionalProperties"] is False
    assert finding_schema["properties"]["severity"]["enum"] == ["critical", "high", "medium", "low"]


def test_schema_every_object_is_strict() -> None:
    schema = _load_schema()
    for node in _walk_objects(schema):
        properties = node.get("properties", {})
        assert node.get("additionalProperties") is False, f"object node missing additionalProperties:false: {node}"
        assert sorted(node.get("required", [])) == sorted(properties.keys()), (
            f"object node's required does not list every property: {node}"
        )


def test_nullable_fields() -> None:
    schema = _load_schema()
    finding_props = schema["properties"]["findings"]["items"]["properties"]
    for field in ("line_start", "line_end", "reproduction_command", "hypothesis"):
        field_type = finding_props[field]["type"]
        assert isinstance(field_type, list) and "null" in field_type, f"{field} must allow null"

    commands_run_item_props = schema["properties"]["commands_run"]["items"]["properties"]
    exit_code_type = commands_run_item_props["exit_code"]["type"]
    assert isinstance(exit_code_type, list) and "null" in exit_code_type


def test_contract_placeholders() -> None:
    prompt = _extract_fixed_prompt()
    placeholders = set(re.findall(r"\{\{(\w+)\}\}", prompt))
    assert placeholders == {"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "TEST_EVIDENCE"}


def test_contract_read_only() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "--sandbox read-only" in text
    for forbidden in ("workspace-write", "danger-full-access", "--dangerously"):
        assert forbidden not in text


def test_contract_references_schema_path() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert ".claude/schemas/codex-review-findings.schema.json" in text
    assert SCHEMA.exists()


# WR-05: template version 2 confines Codex's reads and adds a second secret
# check (32-character lowercase hex, the Radarr/Sonarr API-key shape) before
# raw output is committed.
_HEX32_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")


def test_contract_template_version_six() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "Template version: 6." in text
    for old in (1, 2, 3, 4, 5):
        assert f"## Fixed prompt (version {old})" not in text


# D-17 (Phase 85): phase plan files are agent instructions BM executors
# follow, so they are brought into Codex review scope through a second,
# positive diff rather than by narrowing the blanket .planning/**/*.md
# exclusion (a git pathspec cannot re-include a path an exclude matches).
def test_prompt_includes_plan_file_diff() -> None:
    prompt = _extract_fixed_prompt()
    assert "git diff {{BASE_SHA}}..{{HEAD_SHA}} -- ':(glob).planning/**/*-PLAN.md'" in prompt
    assert "agent instructions" in prompt.lower()
    assert "review scope" in prompt.lower()


def test_contract_prompt_confines_reads_to_working_copy() -> None:
    prompt = _extract_fixed_prompt()
    assert "Read only files inside this working copy" in prompt


def _storage_section() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## Raw output storage")
    end = text.index("## Failure rule", start)
    return text[start:end]


def test_contract_requires_hex_key_scan_before_commit() -> None:
    section = _storage_section()
    assert "gitleaks detect --no-git --source" in section
    assert "[0-9a-f]{32}" in section
    assert "blocks the commit" in section
    # The scan lists file names only, so a hit never prints the key itself.
    assert "grep -rlE" in section


def test_contract_embeds_no_hex_key() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert not _HEX32_RE.search(text)


def _failure_rule_section() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## Failure rule")
    return text[start:]


# IN-06: attempt 2 is the last *automatic* retry; any attempt beyond 2 only
# happens on the owner's explicit choice, and is recorded with its own number.
def test_failure_rule_states_attempt_two_is_last_automatic_retry() -> None:
    section = _failure_rule_section()
    assert "attempt 2 is the last automatic retry" in section.lower()


def test_failure_rule_states_later_attempts_need_owner_choice() -> None:
    section = _failure_rule_section()
    assert "owner" in section.lower()
    assert "recorded" in section.lower() and "attempt number" in section.lower()


# Durable Codex completeness (owner 2026-10-22): template version 3 scopes the
# diff by rule, hands Codex harness-produced test evidence, and asks for
# completeness in the structured fields.
# Owner-approved round 3 (bm:dbe1b7f56bdd:WR-01, template version 5): planning
# markdown, raw transcripts and generated review artifacts are out of review
# scope; .planning/config.json and other non-markdown, non-codex planning
# files stay in it. Planning markdown is background Codex may read on demand.
EXCLUDE_PATHSPECS = (
    "':(exclude,glob).planning/**/codex/**'",
    "':(exclude,glob).planning/**/*.jsonl'",
    "':(exclude,glob).planning/**/*.md'",
)


def test_prompt_diff_command_excludes_review_transcripts() -> None:
    prompt = _extract_fixed_prompt()
    assert "git diff {{BASE_SHA}}..{{HEAD_SHA}} -- . " in prompt
    for pathspec in EXCLUDE_PATHSPECS:
        assert pathspec in prompt


def test_contract_documents_review_scope_exclusions() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## Review scope")
    section = text[start : text.index("\n## ", start + 1)]
    assert ".planning/**/*.md" in section
    assert ".planning/**/codex/**" in section
    assert ".planning/**/*.jsonl" in section
    assert "`.planning/config.json`" in section
    assert "stays in the review diff" in section
    assert "background" in section.lower()
    assert "not review scope" in section.lower()
    assert "Planning markdown is not excluded" not in section


def test_prompt_makes_planning_docs_background_not_scope() -> None:
    prompt = _extract_fixed_prompt()
    assert "Planning markdown stays in scope" not in prompt
    assert "planning markdown on demand as background" in prompt
    assert ".planning/config.json" in prompt
    assert "':(exclude,glob).planning/**'" not in prompt
    assert "it is not review scope" in prompt


def test_prompt_states_test_evidence_terms() -> None:
    prompt = _extract_fixed_prompt()
    assert "{{TEST_EVIDENCE}}" in prompt
    assert "produced by the harness" in prompt
    assert "{{HEAD_SHA}}" in prompt.split("{{TEST_EVIDENCE}}")[0]
    assert "evidence, not approval" in prompt
    assert "not by itself a reason to set review_complete to false" in prompt


def test_prompt_keeps_read_limit_to_the_working_copy() -> None:
    """The harness evidence now sits inside the working copy, so no exception is needed."""
    prompt = _extract_fixed_prompt()
    assert "Read only files inside this working copy; do not read any file outside it." in prompt
    assert "plus {{TEST_EVIDENCE}}" not in prompt


def test_prompt_asks_for_structured_completeness() -> None:
    prompt = _extract_fixed_prompt()
    assert "review_complete" in prompt
    assert "incomplete_reasons" in prompt
    assert "limitations" in prompt


def _invocation_section() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## Invocation")
    end = text.index("## Raw output storage", start)
    return text[start:end]


def test_invocation_uses_runner_and_checker() -> None:
    section = _invocation_section()
    assert "uv run python tests/codex_review_run.py" in section
    assert "--dry-run" in section
    assert "uv run python tests/codex_report_status.py" in section
    assert "uv run --extra dev pytest tests/ -q" in section
    assert "git worktree remove --force" in section


def test_storage_lists_pytest_evidence_file() -> None:
    assert "`.pytest.txt`" in _storage_section()
