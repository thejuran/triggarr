# Queued Milestones

## M004: Version Bump & Release Tag Cleanup

**Problem:** `__version__` is still `"2.5.3"` but a `v2.6.0-dev` tag exists on GitHub. The update checker strips the `-dev` suffix and shows a spurious "↑ v2.6.0-dev" upgrade badge in the nav bar.

**Fix:**
1. Bump `__version__` to `"2.6.0"` in `triggarr/__init__.py` and `pyproject.toml`
2. Delete the `v2.6.0-dev` tag (local + remote)
3. Create proper `v2.6.0` release tag
4. Optionally: make `_parse_version` in `update_check.py` treat pre-release tags as lower than release versions (so `-dev`, `-rc` suffixes don't trigger false upgrade badges)

**Queued:** 2026-04-06
