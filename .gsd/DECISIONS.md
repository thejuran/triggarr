# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 | M001/S04 planning | security | Secure-cookie trusted-proxy boundary for S04 remediation | Session-cookie Secure decisions should use `request.url.scheme == "https"` in shared web code; `X-Forwarded-Proto` is accepted only through Uvicorn's `proxy_headers=True` and `forwarded_allow_ips=get_trusted_proxy_ips()` startup configuration. | S03 security review and S04 research found that direct app-layer `X-Forwarded-Proto` checks made README/SECURITY claims about `TRUSTED_PROXY_IPS` inaccurate. Centralizing on ASGI scheme keeps the trust boundary in Uvicorn, allows tests to reject spoofed direct headers, and lets docs accurately describe secure-cookie behavior. | Yes | agent |
| D002 | M001/S04 | security | Where Triggarr accepts forwarded-proto information for session-cookie Secure decisions | Runtime cookie-setting code uses the ASGI request scheme (`request.url.scheme`) via `is_secure_request(...)`; only Uvicorn proxy-header processing may translate trusted forwarded-proto headers according to `TRUSTED_PROXY_IPS`. | Directly reading `X-Forwarded-Proto` in application routes or middleware lets direct clients spoof HTTPS. Keeping forwarded-header trust at the Uvicorn boundary aligns runtime behavior, tests, and operator documentation around a single trust boundary. | Yes | agent |
