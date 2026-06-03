---
phase: 71-presentation-rewrite
plan: "06"
subsystem: documentation / security-policy
tags: [security, docs, ssrf, csp-nonce, cwe-613, at-rest-plaintext]
dependency_graph:
  requires: ["71-02"]
  provides: ["SECURITY.md reconciled with v2.8/v2.8.1 hardening"]
  affects: ["SECURITY.md"]
tech_stack:
  added: []
  patterns:
    - "Additive/corrective edit: preserve all required substrings, add new bullets in-place"
key_files:
  created: []
  modified:
    - SECURITY.md
decisions:
  - "D-08: SECURITY.md enumerates the v2.8/v2.8.1 hardening as a confident 'what we do' list (CSP script-src nonce, session-secret rotation on password change / CWE-613, apikey= URL rejection, Basic-auth control-char validation, session-secret startup length check)"
  - "D-09: SECURITY.md states the at-rest-plaintext caveat plainly (SecretStr protects repr/log/HTML, NOT disk; secrets are plaintext in triggarr.toml — protect with file permissions + volume security)"
  - "SSRF claim quotes 71-02-SUMMARY.md precise net-behavior verbatim: IP-literal-qualified, localhost permitted both paths, arbitrary DNS = accepted residual risk"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-02"
  tasks: 1
  files: 1
---

# Phase 71 Plan 06: SECURITY.md Reconciliation Summary

Reconciled SECURITY.md with the v2.8/v2.8.1 hardening layer (D-08), added the at-rest-plaintext caveat (D-09), and replaced the stale broad SSRF claim with the precise post-plan-02 scope from 71-02-SUMMARY.md.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Enumerate v2.8/v2.8.1 hardening, add at-rest-plaintext caveat, update SSRF claim to precise scope | `fc882db` |

## Implementation Details

### Changes to SECURITY.md

**Credential Protection section (D-09 — at-rest-plaintext caveat):**

Added a new bullet immediately after the SecretStr bullet:

> **At-rest caveat** -- `SecretStr` protects repr/log/HTML exposure, NOT at-rest secrecy. API keys, auth credentials, and the session secret are stored as plaintext strings in `triggarr.toml`. Protect them with file permissions (`0600`, set by Triggarr on write) and volume security.

This mirrors the README:212 caveat and closes codex MEDIUM SECURITY.md:18,28.

**Web Security section (SSRF update — D-01/D-02/D-03, precise scope from 71-02-SUMMARY.md):**

Replaced the prior broad SSRF bullet with the precise post-plan-02 claim:

- Link-local / unspecified / multicast IP literals + known cloud-metadata hostnames/IPs (e.g. 169.254.169.254, metadata.google.internal) are blocked BOTH at config load (triggarr.toml at startup) AND via the web settings form.
- Loopback IP literals (127.0.0.1, ::1) are PERMITTED at config load (relaxed config-load variant) and blocked ONLY by the web settings form.
- The DNS name `localhost` is a hostname (not an IP literal), is not resolved at validation time, and is PERMITTED in BOTH paths.
- Arbitrary DNS hostnames are not resolved at validation time and remain an accepted residual risk (DNS rebinding); network-layer egress controls are the appropriate mitigation.

This closes codex HIGH SECURITY.md:39 without overstating the block scope.

**Web Security section (D-08 — v2.8/v2.8.1 hardening enumeration):**

1. Updated the "Security headers" bullet to explicitly name the CSP `script-src` nonce approach (per-request nonce from `SecurityHeadersMiddleware`, no `unsafe-inline`).

2. Added four new bullets for the remaining hardening items:
   - `apikey=` URL rejection at model construction
   - Basic-auth control-character validation (C0 + DEL)
   - Session-secret startup length check (< 32 chars warning)
   - Session-secret rotation on password change (CWE-613, v2.8.1)

### SSRF Claim Accuracy Verification

The SSRF claim quotes the precise behavior from `71-02-SUMMARY.md`:
- Does NOT state loopback is blocked at config load (it is permitted there)
- Does NOT say "rejects loopback" without the "IP literal" qualifier
- Does NOT imply the web form blocks `localhost`
- Does NOT claim "cloud-metadata and link-local hostnames are blocked" for arbitrary DNS
- DOES state arbitrary DNS = accepted residual risk (DNS rebinding)

### Preserved Required Wording

All TestSecurity-required substrings remain: `SecretStr`, `CSRF`, `SSRF`, `clamping`, `atomic`, `PUID`, `redact`, `2.x`, `1.x`, `github.com/thejuran/triggarr/security/advisories/new`.

All test_docs_accuracy.py invariants preserved:
- External-auth/direct-access: `external`, `authentication`, `authorization`, `direct access`, `blocked` — all present
- X-Forwarded-Proto / ASGI scheme: `x-forwarded-proto`, `asgi request scheme` (via "ASGI request scheme"), `uvicorn`, `trusted_proxy_ips` — all present
- No forbidden direct-trust phrasing introduced
- No stale auth claims introduced

Triggarr's leading signals (GSVR reporting, threat model depth, private vulnerability reporting) preserved as-is (PREW-07).

## Verification Results

- `uv run pytest tests/test_community_health.py::TestSecurity tests/test_docs_accuracy.py -x -q`: **14 passed**
- `uv run pytest tests/test_community_health.py tests/test_docs_accuracy.py -x -q`: **25 passed**
- `grep -q "nonce" SECURITY.md`: PASS
- `grep -qi "plaintext" SECURITY.md`: PASS
- `grep -q "CWE-613" SECURITY.md`: PASS
- `grep -qi "control" SECURITY.md`: PASS
- `grep -qi "startup" SECURITY.md`: PASS

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. This plan edits a single Markdown policy file. No runtime code, no new attack surface.

## Self-Check: PASSED

- `SECURITY.md` contains `nonce` — FOUND
- `SECURITY.md` contains `CWE-613` — FOUND
- `SECURITY.md` contains `plaintext` — FOUND
- `SECURITY.md` contains `triggarr.toml` — FOUND
- All TestSecurity substrings present — VERIFIED
- All test_docs_accuracy.py invariants satisfied — VERIFIED
- Commit `fc882db` exists — FOUND
- 25 tests pass — VERIFIED
