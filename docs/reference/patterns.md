# Patterns

*Read side, query slices, projections, idempotency, cross-aggregate validation, rejections.*

The shapes that recur across slices: how reads work, when retries stay safe, where slices need another aggregate, what failure looks like. New slices follow them or have a reason not to.

## Read side

Two read paths, picked by query shape.

- **Fold-on-read** (`aggregates/<aggregate>/read.py:load_<aggregate>`) for single-aggregate `GET`. O(events-per-stream).
- **Projection worker** for list / filter / search and high-traffic queries. Background task tails the events channel; `GET` reads a denormalized table.

Read repos live with the aggregate, not the slice; they operate on the stream regardless of which command produced the events.

## Query slices

Symmetric with command slices. No decider, no events.

**`get_<aggregate>`**: single-resource read by id.

```
features/get_<aggregate>/
├── query.py        # GetActor(actor_id: UUID)
├── handler.py      # bind(deps) -> Handler returning Aggregate | None
├── route.py        # GET /<resource>/{id} -> 200 + DTO  (404 on None)
└── tool.py         # MCP tool
```

Reads via fold-on-read. Returns domain types; route + tool do their own Pydantic DTO mapping.

**`list_<aggregates>`**: keyset-paginated list backed by a projection.

```
features/list_<aggregates>/
├── query.py        # ListActors(cursor, limit, status)
├── handler.py      # bind(deps) -> Handler returning ActorListPage
├── route.py        # GET /<resource>?cursor=...&limit=50
└── tool.py         # MCP tool
```

Reads `proj_<bc>_<name>` via `deps.pool`. Cursor is opaque base64 of `(created_at, UUID)` via `encode_cursor`/`decode_cursor`. Default page 50, max 100. Empty: `200 {"items": [], "next_cursor": null}`. Malformed cursor: 422 via `InvalidCursorError`.

Query handlers DO call `kernel.authz.authorize(...)` with the query name as `command_name`. Per-row scoping needs ReBAC (deferred). The port method is `authorize(principal_id, command_name, conduit_id, surface_id)`; the kernel attribute name is `authz` (short, less collision-prone than `authorize`).

## Projections

Background workers maintain denormalized read tables by tailing the event store. Located at `cora.infrastructure.projection`; composition root spawns one in-process worker via FastAPI lifespan, which advances every registered `Projection` along the event stream.

- **`Projection` Protocol** in `cora/<bc>/projections/<name>.py`: `name` (matches `proj_*` table + bookmark), `subscribed_event_types`, `apply(event, conn)`. Advance orders by `(transaction_id, position)` with `pg_snapshot_xmin` exclusion.
- **`apply()` MUST be idempotent** (at-least-once delivery). `INSERT ... ON CONFLICT (key) DO NOTHING/UPDATE` or `# idempotent: <reason>`. Enforced by `test_projection_idempotency.py`.
- **Per-BC registration**: each BC exports `register_<bc>_projections(registry, deps)`; composition root calls it after `wire_<bc>(deps)`.
- **Migration shape**: every `proj_*` migration includes `GRANT SELECT, INSERT, UPDATE, DELETE TO cora_app` plus `INSERT INTO projection_bookmarks (name) VALUES (...) ON CONFLICT DO NOTHING`. Enforced by `test_projection_grants.py`.

Tests use `await drain_projections(pool, registry, deadline=2.0)` instead of `asyncio.sleep`.

**Settings:**

- `projection_use_listen_notify: bool = True`: NOTIFY wake-up (~tens of ms). Flip False if commit lock contends.
- `projection_poll_interval_seconds: float = 5.0`: safety-net poll. Floor 0.1s.

## Lifecycle timestamps

Wall-clock timestamps on aggregates (`created_at`, `versioned_at`, `deprecated_at`) belong on the **projection**, not on aggregate state. Path C (shipped 2026-05-20) moved Method, Plan, Practice, Capability, Family, and Agent over; Surface dropped them entirely.

- **State stays narrow.** Timestamps don't gate invariants, so a decider shouldn't carry them. Removing the field shrinks the from_stored / payload surface.
- **Projection derives from envelope `occurred_at`.** Each genesis event sets `created_at`; subsequent transition events update the matching `<verb>_at` column. Apply remains idempotent.
- **Contract tests source timestamps from the projection row.** A `*_summary` projection backs every list query; contract tests assert on that row, not on the aggregate.
- **Single-record reads still fold the stream.** When the route needs a timestamp without joining the projection, derive it from envelope `occurred_at` at fold time rather than carrying it in state.

## Idempotency

Create-style commands accept an idempotency key so client-side retries don't duplicate. Standard: [IETF `Idempotency-Key`](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07) (Stripe / Adyen / PayPal). Decorator at `cora/infrastructure/idempotency.py`; wrap applied in each BC's `wire.py`.

