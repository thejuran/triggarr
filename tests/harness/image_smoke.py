"""Shipped-image startup smoke driver (CISHIP-01).

Runs every CISHIP-01 assertion -- health, setup/login, static assets, writable
config, persistence across a restart -- against the exact image under test,
started through its real ENTRYPOINT with no source mounts, plus the permanent
missing-static-asset negative (D-01, D-03, D-04). CI's image-smoke job (Plan
07) invokes this exact module against the audited publish-candidate image;
keeping the logic here means the positive run and the negative run share the
same check code.

Usage::

    python -m tests.harness.image_smoke run --image IMAGE --expected-image-id-file PATH

All driver output goes through loguru to stderr -- never the print builtin or
the stdlib logging module (CLAUDE.md). The one exception is a short Python
snippet that runs *inside* the container under test (reading
triggarr.web.routes.STATIC_DIR), not in this driver process.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

from loguru import logger

from tests.harness import checks, stack

_HARNESS_DIR = Path(__file__).resolve().parent
_STUB_SCRIPT_PATH = _HARNESS_DIR / "arr_stub.py"
_FIXTURE_PATH = _HARNESS_DIR / "fixtures" / "triggarr-ci.toml"

_USERNAME = "ci-admin"
_FIRST_RUN_EXIT_TIMEOUT = 60.0
_FIRST_RUN_HEALTH_TIMEOUT = 60.0
_SEEDED_HEALTH_TIMEOUT = 90.0
_DOCKER_HEALTH_TIMEOUT = 120.0
_RESTART_HEALTH_TIMEOUT = 90.0
_LOG_TAIL_LINES = 200
_REDACTED = "***"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="image_smoke", description="Shipped-image startup smoke driver.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run every CISHIP-01 assertion against an image.")
    run_parser.add_argument("--image", required=True, help="Image reference to smoke-test.")
    run_parser.add_argument(
        "--expected-image-id-file",
        required=True,
        help="Path to a file containing the expected docker image ID (D-30).",
    )
    return parser


def _step_a_first_run(session: stack.HarnessSession, image: str) -> None:
    """Fresh volume, first boot: exits 1 after writing a default config, then serves setup."""
    logger.info("[smoke] step A: first-run default-config exit")
    volume = stack.create_volume(session, "firstrun-config")
    name, _port = stack.start_triggarr(session, role="firstrun", image=image, volume=volume, network=None)

    exit_code = stack.wait_for_exit(name, _FIRST_RUN_EXIT_TIMEOUT)
    boot_logs = stack.container_logs(name)
    if exit_code != 1 or "Default config written to" not in boot_logs:
        raise checks.SmokeCheckError(
            "first-run", f"expected exit 1 with a default-config log line, got exit={exit_code}"
        )

    stack.run_docker(["docker", "start", name])
    # Docker reassigns a fresh ephemeral host port on every "docker start" for a
    # dynamic (unspecified) host port -- the port captured at the initial "docker
    # run -d" no longer applies once the container has exited and restarted.
    restarted_port = stack.published_port(name, stack.APP_PORT)
    base = f"http://127.0.0.1:{restarted_port}"
    stack.wait_for_http_health(base, _FIRST_RUN_HEALTH_TIMEOUT)
    checks.check_setup_available(base)
    stack.exec_in(name, ["cat", "/config/triggarr.toml"])  # Must succeed: the app wrote a readable config.

    stack.stop_and_remove(name)
    stack.run_docker(["docker", "volume", "rm", volume])


def _step_b_seeded_run(
    session: stack.HarnessSession,
    image: str,
    username: str,
    disposable_password: str,
    disposable_wrong_password: str,
    known_names: dict[str, str],
) -> tuple[str, str, str, str]:
    """Seeded against the stub: setup, login, dashboard, and a writable, correctly-owned config."""
    logger.info("[smoke] step B: seeded run against the stub")
    network = stack.create_network(session, "net")

    stub_name, _stub_port = stack.start_stub(
        session,
        role="stub",
        image=image,
        network=network,
        api_key=stack.STUB_API_KEY,
        stub_script_path=str(_STUB_SCRIPT_PATH),
    )
    known_names["stub"] = stub_name

    config_volume = stack.create_volume(session, "config")
    stack.seed_volume(session, "config-seed", image=image, volume=config_volume, config_file=_FIXTURE_PATH)

    app_name, app_port = stack.start_triggarr(session, role="app", image=image, volume=config_volume, network=network)
    known_names["app"] = app_name
    base = f"http://127.0.0.1:{app_port}"

    stack.wait_for_http_health(base, _SEEDED_HEALTH_TIMEOUT)
    app_logs = stack.container_logs(app_name)
    if "Connection validated" not in app_logs:
        raise checks.SmokeCheckError("stub-connection", "app logs do not show a validated *arr connection")

    checks.check_static_assets(base)
    checks.check_setup_available(base)
    checks.complete_setup(base, username, disposable_password)
    checks.check_setup_closed(base)
    checks.check_protected_redirects_to_login(base)
    checks.check_login_rejected(base, username, disposable_wrong_password)
    cookie = checks.login(base, username, disposable_password)
    checks.check_dashboard(base, cookie)

    owner = stack.exec_in(app_name, ["stat", "-c", "%u:%g", "/config/triggarr.toml"]).stdout.strip()
    config_text = stack.exec_in(app_name, ["cat", "/config/triggarr.toml"]).stdout
    if owner != stack.RUN_UID_GID or f'username = "{username}"' not in config_text:
        raise checks.SmokeCheckError("config-write", f"unexpected config owner {owner!r} or missing admin username")

    stack.wait_for_docker_health(app_name, _DOCKER_HEALTH_TIMEOUT)
    return network, config_volume, app_name, base


def _step_c_restart(
    session: stack.HarnessSession,
    image: str,
    username: str,
    disposable_password: str,
    network: str,
    config_volume: str,
    app_name: str,
    known_names: dict[str, str],
    collected_logs: dict[str, str],
) -> tuple[str, str]:
    """Stop the first app container; a fresh one on the same volume still has the account."""
    logger.info("[smoke] step C: restart on the same volume")
    collected_logs["app"] = stack.container_logs(app_name)
    del known_names["app"]
    stack.stop_and_remove(app_name)

    app2_name, app2_port = stack.start_triggarr(
        session, role="app-2", image=image, volume=config_volume, network=network
    )
    known_names["app-2"] = app2_name
    base = f"http://127.0.0.1:{app2_port}"

    stack.wait_for_http_health(base, _RESTART_HEALTH_TIMEOUT)
    checks.check_setup_closed(base)
    cookie = checks.login(base, username, disposable_password)
    checks.check_dashboard(base, cookie)

    config_text = stack.exec_in(app2_name, ["cat", "/config/triggarr.toml"]).stdout
    if f'username = "{username}"' not in config_text:
        raise checks.SmokeCheckError("persistence", "config after restart no longer contains the admin username")

    return app2_name, base


def _step_d_missing_static_asset(app2_name: str, base: str) -> None:
    """Permanent negative (D-01/D-03): delete a packaged static asset, confirm the exact rejection."""
    logger.info("[smoke] step D: missing static asset negative")
    result = stack.exec_in(
        app2_name,
        ["python", "-c", "from triggarr.web.routes import STATIC_DIR; print(STATIC_DIR)"],
    )
    static_dir = result.stdout.strip()
    stack.exec_in(app2_name, ["rm", f"{static_dir}/css/output.css"], user="0")
    checks.expect_failure("static-asset-missing", checks.check_static_assets, base)
    logger.info("[smoke] negative static-asset-missing: rejected as expected")


def _step_e_log_hygiene(
    known_names: dict[str, str], collected_logs: dict[str, str], secret_values: list[str]
) -> None:
    """Every container's logs must be free of every disposable credential this run minted."""
    logger.info("[smoke] step E: log hygiene across containers")
    for role, name in known_names.items():
        collected_logs[role] = stack.container_logs(name)
    for role, logs in collected_logs.items():
        for value in secret_values:
            if value and value in logs:
                raise checks.SmokeCheckError("secret-in-logs", f"container role {role!r} shows a disposable secret")


