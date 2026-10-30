"""Drift guard for the three hand-kept lists of review-machinery files (D-17).

The classification policy's sensitive row, the Codex scope's
``AUDITED_INPUTS``/``EXCLUDE_PATHSPECS``, and the owner acceptance
checklist's "- Codex:" line are three independently hand-maintained lists
that must all agree on which files are the review machinery. This module
extracts each list from its source document, compares them against each
other with two documented role-specific exceptions, and asserts that the
Codex review diff's exclusion pathspecs never hide a review-machinery file
or a phase plan file (arch-1, SA-03).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from tests import codex_review_run as runner
from tests.codex_review_run import AUDITED_INPUTS, EXCLUDE_PATHSPECS

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "docs" / "review-classification-policy.md"
RECORD_PATH = REPO_ROOT / "docs" / "review-checkpoint-record.md"

POLICY_TEXT = POLICY_PATH.read_text(encoding="utf-8")
RECORD_TEXT = RECORD_PATH.read_text(encoding="utf-8")

# Documented role-specific exceptions (D-17): each list serves a different
# purpose, so each is allowed exactly one documented divergence from
# AUDITED_INPUTS, with a reason -- anything else is drift.
POLICY_ONLY = {
    "docs/review-checkpoint-record.md": "the record template is review machinery but not a Codex grader input",
    "docker/codex-review/Dockerfile": (
        "the untrusted-review container image is review machinery (it defines the isolation boundary)"
        " but not a Codex grader input"
    ),
}
CHECKLIST_OMITS = {
    ".claude/schemas/codex-review-findings.schema.json": (
        "loaded by tests/codex_report_status.py; the checklist names the procedure's entry points"
    ),
}

# The three current pathspecs, copied as a literal so a real drift in
# tests/codex_review_run.py's EXCLUDE_PATHSPECS is caught, not reconciled
# away quietly.
EXPECTED_EXCLUDES = (
    ":(exclude,glob).planning/**/codex/**",
    ":(exclude,glob).planning/**/*.jsonl",
    ":(exclude,glob).planning/**/*.md",
)

# Matches a repository path whether or not it is wrapped in backticks. The
# extension alternative covers the usual docs/tests/scripts files; the
# "/Dockerfile" alternative additionally matches the extension-less review
# image definition (docker/codex-review/Dockerfile).
_PATH_RE = re.compile(r"(?:docs|tests|\.claude|\.github|docker)/[A-Za-z0-9_./-]+(?:\.(?:md|py|json|cjs)|/Dockerfile)")


def _normalize_path(raw: str) -> str:
    return raw.strip("`").rstrip(".,;:)").replace("\\", "/")


def extract_policy_machinery(policy_text: str) -> set[str]:
    """Return the paths inside the sensitive row's "the review machinery (...)" parenthetical."""
    row = next((line for line in policy_text.splitlines() if line.startswith("| sensitive |")), None)
    region_match = re.search(r"the review machinery \(([^)]*)\)", row) if row is not None else None
    if region_match is None:
        raise AssertionError("extraction found no paths in policy sensitive row")
    paths = {_normalize_path(p) for p in _PATH_RE.findall(region_match.group(1))}
    if not paths:
        raise AssertionError("extraction found no paths in policy sensitive row")
    return paths


def extract_checklist_machinery(record_text: str) -> set[str]:
    """Return the paths on the Owner acceptance checklist's "- Codex:" line."""
    line = next((candidate for candidate in record_text.splitlines() if candidate.strip().startswith("- Codex:")), None)
    if line is None:
        raise AssertionError("extraction found no paths in acceptance checklist Codex line")
    paths = {_normalize_path(p) for p in _PATH_RE.findall(line)}
    if not paths:
        raise AssertionError("extraction found no paths in acceptance checklist Codex line")
    return paths


# --- A dependency-free glob matcher for git's `:(exclude,glob)`/`:(glob)` pathspecs ---

_MAGIC_PREFIX_RE = re.compile(r"^:\([^)]*\)")