- **Apply**: create-style commands (server generates id; retries would otherwise duplicate).
- **Skip**: queries; updates not needing cached-success-on-retry.

```python
register_actor=with_idempotency(
    register_actor.bind(deps),
    deps.idempotency_store,
    command_name="RegisterActor",
    serialize_result=str,
    deserialize_result=UUID,
)
```

Slice exposes `Handler` (bare) and `IdempotentHandler` (wrapped, optional `idempotency_key`). Tests use bare; production wires wrapped. Routes extract via `Header(alias="Idempotency-Key")`.

The cache namespace is the composite `(principal_id, key, surface_id)` per IETF draft-07 §5, so the same `Idempotency-Key` cannot collide across HTTP and MCP surfaces; `command_hash` and `command_name` are conflict-detection parameters on `claim()`, not part of the namespace tuple.

`IdempotencyConflictError` (same key + different body) returns 422. Key max 255 chars. Single-phase MVP; concurrent-retry race documented in the port docstring. MCP tools pass `idempotency_key=None` (no MCP standard yet).

## Cross-aggregate validation

Some commands validate against another aggregate's state (`define_plan` checks Practice + Method + Assets; `start_run` checks Plan + optional Subject + Assets).

**Handler loads upstream aggregates into a slice-local context dataclass; pure decider takes the context as opaque parameter.**

```python
# slice/context.py
@dataclass(frozen=True)
class PlanBindingContext:
    practice: Practice
    method: Method
    assets: dict[UUID, Asset]


# slice/handler.py
practice = await load_practice(deps.event_store, command.practice_id)
if practice is None:
    raise PracticeNotFoundError(command.practice_id)
method = await load_method(deps.event_store, practice.method_id)
if method is None:
    raise MethodNotFoundError(practice.method_id)
assets: dict[UUID, Asset] = {}
for asset_id in sorted(command.asset_ids, key=str):
    asset = await load_asset(deps.event_store, asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)
    assets[asset_id] = asset

context = PlanBindingContext(practice=practice, method=method, assets=assets)
events = decide(state=None, command=command, context=context, now=now, new_id=new_id)


# slice/decider.py
def decide(
    state: Plan | None,
    command: DefinePlan,
    *,
    context: PlanBindingContext,
    now: datetime,
    new_id: UUID,
) -> list[PlanDefined]:
    if context.practice.status is PracticeStatus.DEPRECATED:
        raise PlanBoundPracticeDeprecatedError(context.practice.id)
```

- **Decider stays pure.** No `await`, no port injection. Tests build contexts directly.
- **Capture, don't recompute.** Bind-time data captured in the event payload; replay never re-loads.
- **Eventual consistency.** Concurrent upstream changes between handler-load and event-append are accepted.
- **Existence vs state.** Handler raises `<X>NotFoundError` (404); decider raises domain errors (409).
- **Slice-local context.** Each cross-validating slice gets `<slice>/context.py`. Promote to a shared form only after Rule of Three.

FCIS canonical: data not in the stream is fetched in the shell and passed to the pure core as plain values.

### Dispatch-slice exception

Most command slices have a decider that returns `list[<Event>]` for events on the slice's own aggregate. A small set of cross-BC slices instead validate a loaded aggregate from another BC and dispatch to that BC's own slice without writing an event on any aggregate the consuming BC owns. The current example is `cora.agent.features.promote_caution_proposal`: the slice loads a `Decision`, validates the proposed-Caution payload, and the handler dispatches to `cora.caution.features.{register,supersede}_caution` based on the decision's `choice`. The Agent BC never writes a Caution and never emits an Agent-owned event; the function in `decider.py` returns `ProposedCautionView` (the validated payload + dispatch hint) rather than events.

Treat `decider.py` in such slices as a pure validator-and-extractor: the canonical-args check (`state`, `command`, `*`, keyword-only extras) still applies; the return-type expectation (`list[<Event>]`) does not. The slice's docstring must explain the dispatch shape, and the function's `Invariants:` block enumerates rejections the same way a true decider does. Adopt this shape only when the slice genuinely owns no aggregate writes; when in doubt, emit an event on the source aggregate's stream and dispatch via `EventStore.append_streams`.

## Schema validation posture

Two postures coexist for `Method.parameters_schema` validation against a carrier aggregate's values dict. Pick by whether the operator has already committed to the Run.

- **STRICT** (`validate_effective_parameters_against_method_schema`): used by `start_run` (6g-c). Schemaless Method + non-empty parameters = REJECT. Forces operators to declare a schema before accepting overrides at Run start time.
- **RELAXED** (`validate_adjusted_parameters_against_method_schema`): used by `adjust_run` (6j) and future steering slices. Schemaless Method = SKIP validation. Once an operator started a Run on a schemaless Method, they carry full responsibility for steering it; the system does not second-guess at adjust time.

