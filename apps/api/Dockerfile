# CORA API image.
#
# Build from the REPO ROOT, not from apps/api, so the build context can
# reach nothing it does not need:
#
#   docker build -f apps/api/Dockerfile -t cora-api:dev apps/api
#
# ## Why linux/amd64 is pinned and not negotiable
#
# The EPICS client libraries ship binary wheels for x86_64 ONLY. Checked
# against this repo's uv.lock: epicscorelibs, pvxslibs and p4p each
# publish 4 linux wheels, every one of them *-manylinux*_x86_64.whl.
# There is no linux/aarch64 wheel for any of them. On an arm64 host
# (an Apple Silicon laptop, a Graviton runner) an unpinned build either
# fails to resolve or silently tries to compile EPICS base from source.
#
# So the platform is pinned here rather than left to the builder's
# architecture. On arm64 this build runs under emulation and is slow;
# that is the cost of the wheels being what they are, and a slow correct
# build beats a fast one that cannot talk to an IOC.
#
# ## Why the builder needs a C toolchain
#
# aioca publishes NO linux wheel at all (uv.lock lists a single sdist and
# zero wheels), so it compiles its Channel Access extension against
# epicscorelibs via setuptools-dso at install time. That needs gcc/g++.
# The compiler stays in the builder stage and never reaches the runtime
# image.
#
# ## What this image does NOT do
#
# It does not run migrations. Atlas applies them out of band (`make
# migrate-apply`) using a Go binary that is not a Python dependency and
# is deliberately not installed here: migrations are forward-only and
# operator-sequenced, so an image that migrated itself on boot would let
# a rolling deploy race two schema versions against one database.
#
# It carries no default configuration. `app = create_app()` runs at
# IMPORT, and its boot gates raise there, so a misconfigured container
# exits immediately instead of serving. That is the intended behaviour:
# see docs/stack/deployment.md.

ARG PYTHON_VERSION=3.13.12
# Carried as an ARG rather than a literal so buildkit does not read it as
# a multi-arch mistake, and so a future arm64 EPICS wheel can be tried
# with --build-arg. The default is the only value known to work.
ARG BUILD_PLATFORM=linux/amd64

# ---------------------------------------------------------------- builder
FROM --platform=${BUILD_PLATFORM} python:${PYTHON_VERSION}-slim-bookworm AS builder

# gcc/g++ are here for aioca's sdist (see header). They are NOT copied
# into the runtime stage.
RUN apt-get update \
    && apt-get install --no-install-recommends -y gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies resolve from the committed lock and land in their own
# layer, so a source edit does not trigger an EPICS recompile.
# --frozen: fail rather than silently re-resolve. --no-dev: the dev group
# carries pytest + the tooling. --no-install-project: the project itself
# lands in the next layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------- runtime
ARG PYTHON_VERSION
ARG BUILD_PLATFORM
FROM --platform=${BUILD_PLATFORM} python:${PYTHON_VERSION}-slim-bookworm AS runtime

# curl backs the HEALTHCHECK below. Drop both together if the
# orchestrator does its own probing.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 cora

WORKDIR /app

COPY --from=builder --chown=cora:cora /app/.venv /app/.venv
COPY --from=builder --chown=cora:cora /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER cora

EXPOSE 8000

# Liveness only. /health checks nothing by design; /readyz reports
# Postgres and belongs on the orchestrator's readinessProbe, not here,
# because Docker's HEALTHCHECK failure restarts the container, and
# restarting an app because its database is down is how one outage
# becomes a crash loop. See docs/stack/deployment.md.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# No --reload, no --workers. One process per container: the lifespan
# starts in-process background workers (projection worker, subscribers,
# watchers), and --workers would fork N of each against one database.
# Scale with replicas.
CMD ["uvicorn", "cora.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
