# ---- Stage 1: Tailwind CSS builder ----
# Compiles Tailwind CSS using pytailwindcss. Only the output.css artifact
# is carried forward to the production image.
FROM python:3.13-slim AS builder

# Pin the Tailwind binary version downloaded by pytailwindcss.
# Bump this when upgrading Tailwind CSS (must match the version used
# during local development with `tailwindcss -w`).
ENV TAILWINDCSS_VERSION=v4.2.1

WORKDIR /build

COPY pyproject.toml .
COPY triggarr/ triggarr/

RUN pip install --no-cache-dir pytailwindcss \
    && tailwindcss_install \
    && tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --minify


# ---- Stage 2: Production image ----
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml .
COPY triggarr/ triggarr/
COPY CHANGELOG.md .
RUN pip install --no-cache-dir .

# Pull compiled CSS from the builder stage
COPY --from=builder /build/triggarr/static/css/output.css triggarr/static/css/output.css

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8484

VOLUME /config

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8484/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