def _pathspec_glob(pathspec: str) -> str:
    """Strip the leading `:(...)` magic signature, leaving the bare glob."""
    return _MAGIC_PREFIX_RE.sub("", pathspec, count=1)


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a git-style glob (`**` = any number of segments, `*` = within a segment) to regex."""
    double_star = "DOUBLESTAR"
    single_star = "STAR"
    protected = glob.replace("**", double_star).replace("*", single_star)
    escaped = re.escape(protected)
    # A "**" segment flanked by slashes on both sides matches zero or more
    # whole path segments, which also absorbs one of the two slashes.
    escaped = escaped.replace(f"/{double_star}/", "(?:/.*)?/")
    escaped = escaped.replace(double_star, ".*")
    escaped = escaped.replace(single_star, "[^/]*")
    return re.compile("^" + escaped + "$")


def _pathspec_matches(pathspec: str, path: str) -> bool:
    return bool(_glob_to_regex(_pathspec_glob(pathspec)).match(path))


def in_effective_codex_scope(path: str, exclude_pathspecs: Sequence[str], plan_pathspecs: Sequence[str]) -> bool:
    """True when *path* is in the full diff (unexcluded) or matched by a plan pathspec."""
    in_full_diff = not any(_pathspec_matches(spec, path) for spec in exclude_pathspecs)
    in_plan_diff = any(_pathspec_matches(spec, path) for spec in plan_pathspecs)
    return in_full_diff or in_plan_diff


def machinery_list_problems(
    policy_text: str,
    checklist_text: str,
    audited_inputs: Sequence[str],
    exclude_pathspecs: Sequence[str],
) -> list[str]:
    """Compare the three hand-kept lists and name every disagreement found."""
    problems: list[str] = []
    audited_set = set(audited_inputs)

    policy_machinery: set[str] | None
    try:
        policy_machinery = extract_policy_machinery(policy_text)
    except AssertionError as exc:
        problems.append(str(exc))
        policy_machinery = None

    checklist_machinery: set[str] | None
    try:
        checklist_machinery = extract_checklist_machinery(checklist_text)
    except AssertionError as exc:
        problems.append(str(exc))
        checklist_machinery = None

    if policy_machinery is not None and checklist_machinery is not None:
        reconciled_policy = policy_machinery - set(POLICY_ONLY)
        reconciled_checklist = checklist_machinery | set(CHECKLIST_OMITS)
        for path in sorted(audited_set | reconciled_policy | reconciled_checklist):
            in_audited = path in audited_set
            in_policy = path in reconciled_policy
            in_checklist = path in reconciled_checklist
            if in_audited == in_policy == in_checklist:
                continue  # all three lists agree
            if in_policy == in_checklist and in_audited != in_policy:
                verb = "has an unexpected entry" if in_audited else "is missing"
                problems.append(f"AUDITED_INPUTS {verb} {path}")
            elif in_audited == in_checklist and in_policy != in_audited:
                verb = "has an unexpected entry" if in_policy else "is missing"
                problems.append(f"policy sensitive row {verb} {path}")
            elif in_audited == in_policy and in_checklist != in_audited:
                verb = "has an unexpected entry" if in_checklist else "is missing"
                problems.append(f"acceptance checklist Codex line {verb} {path}")
            else:
                problems.append(f"review-machinery lists disagree on {path}")

    if set(exclude_pathspecs) != set(EXPECTED_EXCLUDES):
        for pathspec in sorted(set(EXPECTED_EXCLUDES) - set(exclude_pathspecs)):
            problems.append(f"EXCLUDE_PATHSPECS is missing {pathspec}")
        for pathspec in sorted(set(exclude_pathspecs) - set(EXPECTED_EXCLUDES)):
            problems.append(f"EXCLUDE_PATHSPECS has an unexpected entry {pathspec}")

    if policy_machinery is not None:
        machinery_paths = sorted(policy_machinery | audited_set)
        for pathspec in exclude_pathspecs:
            for path in machinery_paths:
                if _pathspec_matches(pathspec, path):
                    problems.append(f"EXCLUDE_PATHSPECS entry {pathspec} matches review-machinery file {path}")

    return problems


# --- Real-document tests: today's docs and constants agree exactly ----------


def test_real_documents_match_audited_inputs_with_documented_exceptions() -> None:
    policy_machinery = extract_policy_machinery(POLICY_TEXT)
    checklist_machinery = extract_checklist_machinery(RECORD_TEXT)
    assert policy_machinery == set(AUDITED_INPUTS) | set(POLICY_ONLY)
    assert checklist_machinery == set(AUDITED_INPUTS) - set(CHECKLIST_OMITS)
    assert set(EXPECTED_EXCLUDES) == set(EXCLUDE_PATHSPECS)
    assert machinery_list_problems(POLICY_TEXT, RECORD_TEXT, AUDITED_INPUTS, EXCLUDE_PATHSPECS) == []


def test_policy_classifies_plan_files_as_sensitive() -> None:
    sensitive_row = next(line for line in POLICY_TEXT.splitlines() if line.startswith("| sensitive |"))
    ordinary_row = next(line for line in POLICY_TEXT.splitlines() if line.startswith("| ordinary-docs |"))
    assert "*-PLAN.md" in sensitive_row
    assert "*-PLAN.md" in ordinary_row


PLAN_SAMPLE = ".planning/phases/85-x/85-01-PLAN.md"
PLAN_SAMPLES = (
    PLAN_SAMPLE,
    ".planning/phases/99-y/99-12-PLAN.md",
    ".planning/phases/a/b/85-03-PLAN.md",
)
NON_PLAN_SAMPLES = (
    ".planning/STATE.md",
    ".planning/phases/85-x/85-01-SUMMARY.md",
)


def test_no_exclusion_hides_plan_or_machinery_files() -> None:
    plan_pathspecs = getattr(runner, "PLAN_PATHSPECS", ())
    for sample in PLAN_SAMPLES:
        assert in_effective_codex_scope(sample, EXCLUDE_PATHSPECS, plan_pathspecs), (
            f"{sample} must be in the effective Codex review scope"
        )
    for sample in NON_PLAN_SAMPLES:
        assert not in_effective_codex_scope(sample, EXCLUDE_PATHSPECS, plan_pathspecs), (
            f"{sample} must stay out of the effective Codex review scope"
        )
    machinery_paths = extract_policy_machinery(POLICY_TEXT) | set(AUDITED_INPUTS)
    for path in sorted(machinery_paths):
        assert not any(_pathspec_matches(spec, path) for spec in EXCLUDE_PATHSPECS), (
            f"EXCLUDE_PATHSPECS must not match review-machinery file {path}"
        )
    assert set(EXCLUDE_PATHSPECS) == set(EXPECTED_EXCLUDES)


def test_extra_plan_exclusion_does_not_remove_plan_coverage() -> None:
    """An exclusion that also matches PLAN files doesn't hide them: the positive PLAN diff still covers them."""
    plan_pathspecs = getattr(runner, "PLAN_PATHSPECS", ())
    extra_excludes = (*EXCLUDE_PATHSPECS, ":(exclude,glob).planning/**/*-PLAN.md")
    for sample in PLAN_SAMPLES:
        assert in_effective_codex_scope(sample, extra_excludes, plan_pathspecs), (
            f"{sample} must stay in scope through the positive PLAN diff even if also excluded"
        )


