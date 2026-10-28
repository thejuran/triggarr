# Review image for Phase 85.1 (D-07): isolates the Codex review of an
# untrusted (bot or fork) PR head inside a disposable container. This
# image must contain nothing but the Codex runtime -- no git, Python,
# Node, curl, package manager or shell toolchain beyond the base OS --
# so an injected instruction inside the reviewed diff has nothing useful
# to reach for even if it escaped Codex's own sandboxing. Changing this
# file is a sensitive review-machinery change (see
# docs/review-classification-policy.md) and needs the same risk
# assessment any review-machinery edit does.
#
# The base image below is pinned by digest. That is a deliberately new,
# narrower convention adopted specifically for this one security-
# sensitive image: the repository root Dockerfile pins its base images
# by tag only, not digest, and this file does not claim to match that
# existing practice.
#
# The build context for this image is this directory only; no files
# from the rest of the repository ever enter the image.
#
# CODEX_VERSION here must match REVIEW_CODEX_VERSION in
# tests/codex_review_run.py (asserted by a test added in Plan 85.1-07).

# ---- Stage 1: fetch -- download and checksum-verify the Codex release binary ----
FROM debian:bookworm-slim@sha256:7ccb8b5b60c7654f5b795d94ee7d751cd0811500803f0b09cefcd555e755a55a AS fetch

ARG CODEX_VERSION=0.153.4
ARG CODEX_SHA256_ARM64=5cda6182bd94c3a30f2eb63a495489ebf7f691fddb14d70f48c6c1a5071b6cde

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/codex-fetch

RUN curl -fsSLO "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-aarch64-unknown-linux-musl.tar.gz" \
    && echo "${CODEX_SHA256_ARM64}  codex-aarch64-unknown-linux-musl.tar.gz" | sha256sum -c - \
    && tar -xzf codex-aarch64-unknown-linux-musl.tar.gz \
    && install -m 0755 codex-aarch64-unknown-linux-musl /usr/local/bin/codex

# ---- Stage 2: review -- nothing in the final image but the base OS and the Codex binary ----
FROM debian:bookworm-slim@sha256:7ccb8b5b60c7654f5b795d94ee7d751cd0811500803f0b09cefcd555e755a55a

ARG CODEX_VERSION=0.153.4

RUN groupadd -g 10001 review \
    && useradd -u 10001 -g 10001 -d /home/review -m -s /usr/sbin/nologin review

COPY --from=fetch /usr/local/bin/codex /usr/local/bin/codex

ENV HOME=/home/review \
    LANG=C.UTF-8 \
    CODEX_HOME=/codex-home

LABEL org.triggarr.codex-review="${CODEX_VERSION}"

USER 10001:10001
WORKDIR /work
ENTRYPOINT ["codex"]
