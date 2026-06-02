---
phase: 71
slug: presentation-rewrite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 71 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `71-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `uv run pytest tests/test_validation.py tests/test_config.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds (quick), full suite 965+ tests |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_validation.py tests/test_config.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + `uv run ruff check triggarr/ tests/` clean
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| W0 | 00 | 0 | D-03 | T-71-01 | n/a (test stubs) | unit | `uv run pytest tests/test_validation.py::TestValidateArrUrlConfig -x -q` | ❌ W0 | ⬜ pending |
| W0 | 00 | 0 | D-03 | T-71-01 | n/a (test stubs) | unit | `uv run pytest tests/test_config.py::test_instance_config_metadata_url_raises -x -q` | ❌ W0 | ⬜ pending |
| SSRF-code | — | — | PREW-01 / D-01,D-02 | T-71-01 | `InstanceConfig(url="http://169.254.169.254/…")` raises ValidationError; loopback + private LAN accepted | unit | `uv run pytest tests/test_config.py tests/test_validation.py -x -q` | ❌ W0 then ✅ | ⬜ pending |
| web-form-unchanged | — | — | D-01 | T-71-01 | existing `TestValidateArrUrl` strict behavior intact (loopback still blocked on web form) | unit | `uv run pytest tests/test_validation.py::TestValidateArrUrl -x -q` | ✅ exists | ⬜ pending |
| README-toml | — | — | PREW-01 | — | every README ```toml``` block parses as valid `Settings` | unit | `uv run pytest tests/test_docs_accuracy.py -x -q` | ✅ exists | ⬜ pending |
| security-md | — | — | PREW-03 | T-71-02 | SECURITY.md SSRF + SecretStr documentation checks pass | unit | `uv run pytest tests/test_community_health.py::TestSecurity -x -q` | ✅ exists | ⬜ pending |
| community-health | — | — | PREW-04 | — | CONTRIBUTING/SECURITY/LICENSE present + accurate | unit | `uv run pytest tests/test_community_health.py -x -q` | ✅ exists | ⬜ pending |
| bug-template | — | — | PREW-04 / D-10 | — | bug-report.yml App Type includes Lidarr; version dropdown current | unit | `uv run pytest tests/test_github_templates.py -x -q` | ✅ exists (assertions TBD) | ⬜ pending |
| changelog | — | — | PREW-06 | — | `read_changelog()` renders v2.9.0 entry without error | unit | `uv run pytest tests/test_changelog.py -x -q` | ✅ exists | ⬜ pending |
| ssrf-doc-claim | — | — | PREW-01 / D-03 | T-71-02 | README:215 + SECURITY.md:39 wording matches post-change behavior | source assertion | manual review against `validation.py` + `models/config.py` | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_validation.py` — add `TestValidateArrUrlConfig` (config-load variant: blocks metadata/link-local, allows loopback + private LAN). Do NOT modify existing `TestValidateArrUrl`.
- [ ] `tests/test_config.py` — add `test_instance_config_metadata_url_raises` and `test_instance_config_loopback_url_valid` (InstanceConfig integration).
- [ ] **Read `tests/test_github_templates.py` before editing `bug-report.yml`** — update any version/app-type assertions that the dropdown changes (D-10) would otherwise break (Pitfall 5).
- [ ] **Read `tests/test_docs_accuracy.py` before rewriting README** — it parses every ```toml``` block; the rewrite must keep all TOML blocks valid against `Settings` or CI breaks (Pitfall 4).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fresh screenshots (dashboard, history, settings) with no exposed credentials | PREW-02 | Captured via Playwright against the deployed NAS branch build — not available in the planning/execution session | Verified at milestone-end walkthrough; this phase only updates README image refs + alt text |
| Repo-metadata text (About/topics/homepage) applied in GitHub UI | PREW-05 | GitHub web-UI action; cannot be applied from session | Phase delivers copy-paste text only; maintainer applies manually |
| SSRF doc-claim accuracy wording | PREW-01 / D-03 | Prose accuracy is a source-assertion judgment, not an automated check | Reviewer confirms README:215 + SECURITY.md:39 net claim: "cloud-metadata + link-local blocked everywhere; full scheme + SSRF allow-list enforced on web-UI input" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (TestValidateArrUrlConfig, InstanceConfig tests)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