def test_emptied_plan_pathspecs_drops_plan_sample_from_scope() -> None:
    """If PLAN_PATHSPECS drifts to empty, a PLAN sample falls out of scope -- caught, not silent (checker W04)."""
    problems = []
    if not in_effective_codex_scope(PLAN_SAMPLE, EXCLUDE_PATHSPECS, ()):
        problems.append(f"PLAN_PATHSPECS no longer covers {PLAN_SAMPLE}")
    assert problems, "emptied PLAN_PATHSPECS must be caught, not silently accepted"
    assert any("PLAN_PATHSPECS" in p and PLAN_SAMPLE in p for p in problems)


# --- Mutation tests: each asserts its specific problem substring ------------


def _mutate(text: str, old: str, new: str) -> str:
    assert old in text, f"expected substring not found (fixture drift?): {old!r}"
    return text.replace(old, new, 1)


def test_removing_a_path_from_policy_row_is_flagged() -> None:
    mutated = _mutate(POLICY_TEXT, "`tests/codex_review_run.py`, ", "")
    problems = machinery_list_problems(mutated, RECORD_TEXT, AUDITED_INPUTS, EXCLUDE_PATHSPECS)
    assert any("policy sensitive row" in p and "tests/codex_review_run.py" in p for p in problems)


def test_adding_an_extra_path_to_policy_row_is_flagged() -> None:
    mutated = _mutate(
        POLICY_TEXT,
        "the review machinery (`docs/codex-adversarial-review-contract.md`,",
        "the review machinery (`docs/codex-adversarial-review-contract.md`, `docs/extra-machinery-file.md`,",
    )
    problems = machinery_list_problems(mutated, RECORD_TEXT, AUDITED_INPUTS, EXCLUDE_PATHSPECS)
    assert any("policy sensitive row" in p and "docs/extra-machinery-file.md" in p for p in problems)


