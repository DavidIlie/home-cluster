# syntax=docker/dockerfile:1.23
#
# PostHog MCP server, packaged for self-hosted PostHog.
#
# Upstream lives in the PostHog monorepo at services/mcp and is a Cloudflare
# Workers app (wrangler + miniflare). To run outside Cloudflare we use
# `wrangler dev` bound on 0.0.0.0 — miniflare provides Durable Object + SQLite
# locally. The package.json uses pnpm workspace + catalog protocols
# (`workspace:*`, `catalog:`), so we MUST install from the monorepo root with a
# filter — installing services/mcp standalone fails.
#
# Build & push from your Mac (x64 so it runs on cluster nodes):
#
#   cd kubernetes/apps/observability/posthog/mcp
#   docker login ghcr.io   # one-time, with a PAT scoped to write:packages
#   docker buildx build \
#     --platform linux/amd64 \
#     --build-arg POSTHOG_REF=master \
#     -t ghcr.io/davidilie/posthog-mcp:latest \
#     --push .
#
# Args:
#   POSTHOG_REF — git ref / tag / sha of PostHog/posthog to build from
ARG NODE_IMAGE=node:24-slim

FROM ${NODE_IMAGE} AS builder
ARG POSTHOG_REF=master
ENV PNPM_HOME=/root/.local/share/pnpm \
    PATH=/root/.local/share/pnpm:$PATH \
    CI=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates python3 build-essential \
 && rm -rf /var/lib/apt/lists/* \
 && corepack enable

WORKDIR /src
RUN git clone --depth 1 --branch "${POSTHOG_REF}" --filter=blob:none \
        https://github.com/PostHog/posthog.git . \
 || (git clone --depth 1 --filter=blob:none https://github.com/PostHog/posthog.git . \
     && git fetch --depth 1 origin "${POSTHOG_REF}" \
     && git checkout FETCH_HEAD)

# Filtered install: only @posthog/mcp and its workspace deps.
# `--ignore-scripts` skips lifecycle hooks for unrelated workspaces (Python tooling, etc.).
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --filter @posthog/mcp... --ignore-scripts

# Build mcp UI apps so wrangler has the bundled assets at runtime.
RUN pnpm --filter @posthog/mcp run build:ui-apps

# -----------------------------------------------------------------------------

FROM ${NODE_IMAGE} AS runtime
ENV PNPM_HOME=/home/mcp/.local/share/pnpm \
    PATH=/home/mcp/.local/share/pnpm:$PATH \
    NODE_ENV=production \
    WRANGLER_SEND_METRICS=false \
    POSTHOG_API_BASE_URL=https://posthog.davidhome.ro \
    MCP_APPS_BASE_URL=https://posthog-mcp.davidhome.ro
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 && corepack enable \
 && useradd -m -u 1001 -s /bin/bash mcp \
 && mkdir -p /data \
 && chown -R mcp:mcp /data

# Copy the built monorepo. wrangler resolves workspace packages via the on-disk
# layout, so we keep the full /src tree, not just services/mcp.
COPY --from=builder --chown=mcp:mcp /src /src

WORKDIR /src/services/mcp
USER mcp
EXPOSE 8787
VOLUME ["/data"]

# wrangler dev runs miniflare locally — Durable Objects + SQLite live under
# --persist-to. --ip 0.0.0.0 lets the worker accept traffic from outside the
# pod. --no-show-interactive-dev-session keeps it non-TTY-friendly.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["pnpm", "exec", "wrangler", "dev", \
     "--ip", "0.0.0.0", \
     "--port", "8787", \
     "--persist-to", "/data", \
     "--no-show-interactive-dev-session"]
