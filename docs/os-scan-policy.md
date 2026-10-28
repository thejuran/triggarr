# OS-package scan policy

Status: written 2026-10-26 (Phase 85, CIMAINT-03) before the gate is enforced. Enforced by
the `os-scan` job in `.github/workflows/ci.yml` once Plan 85-15 lands.

## Scope

One OS-package scanner: the Trivy CLI, installed in CI as a pinned binary verified against a
committed SHA-256 checksum. The job never uses the `aquasecurity/trivy-action` or
`aquasecurity/setup-trivy` GitHub Actions — both were compromised in March 2026
(CVE-2026-33634) — so the pinned, checksummed binary install is the only sanctioned path.

The scan runs with `--pkg-types os`, covering OS packages only, against the exact audited
image artifact already produced by the `docker` job (`audited-image`: `image.tar`, scanned
only after its checksum and image ID are verified). Python packages stay pip-audit's job;
this policy does not add a second equivalent gate for Python dependencies (D-12).
Misconfiguration scanning and secret-in-image scanning are out of scope for this gate.

## What blocks (D-08)

A finding blocks the job when all of the following are true:
- Severity is CRITICAL or HIGH.
- A fix is available (the finding's `FixedVersion` field is non-empty).
- No valid, unexpired, owner-approved exception matches the finding's vulnerability ID and
  package.

## What is reported only (D-09)

Every other finding is reported in the CI job summary and does not block:
- CRITICAL or HIGH severity with no fix available (`FixedVersion` empty).
- Every MEDIUM, LOW, and UNKNOWN severity finding, fixed or not.

All findings — every severity, fixed or unfixed — appear in the CI job summary. Nothing is
filtered out of the report: the scan never runs with `--ignore-unfixed`, because that flag
removes unfixed findings from the results entirely rather than just excluding them from the
blocking decision, which would hide a CRITICAL/HIGH-with-no-fix finding that D-09 requires to
stay visible.

## Scanner errors fail closed (D-12)

Any of the following fails the `os-scan` job closed, the same way the existing
`pip-audit --strict` job fails closed on an error:
- A vulnerability-database download failure.
- Any non-zero Trivy exit code.
- Unparseable scan-result JSON.
- A scan report missing its OS-package result section or its OS metadata.
- A malformed `.github/os-scan-exceptions.json` file (see Exceptions below).

A scanner error is never retried into a pass; the remedy is a visible re-run of the job as a
new, recorded attempt.

## Exceptions (D-10)

Exceptions live in a single repository file, `.github/os-scan-exceptions.json`:

```json
{
  "schema": 1,
  "exceptions": [
    {
      "id": "CVE-2026-XXXXX",
      "package": "<pkg name>",
      "reason": "...",
      "approved_by": "<GitHub login>",
      "approved_on": "YYYY-MM-DD",
      "expires": "YYYY-MM-DD"
    }
  ]
}
```

Every field is required. Validation rules:
- `expires` must be present. An entry with no `expires` makes the whole file invalid and
  fails the job.
- `expires` must be at most 30 days after `approved_on`, and at most 30 days after the date
  the scan runs. An entry exceeding either 30-day bound makes the file invalid and fails the
  job.
- `approved_on` must not be in the future.
- An exception matches only the exact same vulnerability ID and package; it never suppresses
  a different finding.
- Once an exception's `expires` date passes, it stops suppressing automatically — the
  matching finding blocks again on the next run, with no separate action needed to
  "re-enable" it.
- An excepted finding is still listed in the CI job summary, marked as excepted, along with
  its expiry date — an exception never removes a finding from the report, only from the
  blocking decision.

Adding or changing an entry in this file is a sensitive change under
[the review classification policy](review-classification-policy.md) (acceptance/release
policy) — it needs the owner's recorded approval and goes through normal review, not an ad
hoc edit.

## Where it applies (D-11)

The `os-scan` job is a mandatory job in the `CI ready` required-status check on every PR and
every push to `main`. `release.yml`'s preflight also requires it via `REQUIRED_JOBS`, so a
published image has always passed this scan before it ships.

If the scan comes back red overnight, the response is a base-image rebuild — via the monthly
Docker base-image update PR, or a manual one — or a time-limited, owner-approved exception
under 30 days. The job itself is never disabled to get past a red result.

## Database

Trivy downloads its vulnerability database fresh on every run. No database caching, no
`--skip-db-update`, and no `--offline-scan` are used. A database download failure fails the
job closed per the Scanner errors section above, rather than scanning with a stale or
missing database. Caching is not introduced unless measured CI time threatens the
~5-minute added-PR-time target (Phase 82 D-14), and that tradeoff goes to the owner before
anything changes.

## Pinning and updates

The Trivy CLI version and its SHA-256 checksum are pinned directly in `ci.yml`. Updating
either is a workflow change and goes through the same review as any other workflow change.
The pinned Trivy version must post-date the GHSA-69fq-xp46-6x23 remediation.