def test_removing_a_path_from_checklist_line_is_flagged() -> None:
    mutated = _mutate(RECORD_TEXT, " → tests/codex_report_status.py", "")
    problems = machinery_list_problems(POLICY_TEXT, mutated, AUDITED_INPUTS, EXCLUDE_PATHSPECS)
    assert any("acceptance checklist Codex line" in p and "tests/codex_report_status.py" in p for p in problems)


def test_adding_an_extra_path_to_checklist_line_is_flagged() -> None:
    mutated = _mutate(
        RECORD_TEXT,
        "tests/codex_report_status.py)>",
        "tests/codex_report_status.py docs/extra-checklist-file.md)>",
    )
    problems = machinery_list_problems(POLICY_TEXT, mutated, AUDITED_INPUTS, EXCLUDE_PATHSPECS)
    assert any("acceptance checklist Codex line" in p and "docs/extra-checklist-file.md" in p for p in problems)


def test_dropping_an_audited_input_entry_is_flagged() -> None:
    mutated = tuple(path for path in AUDITED_INPUTS if path != "tests/codex_review_run.py")
    problems = machinery_list_problems(POLICY_TEXT, RECORD_TEXT, mutated, EXCLUDE_PATHSPECS)
    assert any("AUDITED_INPUTS" in p and "tests/codex_review_run.py" in p for p in problems)


def test_adding_an_audited_input_entry_is_flagged() -> None:
    mutated = (*AUDITED_INPUTS, "docs/extra-audited-file.md")
    problems = machinery_list_problems(POLICY_TEXT, RECORD_TEXT, mutated, EXCLUDE_PATHSPECS)
    assert any("AUDITED_INPUTS" in p and "docs/extra-audited-file.md" in p for p in problems)


def test_exclusion_matching_machinery_is_flagged() -> None:
    mutated = (*EXCLUDE_PATHSPECS, ":(exclude,glob)tests/**")
    problems = machinery_list_problems(POLICY_TEXT, RECORD_TEXT, AUDITED_INPUTS, mutated)
    assert any(
        "EXCLUDE_PATHSPECS" in p and "matches review-machinery file" in p and "tests/codex_review_run.py" in p
        for p in problems
    )


def test_removing_an_exclude_pathspec_is_flagged() -> None:
    mutated = EXCLUDE_PATHSPECS[1:]
    problems = machinery_list_problems(POLICY_TEXT, RECORD_TEXT, AUDITED_INPUTS, mutated)
    assert any("EXCLUDE_PATHSPECS" in p and EXCLUDE_PATHSPECS[0] in p for p in problems)


def test_emptying_policy_machinery_parenthetical_is_flagged() -> None:
    mutated = _mutate(
        POLICY_TEXT,
        "the review machinery (`docs/codex-adversarial-review-contract.md`, `docs/review-checkpoint-record.md`,"
        " `tests/codex_review_run.py`, `tests/codex_report_status.py`,"
        " `.claude/schemas/codex-review-findings.schema.json`, `docker/codex-review/Dockerfile`)",
        "the review machinery (see elsewhere)",
    )
    problems = machinery_list_problems(mutated, RECORD_TEXT, AUDITED_INPUTS, EXCLUDE_PATHSPECS)
    assert "extraction found no paths in policy sensitive row" in problems


def test_replacing_checklist_codex_line_with_prose_is_flagged() -> None:
    mutated = _mutate(
        RECORD_TEXT,
        "- Codex: <status, from docs/codex-adversarial-review-contract.md Invocation"
        " (tests/codex_review_run.py → tests/codex_report_status.py)>",
        "- Codex: <status, from the review contract and the review runner>",
    )
    problems = machinery_list_problems(POLICY_TEXT, mutated, AUDITED_INPUTS, EXCLUDE_PATHSPECS)
    assert "extraction found no paths in acceptance checklist Codex line" in problems
