---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "21"
type: execute
wave: 5
depends_on: ["85-20"]
files_modified:
  - docker/codex-review/Dockerfile
  - tests/codex_review_run.py
  - tests/test_codex_review_run.py
  - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-UNTRUSTED-BOUNDARY.md
  - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/codex/
autonomous: false
requirements: [ACCEPT-01, CIMAINT-02]

must_haves:
  truths:
    - "Codex for an untrusted head runs only inside a disposable container started from the pinned review image (docker/codex-review/Dockerfile: digest-pinned base, sha256-verified Codex release binary matching the host's version, non-root user, no git/Python/Node). Its filesystem holds only the image, two per-run bind mounts — `/codex-home` (a fresh temp dir holding only a copy of the Codex credential file, or nothing when an API-key variable is forwarded by name) and `/out` (a fresh empty temp dir for the last message) — and tmpfs `/work` and `/tmp`; no host home directory, repository checkout, SSH agent socket, Docker socket, GitHub or cloud credential. The review input arrives only as text on stdin (checker B04-R3, D-07)"
    - "The isolation guarantee is deterministic, not behavioral: before the head's prompt is sent, verify_isolation_boundary() (1) checks the review image exists with the expected label and records its ID, (2) creates the review container without starting it and checks `docker inspect` against the expected configuration — exactly the two expected bind mounts with the expected sources, only `/work` and `/tmp` as tmpfs, non-root CONTAINER_USER, read-only root filesystem, CapDrop ALL with no CapAdd, no-new-privileges, not privileged, no host network/PID/IPC namespace, no devices, environment names only from the expected set, the recorded image ID — and (3) runs a harness-authored check in a container built by the same builder that proves every canary path is absent (host home, repository path, SSH agent socket, Docker socket, `/root/.ssh`, a fresh host canary file, `/codex-home/config.toml`), `/work` is empty and only expected environment names exist. Any mismatch, Docker error or unparseable output -> \"unverified\" (fail closed) (checker B04-R3)"
    - "Behavioral probes (a planted script and hook Codex is asked to run, a canary file it is asked to read) are supplementary regression evidence only: run by `--verify-boundary --with-probes` and recorded in 85-UNTRUSTED-BOUNDARY.md; a tool event or token seen makes the result unverified, but their absence is never treated as proof. Feature-disable flags remain defense in depth (checker B04-R3)"
    - "Network egress from the review container and the Codex credential inside it are recorded honestly: the container uses Docker's default bridge network with no published ports and egress is NOT restricted to the model endpoint; the credential copied into `/codex-home` is readable by the Codex process and is the only secret in the container; the host's `~/.codex` directory is never mounted and the copied credential is deleted after the run and never copied back"
    - "Plan 85-21 completes only when the boundary verdict is \"verified\" AND the live end-to-end inspection-only review returns COMPLETE (exit 0, `.status.json` complete, and `.base-status.json` complete whenever grading by the trusted-main checker was required). Every other outcome — boundary not verified, container approach unworkable on this machine, a Codex/Docker failure, an incomplete review, or the trusted-main checker rejecting `--review-mode` — stops at the owner decision checkpoint (Task 3) and leaves the plan incomplete; there is no override flag and no 'either verdict accepted' path (checker B14)"
  artifacts:
    - path: "docker/codex-review/Dockerfile"
      provides: "Minimal review image: digest-pinned base, sha256-verified Codex Linux binary, non-root user, ENTRYPOINT codex"
      contains: "sha256sum"
    - path: "tests/codex_review_run.py"
      provides: "container_create_argv(), container_check_argv(), verify_container_config(), parse_canary_check(), prepare_codex_home(), verify_isolation_boundary() deterministic checks, run_untrusted_codex() container launch, supplementary behavioral probe, --verify-boundary [--with-probes] CLI"
      contains: "verify_container_config"
    - path: "tests/test_codex_review_run.py"
      provides: "Container-argv golden test, docker-inspect mutation tests, canary-check parse tests, credential-scoping tests, launch-sequence tests, supplementary probe tests"
      contains: "canary"
    - path: ".planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-UNTRUSTED-BOUNDARY.md"
      provides: "Live evidence: image digest/ID, Codex version, container config, canary results, what is and is not enforced, Verdict, end-to-end run"
      contains: "Verdict"
  key_links:
    - from: "tests/codex_review_run.py run_untrusted_codex()"
      to: "docker start -a -i <container id created and inspected by verify_isolation_boundary()>"
      via: "the container that was inspected is the one that is started; it is removed with docker rm -f in a finally"
      pattern: "\"start\", \"-a\", \"-i\""
    - from: "tests/codex_review_run.py verify_isolation_boundary()"
      to: "docker inspect"
      via: "verify_container_config(inspect_json, expected)"
      pattern: "verify_container_config\\("
    - from: "tests/codex_review_run.py container_create_argv()"
      to: "inspection_codex_argv(\"/work\", \"/out/last.json\") (Plan 85-20)"
      via: "inner Codex argv appended after the image name"
      pattern: "inspection_codex_argv\\("