def _dump_logs(known_names: dict[str, str], collected_logs: dict[str, str], secret_values: list[str]) -> None:
    """On failure, log the last lines of every known container's logs with every secret value blanked out."""
    for role, name in known_names.items():
        collected_logs[role] = stack.container_logs(name)
    for role, logs in collected_logs.items():
        redacted = logs
        for value in secret_values:
            if value:
                redacted = redacted.replace(value, _REDACTED)
        tail = "\n".join(redacted.splitlines()[-_LOG_TAIL_LINES:])
        logger.error("[smoke] {role} container logs (tail, redacted):\n{tail}", role=role, tail=tail)


def _run(image: str, expected_image_id_file: Path) -> int:
    expected_id = expected_image_id_file.read_text(encoding="utf-8").strip()
    session = stack.new_session("smoke")
    logger.info("[smoke] session {sid}", sid=session.session_id)

    username = _USERNAME
    # Disposable per run; never written anywhere other than this process's own memory
    # and the two form-submissions below.
    disposable_password = secrets.token_urlsafe(18)
    disposable_wrong_password = secrets.token_urlsafe(18)
    secret_values = [disposable_password, disposable_wrong_password, stack.STUB_API_KEY]

    known_names: dict[str, str] = {}
    collected_logs: dict[str, str] = {}

    try:
        logger.info("[smoke] step 0: verify image identity")
        stack.assert_image_identity(image, expected_id)

        _step_a_first_run(session, image)

        network, config_volume, app_name, _app_base = _step_b_seeded_run(
            session, image, username, disposable_password, disposable_wrong_password, known_names
        )

        app2_name, app2_base = _step_c_restart(
            session,
            image,
            username,
            disposable_password,
            network,
            config_volume,
            app_name,
            known_names,
            collected_logs,
        )

        _step_d_missing_static_asset(app2_name, app2_base)

        _step_e_log_hygiene(known_names, collected_logs, secret_values)

        logger.info("SMOKE PASSED")
        return 0
    except checks.SmokeCheckError as exc:
        logger.error("SMOKE FAILED [{}] {}", exc.reason, exc.detail)
        _dump_logs(known_names, collected_logs, secret_values)
        return 1
    except Exception as exc:  # Top-level driver boundary: never exit without tearing down.
        logger.error("SMOKE FAILED [{}] {}", "unexpected-error", type(exc).__name__)
        _dump_logs(known_names, collected_logs, secret_values)
        return 1
    finally:
        session.teardown()


def main(argv: list[str]) -> int:
    """Parse CLI args and run the smoke sequence; always returns 0 (pass) or 1 (fail)."""
    logger.remove()
    logger.add(sys.stderr, format="{message}", level="INFO")

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(image=args.image, expected_image_id_file=Path(args.expected_image_id_file))
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
