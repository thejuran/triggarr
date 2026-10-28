# ---- Stage 1: Tailwind CSS builder ----
# Compiles Tailwind CSS using pytailwindcss. Only the output.css artifact
# is carried forward to the production image.
FROM python:3.13-slim AS builder

# Pin the Tailwind binary version downloaded by pytailwindcss.
# Bump this when upgrading Tailwind CSS (must match the version used
# during local development with `tailwindcss -w`).
ENV TAILWINDCSS_VERSION=v4.2.2

WORKDIR /build

COPY pyproject.toml .
COPY triggarr/ triggarr/

RUN pip install --no-cache-dir pytailwindcss \
    && tailwindcss_install \
    && tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --minify


# ---- Stage 2: Locked dependency export ----
# Build-only stage: pins uv to export pyproject.toml's resolved, hash-pinned
# dependency set from uv.lock. Neither uv nor this stage ships in the final
# image -- only the exported requirements-locked.txt file is copied out.
FROM python:3.13-slim AS deps

ENV UV_VERSION=0.12.17

WORKDIR /build

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir "uv==${UV_VERSION}" \
    && uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file requirements-locked.txt


# ---- Stage 3: Production image ----
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install exactly the locked, hash-checked dependency set -- never
# pyproject.toml's loose constraints -- so the image can't silently
# diverge from the lockfile CI already audited (CIMAINT-01).
COPY --from=deps /build/requirements-locked.txt /tmp/requirements-locked.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements-locked.txt \
    && rm /tmp/requirements-locked.txt
RUN pip install --no-cache-dir --no-deps "idna==3.4"

COPY pyproject.toml .
COPY triggarr/ triggarr/
COPY CHANGELOG.md .
RUN pip install --no-cache-dir --no-deps .

# Pull compiled CSS from the builder stage
COPY --from=builder /build/triggarr/static/css/output.css triggarr/static/css/output.css

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create a non-root fallback user for security scanners and in case
# entrypoint.sh fails before its own setpriv privilege drop.
RUN useradd -r -s /sbin/nologin -d /config triggarr_default

EXPOSE 8484

VOLUME /config

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8484/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