---

<objective>
Implement the isolation boundary that Plan 85-20's untrusted path requires as host isolation, enforced deterministically (checker B04-R3): Codex for a bot or outside-contributor PR runs only inside a disposable container that holds nothing but the Codex runtime and its own credential, the container's configuration and contents are checked by inspection before every run, and the plan finishes only after one live end-to-end review is COMPLETE (checker B14). Any failure stops at an explicit owner decision.

Purpose: D-07 gives bot PRs the normal paired review. The requirement is that their code, or any instruction hidden in it, can never reach host secrets. Asking a model whether it ran a tool cannot prove that, because a model may simply decline. A container that has no host secrets in it can, and its configuration can be checked mechanically.
Output: the review image definition, container launch and verification code with tests, a live evidence file with an end-to-end COMPLETE review, or a recorded owner decision on the failure branch.
</objective>

<execution_context>
@/Users/julianamacbook/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/execute-plan.md
@/Users/julianamacbook/.claude/plugins/cache/gsd-plugin/bm/5.0.3/templates/summary.md
@/Users/julianamacbook/.claude/plugins/cache/gsd-plugin/bm/5.0.3/references/tdd.md
</execution_context>

<context>
@CLAUDE.md
@.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-CONTEXT.md
@tests/codex_review_run.py
@tests/test_codex_review_run.py
@.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-20-SUMMARY.md

