"""Guard tests for the repository instructions that wire the paired BM +
Codex review and content-based classification into CLAUDE.md (REVIEW-02,
REVIEW-08).

These tests pin two things against silent regression: that CLAUDE.md keeps
pointing at the three review docs (and that those docs actually exist), and
that none of the hard constraints already in CLAUDE.md -- the /deep-review
offer, "Do not weaken CI", the review-acceptance environment, Greptile's
optional status, and Codex's read-only sandbox -- are lost when the review
sections are restructured.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PILOT_DOC = REPO_ROOT / "docs" / "buildomator-greptile-pilot.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_claude_md_links_review_docs() -> None:
    """CLAUDE.md links the classification policy, Codex contract and checkpoint record docs."""
    text = _read(CLAUDE_MD)
    linked_docs = (
        "docs/review-classification-policy.md",
        "docs/codex-adversarial-review-contract.md",
        "docs/review-checkpoint-record.md",
    )
    for doc in linked_docs:
        assert doc in text, f"CLAUDE.md must link {doc}"
        assert (REPO_ROOT / doc).is_file(), f"{doc} is linked from CLAUDE.md but does not exist"


def test_claude_md_keeps_hard_constraints() -> None:
    """Restructuring CLAUDE.md's review sections must not drop any existing safeguard."""
    text = _read(CLAUDE_MD)
    hard_constraints = (
        "/deep-review",
        "Do not weaken CI",
        "review-acceptance",
        "Greptile is optional",
        "--sandbox read-only",
    )
    for constraint in hard_constraints:
        assert constraint in text, f"CLAUDE.md must still contain the hard constraint: {constraint!r}"


def test_claude_md_codex_pairing_paths() -> None:
    """The Codex pairing instruction names all four BM code-review entry paths."""
    text = _read(CLAUDE_MD)
    paths = ("phase execution", "quick task", "/bm:code-review", "review after fixes")
    for path in paths:
        assert path in text, f"CLAUDE.md's Codex pairing instruction must name {path!r}"


def test_pilot_doc_points_to_policy() -> None:
    """The pilot doc's routine workflow links the review-classification policy."""
    text = _read(PILOT_DOC)
    assert "review-classification-policy.md" in text


POLICY_DOC = REPO_ROOT / "docs" / "review-classification-policy.md"
ACCEPTANCE_DOC = REPO_ROOT / "docs" / "owner-cli-acceptance.md"

# The review machinery itself is sensitive content (vibe-check #1, owner-approved round 6).
REVIEW_MACHINERY = (
    "docs/codex-adversarial-review-contract.md",
    "docs/review-checkpoint-record.md",
    "tests/codex_review_run.py",
    "tests/codex_report_status.py",
    ".claude/schemas/codex-review-findings.schema.json",
)


def _sensitive_covers_cell() -> str:
    row = next(line for line in _read(POLICY_DOC).splitlines() if line.startswith("| sensitive |"))
    return row.split("|")[2]


def test_policy_sensitive_row_names_the_review_machinery() -> None:
    covers = _sensitive_covers_cell()
    for path in REVIEW_MACHINERY:
        assert f"`{path}`" in covers, f"the sensitive row's 'What it covers' must name {path}"
        assert (REPO_ROOT / path).is_file(), f"{path} is named as sensitive but does not exist"


def _acceptance_step(number: int) -> str:
    prefix = f"{number}. "
    return next(line for line in _read(ACCEPTANCE_DOC).splitlines() if line.startswith(prefix))


def test_acceptance_prerequisites_include_the_paired_codex_review() -> None:
    """Step 1 lists the current head's Codex pass (vibe-check #7, owner-approved round 6)."""
    step = _acceptance_step(1)
    assert "Codex" in step
    assert "docs/codex-adversarial-review-contract.md" in step
    assert "INCOMPLETE" in step
    assert "PENDING" in step


def test_acceptance_codex_exception_is_an_approved_fallback_only() -> None:
    """Only an owner-approved fallback stands in for an incomplete Codex pass (vibe-check pass 2 #5)."""
    step = _acceptance_step(1)
    assert "owner-approved fallback review recorded for this exact head" in step
    assert "a wait or retry-later choice blocks acceptance" in step
    assert "owner's choice recorded" not in step


def test_acceptance_prerequisites_keep_the_existing_items() -> None:
    step = _acceptance_step(1)
    for item in ("CI", "Greptile is optional since 2026-10-22", "vibe-check/UAT", "finding dispositions"):
        assert item in step, f"step 1 must still list {item!r}"
