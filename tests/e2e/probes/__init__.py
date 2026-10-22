"""Standalone pytest probe targets for the D-33 capture-policy guard and its sensitivity tests.

Every module here is named ``probe_*.py`` (not ``test_*.py``) so the normal
browser-e2e run never collects it. Each probe is invoked directly as its own
pytest target -- by tests/e2e/test_capture_policy.py (inside a subprocess)
and by tests/test_e2e_capture_guard.py (the default unit job, no Docker, no
browser) -- with ``-o python_files=probe_*.py -o python_functions=probe_*``.
"""
