"""Pytest plugin recording that a test's setup phase actually started.

Loaded explicitly with ``-p tests.e2e.probes.sentinel_plugin`` by the capture
guard's subprocess cases (tests/e2e/test_capture_policy.py,
tests/test_e2e_capture_guard.py). ``pytest_runtest_setup`` fires before any
of the item's own fixtures run, so an absent sentinel file after the
subprocess exits proves the capture-policy guard rejected the selection in
``pytest_collection_finish`` -- before any fixture ran and before any
browser launched.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Append this item's nodeid to $E2E_SENTINEL_FILE before any of its fixtures run."""
    path = os.environ.get("E2E_SENTINEL_FILE")
    if not path:
        return
    with Path(path).open("a") as handle:
        handle.write(item.nodeid + "\n")
