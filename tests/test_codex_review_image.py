"""Static checks of docker/codex-review/Dockerfile's pins and final-stage contents.

The review image runs Codex against an untrusted (bot/fork) PR head inside a
disposable container (D-07). These tests parse the Dockerfile as text --
no Docker daemon is required -- and pin the properties that make it safe to
use for that purpose: a digest-pinned base, a checksum-verified Codex
binary, and a final stage that contains nothing but the Codex runtime.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests import codex_review_run as runner

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE_PATH = REPO_ROOT / "docker" / "codex-review" / "Dockerfile"

_FROM_LINE_RE = re.compile(r"^FROM debian:bookworm-slim@sha256:[0-9a-f]{64}( AS \w+)?$")


def _dockerfile_text() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _first_from_start(text: str) -> int:
    match = re.search(r"^FROM ", text, re.MULTILINE)
    assert match is not None, "Dockerfile has no FROM line"
    return match.start()


def _header_comment() -> str:
    text = _dockerfile_text()
    return text[: _first_from_start(text)]


def _final_stage() -> str:
    text = _dockerfile_text()
    from_starts = [m.start() for m in re.finditer(r"^FROM ", text, re.MULTILINE)]
    assert from_starts, "Dockerfile has no FROM line"
    return text[from_starts[-1] :]


def test_from_lines_pin_base_by_digest() -> None:
    text = _dockerfile_text()
    from_lines = [line for line in text.splitlines() if line.startswith("FROM ")]
    assert len(from_lines) == 2, f"expected exactly 2 FROM lines, found {len(from_lines)}"
    for line in from_lines:
        assert _FROM_LINE_RE.match(line), f"FROM line is not a digest-pinned debian:bookworm-slim: {line!r}"


def test_codex_version_and_sha256_are_pinned() -> None:
    text = _dockerfile_text()
    assert "ARG CODEX_VERSION=0.153.4" in text
    assert "ARG CODEX_SHA256_ARM64=5cda6182bd94c3a30f2eb63a495489ebf7f691fddb14d70f48c6c1a5071b6cde" in text


def test_download_url_uses_versioned_release_path() -> None:
    text = _dockerfile_text()
    assert "releases/download/rust-v${CODEX_VERSION}/codex-aarch64-unknown-linux-musl.tar.gz" in text


def test_fetch_stage_verifies_checksum_before_extracting() -> None:
    text = _dockerfile_text()
    assert text.count("sha256sum -c") == 1
    sha_index = text.index("sha256sum -c")
    tar_index = text.index("tar -xzf")
    assert sha_index < tar_index, "checksum verification must happen before extraction"


def test_final_stage_has_no_extra_tooling() -> None:
    final_stage = _final_stage()
    for token in ("apt-get", "curl", "git", "python", "node", "pip"):
        assert token not in final_stage, f"final stage must not contain {token!r}: {final_stage!r}"


def test_final_stage_copies_only_codex_binary() -> None:
    final_stage = _final_stage()
    copy_lines = [line.strip() for line in final_stage.splitlines() if line.strip().startswith("COPY")]
    assert copy_lines == ["COPY --from=fetch /usr/local/bin/codex /usr/local/bin/codex"]


def test_final_stage_declares_required_runtime_config() -> None:
    final_stage = _final_stage()
    assert "USER 10001:10001" in final_stage
    assert "WORKDIR /work" in final_stage
    assert 'ENTRYPOINT ["codex"]' in final_stage
    assert "HOME=/home/review" in final_stage
    assert "LANG=C.UTF-8" in final_stage
    assert "CODEX_HOME=/codex-home" in final_stage
    assert re.search(
        r'LABEL org\.triggarr\.codex-review="(\$\{CODEX_VERSION\}|0\.153\.4)"',
        final_stage,
    ), "final stage must label the image with the Codex version"


def test_final_stage_creates_non_root_review_user() -> None:
    final_stage = _final_stage()
    assert re.search(r"groupadd\s+-g\s+10001\s+review\b", final_stage), "final stage must create group review:10001"
    assert re.search(
        r"useradd\s+-u\s+10001\s+-g\s+10001\b[^\n]*\breview\b", final_stage
    ), "final stage must create user review:10001"


def test_header_comment_documents_digest_pinning_and_sensitivity() -> None:
    header = _header_comment()
    assert "deliberately new" in header
    assert "digest" in header
    assert "sensitive review-machinery change" in header


def test_review_image_version_parity() -> None:
    text = _dockerfile_text()
    match = re.search(r"ARG CODEX_VERSION=([0-9.]+)", text)
    assert match is not None, "Dockerfile has no ARG CODEX_VERSION="
    assert match.group(1) == runner.REVIEW_CODEX_VERSION
    assert runner.REVIEW_IMAGE_REF == "triggarr-codex-review:" + runner.REVIEW_CODEX_VERSION
