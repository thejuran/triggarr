# Phase 85 Plan 12: Verified Tool Pins and OS-Scan Baseline

**Checked:** 2026-10-27

## Tool pins

```
TRIVY_VERSION=0.76.1
TRIVY_LINUX_64BIT_SHA256=c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0
ACTIONLINT_VERSION=1.7.12
ACTIONLINT_SHA256=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
```

| Field | Trivy | actionlint |
|---|---|---|
| Version (`TRIVY_VERSION` / `ACTIONLINT_VERSION`) | `0.76.1` | `1.7.12` |
| Linux amd64/linux_amd64 SHA-256 (`TRIVY_LINUX_64BIT_SHA256` / `ACTIONLINT_SHA256`) | `c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0` (`trivy_0.76.1_Linux-64bit.tar.gz`) | `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` (`actionlint_1.7.12_linux_amd64.tar.gz`) |
| Source (release) | https://github.com/aquasecurity/trivy/releases/tag/v0.76.1 | https://github.com/rhysd/actionlint/releases/tag/v1.7.12 |
| Source (checksums file) | https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_checksums.txt | https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_checksums.txt |
| Check date | 2026-10-27 | 2026-10-27 |

Also recorded for the local baseline run only (never pinned in CI, which is amd64-only):

- `TRIVY_MACOS_ARM64_SHA256` = `11a9b6cd2752011b54f01ea4bd0dbfa9f0c41dc6538d5a3f9d23955f471bf4e5` (`trivy_0.76.1_macOS-ARM64.tar.gz`), verified with `shasum -a 256 -c` against the downloaded checksums file before extraction — passed (`trivy_0.76.1_macOS-ARM64.tar.gz: OK`).

### Trivy advisory check (GHSA-69fq-xp46-6x23 / CVE-2026-33634)

`gh api repos/aquasecurity/trivy/security-advisories/GHSA-69fq-xp46-6x23` was fetched directly (not WebFetch). The advisory's own `vulnerabilities` block names exactly one affected Trivy binary version: `vulnerable_version_range: "=0.69.4"`, `patched_versions: "0.69.3"` (the compromised release was live for ~3 hours on 2026-03-19, and the attacker's attempted `v0.70.0` release was stopped before it shipped — no tag or release was ever published for it). `v0.76.1` was released 2026-10-21 — the current latest release, more than seven months after the remediation, and not named anywhere in the advisory's affected-version list. **Result: v0.76.1 is a safe version to pin; it is not v0.69.4 and post-dates the remediation by a wide margin.**

The GitHub Actions wrapped around the binary (`trivy-action`, `setup-trivy`) were separately compromised by tag hijacking in the same incident — irrelevant here because this plan pins and downloads the Trivy CLI binary directly (per `docs/os-scan-policy.md` and RESEARCH.md Pitfall 1); no `trivy-action`/`setup-trivy` Action is used anywhere in this repo.

### Signature-verification status (Trivy)

The v0.76.1 release publishes a cosign sigstore bundle for the checksums file (`trivy_0.76.1_checksums.txt.sigstore.json`), confirmed present via `gh release view v0.76.1 --repo aquasecurity/trivy --json assets`. `cosign` is **not installed** on this execution machine (`which cosign` → not found), so the sigstore bundle was **not verified**. Integrity for this plan's local run instead relied on `shasum -a 256 -c` against the downloaded checksums file, which passed for the macOS ARM64 tarball used locally. The checksums file itself was fetched from the same GitHub Releases API/CDN as the binaries (`gh release download`), so this is checksum-based integrity only, not independent-of-GitHub signature verification. CI's own install step (Plan 85-15) pins the Linux amd64 SHA-256 recorded above directly in `ci.yml` and verifies it with `sha256sum -c`, matching this repo's existing pinned-binary pattern (Tailwind, pip-audit); cosign verification was not added to that step by this plan.

### actionlint note

Upstream `rhysd/actionlint`'s latest release is still `v1.7.12` (2026-03-30), matching both RESEARCH.md's prior finding and this machine's local Homebrew install (`actionlint --version` → `1.7.12`, `installed from Homebrew`). `actionlint .github/workflows/*.yml` was run locally against every workflow file in this repo: **exit 0, zero findings** — no false positives for `runs-on: ubuntu-latest` or anything else. No fork (`kjanat/actionlint`) is needed; RESEARCH.md's fallback condition did not trigger.

## Baseline scan

