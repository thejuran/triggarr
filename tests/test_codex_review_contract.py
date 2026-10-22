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
    """Return the first fenced block after the '## Fixed prompt (version 1)' heading."""
    text = CONTRACT.read_text(encoding="utf-8")
    heading = "## Fixed prompt (version 1)"
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
    assert placeholders == {"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE"}


def test_contract_read_only() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "--sandbox read-only" in text
    for forbidden in ("workspace-write", "danger-full-access", "--dangerously"):
        assert forbidden not in text


def test_contract_references_schema_path() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert ".claude/schemas/codex-review-findings.schema.json" in text
    assert SCHEMA.exists()
