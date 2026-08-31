"""Closed enumeration of process-level arrival surface kinds.

Closed enum on purpose: adding a new surface (gRPC, websocket, A2A,
batch) requires a code release. Same precedent as
`equipment.aggregates.family.Affordance` and
`recipe.aggregates.capability.ExecutorShape`. Open enumeration is
what killed the AAS Capability Submodel (per
project_family_affordance_design failure-mode lesson) — closed-enum
discipline keeps the operational vocabulary small and grep-able.

V1 values:

- HTTP: requests arriving on the FastAPI HTTP socket.
- MCP_STDIO: MCP tool calls arriving over the local stdio transport
  (typical for local-dev / IDE-bound Claude Code sessions). Implicit
  loopback trust; usually distinct authz posture from remote agents.
- MCP_STREAMABLE_HTTP: MCP tool calls arriving over the
  streamable-http transport (typical for remote agents). Must
  authenticate; audit trail should differentiate from stdio.
- IN_PROCESS: no transport at all. CORA's own background code (agent
  runtimes, tick loops, capture readers) calling a handler directly,
  in-process, on behalf of no external caller. Distinct from every
  other member above, which all name a real wire protocol a request
  arrived over; this one names the absence of one. Orthogonal to the
  deferred transports below, none of which describe in-process work
  either. Not named INTERNAL: that word already names an unrelated
  domain value elsewhere (`Operation.acquisitions.trigger_mode`'s
  `"Internal"` camera-trigger source), and on its own reads as
  "internal network" rather than "no transport."

Deferred kinds (with documented anticipated names so future code
review catches conflicts):

- A2A: Agent-to-Agent inbound. Per Round 2 corpus, A2A spec v1.0.0
  defines multiple bindings (JSON-RPC / gRPC / REST). Trigger-time
  decision: one collapsed SurfaceKind.A2A vs split per-binding
  (A2A_JSONRPC / A2A_GRPC / A2A_REST). Default-preferred: collapsed.
- GRPC: standalone gRPC API (non-A2A).
- WEBSOCKET: persistent bidirectional channel.
- BATCH: cron / scheduled / queue-driven entry.

These names are reserved by listing — do not pick conflicting
identifiers when the time comes.
"""

from enum import StrEnum


class SurfaceKind(StrEnum):
    HTTP = "http"
    MCP_STDIO = "mcp_stdio"
    MCP_STREAMABLE_HTTP = "mcp_streamable_http"
    IN_PROCESS = "in_process"
