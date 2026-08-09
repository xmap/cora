# Surfaces

*Surfaces, handlers, cross-cutting concerns.*

Every command and query has one handler and as many surface adapters as needed. A new surface is a new adapter; the core does not move. For the adapters in service today, see [Stack/Backend](../stack/backend.md).

## Surface aggregate

The Trust BC carries a `Surface` aggregate that names the ingress shape each call arrives through. Three seeded values today, modeled as a closed `SurfaceKind` enum:

| Surface | Kind | Default policy binding |
| --- | --- | --- |
| HTTP | `HTTP` | V2 bootstrap policy |
| MCP stdio | `MCP_STDIO` | n/a |
| MCP streamable HTTP | `MCP_STREAMABLE_HTTP` | n/a |

`surface_id` threads through every command + query handler, the `Authorize` port, Policy evaluation, and the idempotency-cache key namespace (so the same `Idempotency-Key` on different surfaces does not collide). The composition root injects the resolved `surface_id` per-request; tests use a canonical `NIL_SENTINEL_ID` from `cora.infrastructure.routing`.

## Cross-cutting

- **Idempotency.** Create-style commands accept an `Idempotency-Key` header (IETF draft-07). The store remembers `(principal_id, key, surface_id) → result` (with `command_name` + `command_hash` tracked as conflict-detection fields) and replays on retry. The composite key per draft-07 §5 keeps cross-surface keys isolated.
- **Authentication.** Bearer-token at the HTTP edge (`BearerAuthMiddleware` + `TokenVerifier` per IdP); legacy `X-Principal-Id` from a verifying proxy when no IdPs are configured. See [Stack/Auth](../stack/auth.md).
- **Authorization.** Every command and query calls an `Authorize` port (`authorize(principal_id, command_name, conduit_id, surface_id)`). Policy model is permission-list ABAC (ReBAC is a deferred future phase); cross-principal contract tests (BOLA) cover read endpoints across 15 aggregates.
- **Observability.** Structured logs, distributed tracing, and metrics on every handler. Trace context is the source of truth for correlation id.
- **Migrations.** Forward-only. A rollback is a new compensating migration. CI verifies hash-sum integrity and runs a safety scan on net-new migrations.
