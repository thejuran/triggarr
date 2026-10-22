# Review classification policy

Status: active from Phase 83 (v2.13). Instruction-enforced: GitHub does not yet check it (Phase 85, ACCEPT-03). Existing GitHub protections are unchanged.

## Principle

A written review-classification policy exists. Ordinary documentation and planning-only changes receive a focused consistency review; Greptile, independent Codex code review and vibe-check are not routinely required for them. Classification depends on content, not file extension: changes to agent instructions, executable workflows, hooks, permissions, acceptance or release policy, or operational procedures are sensitive and require a risk assessment (RISK-01) and the applicable technical review, even when they live in Markdown. A mixed PR follows the requirements of its most consequential change.

## Classes

| Class | What it covers | Required review |
|---|---|---|
| ordinary-docs | User/developer documentation prose, planning files (`.planning/**` status, roadmap, summaries, evidence records), comments-only edits — that do not change agent instructions, workflows, hooks, permissions, acceptance/release policy or operational procedures. | A focused consistency review only, defined verbatim per D-18 as checking that facts, links, SHAs and STATE/ROADMAP/REQUIREMENTS agree with the code and with each other. No BM code review, no Codex code review, no vibe-check routinely. |
| sensitive | Agent instructions (`CLAUDE.md`, `.claude/**`, AGENTS-style files, BM configuration `.planning/config.json`, `greptile.json`), executable workflows and scripts (`.github/workflows/**`, `.github/scripts/**`), hooks, permissions, acceptance or release policy (`docs/owner-cli-acceptance.md`, `docs/buildomator-greptile-pilot.md`, release docs), operational procedures (`docs/operations/**`, runbooks), and this policy itself — even in Markdown. | A RISK-01 risk assessment plus the applicable technical review: BM code review and its paired Codex pass per `docs/codex-adversarial-review-contract.md`, Greptile when it runs, and a vibe-check recommendation when risk is high (RISK-02). |
| code | Application code, tests, Dockerfile, dependencies and build configuration. | The current full process: BM code review with paired Codex, Greptile when it runs, CI, and routine vibe-check while the owner keeps it (standing rule until PILOT-03), plus RISK-01/RISK-02. |

## Mixed changes

A PR records every class present among its changes (`classes_present`) and follows the required-review requirements of its most consequential class present. Sensitive and code both carry the full technical review described above; ordinary-docs is the least consequential of the three, so a PR that mixes ordinary-docs with either sensitive or code content is classified and reviewed as the more consequential class, never diluted toward ordinary-docs.

## Ground rules

- **D-18:** Claude classifies each PR and records the classification and rationale against the exact head SHA; it reclassifies when the head changes. When in doubt, classify upward (toward the more consequential class). The owner can overrule any classification at acceptance.
- **D-13:** One branch and one PR per phase, with no docs-only PRs. Ordinary docs/planning commits ride inside phase PRs and are classified as part of that PR's overall classification, not as a standalone PR.
- **D-14:** This policy is demonstrated on Phase 83's own sensitive/mixed PR (see `.planning/REQUIREMENTS.md` REVIEW-08 and `.planning/ROADMAP.md` Phase 83 criterion 7 for the owner's 2026-10-22 scope decision). Phase 85's ACCEPT-03 designs and verifies the GitHub-side mechanism that honors this policy.
- Codex stays paired with every BM code-review run (REVIEW-02); an ordinary planning edit does not force a code-review run to happen in the first place.
- Exact-commit owner acceptance applies to every PR, whatever its class.
- Any review that still runs automatically on ordinary-docs content (currently Greptile, while free credits last) is disclosed in the PR rather than described as unnecessary.
- Classification never waives a finding or reduces the coverage required by another rule. It decides how much review a PR gets up front; it never excuses a result after the fact.

## Classification record

The per-head record lives in the PR checkpoint comment (D-10), not in a GitHub repository variable, and is adapted from the `REVIEW_DISPOSITIONS` register shape in `docs/buildomator-greptile-pilot.md`:

```json
{"schema":1,"head":"FULL_COMMIT_SHA","classification":"ordinary-docs|sensitive|code","classes_present":["..."],"rationale":"...","supersedes_head":"FULL_COMMIT_SHA|null"}
```

- `head`: the exact head SHA this record applies to.
- `classification`: the single most consequential class governing required review for this head.
- `classes_present`: every class actually present among the changes at this head.
- `rationale`: why this head got this classification — which files or content drove it.
- `supersedes_head`: the prior head's SHA this record replaces, or `null` for the first record on a PR.

### Worked examples

**ordinary-docs example:**

```json
{"schema":1,"head":"a1b2c3d4e5f6...","classification":"ordinary-docs","classes_present":["ordinary-docs"],"rationale":"README wording fix and a STATE.md status update; no agent instructions, workflows, hooks, permissions, acceptance/release policy or operational procedures touched.","supersedes_head":null}
```

**sensitive example:**

```json
{"schema":1,"head":"b2c3d4e5f6a1...","classification":"sensitive","classes_present":["sensitive"],"rationale":"Edits CLAUDE.md's review-pairing section and .github/workflows/review-acceptance.yml comments; agent instructions and a workflow file are sensitive even though both changes are Markdown/YAML text, not application code.","supersedes_head":null}
```

**code example:**

```json
{"schema":1,"head":"c3d4e5f6a1b2...","classification":"code","classes_present":["code"],"rationale":"Adds a new FastAPI route and its tests in triggarr/web/routes.py and tests/test_routes.py; application code and tests require the current full process.","supersedes_head":null}
```

**Upward-reclassification example:** a PR first classified `ordinary-docs` (README and `.planning/` wording only) later gains a commit editing `CLAUDE.md`. The new head is reclassified `sensitive`, not left at `ordinary-docs`, and the new record's `supersedes_head` points at the prior head:

```json
{"schema":1,"head":"d4e5f6a1b2c3...","classification":"sensitive","classes_present":["ordinary-docs","sensitive"],"rationale":"Prior head only touched README/.planning wording (ordinary-docs). This head adds an edit to CLAUDE.md's review-pairing section, which is agent instructions and therefore sensitive; classifying upward per D-18 rather than keeping the earlier ordinary-docs classification.","supersedes_head":"a1b2c3d4e5f6..."}
```
