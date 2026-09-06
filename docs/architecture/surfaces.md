# Surfaces

*Surfaces, handlers, cross-cutting concerns.*

Every command and query has one handler and as many surface adapters as needed. A new surface is a new adapter; the core does not move. For the adapters in service today, see [Stack/Backend](../stack/backend.md).

## Surface aggregate

The Trust BC carries a `Surface` aggregate that names the ingress shape each call arrives through. Four seeded values today, modeled as a closed `SurfaceKind` enum:

| Surface | Kind | Default policy binding |
| --- | --- | --- |
| HTTP | `HTTP` | V2 bootstrap policy |
| MCP stdio | `MCP_STDIO` | n/a |
| MCP streamable HTTP | `MCP_STREAMABLE_HTTP` | n/a |
| In-process | `IN_PROCESS` | n/a |

`IN_PROCESS` names CORA's own in-process work: agent tick loops, capture readers, and one-time operator entrypoints that call a handler directly with no HTTP request or MCP tool call behind them. Every such call site passes it explicitly; there is no default-binding policy or Settings knob for it, since the calls it names always originated in-process.

`surface_id` threads through every command + query handler, the `Authorize` port, Policy evaluation, and the idempotency-cache key namespace (so the same `Idempotency-Key` on different surfaces does not collide). The composition root injects the resolved `surface_id` per-request; tests use a canonical `NIL_SENTINEL_ID` from `cora.infrastructure.routing`.

## Cross-cutting

- **Idempotency.** Create-style commands accept an `Idempotency-Key` header (IETF draft-07). The store remembers `(principal_id, key, surface_id) → result` (with `command_name` + `command_hash` tracked as conflict-detection fields) and replays on retry. The composite key per draft-07 §5 keeps cross-surface keys isolated.
- **Authentication.** Bearer-token at the HTTP edge (`BearerAuthMiddleware` + `TokenVerifier` per IdP); legacy `X-Principal-Id` from a verifying proxy when no IdPs are configured. See [Stack/Auth](../stack/auth.md).
- **Authorization.** Every command and query calls an `Authorize` port (`authorize(principal_id, command_name, conduit_id, surface_id)`). Policy model is permission-list ABAC (ReBAC is a deferred future phase); cross-principal contract tests (BOLA) cover read endpoints across 15 aggregates.
- **Observability.** Structured logs, distributed tracing, and metrics on every handler. Trace context is the source of truth for correlation id.
- **Migrations.** Forward-only. A rollback is a new compensating migration. CI verifies hash-sum integrity and runs a safety scan on net-new migrations.
- **API evolution.** Additive by default: add fields, do not remove them or narrow what they promise. Clean URLs with no version prefix. A genuinely breaking change is carried by an `X-Cora-Api-Version: YYYY-MM-DD` request header, not a `/v1/` path, and that dispatch is not built until a break needs it. See [API evolution](#api-evolution) for what counts as breaking and the one exception taken so far.

## API evolution

The committed `apps/api/openapi.json` snapshot is the wire contract, and `test_openapi_drift` fails whenever a route's response shape stops matching it. That makes every contract change visible in a diff. It does not classify one: whether a given diff is additive or breaking is a judgement a reader still has to make, so the reasoning is recorded here when it is not obvious.

Breaking means a response a caller could rely on stops arriving. Removing a field is the clear case. So is narrowing one: a field that was always present becoming sometimes absent breaks a caller that dereferenced it without checking, which the type said it never had to do.

### The exception taken so far: `model_ref` on `AgentResponse`

`model_ref` used to be required and non-null on every `AgentResponse`. With the Brain change it became nullable, and it is now null for most agents: eighteen of the twenty-four seeded agent definitions declare a rule brain, and the six that name a model are RunDebriefer and CautionDrafter across their three deployment profiles each. By the definition above that is breaking, and it shipped without a version header. Three reasons, and the third is the one that expires.

**The withdrawn guarantee was a guarantee to return a lie.** A rule-brained agent has no model to name, but the schema required one, so the field carried a sentinel: provider `deterministic`, model `agent:<Name>:v1`. A caller reading `model_ref.provider` for one of them got a provider that names no vendor and a model that was never called or approved. The field did not become less informative when it went null; it stopped misreporting.

**The replacement is additive and strictly better.** `brain` was added alongside, and it states the kind of thinking an agent does rather than assuming that thinking is always a model. A caller that wants the served model still finds `model_ref` populated for the two agents that have one, without reaching through the discriminated shape.

**There are no consumers.** The REST surface has never been published to a client outside this repository, and no in-repo consumer reads the field. A version boundary introduced here would be maintained forever to protect nobody, which is the version proliferation the additive default exists to avoid.

That third reason is the one with an expiry, and it is doing most of the work. **Once the REST surface has any consumer outside this repository, this precedent stops applying.** A narrowing change after that point needs the header, whether or not the old value was a sentinel. Cite this section for the sentinel argument if it genuinely fits; do not cite it for "CORA does not version."
