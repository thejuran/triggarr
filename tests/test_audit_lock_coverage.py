"""Pytest wrapper for the SAFETY-05 AST audit at tests/audit_lock_coverage.py.

This test imports and calls the audit function IN-PROCESS (not via
subprocess) so pytest captures the assertion details cleanly when a future
contributor adds a config-mutating route that bypasses search_lock.
"""

from tests.audit_lock_coverage import audit_lock_coverage


def test_all_config_writes_locked() -> None:
    """Every _atomic_toml_write in triggarr/web/routes.py must be inside
    `async with request.app.state.search_lock:` (or `app.state.search_lock`).
    SAFETY-05.
    """
    covered, uncovered_count, uncovered_linenos = audit_lock_coverage()
    assert uncovered_count == 0, (
        f"SAFETY-05 violation: {uncovered_count} `_atomic_toml_write` "
        f"reference(s) in triggarr/web/routes.py are not lexically dominated "
        f"by `async with request.app.state.search_lock:`. "
        f"Uncovered linenos: {uncovered_linenos}. "
        f"Each config-mutating route MUST acquire app.state.search_lock "
        f"before invoking _atomic_toml_write."
    )
    assert covered >= 7, (
        f"Expected at least 7 `_atomic_toml_write` references in routes.py "
        f"(POST /settings, /api/instance/add, /api/instance/remove, /setup, "
        f"/settings/password, /settings/security, /settings/api-key/regenerate), "
        f"found {covered}. Either a route was removed or the audit walker is broken."
    )
