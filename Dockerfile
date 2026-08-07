# syntax=docker/dockerfile:1

##############################################################################
# Stage 1: builder - installs python dependencies into a self-contained venv.
# Build-only tooling (compilers, -dev headers, pip cache) never reaches the
# final image.
##############################################################################
FROM python:3.15.0b3-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# Build-time only headers/toolchain (discarded with this stage)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        liblzma-dev \
    && rm -rf /var/lib/apt/lists/*

# Self-contained venv so the runtime stage only needs one COPY
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
# BuildKit cache mount keeps rebuilds fast without baking the cache into a layer
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install -r /tmp/requirements.txt

# Strip build artefacts that are dead weight at runtime.
# NOTE: do NOT blanket-delete directories named test/tests - several packages
# ship importable public APIs under those names (e.g. django.test, which DRF
# and simplejwt import at settings-load time).
RUN find /opt/venv -depth \( -name '__pycache__' -o -name '*.pyc' -o -name '*.pyo' \) -exec rm -rf {} + ; \
    find /opt/venv -name '*.so' -exec strip --strip-unneeded {} + 2>/dev/null ; \
    rm -rf /opt/venv/share/man /opt/venv/share/doc ; \
    true


##############################################################################
# Stage 2: runtime
##############################################################################
FROM python:3.15.0b3-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

# --- memory tuning ---------------------------------------------------------
# glibc reserves up to 64MB of arena per thread by default; capping this is the
# single biggest RSS reduction for multi-threaded Python workloads.
ENV MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=131072

# BLAS/OpenMP otherwise spin up one thread pool per CPU core, each with large
# private buffers. This workload is IO-bound, so one thread each is plenty.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

# Keep the downloaded sentence-transformer model on the persistent volume
# instead of growing the container's writable layer on every restart.
ENV HF_HOME=/news_platform/data/.cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1

# Django debug mode retains every executed SQL query in memory for the lifetime
# of the process - never appropriate for a long-running container.
# Override in docker-compose if you really need it.
ENV DEBUG=false

# Process sizing - override in docker-compose to trade memory for throughput
ENV GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4 \
    CELERY_CONCURRENCY=2 \
    REDIS_MAXMEMORY=256mb \
    ENABLE_FLOWER=true

# Runtime OS packages + redis, installed and cleaned within a single layer.
# gpg is only needed to dearmor the redis signing key, so it is purged again.
# lsb-release is replaced by /etc/os-release, and nano is dropped entirely.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gpg \
        netcat-traditional \
    && curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/redis.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends redis-server \
    && apt-get purge -y gpg \
    && apt-get autoremove -y --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
              /usr/share/doc/* /usr/share/man/* /usr/share/locale/*

# Python environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Add non-root user "app_user"
#
# /news_platform/data is deliberately created here, even though it is empty:
# the directory is untracked in git and excluded by .dockerignore, so it never
# arrives via COPY. If the mount point does not exist in the image, Docker
# creates it as root:root when the VOLUME is materialised, and the non-root
# process cannot write to it. Pre-creating it means a fresh named/anonymous
# volume inherits app_user ownership from the image instead.
# The db_migrations subtree is created too - Django writes migration files there
# on first boot.
#
# NOTE: `install -d -o/-g` applies the ownership only to the *final* path
# component - any intermediate parent it has to create is left owned by root.
# So the tree is built with mkdir -p and ownership is applied once, recursively,
# afterwards. All of these directories are empty, so the extra layer is tiny.
RUN useradd -U -m -d /home/app_user app_user \
    && mkdir -p /news_platform/staticfiles \
                /news_platform/static/splashscreens \
                /news_platform/data/.cache \
    && for app in articles feeds preferences markets django_celery_beat webpush \
                  sessions auth authtoken admin contenttypes; do \
           mkdir -p "/news_platform/data/db_migrations/$app"; \
       done \
    && chown -R app_user:app_user /news_platform \
    && chmod -R 0755 /news_platform

WORKDIR /news_platform
USER app_user:app_user

# Copy code last so the dependency layers stay cached across code changes.
# --chown already sets ownership; a follow-up `chown -R` would duplicate the
# entire tree into a second image layer, so it is deliberately omitted.
COPY --chown=app_user:app_user . /news_platform/

# Add docker container labels
LABEL org.opencontainers.image.title="News Platform"
LABEL org.opencontainers.image.description="News Aggregator - Aggregates news articles from several RSS feeds, fetches full-text if possible, sorts them by relevance (based on user settings), and display on distraction-free homepage."
LABEL org.opencontainers.image.authors="https://github.com/vanalmsick"
LABEL org.opencontainers.image.url="https://github.com/vanalmsick/news_platform"
LABEL org.opencontainers.image.documentation="https://vanalmsick.github.io/news_platform/"
LABEL org.opencontainers.image.source="https://hub.docker.com/r/vanalmsick/news_platform"
LABEL org.opencontainers.image.licenses="MIT"

# Expose Port: Main website
EXPOSE 80
# Expose Port: Celery Flower - for dev
EXPOSE 5555
# Expose Port: Supervisord - for dev
EXPOSE 9001
# Permanent storage for database and config files
VOLUME /news_platform/data

# Configure automatic docker container healthcheck
HEALTHCHECK --interval=5m --timeout=60s --retries=3 --start-period=120s \
    CMD curl --max-time 30 --connect-timeout 30 --silent --output /dev/null --show-error --fail http://localhost:80/ || exit 1

# Start News Platform using supervisord
CMD ["supervisord", "-c", "./supervisord.conf"]