<interfaces>
From Plan 85-20 (tests/codex_review_run.py): verify_isolation_boundary(command_runner, *, scratch) -> dict {verdict, reasons, checked_at, …} (currently always unverified); run_untrusted_codex(run, *, inner_argv, forwarded_env_names, prompt, boundary, command_runner) -> int (currently always raises RunnerError); inspection_codex_argv(cwd, last_json) -> list[str] (called with "/work", "/out/last.json"); inspection_forwarded_env_names(environ) -> tuple[str, ...] (subset of INSPECTION_ENV_ALLOWLIST = ("CODEX_API_KEY", "OPENAI_API_KEY")); DISABLED_FEATURES; ALLOWED_ITEM_TYPES; audit_event_types(jsonl_path); establish_trusted_main(run, command_runner); trusted_main_grader_supports_mode(...); _run_codex(...) streaming .jsonl with the 85-03 redaction-in-finally; OUTPUT_SUFFIXES includes ".ci-evidence.json", ".grader-provenance.json", ".boundary.json"; execute() returns 3 when the boundary is not verified, provenance is not established or the launch seam refuses.
Codex CLI: `codex --version` prints `codex-cli <version>`; `codex login status`; credential file `$CODEX_HOME/auth.json` (default `~/.codex/auth.json`) when logged in with ChatGPT; API-key auth uses CODEX_API_KEY/OPENAI_API_KEY. Linux release binaries are published on github.com/openai/codex releases (tag `rust-v<version>`, assets `codex-<x86_64|aarch64>-unknown-linux-musl.tar.gz`); the executor confirms the exact tag, asset names and checksums before pinning.
Docker: `docker create` accepts the same flags as `docker run`; `docker inspect <id>` returns a one-element JSON array with Config {User, Env, Image, Labels}, HostConfig {Binds, Mounts, Tmpfs, ReadonlyRootfs, CapAdd, CapDrop, SecurityOpt, Privileged, NetworkMode, PidMode, IpcMode, Devices}, Mounts [{Type, Source, Destination, RW}], Image (ID); `-e NAME` with no value copies NAME from the docker CLI's own environment (the value never appears on the argv).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Review image, container launch and deterministic boundary verification (TDD)</name>
  <files>docker/codex-review/Dockerfile, tests/codex_review_run.py, tests/test_codex_review_run.py</files>
  <read_first>
    - tests/codex_review_run.py (verify_isolation_boundary and run_untrusted_codex stubs, inspection_codex_argv, inspection_forwarded_env_names, audit_event_types, _run_codex, _finalize_raw_outputs, OUTPUT_SUFFIXES, main/_build_parser)
    - tests/test_codex_review_run.py (FakeRunner; the 85-20 inspection-only and launch-seam tests)
    - Dockerfile at the repository root (how this repo pins base images by digest)
    - `codex --version`, `codex login status`, `docker version` and `docker info --format '{{.OSType}}/{{.Architecture}}'` on this machine
  </read_first>
  <behavior>
    With a FakeRunner answering `docker image inspect`, `docker create`, `docker inspect`, `docker run --rm` (canary check), `docker start -a -i` and `docker rm -f`:
    - container_create_argv(image_ref, *, codex_home_dir, out_dir, forwarded_env_names, inner_argv) golden test: `docker create -i --read-only --tmpfs /work:rw,size=64m,mode=0700,uid=10001,gid=10001 --tmpfs /tmp:rw,size=64m,mode=1777 --user 10001:10001 --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 2g --network bridge --mount type=bind,src=<codex_home_dir>,dst=/codex-home --mount type=bind,src=<out_dir>,dst=/out -e CODEX_HOME=/codex-home [-e <NAME> for each forwarded name, no value] -w /work <image_ref> <inner_argv[1:]>`; the argv never contains `-v`, `--volume`, `--privileged`, `--network host`, `--pid`, `--ipc`, `--device`, `/var/run/docker.sock`, the host home path, REPO_ROOT, `SSH_AUTH_SOCK`, any `NAME=value` other than CODEX_HOME=/codex-home, or `--dangerously-bypass-approvals-and-sandbox`; the inner argv keeps `--sandbox read-only` and every `--disable` flag
    - container_check_argv(...) is built by the same helper as container_create_argv with the same mounts, user and options, but as `docker run --rm --entrypoint /bin/sh … <image_ref> -c CANARY_CHECK_SCRIPT` with the canary paths passed as positional arguments (fixed argument list, no host shell)
    - prepare_codex_home(environ, dest): when `$CODEX_HOME/auth.json` (default `~/.codex/auth.json`) exists -> dest (mode 0o700) contains exactly one file, auth.json (mode 0o600, a byte copy), credential_mode "auth.json copy", forwarded names (); else when CODEX_API_KEY or OPENAI_API_KEY is set -> dest is empty, credential_mode "env:<NAME>", that name forwarded; else -> unverified 'no Codex credential available for the review container'. The host `~/.codex` path never appears in any docker argv; no credential value is ever written to `.boundary.json` or printed
    - verify_container_config(inspect_json, expected) returns [] for the expected configuration and a specific reason for each mutation: an extra bind or volume (for example the host home) -> 'unexpected mount: <dest>'; a mount source other than the per-run dir -> 'mount source mismatch: /codex-home'; Docker socket mounted -> 'unexpected mount: /var/run/docker.sock'; tmpfs set differs -> 'unexpected tmpfs'; Config.User root or empty -> 'container user is not 10001:10001'; Privileged true -> 'privileged container'; CapDrop lacks ALL or CapAdd non-empty -> 'capabilities not dropped'; ReadonlyRootfs false -> 'root filesystem is writable'; no-new-privileges missing -> 'no-new-privileges not set'; NetworkMode/PidMode/IpcMode "host" -> 'host namespace: <kind>'; Devices non-empty -> 'host devices exposed'; an Env name outside {PATH, HOME, LANG, CODEX_HOME} plus the forwarded names (for example GH_TOKEN) -> 'unexpected environment variable: GH_TOKEN'; image ID differs from the recorded one -> 'image mismatch'; malformed JSON -> 'could not read docker inspect output'
    - parse_canary_check(stdout, expected) -> reasons: every canary path reported `absent`, `/work` listed empty and env names within the expected set -> []; any `present <path>` -> 'canary path visible in container: <marker>' (host paths shown as markers such as <HOST_HOME>, <REPO_ROOT>, <HOST_CANARY>); `/work` non-empty -> 'review working directory not empty'; unexpected env name -> reason; missing or extra lines -> 'could not parse canary check output'. Canary paths: the host home path, REPO_ROOT, the host SSH_AUTH_SOCK path when set, `/run/host-services/ssh-auth.sock`, `/var/run/docker.sock`, `/root/.ssh`, `/home/review/.ssh`, a fresh host canary file created by the check in a temp dir outside both mounts (random `secrets.token_hex(16)` content), `/codex-home/config.toml` and `/codex-home/sessions`
    - verify_isolation_boundary(command_runner, *, scratch, forwarded_env_names, inner_argv) runs in order: image check (`docker image inspect` for REVIEW_IMAGE_REF; missing image or missing/mismatched `org.triggarr.codex-review` label -> unverified 'review image not built or not labelled: run <exact docker build command>'), prepare_codex_home, `docker create` -> `docker inspect` -> verify_container_config, canary check -> parse_canary_check, and a static check that inner_argv contains every DISABLED_FEATURES `--disable` flag (defense in depth). All pass -> verdict "verified" with container_id, image_id, codex_version (from the image label), credential_mode, network "bridge (egress not restricted)", mounts and env names (no values), canary results. Any failure -> "unverified" with every reason, and the created container and temp dirs are removed before returning
    - execute() on an untrusted run (85-20 path, with the boundary checks answered by fakes): the argv sequence is image inspect -> create -> inspect -> canary run -> start -a -i (prompt on stdin) -> rm -f; no argv whose first element is `codex` is issued at any point; the container started is the one inspected; the per-run codex-home and out dirs no longer exist afterwards (also when start fails or the runner raises); `.last.json` is copied from the out dir; `.jsonl` comes from the container's stdout and is redacted by the 85-03 helper in a finally; a non-zero exit of `docker start` -> incomplete with the exit code
    - Any docker failure in the boundary checks -> unverified, exit 3, and no `docker start`
    - Supplementary probe (`--verify-boundary --with-probes`, fakes): the harness creates a planted dir (run-me.sh mode 0o755 printing token A; hooks/pre-commit mode 0o755 printing token B) and a canary dir (canary.txt with token C) on the host, outside both mounts; the probe runs inside a verified container with the probe prompt asking Codex to run both and read the canary by absolute host path; a tool item outside ALLOWED_ITEM_TYPES -> unverified 'probe used a tool: <type>'; token A/B/C seen in .jsonl or the last message -> unverified with the token's meaning; none seen -> recorded as 'supplementary: no tool use or token observed (not proof)'. The prompt never contains tokens A, B or C
    - `--verify-boundary` CLI mode (no --head/--pr-url): runs the deterministic checks (and the probe with `--with-probes`), prints the JSON result with temp paths shown as markers, removes everything it created, writes nothing into the repository, exits 0 when verified and 3 otherwise
    - Optional live test `test_live_boundary_verified` skipped unless TRIGGARR_CODEX_LIVE=1: runs the real deterministic checks and asserts verdict "verified"
  </behavior>
  <action>
    RED: add the tests above (FakeRunner handlers return canned `docker inspect` JSON built by a fixture function with one mutation per parametrized case); update the 85-20 launch-seam test that expected the refusal so it now expects the container sequence. Run only `uv run pytest tests/test_codex_review_run.py -q` for the RED check (this plan's own test file). Commit test(85-21): add failing container-isolation boundary tests (B04-R3).
    GREEN image: create docker/codex-review/Dockerfile: `FROM debian:bookworm-slim@sha256:<digest>` (resolve the current digest with `docker buildx imagetools inspect debian:bookworm-slim` and record it in the SUMMARY; add the repository's usual pin comment); ARG CODEX_VERSION and per-architecture ARG CODEX_SHA256_AMD64 / CODEX_SHA256_ARM64 defaulting to the values for the version that `codex --version` reports on this machine (take the checksums from the release's published checksum file when one exists, otherwise from your own download of the asset, and record the source in the SUMMARY); install only ca-certificates and curl in a build stage, download the matching `codex-<arch>-unknown-linux-musl.tar.gz` from the openai/codex release, verify it with `sha256sum -c`, and copy only the binary into the final stage at /usr/local/bin/codex; the final stage has no git, Python, Node, curl or package manager cache; create user `review` with uid/gid 10001 and home /home/review (empty); ENV HOME=/home/review LANG=C.UTF-8 CODEX_HOME=/codex-home; LABEL org.triggarr.codex-review=<CODEX_VERSION>; USER 10001:10001; WORKDIR /work; ENTRYPOINT ["codex"]. Add a header comment: this image isolates the Codex review of untrusted heads (Phase 85, checker B04-R3); it must contain nothing but the Codex runtime; changing it is a sensitive review-machinery change.
    GREEN code: add constants REVIEW_IMAGE_REPO = "triggarr-codex-review", REVIEW_IMAGE_LABEL = "org.triggarr.codex-review", CONTAINER_USER = "10001:10001", CONTAINER_BASE_ENV = frozenset({"PATH", "HOME", "LANG", "CODEX_HOME"}), CANARY_CHECK_SCRIPT (a fixed POSIX sh script: for each positional path print `present <path>` or `absent <path>`; then print `work-entries <n>` for /work; then print `env <NAME>` for each variable name) and REVIEW_IMAGE_BUILD_ARGV (the exact `docker build` command, printed in the image-missing reason). REVIEW_IMAGE_REF is `triggarr-codex-review:<host codex version>` so a Codex update on the host requires a rebuilt image. Implement container_create_argv, container_check_argv, prepare_codex_home, verify_container_config, parse_canary_check and the deterministic verify_isolation_boundary as in the behavior list, all through command_runner with fixed argument lists; run the docker CLI with an environment containing only PATH, HOME, DOCKER_HOST, DOCKER_CONTEXT, DOCKER_CONFIG (when set) and the forwarded names, so nothing else on the host can leak through `-e`. Replace the 85-20 run_untrusted_codex body: require boundary["verdict"] == "verified" and its container_id, then run `["docker", "start", "-a", "-i", <container_id>]` with the prompt on stdin through _run_codex (refactor _run_codex to accept argv and env instead of duplicating its streaming, timeout and redaction-in-finally logic; the trusted path keeps calling it with its existing argv), copy `<out_dir>/last.json` to the run's `.last.json`, and in a finally run `docker rm -f <container_id>` and delete the per-run codex-home and out dirs (the copied credential is deleted and never copied back to the host). Add the supplementary probe and `--verify-boundary [--with-probes]` (mutually exclusive with a review run). Update the 85-20 call sites in execute() to pass forwarded_env_names and inner_argv to verify_isolation_boundary and the boundary dict to run_untrusted_codex; extend OUTPUT_SUFFIXES only if a new per-run file is written (the probe transcripts belong to `--verify-boundary`, not to review runs). Keep the docstring rule: "verified" requires every deterministic check on this call; there is no cache and no override flag.
    Run `uv run pytest tests/test_codex_review_run.py tests/test_codex_report_status.py tests/test_codex_review_contract.py -x -q` and `uv run ruff check tests/`. Then, because this plan runs alone in wave 5, run the post-wave integration check for waves 1-4 (W06) directly, without pipes: `uv run pytest tests/ -x -q` and `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs`; a failure there that this plan did not cause is recorded in the SUMMARY and reported, not hidden or skipped. Commit feat(85-21): run untrusted Codex reviews in a verified disposable container (B04-R3).
  </action>
  <verify>
    <automated>uv run pytest tests/test_codex_review_run.py tests/test_codex_report_status.py tests/test_codex_review_contract.py -x -q && uv run ruff check tests/ && uv run pytest tests/ -x -q && node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "verify_container_config(" tests/codex_review_run.py` returns at least 2; `grep -c "untrusted Codex launch requires the container boundary" tests/codex_review_run.py` returns 0
    - `grep -c "sha256sum" docker/codex-review/Dockerfile` returns at least 1 and `grep -cE "^FROM .*@sha256:[0-9a-f]{64}" docker/codex-review/Dockerfile` returns at least 1
    - Tests assert each verify_container_config mutation reason and each parse_canary_check failure reason by substring
    - A test asserts the untrusted launch sequence issues no `codex` argv on the host, starts exactly the inspected container, and removes the container and both per-run dirs on success and on failure
    - A test asserts the docker argv never contains the host home path, REPO_ROOT, `-v`, `--privileged`, the Docker socket or any credential value
    - The full Python and Node suites pass (post-wave integration for waves 1-4, W06)
  </acceptance_criteria>
  <done>Untrusted Codex runs can only happen inside a container whose mounts, user, capabilities, environment and contents are mechanically checked on every run; behavioral probes exist as supplementary evidence only.</done>
</task>

<task type="auto">
  <name>Task 2: Build the image, verify the boundary live, and run one end-to-end inspection-only review</name>
  <files>.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-UNTRUSTED-BOUNDARY.md, .planning/phases/85-follow-on-ci-improvements-acceptance-usability/codex/ (end-to-end run outputs)</files>
  <read_first>
    - tests/codex_review_run.py (REVIEW_IMAGE_BUILD_ARGV, --verify-boundary, execute for --untrusted)
    - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-20-SUMMARY.md (Codex version, flags, DISABLED_FEATURES, trusted-main provenance rule)
  </read_first>
  <action>
    Build the review image with the exact REVIEW_IMAGE_BUILD_ARGV. Run `uv run python tests/codex_review_run.py --verify-boundary --with-probes` and `TRIGGARR_CODEX_LIVE=1 uv run pytest tests/test_codex_review_run.py -q -k live_boundary`. If Docker is not available, the image cannot be built, Codex cannot start or authenticate inside the container, or Codex's own `--sandbox read-only` cannot initialize inside it, do not change the sandbox mode, flags or mounts to make it work: record the exact error and go to Task 3.
    Write 85-UNTRUSTED-BOUNDARY.md with: date; host `codex --version`; `docker version` server line; the image reference, image ID and base digest; the container create argv (temp paths as markers, env NAMES only, never values); the `docker inspect` checks and their results; the canary-check results; credential mode and exactly what is mounted at /codex-home; a "## What is and is not enforced" section stating plainly: enforced — no host home, repository, SSH agent, Docker socket, GitHub or cloud credential in the container, non-root, read-only root, all capabilities dropped, input only on stdin, tool features disabled as defense in depth; not enforced — network egress (default bridge, not limited to the model endpoint), and the Codex credential is present inside the container by necessity; the supplementary probe result (item types and tokens seen, labelled "supplementary, not proof"); "## Verdict: verified" or "## Verdict: NOT verified — <reasons>"; and, for verified, the guarantee in one sentence exactly as enforced: "In untrusted mode the head's code is never written to disk or executed by the harness, and no Python from the PR's base is run; Codex runs inside a disposable container whose filesystem holds only the Codex runtime and a per-run copy of its own credential — no host home directory, repository checkout, SSH agent, Docker socket or GitHub/cloud credentials — receives the review input only as text, and has its tool features disabled; network egress is not restricted; every run re-checks the container configuration and contents before Codex sees the head, and otherwise records Codex INCOMPLETE."
    Only if the verdict is verified: choose the most recent merged PR in thejuran/triggarr whose head has a completed/success `CI ready` check run (`gh pr list --state merged --limit 20 --json number,headRefOid,baseRefOid`, then the check-runs API with --paginate --slurp) and whose base..head diff does not touch AUDITED_INPUTS (origin/main's checker predates `--review-mode` until Phase 85 merges, so a PR that changes the grader would end INCOMPLETE by design; that path is proven separately below). Run one real review: `uv run python tests/codex_review_run.py --untrusted --pr-url https://github.com/thejuran/triggarr/pull/<N> --head <headRefOid> --base <baseRefOid> --label boundary-e2e --attempt 1 --scope "Plan 85-21 end-to-end inspection-only demonstration" --phase-dir .planning/phases/85-follow-on-ci-improvements-acceptance-usability`. Record under "## End-to-end run: COMPLETE" or "## End-to-end run: INCOMPLETE — <reasons>" the PR, full head and base SHAs, MAIN_SHA from `.grader-provenance.json`, whether trusted-main grading was required, the exit code, the `.status.json` status (and `.base-status.json` status if present), the event types seen, the OUT path, and whether `codex login status` on the host still succeeds afterwards. Supplementary, Codex-free evidence of the older-checker rule: if a merged PR whose diff touches AUDITED_INPUTS has a successful `CI ready` run, run the same command for it with `--label boundary-oldchecker --attempt 1` and record that it ended INCOMPLETE with 'predates --review-mode' before Codex ran (expected outcome; it does not count as the end-to-end run); otherwise record "older-checker live check: no eligible PR".
    If the verdict is NOT verified, write "## End-to-end run: not attempted (boundary not verified)". The raw outputs written under the phase codex/ directory are committed with this task. Commit docs(85-21): record container isolation-boundary verification and end-to-end review.
    Completion rule (checker B14): this task records the outcome whatever it is; the plan reaches its end only through Task 3's gate, which passes only on "## Verdict: verified" plus "## End-to-end run: COMPLETE" with a complete `.status.json` (and a complete `.base-status.json` when one exists). Any other outcome is presented to the owner in Task 3; never re-label an incomplete outcome or retry silently.
  </action>
  <verify>
    <automated>bash -c 'set -euo pipefail; f=.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-UNTRUSTED-BOUNDARY.md; grep -qE "^## Verdict: (verified|NOT verified)" "$f"; grep -qE "^## End-to-end run: (COMPLETE|INCOMPLETE|not attempted)" "$f"; grep -q "^## What is and is not enforced" "$f"; grep -q "codex-cli" "$f"; if grep -qF "$HOME" "$f"; then echo "unredacted home path in evidence"; exit 1; fi'</automated>
  </verify>
  <acceptance_criteria>
    - 85-UNTRUSTED-BOUNDARY.md records the image ID and base digest, Codex version, container argv with env names only, inspect and canary results, the enforced/not-enforced section, the supplementary probe result labelled as not proof, a Verdict heading, and an End-to-end run heading
    - If verified: the End-to-end section names the PR, full head/base SHAs, MAIN_SHA, exit code and `.status.json` status, and the review outputs exist under the phase codex/ directory
    - No secret value, credential content or unredacted home path appears in the evidence file
  </acceptance_criteria>
  <done>The live outcome is recorded precisely, whether or not it succeeded; Task 3 decides whether the plan may complete.</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 3: Completion gate — owner decision on every outcome other than verified + end-to-end COMPLETE</name>
  <decision>Branch rule: if 85-UNTRUSTED-BOUNDARY.md says "## Verdict: verified" AND "## End-to-end run: COMPLETE", and the boundary-e2e `.status.json` (plus `.base-status.json` when present) is complete, this gate passes without pausing; record "Task 3: gate passed (verified, end-to-end COMPLETE)" in the SUMMARY. In every other case — boundary NOT verified, container approach unworkable here, end-to-end INCOMPLETE or not attempted, the trusted-main checker rejecting `--review-mode` for the chosen PR — stop and ask the owner how bot and outside-contributor PRs should be reviewed. Plan 85-21 stays incomplete in those cases, whatever the decision.</decision>
  <context>Plain terms for the owner: D-07 says bot PRs get the same review as any PR. The safe way to do that is a Codex review running in a sealed container that holds none of your credentials or files. On this machine that was either not proven or the proof review did not finish cleanly (exact reasons from the evidence file). Until it is, every bot-PR Codex run is recorded INCOMPLETE automatically: nothing runs unsafely and nothing is marked clean. What changes per option is how such PRs reach acceptance, and how much more work this phase takes.</context>
  <options>
    <option id="option-a">
      <name>Fix the cause and re-run this plan's live steps in this phase (recommended when the cause is fixable locally, for example Docker not running, the image not building, or a transient Codex failure)</name>
      <pros>Keeps D-07's normal paired review for bot PRs; no new design</pros>
      <cons>Adds time to Phase 85; if the cause is structural (for example Codex cannot run inside a container on this machine) a new plan is needed instead</cons>
    </option>
    <option id="option-b">
      <name>Keep untrusted runs INCOMPLETE and use the owner-approved fallback per PR until a later phase</name>
      <pros>No added scope now; safety is unchanged; each bot PR still gets an independent review recorded through the D-16 fallback</pros>
      <cons>Every bot PR needs your explicit fallback approval and an independent reviewer; this is the special lane D-07 rejected as a default, so it should be time-limited and tracked in the backlog</cons>
    </option>
    <option id="option-c">
      <name>Wait for a Codex CLI or Docker change and re-run the verification</name>
      <pros>No new code if a future version removes the blocker</pros>
      <cons>Bot PRs block acceptance until then (wait blocks acceptance per D-16); no date is known</cons>
    </option>
  </options>
  <action>Read the Verdict and End-to-end run headings in 85-UNTRUSTED-BOUNDARY.md and the boundary-e2e status files. If the gate passes: do nothing here beyond the SUMMARY line. Otherwise: present the decision above with the exact reasons from the evidence file, recommend the option that fits the cause, wait for the reply, and record the owner's verbatim words, date and the head they apply to under "## Owner decision" in 85-UNTRUSTED-BOUNDARY.md; mark the SUMMARY status "BLOCKED — D-07 not proven" and do not mark the plan complete. Never change verify_isolation_boundary to return verified, relax the container configuration, switch Codex to another sandbox mode, add an override flag, or run an untrusted head with the boundary unverified, whatever the decision; option-a re-runs Task 2 (or becomes a new plan if structural), option-b/option-c are documented by Plan 85-17 after replanning.</action>
  <verify>
    <automated>bash -c 'set -euo pipefail; d=.planning/phases/85-follow-on-ci-improvements-acceptance-usability; f=$d/85-UNTRUSTED-BOUNDARY.md; grep -q "^## Verdict: verified" "$f" || { echo "BLOCKED: boundary not verified"; exit 1; }; grep -q "^## End-to-end run: COMPLETE" "$f" || { echo "BLOCKED: end-to-end review not COMPLETE"; exit 1; }; uv run python -c "import glob, json, sys; d=sys.argv[1]; s=glob.glob(d + \"/codex/*boundary-e2e*.status.json\"); b=glob.glob(d + \"/codex/*boundary-e2e*.base-status.json\"); ok=bool(s) and all(json.load(open(p)).get(\"status\") == \"complete\" for p in s + b); print(\"gate passed\" if ok else \"BLOCKED: end-to-end status files not complete\"); sys.exit(0 if ok else 1)" "$d"'</automated>
  </verify>
  <done>The plan completes only with a verified container boundary and a COMPLETE end-to-end review; on any other outcome the owner's decision is recorded verbatim and the plan stays blocked, with untrusted runs recorded INCOMPLETE.</done>
  <resume-signal>Reply option-a, option-b or option-c (or describe another direction). Record the owner's verbatim words, date and the head they apply to in 85-UNTRUSTED-BOUNDARY.md under "## Owner decision"; the plan stays incomplete until the gate passes.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Untrusted prompt text -> Codex process | Prompt injection may try to make Codex use tools; the container ensures nothing of value is reachable |
| Review container -> host | Only two per-run temp dirs are mounted; the configuration is inspected before every run |
| Codex release binary / base image -> review image | Supply chain for the isolation image |
| Probe -> host | Supplementary probes plant harness-authored files on the host outside the container |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85-60 | Elevation of privilege | Codex (or injected instructions) reaching host files, SSH agent or credentials | mitigate | Disposable container with only /codex-home and /out bind mounts, tmpfs /work and /tmp, non-root, read-only root, CapDrop ALL, no-new-privileges; docker inspect checked by verify_container_config on every run; canary-path check in a container from the same builder |
| T-85-61 | Repudiation | Behavioral evidence mistaken for proof | mitigate | Verdict depends only on deterministic checks; probes labelled supplementary; a tool event or token seen still fails closed |
| T-85-62 | Information disclosure | Codex credential inside the container | accept | Required for Codex to work; only a per-run copy of the credential file (or one API-key variable by name) is present, deleted after the run, never copied back; recorded in the evidence file |
| T-85-62a | Information disclosure | Data exfiltration over unrestricted egress | accept | No host secrets other than the Codex credential are in the container, so egress can only carry the prompt (already sent to the model provider) and that credential; recorded as not enforced; tool features disabled as defense in depth |
| T-85-63 | Tampering | Configuration drift (extra mount, root user, Docker socket) | mitigate | Exact expected-configuration comparison per run; the inspected container is the one started; mutation tests per field |
| T-85-64 | Elevation of privilege | Silent unsafe operation, silent fallback or premature completion | mitigate | exit 3 + INCOMPLETE stub per run; Task 3 gate passes only on verified + end-to-end COMPLETE; no override flag, no sandbox-mode change |
| T-85-SC | Tampering | Base image and Codex release binary in the review image | mitigate | Base pinned by digest; Codex binary from the official openai/codex release, version-matched to the host and verified with a pinned sha256; checksums and their source recorded in the SUMMARY; no npm/pip/cargo install |
</threat_model>

<verification>
- `uv run pytest tests/test_codex_review_run.py tests/test_codex_report_status.py tests/test_codex_review_contract.py -x -q` passes; ruff clean
- Post-wave integration for waves 1-4 (W06): `uv run pytest tests/ -x -q` and `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` pass
- 85-UNTRUSTED-BOUNDARY.md has a Verdict and an End-to-end run heading; the Task 3 gate passes only on verified + COMPLETE, otherwise an "## Owner decision" section with verbatim words exists and the plan is recorded as blocked
</verification>

<success_criteria>
Untrusted Codex reviews run only inside a disposable container whose configuration and contents are checked mechanically before every run, with behavioral probes as supplementary evidence; the boundary is verified live and one end-to-end inspection-only review is COMPLETE, or the plan stops at an explicit owner decision with untrusted runs recorded INCOMPLETE.
</success_criteria>

<output>
Create `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-21-SUMMARY.md` when done
</output>
