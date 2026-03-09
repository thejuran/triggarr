# Triggarr Pending TODOs

## Make config directory configurable (GitHub issue)
- Hardcoded `/config/` paths prevent running outside Docker
- Fix: add `TRIGGARR_CONFIG_DIR` env var in `triggarr/models/config.py` and `triggarr/state.py`
- Plan saved at `.claude/plans/mellow-tinkering-creek.md`

## CSS broken behind reverse proxy (GitHub issue)
- `url_for()` in `base.html` generates `http://` URLs because Uvicorn doesn't read `X-Forwarded-Proto`
- Fix: add `proxy_headers=True, forwarded_allow_ips="*"` to `uvicorn.Config` in `triggarr/__main__.py:43`
- One-line change, no new dependencies
