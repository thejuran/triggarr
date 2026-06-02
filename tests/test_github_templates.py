"""Tests for GitHub issue templates, PR template, and config.

Validates that required template files exist with correct content
per COMM-04, COMM-05, COMM-06, COMM-07.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


class TestBugReportTemplate:
    """COMM-04: Bug report YAML form with dropdowns."""

    path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml"

    def test_file_exists(self):
        assert self.path.exists(), "bug-report.yml must exist"

    def test_valid_yaml(self):
        data = yaml.safe_load(self.path.read_text())
        assert data["name"] == "Bug Report"

    def test_has_dropdowns(self):
        content = self.path.read_text()
        assert content.count("type: dropdown") == 3, "Must have 3 dropdown fields"

    def test_version_dropdown_options(self):
        data = yaml.safe_load(self.path.read_text())
        version_options = data["body"][0]["attributes"]["options"]
        for version in ("v2.8.1", "v2.8", "v2.7", "v2.6", "v2.5", "v2.4", "Older"):
            assert version in version_options, f"Version dropdown must include '{version}'"
        # Assert dropped options are absent (catches renames / stale entries)
        assert "v2.3" not in version_options, "v2.3 should have been removed from version dropdown"

    def test_deployment_dropdown_options(self):
        content = self.path.read_text()
        for method in ("Docker Compose", "Docker run", "Bare metal"):
            assert method in content, f"Deployment dropdown must include '{method}'"

    def test_app_type_dropdown_options(self):
        data = yaml.safe_load(self.path.read_text())
        app_options = data["body"][2]["attributes"]["options"]
        for app in ("Radarr", "Sonarr", "Lidarr", "All"):
            assert app in app_options, f"App type dropdown must include '{app}'"
        # Assert dropped options are absent
        assert "Both" not in app_options, "'Both' should have been replaced by 'All' in App Type dropdown"

    def test_config_excerpt_redaction_warning(self):
        content = self.path.read_text()
        assert "Remove API keys" in content, "Config excerpt must warn about API key redaction"

    def test_config_excerpt_is_optional(self):
        """Config excerpt field must be optional (required: false) per D-06."""
        content = self.path.read_text()
        # Find the config section and verify it has required: false
        lines = content.split("\n")
        in_config_block = False
        found_optional = False
        for line in lines:
            if "id: config" in line:
                in_config_block = True
            if in_config_block and "required: false" in line:
                found_optional = True
                break
            # Reset if we hit another top-level block
            if in_config_block and line.startswith("  - type:"):
                break
        assert found_optional, "Config excerpt field must have required: false"


class TestFeatureRequestTemplate:
    """COMM-05: Feature request YAML form."""

    path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature-request.yml"

    def test_file_exists(self):
        assert self.path.exists(), "feature-request.yml must exist"

    def test_valid_yaml(self):
        data = yaml.safe_load(self.path.read_text())
        assert data["name"] == "Feature Request"

    def test_has_use_case_field(self):
        content = self.path.read_text()
        assert "use-case" in content or "use_case" in content, "Must have use case field"

    def test_has_alternatives_field(self):
        content = self.path.read_text()
        assert "alternatives" in content.lower(), "Must have alternatives considered field"


class TestIssueTemplateConfig:
    """COMM-06: Issue template config with blank issues disabled."""

    path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"

    def test_file_exists(self):
        assert self.path.exists(), "config.yml must exist"

    def test_valid_yaml(self):
        data = yaml.safe_load(self.path.read_text())
        assert data["blank_issues_enabled"] is False

    def test_blank_issues_disabled(self):
        content = self.path.read_text()
        assert "blank_issues_enabled: false" in content

    def test_discussions_contact_link(self):
        content = self.path.read_text()
        assert "discussions" in content.lower(), "Must link to Discussions"


class TestPRTemplate:
    """COMM-07: PR template with CI checklist."""

    path = REPO_ROOT / ".github" / "pull_request_template.md"

    def test_file_exists(self):
        assert self.path.exists(), "pull_request_template.md must exist"

    def test_has_three_checklist_items(self):
        content = self.path.read_text()
        assert content.count("- [ ]") == 3, "Must have exactly 3 checklist items"

    def test_checklist_has_test_command(self):
        content = self.path.read_text()
        assert "uv run pytest tests/ -x -q" in content

    def test_checklist_has_lint_command(self):
        content = self.path.read_text()
        assert "uv run ruff check triggarr/ tests/" in content

    def test_checklist_has_docker_build(self):
        content = self.path.read_text()
        assert "docker build -t triggarr:local ." in content
