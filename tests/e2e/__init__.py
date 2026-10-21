"""Browser regression suite (Playwright) against the shipped image.

Collected only by the ``browser-e2e`` CI job, never by the default
``pytest tests/`` run used by the ``test`` job -- see ``tests/conftest.py``'s
``collect_ignore``. Running ``pytest tests/e2e`` without ``TRIGGARR_E2E_IMAGE``
set fails closed (collects nothing, non-zero exit) rather than silently
skipping (D-12).
"""
