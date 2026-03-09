"""Tests for fetcharr.web.validation helpers."""

from __future__ import annotations

from fetcharr.web.validation import safe_int, safe_log_level, validate_arr_url

# ---------------------------------------------------------------------------
# validate_arr_url
# ---------------------------------------------------------------------------

class TestValidateArrUrl:
    """URL validation: scheme enforcement, SSRF blocking, private-IP allow."""

    def test_valid_http_url(self) -> None:
        ok, err = validate_arr_url("http://radarr:7878")
        assert ok is True
        assert err == ""

    def test_valid_https_url(self) -> None:
        ok, err = validate_arr_url("https://radarr.example.com:7878")
        assert ok is True
        assert err == ""

    def test_empty_string_allowed(self) -> None:
        ok, err = validate_arr_url("")
        assert ok is True
        assert err == ""

    def test_ftp_scheme_rejected(self) -> None:
        ok, err = validate_arr_url("ftp://evil.com")
        assert ok is False
        assert "scheme" in err.lower()

    def test_file_scheme_rejected(self) -> None:
        ok, err = validate_arr_url("file:///etc/passwd")
        assert ok is False
        assert "scheme" in err.lower()

    def test_cloud_metadata_ip_blocked(self) -> None:
        ok, err = validate_arr_url("http://169.254.169.254/latest/meta-data")
        assert ok is False

    def test_gcp_metadata_hostname_blocked(self) -> None:
        ok, err = validate_arr_url("http://metadata.google.internal")
        assert ok is False

    def test_link_local_ip_blocked(self) -> None:
        ok, err = validate_arr_url("http://169.254.42.42")
        assert ok is False
        assert "blocked" in err.lower()

    def test_private_192_168_allowed(self) -> None:
        ok, err = validate_arr_url("http://192.168.1.100:7878")
        assert ok is True
        assert err == ""

    def test_private_10_x_allowed(self) -> None:
        ok, err = validate_arr_url("http://10.0.0.5:7878")
        assert ok is True
        assert err == ""

    def test_hostname_allowed(self) -> None:
        ok, err = validate_arr_url("http://radarr:7878")
        assert ok is True
        assert err == ""

    # W7 regression: SSRF blocklist gaps (Phase 16 code review)

    def test_ipv6_loopback_blocked(self) -> None:
        ok, err = validate_arr_url("http://[::1]:7878")
        assert ok is False
        assert "blocked" in err.lower()

    def test_ipv4_loopback_blocked(self) -> None:
        ok, err = validate_arr_url("http://127.0.0.1:7878")
        assert ok is False
        assert "blocked" in err.lower()

    def test_zero_address_blocked(self) -> None:
        ok, err = validate_arr_url("http://0.0.0.0:7878")
        assert ok is False

    def test_azure_metadata_blocked(self) -> None:
        ok, err = validate_arr_url("http://metadata.azure.com")
        assert ok is False

    def test_alibaba_metadata_blocked(self) -> None:
        ok, err = validate_arr_url("http://100.100.100.200")
        assert ok is False


# ---------------------------------------------------------------------------
# safe_int
# ---------------------------------------------------------------------------

class TestSafeInt:
    """Integer parsing with clamping and safe defaults."""

    def test_valid_value(self) -> None:
        assert safe_int("30", default=5, minimum=1, maximum=1440) == 30

    def test_none_returns_default(self) -> None:
        assert safe_int(None, default=5, minimum=1, maximum=1440) == 5

    def test_empty_string_returns_default(self) -> None:
        assert safe_int("", default=5, minimum=1, maximum=1440) == 5

    def test_non_numeric_returns_default(self) -> None:
        assert safe_int("abc", default=5, minimum=1, maximum=1440) == 5

    def test_below_minimum_clamped(self) -> None:
        assert safe_int("0", default=5, minimum=1, maximum=1440) == 1

    def test_above_maximum_clamped(self) -> None:
        assert safe_int("9999", default=5, minimum=1, maximum=1440) == 1440

    def test_negative_below_minimum_clamped(self) -> None:
        assert safe_int("-5", default=5, minimum=1, maximum=100) == 1


# ---------------------------------------------------------------------------
# safe_log_level
# ---------------------------------------------------------------------------

class TestSafeLogLevel:
    """Log level allowlist with case-insensitive matching."""

    def test_debug_accepted(self) -> None:
        assert safe_log_level("debug") == "debug"

    def test_uppercase_normalised(self) -> None:
        assert safe_log_level("INFO") == "info"

    def test_whitespace_stripped(self) -> None:
        assert safe_log_level(" warning ") == "warning"

    def test_disallowed_level_defaults(self) -> None:
        assert safe_log_level("critical") == "info"

    def test_empty_string_defaults(self) -> None:
        assert safe_log_level("") == "info"

    def test_none_defaults(self) -> None:
        assert safe_log_level(None) == "info"