Both adapters live in `cora/run/aggregates/run/parameters_validation.py` and delegate to the shared values-validator at `cora/shared/json_schema_validation.py` (which dispatches on whether the caller supplied a `no_schema_message`). Pick STRICT for "operator hasn't proven they know what they're doing yet"; pick RELAXED for "operator already committed; respect their judgment."

## Rejections

A slice's behavioral contract has two halves: the events the decider emits on success, and the named exceptions it raises on failure. Both are first-class. When designing a new slice, enumerate the rejection list as a peer to the event list, not as an afterthought.

**Two domain families** plus three cross-cutting families and two infra families:

| Family | Naming | HTTP | Defined in |
| --- | --- | --- | --- |
| Validation | `Invalid<Aggregate><Field>Error(ValueError)` | 400 | `aggregates/<aggregate>/state.py` |
| Not found | `<Aggregate>NotFoundError` | 404 | `aggregates/<aggregate>/state.py` |
| Already exists | `<Aggregate>AlreadyExistsError` | 409 | `aggregates/<aggregate>/state.py` |
| State transition | `<Aggregate>Cannot<Verb>Error` | 409 | `aggregates/<aggregate>/state.py` |
| Authorization | `UnauthorizedError` | 403 | `cora/<bc>/errors.py` |
| Idempotency conflict | `IdempotencyConflictError` | 422 | `cora/infrastructure/ports/` |
| Cursor parse | `InvalidCursorError` | 422 | `cora/infrastructure/projection/` |

Existence vs state per the rule above: handler raises `<X>NotFoundError` (404) when an upstream aggregate is missing entirely; decider raises `<X>Cannot<Verb>Error` (409) when state forbids the transition. Same naming convention covers both single-stream and cross-aggregate slices.

**Decider docstrings carry an `Invariants:` block** listing each rejection inline with its exception name. This is the contract; downstream readers (test author, API consumer) shouldn't have to re-derive it from the body.

```python
def decide(state: Asset | None, command: AddAssetPort, *, now: datetime) -> list[AssetPortAdded]:
    """Decide the events produced by adding a port to an existing Asset.

    Invariants:
      - State must not be None (asset must exist) -> AssetNotFoundError
      - Asset must not be Decommissioned (lifecycle gate) -> AssetCannotAddPortError
      - Port name must not already exist (strict-not-idempotent) -> AssetCannotAddPortError
    """
```

**Central exception-to-status mapping** in each BC's `routes.py`. One handler per family, registered against a tuple of error classes via a loop. Adding a new error in a family is one tuple entry, not a new handler. Loop-collapse pattern is documented in the [`access/routes.py`](https://github.com/xmap/cora/blob/main/apps/api/src/cora/access/routes.py) module docstring; Equipment / Subject / Recipe / Run / Data / Decision / Trust mirror it.

```python
for cannot_transition_cls in (AssetCannotActivateError, AssetCannotDecommissionError, ...):
    app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
```

Routes do NOT wrap handler calls in try/except. Decider raises, central handler catches, FastAPI emits the JSON response. The response body is uniform: `{"detail": str(exc)}`.

**Cross-BC infra errors** (`ConcurrencyError`, `IdempotencyConflictError`, `IdempotencyClaimLostError`, `CachedHandlerError`, `InvalidCursorError`) are registered globally by the first-booted BC (Access). Other BCs do NOT re-register them; the JSON shape is the same regardless of which BC issued the error.

**Cross-BC domain errors** (BC X's slice raises BC Y's domain error via a cross-aggregate `load_*` port call) are registered ONLY by the owning BC. Examples: `recipe/routes.py` owns the HTTP mapping for `MethodNotFoundError` / `CapabilityNotFoundError` even when raised from `operation/features/register_procedure`'s handler; `decision/routes.py` owns `DecisionParentAgentMismatchError` / `DecisionParentRunMismatchError` even when raised from `agent/features/re_debrief_run`. FastAPI's `add_exception_handler` is app-scoped (last-wins); the architecture fitness `test_every_domain_error_registered_as_http_handler` only walks `cora.<bc>.aggregates.*.__all__`, so it does not require — and does not benefit from — a duplicate registration in the consumer BC. Each consumer BC's `routes.py` documents the non-registration with a comment near the existing handler-tuple loops.

**Boundary 422s via Pydantic** are NOT raised as domain errors. Required-field length / pattern / type checks (for example `reason: str = Field(min_length=1, max_length=500)`) live in the route's request model and surface as FastAPI's standard 422. When enumerating a slice's rejections at design time, list these as boundary cases (`boundary: Pydantic min_length on reason -> 422`) so the rejection list is exhaustive.
