"""Tests for triggarr.web.validation helpers."""

from __future__ import annotations

from triggarr.web.validation import safe_int, safe_log_level, validate_arr_url, validate_instance_name

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

    # SHIELD-007: IPv4-mapped IPv6 SSRF bypass prevention

    def test_ipv4_mapped_ipv6_loopback_blocked(self) -> None:
        ok, err = validate_arr_url("http://[::ffff:127.0.0.1]:7878")
        assert ok is False
        assert "blocked" in err.lower()

    def test_ipv4_mapped_ipv6_link_local_blocked(self) -> None:
        ok, err = validate_arr_url("http://[::ffff:169.254.169.254]:7878")
        assert ok is False
        assert "blocked" in err.lower()

    def test_ipv4_mapped_ipv6_unspecified_blocked(self) -> None:
        ok, err = validate_arr_url("http://[::ffff:0.0.0.0]:7878")
        assert ok is False
        assert "blocked" in err.lower()

    def test_ipv4_mapped_ipv6_multicast_blocked(self) -> None:
        ok, err = validate_arr_url("http://[::ffff:224.0.0.1]:7878")
        assert ok is False
        assert "blocked" in err.lower()

    # SHIELD-007: Multicast address blocking

    def test_multicast_ipv4_blocked(self) -> None:
        ok, err = validate_arr_url("http://224.0.0.1:7878")
        assert ok is False
        assert "blocked" in err.lower()

    def test_multicast_ipv6_blocked(self) -> None:
        ok, err = validate_arr_url("http://[ff02::1]:7878")
        assert ok is False
        assert "blocked" in err.lower()

    # SHIELD-007: Private IPs via IPv4-mapped IPv6 still allowed

    def test_ipv4_mapped_ipv6_private_192_allowed(self) -> None:
        ok, err = validate_arr_url("http://[::ffff:192.168.1.100]:7878")
        assert ok is True
        assert err == ""

    def test_ipv4_mapped_ipv6_private_10_allowed(self) -> None:
        ok, err = validate_arr_url("http://[::ffff:10.0.0.1]:7878")
        assert ok is True
        assert err == ""


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
        assert safe_int("0", default=5, minimum=0, maximum=1440) == 0

    def test_above_maximum_clamped(self) -> None:
        assert safe_int("9999", default=5, minimum=1, maximum=1440) == 1440

    def test_negative_clamped_to_zero(self) -> None:
        assert safe_int("-5", default=5, minimum=0, maximum=100) == 0

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


# ---------------------------------------------------------------------------
# validate_instance_name
# ---------------------------------------------------------------------------


class TestValidateInstanceName:
    """Instance name validation: empty, too-long, double-underscore, invalid chars."""

    def test_empty_rejected(self) -> None:
        ok, err = validate_instance_name("")
        assert ok is False
        assert "empty" in err.lower()

    def test_whitespace_only_rejected(self) -> None:
        ok, err = validate_instance_name("   ")
        assert ok is False
        assert "empty" in err.lower()

    def test_too_long_rejected(self) -> None:
        ok, err = validate_instance_name("a" * 33)
        assert ok is False
        assert "too long" in err.lower()

    def test_double_underscore_rejected(self) -> None:
        ok, err = validate_instance_name("foo__bar")
        assert ok is False
        assert "double underscore" in err.lower()

    def test_invalid_start_char_rejected(self) -> None:
        ok, err = validate_instance_name("!bad")
        assert ok is False
        assert "alphanumeric" in err.lower()

    def test_valid_simple_name(self) -> None:
        ok, err = validate_instance_name("My Instance")
        assert ok is True
        assert err == ""

    def test_valid_name_with_digits(self) -> None:
        ok, err = validate_instance_name("4K Radarr")
        assert ok is True
        assert err == ""

    def test_valid_name_with_single_underscore(self) -> None:
        ok, err = validate_instance_name("my_instance")
        assert ok is True
        assert err == ""

    def test_valid_name_with_dot_and_hyphen(self) -> None:
        ok, err = validate_instance_name("v2.0-test")
        assert ok is True
        assert err == ""

    def test_max_length_accepted(self) -> None:
        ok, err = validate_instance_name("a" * 32)
        assert ok is True
        assert err == ""
