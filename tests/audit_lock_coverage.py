"""SAFETY-05 AST audit: every `_atomic_toml_write` reference in routes.py
must be lexically dominated by `async with request.app.state.search_lock:`.

This script is a static check that complements the dynamic test
`tests/test_web.py::test_concurrent_settings_save_serialized`. It runs in
two modes:

  1. As a pytest test via `tests/test_audit_lock_coverage.py` (in-process
     import + call so assertions are captured cleanly).
  2. As a one-shot CLI check the executor or CI can invoke during plan
     verification: `uv run python tests/audit_lock_coverage.py`.

Why AST instead of a line-distance grep: a handler that acquires the lock,
does N lines of unrelated work, then writes the config is correctly locked
but a grep with a fixed line window would mis-count. Conversely, a handler
that briefly exits the `async with` block via an early-return path and then
writes the config is NOT correctly locked but a grep could still pass it.
The AST walk asserts true lexical dominance: at least one ancestor of the
`_atomic_toml_write` reference is an `ast.AsyncWith` whose `context_expr`
resolves to `request.app.state.search_lock` or `app.state.search_lock`.

Note: this script uses plain `print()` to stdout because it must be runnable
outside the loguru-configured app context (e.g., in CI before any Triggarr
import succeeds). This is the one exception to the loguru-only convention
documented in CLAUDE.md -- audit tooling, not production code.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Default target: triggarr/web/routes.py relative to the repo root, which is
# the parent of this file's parent (tests/audit_lock_coverage.py).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ROUTES = _REPO_ROOT / "triggarr" / "web" / "routes.py"


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Map id(child) -> parent for every node in tree (single pass)."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _ancestors(node: ast.AST, parents: dict[int, ast.AST]):
    """Yield each ancestor of *node* walking upward to the module root."""
    cur = parents.get(id(node))
    while cur is not None:
        yield cur
        cur = parents.get(id(cur))


def _is_search_lock_context(expr: ast.expr) -> bool:
    """Return True if *expr* is `request.app.state.search_lock` or
    `app.state.search_lock` (the two forms used in this codebase).
    """
    # request.app.state.search_lock  (the canonical form in routes.py)
    # ast.Attribute(value=ast.Attribute(value=ast.Attribute(value=ast.Name('request'),
    #     attr='app'), attr='state'), attr='search_lock')
    if not isinstance(expr, ast.Attribute) or expr.attr != "search_lock":
        return False
    parent = expr.value
    if not isinstance(parent, ast.Attribute) or parent.attr != "state":
        return False
    grand = parent.value
    if isinstance(grand, ast.Attribute) and grand.attr == "app":
        root = grand.value
        # `request.app.state.search_lock` or (unlikely) `app.app.state.search_lock`.
        return isinstance(root, ast.Name) and root.id in ("request", "app")
    # `app.state.search_lock` shape: grand is the Name('app') directly.
    return isinstance(grand, ast.Name) and grand.id == "app"


def _references_atomic_write(node: ast.AST) -> bool:
    """Return True if *node* is a Name('_atomic_toml_write') or
    Attribute(attr='_atomic_toml_write')."""
    if isinstance(node, ast.Name) and node.id == "_atomic_toml_write":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "_atomic_toml_write"


def audit_lock_coverage(
    routes_path: Path = _DEFAULT_ROUTES,
) -> tuple[int, int, list[int]]:
    """Walk *routes_path*, find every `_atomic_toml_write` reference, and
    verify each is lexically dominated by `async with ... search_lock:`.

    Returns:
        (covered, uncovered_count, uncovered_linenos)
    """
    source = routes_path.read_text()
    tree = ast.parse(source, filename=str(routes_path))
    parents = _build_parent_map(tree)

    covered = 0
    uncovered_linenos: list[int] = []
    seen: set[int] = set()  # dedupe by lineno to avoid double-counting

    for node in ast.walk(tree):
        if not _references_atomic_write(node):
            continue
        # Skip the import binding itself -- it is not a runtime call.
        if isinstance(node, ast.Name) and isinstance(
            parents.get(id(node)), (ast.ImportFrom, ast.Import, ast.alias)
        ):
            continue
        # If the reference is an alias inside an Import/ImportFrom, also skip.
        parent_node = parents.get(id(node))
        if isinstance(parent_node, ast.alias):
            continue
        lineno = getattr(node, "lineno", None)
        if lineno is None or lineno in seen:
            continue
        # Filter out the `from triggarr.config import _atomic_toml_write, ...`
        # line by inspecting the chain of ancestors for ImportFrom.
        is_import = False
        for ancestor in _ancestors(node, parents):
            if isinstance(ancestor, (ast.Import, ast.ImportFrom)):
                is_import = True
                break
            # Stop walking once we hit a function/class -- imports live at
            # module scope so an enclosing function rules out import context.
            if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                break
        if is_import:
            continue
        seen.add(lineno)

        # Walk ancestors looking for AsyncWith with search_lock context.
        locked = False
        for ancestor in _ancestors(node, parents):
            if not isinstance(ancestor, ast.AsyncWith):
                continue
            for item in ancestor.items:
                if _is_search_lock_context(item.context_expr):
                    locked = True
                    break
            if locked:
                break

        if locked:
            covered += 1
        else:
            uncovered_linenos.append(lineno)

    return covered, len(uncovered_linenos), uncovered_linenos


def main() -> int:
    covered, uncovered_count, uncovered_linenos = audit_lock_coverage()
    total = covered + uncovered_count
    if uncovered_count == 0:
        print(f"covered: {covered} / {total}, uncovered: 0")
        return 0
    print(
        f"covered: {covered} / {total}, uncovered: {uncovered_linenos}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
