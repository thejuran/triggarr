"""Tests for community health files (CONTRIBUTING.md, SECURITY.md, LICENSE).

Validates that required community health files exist at the repo root
with the correct content per COMM-01, COMM-02, COMM-03, and D-03.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class TestContributing:
    """COMM-01: CONTRIBUTING.md has fork/branch/PR workflow, dev setup, test/lint commands."""

    path = REPO_ROOT / "CONTRIBUTING.md"

    def test_file_exists(self):
        assert self.path.exists(), "CONTRIBUTING.md must exist at repo root"

    def test_contains_dev_setup(self):
        content = self.path.read_text()
        assert "uv sync --extra dev" in content, "Must contain dev setup command"

    def test_contains_test_command(self):
        content = self.path.read_text()
        assert "uv run pytest tests/ -x -q" in content, "Must contain test command"

    def test_contains_lint_command(self):
        content = self.path.read_text()
        assert "uv run ruff check triggarr/ tests/" in content, "Must contain lint command"

    def test_contains_docker_build(self):
        content = self.path.read_text()
        assert "docker build -t triggarr:local ." in content, "Must contain Docker build command"

    def test_contains_conventional_commits(self):
        content = self.path.read_text()
        for prefix in ("feat:", "fix:", "docs:", "test:"):
            assert prefix in content, f"Must contain conventional commit prefix '{prefix}'"

    def test_contains_fork_workflow(self):
        content = self.path.read_text()
        assert "fork" in content.lower(), "Must mention fork workflow"

    def test_contains_pr_workflow(self):
        content = self.path.read_text()
        assert "PR" in content or "pull request" in content.lower(), "Must mention PR workflow"


class TestSecurity:
    """COMM-02 + COMM-03: SECURITY.md has supported versions, reporting link, security model."""

    path = REPO_ROOT / "SECURITY.md"

    def test_file_exists(self):
        assert self.path.exists(), "SECURITY.md must exist at repo root"

    def test_supported_versions_table(self):
        content = self.path.read_text()
        assert "2.x" in content, "Must list 2.x as supported"
        assert "1.x" in content, "Must list 1.x as unsupported"

    def test_private_vulnerability_reporting_link(self):
        content = self.path.read_text()
        assert "github.com/thejuran/triggarr/security/advisories/new" in content

    def test_secretstr_documented(self):
        content = self.path.read_text()
        assert "SecretStr" in content, "Must document SecretStr credential protection"

    def test_csrf_documented(self):
        content = self.path.read_text()
        assert "CSRF" in content, "Must document CSRF protection"

    def test_ssrf_documented(self):
        content = self.path.read_text()
        assert "SSRF" in content, "Must document SSRF validation"

    def test_input_clamping_documented(self):
        content = self.path.read_text()
        assert "clamping" in content.lower(), "Must document input clamping"

    def test_atomic_writes_documented(self):
        content = self.path.read_text()
        assert "atomic" in content.lower(), "Must document atomic file writes"

    def test_docker_hardening_documented(self):
        content = self.path.read_text()
        assert "PUID" in content, "Must document PUID/PGID privilege dropping"

    def test_loguru_redaction_documented(self):
        content = self.path.read_text()
        assert "redact" in content.lower(), "Must document loguru redaction"


class TestLicense:
    """D-03: MIT LICENSE file."""

    path = REPO_ROOT / "LICENSE"

    def test_file_exists(self):
        assert self.path.exists(), "LICENSE must exist at repo root"

    def test_is_mit(self):
        content = self.path.read_text()
        assert "MIT License" in content, "Must be MIT License"

    def test_correct_year(self):
        content = self.path.read_text()
        assert "2026" in content, "Must contain correct year"
