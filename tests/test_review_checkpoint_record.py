"""Drift guards for docs/review-checkpoint-record.md (REVIEW-06, IN-06, Codex F002)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD = REPO_ROOT / "docs" / "review-checkpoint-record.md"

_GH_API_PATCH_RE = re.compile(r"gh api --method PATCH[^\n`]*")


def _read() -> str:
    return RECORD.read_text(encoding="utf-8")


# Codex F002: `gh api --method PATCH ... --field body@FILE` fails argument
# parsing with "invalid key" -- `--field`/`-F` needs `key=value` syntax, so
# a file reference must be `body=@FILE`, never `body@FILE`.
def test_comment_update_command_uses_valid_field_syntax() -> None:
    text = _read()
    match = _GH_API_PATCH_RE.search(text)
    assert match, "no `gh api --method PATCH ...` command found in the checkpoint record"
    command = match.group(0)
    assert "body@FILE" not in command, f"invalid --field syntax (missing '='): {command!r}"
    assert re.search(r"(-F|--field)\s+body=@FILE", command), f"expected 'body=@FILE' syntax, got: {command!r}"
