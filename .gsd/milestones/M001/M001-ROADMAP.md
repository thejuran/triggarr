# M001: Portable Config Directory & Documentation Refresh

**Vision:** Turn the legacy configurable-config-directory TODO into verified current behavior, then bring README and adjacent project docs back into alignment with Triggarr's actual config, auth/security, Docker, and standalone-install behavior.

## Success Criteria

- A custom absolute `TRIGGARR_CONFIG_DIR` is proven to drive config and state paths without regressing the Docker `/config` default.
- README and adjacent docs describe the current nested multi-instance config format, standalone config directory behavior, and auth/security posture accurately.
- The stale `TODO.md` entry is retired or rewritten so future agents do not plan already-shipped work.
- Final verification includes focused tests, full project tests, lint, and a user docs-review/UAT gate before completion.

## Slices

- [x] **S01: S01** `risk:high` `depends:[]`
  > After this: After this: a temporary absolute `TRIGGARR_CONFIG_DIR` is proven through tests/startup checks to control config and state paths, and any real residual `/config` bug is fixed or documented as absent.

- [x] **S02: S02** `risk:medium` `depends:[]`
  > After this: After this: README and adjacent docs explain current Docker/standalone setup, nested multi-instance config, auth/security behavior, and no longer point to stale missing configurable-config work.

- [x] **S03: S03** `risk:low` `depends:[]`
  > After this: After this: focused tests, full tests, lint, operational config-dir check, and user documentation review have all passed, so the milestone can be completed with evidence.

- [x] **S04: S04** `risk:high` `depends:[]`
  > After this: After this: README/SECURITY external-auth and secure-cookie trust-boundary guidance is reconciled with implementation, S02 delivery evidence is repaired or superseded with a real artifact trail, requirement coverage is explicitly scoped/proven for touched requirements, and focused/full/lint verification has been rerun.

- [x] **S05: S05** `risk:medium` `depends:[]`
  > After this: After this: a human has reviewed the README/SECURITY/TODO documentation diff, release/deep-review caveats are resolved or explicitly deferred by the user, and validation can rerun with UAT evidence.

- [x] **S06: S06** `risk:high` `depends:[]`
  > After this: After this: validation has an explicit requirement-scope coverage artifact, S02 placeholder/task-state inconsistency is resolved or accepted via canonical supersession, human documentation UAT/deep-review is approved or explicitly deferred only if a real human decision exists (otherwise recorded as unresolved/escalated with needs-attention posture), and focused/full/lint checks have fresh evidence for rerun validation.

## Boundary Map

### S01 → S02

Produces:
- Verified config-dir contract: `TRIGGARR_CONFIG_DIR` absolute path rules, `/config` default behavior, and config/state path derivation.
- List of any runtime/path defects fixed or explicitly found absent.

Consumes:
- Existing config/state/startup modules and tests.

### S02 → S03

Produces:
- Updated README/TODO/supporting docs that reflect verified behavior.
- Documentation audit notes identifying the source-of-truth code/tests used for each user-facing claim.

Consumes:
- S01 verified config-dir contract.

### S03 final closure

Produces:
- Integrated verification evidence across tests, lint, operational path check, and user docs review.

Consumes:
- S01 runtime proof and S02 documentation updates.
