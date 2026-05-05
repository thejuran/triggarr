---
estimated_steps: 8
estimated_files: 13
skills_used: []
---

# T01: Audited README and adjacent docs against verified auth, config-dir, multi-instance, release, and Lidarr behavior.

Why: the README already shows signs of mixed-era documentation, so edits should be grounded in code and tests rather than assumptions.

Do:
1. Load the `write-docs` skill before editing prose.
2. Compare README install, configuration, security, reverse proxy, and development sections against current source/tests.
3. Identify stale claims, especially flat config examples, no-auth wording, config-dir location language, current version/install examples, and Radarr/Sonarr/Lidarr capability claims.
4. Check adjacent docs (`SECURITY.md`, `CONTRIBUTING.md`, `docker-compose.yml`, `CHANGELOG.md`, `TODO.md`) for conflicting user-facing guidance.
5. Produce a concise docs audit list in the task summary before making broad prose changes.

Done when: every planned doc edit has a source-of-truth file/test behind it.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-SUMMARY.md`
- `README.md`
- `SECURITY.md`
- `TODO.md`

## Expected Output

- `M001/S02/T01 summary with docs audit findings`

## Verification

`rg -n "no authentication|TRIGGARR_CONFIG_DIR|\[radarr\]|\[sonarr\]|\[lidarr\]|/config|mellow-tinkering-creek|latest/download" README.md SECURITY.md CONTRIBUTING.md docker-compose.yml CHANGELOG.md TODO.md` plus written audit findings.

## Observability Impact

Documents doc drift sources so future agents can update prose without redoing the entire investigation.
