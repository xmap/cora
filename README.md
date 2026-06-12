# CORA

[![CI](https://github.com/xmap/cora/actions/workflows/ci.yml/badge.svg)](https://github.com/xmap/cora/actions/workflows/ci.yml)
[![Docs](https://github.com/xmap/cora/actions/workflows/docs.yml/badge.svg)](https://xmap.github.io/cora/)
[![Coverage](https://raw.githubusercontent.com/xmap/cora/python-coverage-comment-action-data/badge.svg)](https://github.com/xmap/cora/tree/python-coverage-comment-action-data)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)

CORA is the system of record for the experiment: the one place that holds why each run did what it did, who or what approved it, under which recipe, and how to replay it later. It owns no servo loop, runs no reconstruction, and stores no dataset bytes; it records what your existing tools decide and, where a facility wants it, governs the choices between them. Pilot: APS beamline 2-BM, a micro-CT instrument at Argonne National Laboratory; rollout to APS's other imaging beamlines (7-BM, 32-ID), then cross-facility validation at MAX IV in Sweden. Long-horizon goal: facility-neutral across photon sources, neutron sources, free-electron lasers, and HPC centres.

The name is also the diagnosis: **Continuously Overpromised, Rarely Automated**. Most facility software lives forever as a slide-deck capability. CORA is the version that ships.

## Status

**Active development; pre-1.0.** Seventeen bounded contexts are in place on an event-sourced core (event store, ports, projections), most at stable internal maturity. APIs, schema, and BC topology are still subject to change. Not yet production-ready.

## Documentation map

The full docs render as a static site at **[xmap.github.io/cora](https://xmap.github.io/cora/)** (auto-deployed on every push to `main`).

| Section | Subject | Where |
| --- | --- | --- |
| README | What CORA is, status, quick start | this file |
| Architecture | Bounded contexts, aggregates, slices, event sourcing, API surfaces, standards lenses | [docs/architecture/](docs/architecture/index.md) |
| Stack | Concrete picks (backend, data, auth, frontend, observability, operations) and what is deliberately deferred | [docs/stack/](docs/stack/index.md) |
| Reference | Rules for writing CORA code: layout, modeling, patterns, runtime, workflow | [docs/reference/](docs/reference/index.md) |
| Glossary | Terminology used across architecture, code, commits, and prose | [docs/reference/glossary.md](docs/reference/glossary.md) |
| Deployments | Pilots driving the model. Today: 2-BM micro-CT at APS | [docs/deployments/](docs/deployments/index.md) |
| Contributing | What kinds of collaboration are wanted | [CONTRIBUTING.md](CONTRIBUTING.md) |

Exact pinned versions live in `apps/api/pyproject.toml`, `Makefile`, and `infra/atlas/migrations/`, not in the docs.

## Quick start

Requires: Python 3.13.12 (managed via uv), Docker (for Postgres), [Atlas](https://atlasgo.io/) (for schema migrations). Node 24 LTS comes later for the frontend.

```bash
# Install uv and Atlas (one-time per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -sSf https://atlasgo.sh | sh

# Install Python deps (runs `uv sync --all-extras` inside apps/api)
make install

# Install pre-commit hooks (one-time per clone)
make precommit

# Start Postgres + pgvector
make db-up

# Apply schema migrations
make migrate-apply

# Run the full test suite
make test

# Start the dev server
make dev
# API at http://localhost:8000
# Health check at http://localhost:8000/health
# REST API: POST /actors  (see /docs for OpenAPI)
# MCP server mounted at /mcp (streamable HTTP transport)
```

Run `make help` for the full list of dev commands.

See [docs/reference/](docs/reference/index.md) for commit message conventions and BC layout. See [CONTRIBUTING.md](CONTRIBUTING.md) for what kinds of collaboration are wanted.

## API surfaces

CORA exposes every command on two equivalent surfaces backed by the same handler:

**REST.** OpenAPI docs at `http://localhost:8000/docs` (Swagger UI) and `/redoc`. Example:

```bash
curl -X POST http://localhost:8000/actors \
  -H 'Content-Type: application/json' \
  -d '{"name": "Doga"}'
# -> 201 {"actor_id": "01900000-..."}
```

**MCP** (Model Context Protocol, the agent surface). Streamable HTTP transport mounted at `/mcp`. Point an MCP-aware client (Claude Code, etc.) at `http://localhost:8000/mcp` and tools across every scaffolded BC (`access`, `agent`, `calibration`, `campaign`, `caution`, `data`, `decision`, `enclosure`, `equipment`, `federation`, `operation`, `recipe`, `run`, `safety`, `subject`, `supply`, `trust`) appear in the client.

Wire-level: JSON-RPC over POSTs, handshake is `initialize` (protocol version `2025-11-25`) → `notifications/initialized` → `tools/*`, with `mcp-session-id` propagated from the initialize response headers. Example listing tools by hand:

```bash
# Initialize, capture session id from response headers
SID=$(curl -si -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"cli","version":"0.1"}}}' \
  | awk -F': ' '/^mcp-session-id/ {print $2}' | tr -d '\r')

# Acknowledge, then list tools
curl -s -X POST http://localhost:8000/mcp -H "mcp-session-id: $SID" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'

curl -s -X POST http://localhost:8000/mcp -H "mcp-session-id: $SID" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

For the full handshake-and-call sequence used by tests, see `apps/api/tests/contract/_mcp_helpers.py`.

## Repo layout (monorepo)

```
cora/
├── apps/
│   └── api/                       # backend
│       ├── src/cora/
│       │   ├── api/               # entrypoints
│       │   ├── infrastructure/    # ports, kernel, adapters
│       │   └── <bc>/              # one folder per bounded context
│       │       ├── aggregates/    # state, events, evolver
│       │       └── features/      # vertical slices
│       ├── tests/                 # unit, integration, contract, architecture, e2e
│       └── pyproject.toml
├── infra/
│   ├── atlas/                     # migrations
│   └── docker-compose.yml
├── docs/                          # architecture, stack, reference, deployments, catalog, projects
├── scripts/                       # dev and CI helpers
├── mkdocs.yml                     # docs site config
├── CONTRIBUTING.md
├── Makefile
└── README.md
```

- **`<bc>/`** is one of 17 bounded contexts scaffolded today: `access`, `agent`, `calibration`, `campaign`, `caution`, `data`, `decision`, `enclosure`, `equipment`, `federation`, `operation`, `recipe`, `run`, `safety`, `subject`, `supply`, `trust`. Each follows the same `aggregates/` + `features/` shape (see [docs/reference/](docs/reference/index.md)).
- **`tests/`** mirrors `src/` and splits by category: `unit/` (pure), `integration/` (real Postgres), `contract/` (REST and MCP schema), `architecture/` (fitness checks), `e2e/` (full surface-to-store flows).
- **Planned but not yet on disk:** `apps/web` (frontend), `apps/workers` (background processors and agents), `packages/` (shared libs).

## Architecture (high level)

Functional DDD with bounded contexts. Hexagonal (Functional Core / Imperative Shell). Event-sourced backend on a relational store. Two equivalent API surfaces (REST and MCP) backed by the same handler. Agents are principals, not features: same identity, authz, and audit as humans. The recipe ladder (Method, Practice, Plan, Run) is the facility-neutrality mechanism.

CORA spans three tiers. The spine is always CORA: the event log, decisions, the recipe ladder, trust, and audit, running at decision-grade latency and never inside a deterministic real-time loop. The execution edge is optional: a substrate-neutral ControlPort and Conductor (EPICS adapters shipped) a facility may adopt to drive operations, or skip in favour of its own tools. The floor is never CORA: servo control, position-synchronised output, and FPGA triggering stay in the IOCs and motion controllers. Only the spine and the floor are fixed; how far the edge reaches between them is the facility's choice. See [the recording spine and the optional execution edge](docs/architecture/standards.md#the-recording-spine-and-the-optional-execution-edge).

Modelling lenses, borrowed for shared vocabulary with the field rather than wire conformance: ISA-95 (asset hierarchy), ISA-88 (episodic procedures), ISA-106 (continuous operations), ISA-99 / IEC 62443 (trust topology), ISO/IEC 42001 + NIST AI RMF (AI governance), W3C PROV-O (provenance at API boundaries).

For the full design discussion see [docs/architecture/](docs/architecture/index.md); concrete picks (FastAPI, Postgres, Atlas, MCP SDK, etc.) live in [docs/stack/](docs/stack/index.md).
