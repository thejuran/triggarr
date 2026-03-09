# Deferred Items -- Phase 20.2

## Pre-existing test failures (out of scope)

- `tests/test_search.py::test_radarr_cycle_logs_failed_search_to_db` -- expects `"API timeout"` in detail but DRSEC-07 sanitization now returns `"Exception"` (type name only). Test predates the sanitization change.
- `tests/test_search.py::test_sonarr_cycle_logs_failed_search_to_db` -- same pattern, expects `"Connection refused"` but gets `"Exception"`.

Both tests need updating to match the DRSEC-07 exception sanitization behavior introduced in Phase 20.1.
