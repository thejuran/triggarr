# Deferred Items - Phase 21

## Pre-existing Test Failure

- **File:** tests/test_search.py::test_radarr_cycle_logs_failed_search_to_db
- **Issue:** Test expects `detail` to contain "API timeout" but gets "Exception" (exception type name stored instead of message string)
- **Root cause:** Likely `type(exc).__name__` used where `str(exc)` was intended in search engine error handling
- **Discovered during:** 21-02 execution
- **Impact:** Does not affect production behavior, only test assertion
