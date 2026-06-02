# 70-CODEX-REVIEW.md — Codex Adversarial Docs Pass (PDISC-02)

**Provenance:**
- Codex version: codex-cli 0.133.0
- Command: `/opt/homebrew/bin/codex exec --sandbox read-only --ephemeral --color never -o $RAW -c 'approval_policy="never"' "<framing-prompt>" < /dev/null`
- Config: approval=never, sandbox=read-only, model=gpt-5.5, reasoning=xhigh
- Docs reviewed: README.md, SECURITY.md, CONTRIBUTING.md
- Date: 2026-06-02
- Branch: launch-hardening
- Commit: 38fa67f
- Exit code: 0 (success)
- Session ID: 019e8a1e-da78-7032-8349-dadd144e8d45

**Note on flag:** The `--ask-for-approval never` flag documented in RESEARCH.md does not exist in codex-cli 0.133.0. The equivalent is `-c 'approval_policy="never"'`, which achieves the same effect (auto-approve read-only operations without interactive TTY) while keeping `--sandbox read-only` active. stdin redirected from `/dev/null` to suppress TTY wait.

**Credential scrub:** Passed. No real API keys, passwords, tokens, or hostnames-with-embedded-credentials in this artifact. Placeholder strings (`<radarr-api-key>`, `<sonarr-api-key>`, etc.) are allow-listed.

---

## Findings

| Severity | File:Line | Claim/Instruction | Issue Type | Recommended Correction |
|----------|-----------|-------------------|------------|------------------------|
| HIGH | README.md:82, README.md:85 | "install the current release directly" with `triggarr-2.7.2-py3-none-any.whl` | Factually wrong / setup failure | Project version is `2.8.1` in `pyproject.toml` and `triggarr/__init__.py`; the `/releases/latest/download/` URL with a stale wheel filename will 404 once latest points at a release without that asset. Update to `triggarr-2.8.1-py3-none-any.whl`, or use a `curl`+`pip` pattern that queries the latest release without hardcoding the filename. |
| HIGH | README.md:98, README.md:108-109 | Minimal systemd unit runs as `User=triggarr` with `TRIGGARR_CONFIG_DIR=/var/lib/triggarr` | Incomplete / setup failure | Add `StateDirectory=triggarr` to the unit, or instruct users to pre-create the directory: `sudo install -d -o triggarr -g triggarr -m 700 /var/lib/triggarr`. As written, the `triggarr` service user typically cannot create `/var/lib/triggarr`, so the first start fails before config generation. |
| HIGH | README.md:215, SECURITY.md:39 | "URL validation blocks SSRF attempts by rejecting non-HTTP schemes and metadata, link-local, loopback, unspecified, or multicast targets" / "URL inputs are validated against an allow-list of schemes and a block-list of cloud metadata and link-local hostnames" | Factually wrong / misleading security claim | Scope the claim to the web settings form: `validate_arr_url()` is applied only in the settings POST handler, not when loading from TOML. A URL set directly in `triggarr.toml` bypasses SSRF validation. Correct by either scoping the claim ("when saved via the web UI") or moving validation into `InstanceConfig.url` so TOML-loaded config is also validated. |
| MEDIUM | SECURITY.md:18, SECURITY.md:28 | "protects stored service credentials" and "Credential Protection" section describing SecretStr, Loguru redaction, and UI masking | Misleading security claim | `SecretStr` protects repr/log/HTML exposure, not at-rest secrecy. The SECURITY.md implies stronger protection than it delivers. Add an explicit statement that API keys, auth credentials, and session secrets are plaintext in `triggarr.toml`; protect them with file permissions and volume security. (The README's Security Model already says this at README:212 — mirror that caveat in SECURITY.md.) |
| MEDIUM | README.md:25 | "Tag-based filtering — scope searches to specific tags per instance" | Incomplete / misleading behavior | Document fail-open behavior: if tag fetch fails or a configured tag name is not found in the *arr instance, Triggarr logs a warning and searches all items for that queue. A user expecting tag-scoped searches will get unscoped searches silently. Either document this clearly or change behavior to fail closed when a configured tag cannot be resolved. |
| MEDIUM | README.md:275, CONTRIBUTING.md:20 | `uv run tailwindcss -i ... --watch` | Incomplete / version-misleading | Pin the Tailwind binary version in dev instructions and keep it aligned with Docker. The Dockerfile pins `TAILWINDCSS_VERSION=v4.2.1`, while the committed `output.css` header indicates Tailwind `v4.2.2`; first-time contributors who run the watch command may regenerate CSS with a different version. Add `export TAILWINDCSS_VERSION=v4.x.x` before the watch command and document which version to use. |

---

## Notes for Phase 71

- **README.md:85** (HIGH) — the pip install version mismatch is the most critical: a user following the standalone instructions installs v2.7.2, not v2.8.1. The fix is to not hardcode the wheel filename. PREW-01.
- **README.md:98-109** (HIGH) — the systemd unit is a real friction point for standalone users. Adding `StateDirectory=triggarr` is a one-line fix. PREW-01.
- **README.md:215 / SECURITY.md:39** (HIGH) — the SSRF claim overstates protection scope. Either scope the claim or widen the validation. PREW-01 / PREW-03.
- **SECURITY.md:18,28** (MEDIUM) — the credential-protection section needs a plaintext-on-disk caveat to set accurate expectations. PREW-03.
- **README.md:25** (MEDIUM) — tag filtering fail-open behavior should be documented. PREW-01.
- **README.md:275 / CONTRIBUTING.md:20** (MEDIUM) — Tailwind version pinning in dev docs. PREW-01 / PREW-04.
- **SECURITY.md gaps** (from RESEARCH.md — not surfaced by codex but confirmed by direct inspection): CSP nonce (`script-src nonce`), session-secret rotation on password change (CWE-613), `apikey=` URL rejection, Basic-auth control-char validation, session-secret startup length check — none of these appear in SECURITY.md by name. Add to SECURITY.md in Phase 71 PREW-03.
