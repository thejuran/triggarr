"""Unit-level guards for the browser suite's secret handling (runs in the default job, no Docker or browser).

pytest prints a failing test's fixture arguments, so any fixture object that holds a credential must keep it
out of its repr. The capture-policy probe hands its parent only a fingerprint of a real-looking API key, so a
blank or malformed key can never pass the leak check unexamined.
"""

from __future__ import annotations

import secrets

from tests.e2e.conftest import Credentials, SensitiveRegistry, api_key_handoff, secret_fingerprint


def test_sensitive_registry_repr_hides_registered_values() -> None:
    registry = SensitiveRegistry()
    value = secrets.token_hex(16)
    registry.register(value)
    assert value not in repr(registry)


def test_credentials_repr_hides_password() -> None:
    password = secrets.token_urlsafe(18)
    assert password not in repr(Credentials(username="e2e-admin", password=password))


def test_api_key_handoff_refuses_blank_and_malformed_keys() -> None:
    salt_hex = secrets.token_hex(16)
    for not_a_key in ("", "   ", "abc", secrets.token_hex(16).upper(), secrets.token_hex(17)):
        assert api_key_handoff(not_a_key, salt_hex) is None


def test_api_key_handoff_fingerprints_a_real_key() -> None:
    salt_hex = secrets.token_hex(16)
    key = secrets.token_hex(16)
    assert api_key_handoff(key, salt_hex) == secret_fingerprint(key, salt_hex)
