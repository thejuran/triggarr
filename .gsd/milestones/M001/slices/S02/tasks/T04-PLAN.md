---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T04: Apply final docs review corrections

Fix the slice-level reviewer findings in README.md and SECURITY.md without changing runtime code. Required corrections: (1) adjust SECURITY.md session-cookie wording to say cookies are marked secure when the request is HTTPS or carries X-Forwarded-Proto: https, and direct operators to configure TRUSTED_PROXY_IPS so forwarded headers are only honored from expected proxies; (2) adjust README Docker config-dir wording so it says Triggarr uses /config when TRIGGARR_CONFIG_DIR is unset, not that the image exports the env var; (3) adjust README SSRF wording so it names blocked non-HTTP, metadata/link-local/loopback/unspecified/multicast cases rather than inappropriate public IPs; (4) soften README full-subnet TRUSTED_PROXY_IPS guidance so specific proxy IPs are preferred and full-subnet trust is only for fully trusted Docker networks. Optionally add one sentence clarifying that config TOML credentials are plaintext on disk protected by file permissions/volume security, not encrypted at rest.

## Inputs

- `Slice-level reviewer and security subagent findings from the failed S02 completion attempt`
- `README.md`
- `SECURITY.md`
- `TODO.md`
- `.gsd/DEFERRED-BACKLOG.md`

## Expected Output

- `README.md and SECURITY.md accurately reflect current implementation and operational guidance`
- `S02 documentation stale-marker scans pass after final corrections`

## Verification

rg -n "The Docker image defaults `TRIGGARR_CONFIG_DIR`|inappropriate public IPs|forwarded as HTTPS by a trusted proxy|use 172\.18\.0\.0/16 for the full subnet|mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`" README.md SECURITY.md TODO.md .gsd/DEFERRED-BACKLOG.md should return no matches; then run the README TOML extraction/Settings parse check from T02 if README examples changed.
