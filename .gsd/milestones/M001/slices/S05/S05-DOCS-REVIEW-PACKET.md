# S05 Documentation Review Packet

## Reader and Post-Read Action

Reader: an operator installing or upgrading Triggarr.

Post-read action: configure Docker or standalone runtime paths and choose a safe authentication/proxy mode without being misled by stale documentation claims.

This packet is a human-review aid. **Agent-side review is not human UAT** and must not be recorded as human approval. A release verifier can use this packet to focus the review, but a human still needs to approve, request changes, or explicitly defer the documentation gate.

## Review Scope

Review the committed range, not the current working-tree diff:

```bash
git diff --stat a3f09ad^..HEAD -- README.md SECURITY.md TODO.md
git diff a3f09ad^..HEAD -- README.md SECURITY.md TODO.md
```

Expected scope from the range summary:

- `README.md`, `SECURITY.md`, and `TODO.md` are the only docs in this packet's review range.
- The range changes 3 files with 115 insertions and 68 deletions.
- The review source is `a3f09ad^..HEAD`; an empty working-tree diff is insufficient evidence because these changes may already be committed in the local branch.

## Changed Claims to Review

### Portable config directory behavior

Confirm the docs say runtime files derive from `TRIGGARR_CONFIG_DIR` when it is set to an absolute path, and from `/config` when unset for Docker compatibility. The operator should understand where `triggarr.toml`, `state.json`, and `triggarr.db` will live before starting Docker or standalone Triggarr.

### Docker and standalone first-run behavior

Confirm the docs distinguish Docker from standalone operation:

- Docker with an empty `/config` volume writes the default config first and then starts normally on the next restart when managed by the compose example.
- Standalone installs require `TRIGGARR_CONFIG_DIR` to be set before process start, and the first run writes the default template before the operator starts Triggarr again.

### Nested multi-instance TOML

Confirm the README examples use nested app instance tables, such as `[radarr.Default]`, `[radarr."4K"]`, `[sonarr.Default]`, and `[lidarr.Default]`. The docs must not revive flat `[radarr]`, `[sonarr]`, or `[lidarr]` connection examples.

### Authentication and security modes

Confirm the docs no longer claim Triggarr has no authentication. The reviewer should see the setup flow and the supported `[auth].method` modes:

- `Forms` as the default browser login/session-cookie mode.
- `Basic` as HTTP Basic credentials with session-cookie establishment.
- `External` as a bypass of local auth only when an upstream reverse proxy or SSO layer already enforces authentication and authorization.
- `Disabled` as an intentional no-auth mode that should be limited to already-private networks.

### External-auth trust boundary

Confirm `External` auth guidance is not merely "put it behind a proxy." It must tell operators to block or firewall direct access to port 8484 so the proxy is the sole path to Triggarr, and the proxy must enforce both authentication and authorization before traffic reaches Triggarr.

### Secure-cookie ASGI/Uvicorn behavior

Confirm secure-cookie language says cookies are marked `Secure` when the ASGI request scheme is HTTPS. Behind a reverse proxy, `X-Forwarded-Proto` may influence that scheme only after Uvicorn accepts forwarded headers from peers listed in `TRUSTED_PROXY_IPS`. The docs must not imply application route or middleware code directly trusts client-supplied `X-Forwarded-Proto`.

### TODO retirement

Confirm `TODO.md` says no pending TODOs are tracked there and explicitly retires the old configurable config-directory item because current code derives config, state, and SQLite paths from `TRIGGARR_CONFIG_DIR` or `/config`.

## Approval Checklist

A human reviewer should mark one of these outcomes in the later S05 UAT gate artifact:

- Approved: README/SECURITY/TODO are accurate enough for release.
- Approved with caveats: release can proceed if the caveats are recorded and accepted.
- Changes requested: release validation must pause until the requested documentation changes are made and verified.
- Deferred: human documentation UAT is explicitly deferred; this is a release caveat, not approval.

Before approving, check each item:

- [ ] The review used `a3f09ad^..HEAD`, not only an empty working-tree diff.
- [ ] The reader is clearly served: an operator installing or upgrading Triggarr.
- [ ] The post-read action is executable: configure Docker/standalone paths and choose a safe auth/proxy mode.
- [ ] Portable config-directory behavior is accurate for Docker and standalone installs.
- [ ] Nested multi-instance TOML examples match the real settings shape.
- [ ] Auth modes are described without stale "no authentication" claims.
- [ ] `External` auth requires upstream authentication, upstream authorization, and blocked/firewalled direct access.
- [ ] Secure-cookie behavior is described through ASGI request scheme and Uvicorn trusted-proxy handling.
- [ ] `TODO.md` retirement language does not imply config-directory work remains pending.
- [ ] No real API keys, generated auth secrets, cookies, password hashes, session secrets, or secret environment values appear in the docs or in this packet.

## Mechanical Guardrails

Run the stale-claim scan from the slice plan. No matches is the expected pass condition:

```bash
git grep -n -i -E 'no authentication|authentication is not implemented|config directory is not configurable|make config directory configurable|flat \[radarr\]|\[radarr\][[:space:]]*$|TRIGGARR_GENERAL__|directly trusts.*x-forwarded-proto|routes trust.*x-forwarded-proto' -- README.md SECURITY.md TODO.md CONTRIBUTING.md docs 2>/dev/null || true
```

Run the docs-accuracy guardrail before recording approval:

```bash
uv run pytest tests/test_docs_accuracy.py -q
```

If README, SECURITY, or TODO changes after approval, rerun `uv run pytest tests/test_docs_accuracy.py -q` and repeat the relevant human review items before carrying approval forward.

## Evidence Provenance Caveat

Do not use the old S02 slice summary as authoritative release evidence for this documentation work. `S02-SUMMARY.md` was superseded for downstream validation purposes. Future validation should use S04's evidence assessment at `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`, plus the referenced S02 task summaries, for the docs/evidence provenance trail.

S04's UAT also states that automated checks did not prove human readability or release-manager acceptance; those remain assigned to S05.

## Redaction Rules

Use placeholders only. Do not include real Radarr/Sonarr/Lidarr API keys, generated Triggarr API keys, password hashes, session secrets, cookies, bearer tokens, or secret environment values in review notes, screenshots, copied config, or gate artifacts.

## Reader-Test Result

Cold-reader test: after reading this packet, an operator-reviewer knows exactly which committed range to inspect, which claims are high risk, which stale claims must stay absent, which automated guardrails to rerun, and why agent-side review is not human UAT. The post-read action is actionable: approve, request changes, defer, or approve with caveats based on whether the docs safely guide Docker/standalone path configuration and auth/proxy mode selection.