- **Base image digest:** `python@sha256:b3575dcf816cdacc5292df77a6e3e59b8941631078373a045efa2ac1e9c5c3b2` (`python:3.13-slim`, as pulled locally on 2026-10-27 via `docker image inspect python:3.13-slim --format '{{index .RepoDigests 0}}'`)
- **Trivy exit code:** `0`
- **Gate exit code:** `0`
- **Bucket counts:** blocking: 0, excepted: 0, expired exceptions: 0, reported unfixed: 44, reported other: 120, ignored non-OS: 0
- **Wall-clock time:** 7 seconds total for the Trivy invocation itself (`trivy image --input image.tar --pkg-types os --format json --output trivy-results.json`), including a fresh ~130 MiB vulnerability-DB download (no DB caching, per RESEARCH.md Open Question 3's resolution). Well inside the ~5-minute added-PR-time budget (Phase 82 D-14).

### Platform substitution (deviation — see below)

The plan specifies `docker build --platform linux/amd64`. That build crashed inside the Dockerfile's `deps` stage the moment the pip-installed `uv==0.12.17` binary executed, with `qemu: uncaught target signal 11 (Segmentation fault)`, exit code 139 — identical to the QEMU/Rust-binary emulation incompatibility already documented in Plan 85-08's SUMMARY.md as a deviation on this same machine. The image used for this baseline was instead built with `docker build --platform linux/arm64` (this Mac's native, non-emulated platform), which succeeded. See "Deviations from Plan" below for the full analysis and its cost-if-wrong.

### Full gate summary (pasted verbatim from `os-scan-gate.cjs --summary`)

```markdown
## OS-package scan

Scanned: 2026-10-27 (Trivy 0.76.1)

blocking: 0, excepted: 0, expired exceptions: 0, reported unfixed: 44, reported other: 120, ignored non-OS: 0

### Reported (unfixed)

| ID | Package | Installed | Fixed | Severity |
|----|---------|-----------|-------|----------|
| CVE-2026-76642 | bsdutils | 1:2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | bsdutils | 1:2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | bsdutils | 1:2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | bsdutils | 1:2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-54369 | libacl1 | 2.3.2-2+b1 | (none) | HIGH |
| CVE-2026-76642 | libblkid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | libblkid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | libblkid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | libblkid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-76642 | liblastlog2-2 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | liblastlog2-2 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | liblastlog2-2 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | liblastlog2-2 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-76642 | libmount1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | libmount1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | libmount1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | libmount1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2025-69720 | libncursesw6 | 6.5+20250216-2 | (none) | HIGH |
| CVE-2026-76642 | libsmartcols1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | libsmartcols1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | libsmartcols1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | libsmartcols1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-16742 | libsystemd0 | 257.13-1~deb13u1 | (none) | HIGH |
| CVE-2025-69720 | libtinfo6 | 6.5+20250216-2 | (none) | HIGH |
| CVE-2026-16742 | libudev1 | 257.13-1~deb13u1 | (none) | HIGH |
| CVE-2026-76642 | libuuid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | libuuid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | libuuid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | libuuid1 | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-76642 | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-76642 | mount | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | mount | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | mount | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | mount | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2025-69720 | ncurses-base | 6.5+20250216-2 | (none) | HIGH |
| CVE-2025-69720 | ncurses-bin | 6.5+20250216-2 | (none) | HIGH |
| CVE-2026-9538 | perl-base | 5.40.1-6+deb13u1 | (none) | HIGH |
| CVE-2026-76642 | util-linux | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78408 | util-linux | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78409 | util-linux | 2.41.5-0+deb13u1 | (none) | HIGH |
| CVE-2026-78410 | util-linux | 2.41.5-0+deb13u1 | (none) | HIGH |

### Reported (other)

| ID | Package | Installed | Fixed | Severity |
|----|---------|-----------|-------|----------|
| CVE-2011-3374 | apt | 3.0.3 | (none) | LOW |
| TEMP-0841856-B18BAF | bash | 5.2.37-2+b10 | (none) | LOW |
| CVE-2026-3184 | bsdutils | 1:2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | bsdutils | 1:2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2017-18018 | coreutils | 9.7-3 | (none) | LOW |
| CVE-2025-5278 | coreutils | 9.7-3 | (none) | LOW |
| CVE-2026-56391 | coreutils | 9.7-3 | (none) | LOW |
| CVE-2026-56392 | coreutils | 9.7-3 | (none) | LOW |
| CVE-2026-102473 | dash | 0.5.12-12 | (none) | LOW |
| CVE-2026-102474 | dash | 0.5.12-12 | (none) | LOW |
| CVE-2026-53910 | diffutils | 1:3.10-4 | (none) | LOW |
| CVE-2026-102010 | gcc-14-base | 14.2.0-19 | (none) | MEDIUM |
| CVE-2026-95619 | gcc-14-base | 14.2.0-19 | (none) | MEDIUM |
| CVE-2026-54370 | libacl1 | 2.3.2-2+b1 | (none) | MEDIUM |
| CVE-2011-3374 | libapt-pkg7.0 | 3.0.3 | (none) | LOW |
| CVE-2026-54371 | libattr1 | 1:2.5.2-3 | (none) | MEDIUM |
| CVE-2026-3184 | libblkid1 | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | libblkid1 | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2026-42250 | libbz2-1.0 | 1.0.8-6 | (none) | MEDIUM |
| CVE-2026-18374 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-19499 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-19542 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-5435 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-6238 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-6368 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-6791 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-77117 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-80489 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-8674 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-86805 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-89092 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-95818 | libc-bin | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2010-4756 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2018-20796 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010022 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010023 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010024 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010025 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-9192 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2026-97399 | libc-bin | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2026-18374 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-19499 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-19542 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-5435 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-6238 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-6368 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-6791 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-77117 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-80489 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-8674 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-86805 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-89092 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2026-95818 | libc6 | 2.41-12+deb13u4 | (none) | MEDIUM |
| CVE-2010-4756 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2018-20796 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010022 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010023 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010024 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-1010025 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2019-9192 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2026-97399 | libc6 | 2.41-12+deb13u4 | (none) | LOW |
| CVE-2026-102010 | libgcc-s1 | 14.2.0-19 | (none) | MEDIUM |
| CVE-2026-95619 | libgcc-s1 | 14.2.0-19 | (none) | MEDIUM |
| CVE-2026-3184 | liblastlog2-2 | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | liblastlog2-2 | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2026-3184 | libmount1 | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | libmount1 | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2025-6141 | libncursesw6 | 6.5+20250216-2 | (none) | LOW |
| CVE-2026-54411 | libpam-modules | 1.7.0-5 | (none) | MEDIUM |
| CVE-2026-54411 | libpam-modules-bin | 1.7.0-5 | (none) | MEDIUM |
| CVE-2026-54411 | libpam-runtime | 1.7.0-5 | (none) | MEDIUM |
| CVE-2026-54411 | libpam0g | 1.7.0-5 | (none) | MEDIUM |
| CVE-2026-3184 | libsmartcols1 | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | libsmartcols1 | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2026-50812 | libsqlite3-0 | 3.46.1-7+deb13u2 | (none) | MEDIUM |
| CVE-2026-50813 | libsqlite3-0 | 3.46.1-7+deb13u2 | (none) | MEDIUM |
| CVE-2021-45346 | libsqlite3-0 | 3.46.1-7+deb13u2 | (none) | LOW |
| CVE-2025-70873 | libsqlite3-0 | 3.46.1-7+deb13u2 | (none) | LOW |
| CVE-2026-102010 | libstdc++6 | 14.2.0-19 | (none) | MEDIUM |
| CVE-2026-95619 | libstdc++6 | 14.2.0-19 | (none) | MEDIUM |
| CVE-2026-15059 | libsystemd0 | 257.13-1~deb13u1 | (none) | MEDIUM |
| CVE-2013-4392 | libsystemd0 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2023-31437 | libsystemd0 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2023-31438 | libsystemd0 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2023-31439 | libsystemd0 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2026-40228 | libsystemd0 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2025-6141 | libtinfo6 | 6.5+20250216-2 | (none) | LOW |
| CVE-2026-15059 | libudev1 | 257.13-1~deb13u1 | (none) | MEDIUM |
| CVE-2013-4392 | libudev1 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2023-31437 | libudev1 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2023-31438 | libudev1 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2023-31439 | libudev1 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2026-40228 | libudev1 | 257.13-1~deb13u1 | (none) | LOW |
| CVE-2026-3184 | libuuid1 | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | libuuid1 | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2026-3184 | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2007-5686 | login.defs | 1:4.17.4-2 | (none) | LOW |
| CVE-2024-56433 | login.defs | 1:4.17.4-2 | (none) | LOW |
| TEMP-0628843-DBAD28 | login.defs | 1:4.17.4-2 | (none) | LOW |
| CVE-2026-3184 | mount | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | mount | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2025-6141 | ncurses-base | 6.5+20250216-2 | (none) | LOW |
| CVE-2025-6141 | ncurses-bin | 6.5+20250216-2 | (none) | LOW |
| CVE-2007-5686 | passwd | 1:4.17.4-2 | (none) | LOW |
| CVE-2024-56433 | passwd | 1:4.17.4-2 | (none) | LOW |
| TEMP-0628843-DBAD28 | passwd | 1:4.17.4-2 | (none) | LOW |
| CVE-2026-15534 | perl-base | 5.40.1-6+deb13u1 | (none) | MEDIUM |
| CVE-2011-4116 | perl-base | 5.40.1-6+deb13u1 | (none) | LOW |
| CVE-2026-82560 | perl-base | 5.40.1-6+deb13u1 | (none) | UNKNOWN |
| TEMP-0517018-A83CE6 | sysvinit-utils | 3.14-4 | (none) | LOW |
| CVE-2026-18477 | tar | 1.35+dfsg-3.1 | (none) | MEDIUM |
| CVE-2026-18508 | tar | 1.35+dfsg-3.1 | (none) | MEDIUM |
| CVE-2026-5704 | tar | 1.35+dfsg-3.1 | (none) | MEDIUM |
| CVE-2005-2541 | tar | 1.35+dfsg-3.1 | (none) | LOW |
| TEMP-0290435-0B57B5 | tar | 1.35+dfsg-3.1 | (none) | LOW |
| CVE-2026-3184 | util-linux | 2.41.5-0+deb13u1 | (none) | MEDIUM |
| CVE-2022-0563 | util-linux | 2.41.5-0+deb13u1 | (none) | LOW |
| CVE-2026-27171 | zlib1g | 1:1.3.dfsg+really1.3.1-1+b1 | (none) | MEDIUM |
| CVE-2026-85091 | zlib1g | 1:1.3.dfsg+really1.3.1-1+b1 | (none) | MEDIUM |

Policy: docs/os-scan-policy.md
```

Every finding in this baseline shows `Fixed: (none)` — no package has a fix available yet in Debian 13 ("trixie") as of this scan date, so **nothing meets D-08's blocking criteria** (CRITICAL/HIGH severity AND a fix available). There are also zero CRITICAL findings.

## Decision needed

**No blocking findings at baseline; no decision needed.** Every HIGH/MEDIUM/LOW/UNKNOWN finding in this scan has `FixedVersion` empty (`(none)`), so D-08's blocking condition (severity CRITICAL/HIGH AND a fix available) never applies. Per the plan's own instruction ("If 'Decision needed' says None, record ... and continue without asking"), Task 2's checkpoint does not trigger, and no owner decision, exception, or rebuild is needed before Plan 85-15 enforces the gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Built the baseline image on `linux/arm64` instead of the plan's specified `linux/amd64`, due to the same QEMU/Rust-binary segfault already documented in Plan 85-08**
- **Found during:** Task 1 (local baseline build step)
- **Issue:** `docker build --platform linux/amd64 -t triggarr:p85-12-baseline .` crashed inside the Dockerfile's `deps` stage the instant the pip-installed `uv==0.12.17` binary executed: `qemu: uncaught target signal 11 (Segmentation fault) - core dumped`, exit code 139. This is the identical failure mode Plan 85-08's SUMMARY.md already recorded as a deviation on this same machine (QEMU-user emulation of Rust binaries segfaults under `--platform linux/amd64` here, independent of any Dockerfile or script defect) — confirmed by this plan hitting it a second time at the exact same `RUN pip install "uv==${UV_VERSION}" && uv export ...` line.
- **Fix:** Built the baseline image with `docker build --platform linux/arm64 -t triggarr:p85-12-baseline .` instead — this Mac's native, non-emulated platform. The build succeeded end-to-end (all stages, including the `deps` stage's `uv export`). The resulting image is what was saved, scanned with the pinned Trivy binary, and run through the gate for this baseline.
- **Cost if wrong:** Trivy's OS-package scan results describe the Debian 13 base-image layer and any OS packages `apt`/`pip install`s into it — this is architecture-independent at the package-manager level (the same Debian package versions and their CVE status apply on arm64 and amd64 base images from the same `python:3.13-slim` tag), so the baseline's finding set is not expected to differ between architectures. If an amd64-specific OS package (not applicable in a Python slim image, which has no architecture-conditional package list) existed, this substitution could miss it; no such risk is identified here. Real, non-emulated amd64 enforcement happens automatically once Plan 85-15 wires the Trivy scan into `ci.yml`'s `os-scan` job, which runs on GitHub's actual x86_64 runners — the definitive amd64 answer arrives for free at that point, consistent with how Plan 85-08 already deferred its own amd64-specific verification to CI.
- **Files modified:** none — this is a verification-method substitution, not a code change. No scan artifacts (image, tarball, JSON) were committed; all were written under `$TMPDIR/p85-12/`, outside the repo.
- **Verification:** `docker build --platform linux/arm64 -t triggarr:p85-12-baseline .` succeeded; `git status --porcelain` showed no new files in the repo at any point during this plan.
- **Committed in:** recorded in this file's "Baseline scan" section above; no separate commit needed for the deviation itself since no code changed.

---

**Total deviations:** 1 auto-fixed (1 blocking — local verification platform substitution, matching the precedent already recorded in Plan 85-08)
**Impact on plan:** No change to any committed file's content beyond this baseline-evidence doc itself. The substitution only affects which CPU architecture ran the one-time local proof; CI enforcement (Plan 85-15) runs on real amd64 GitHub Actions runners regardless.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Plan: 12*
