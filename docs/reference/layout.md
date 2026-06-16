# Layout

*BC structure, imports, naming, bootstrap, shared code.*

Two axes on purpose: aggregates own the data shape so the domain stays explicit, slices own the use cases so a feature lives in one folder. Modular Monolith on the macro side, Vertical Slice on the micro. Keeping both stops the codebase from collapsing into either pure DDD or pure feature-folders.

## BC layout

Two-axis: aggregates own data shape; features (vertical slices) own use cases.

```
cora/<bc>/
├── __init__.py                       # re-exports public BC surface
├── _bootstrap.py                     # BC-internal constants
├── _projections.py                   # register_<bc>_projections(registry) entry point
├── _<aggregate>_update_handler.py    # update-handler factory hoist (when n>=3 update slices share scaffolding)
├── errors.py                         # BC-application-layer errors
├── routes.py                         # register_<bc>_routes(app)
├── tools.py                          # register_<bc>_tools(mcp, *, get_handlers)
├── wire.py                           # <Bc>Handlers bundle + wire_<bc>(deps)
├── aggregates/
│   └── <aggregate>/
│       ├── state.py                  # state + value objects + domain errors
│       ├── events.py                 # event classes + union + payload helpers
│       ├── evolver.py                # evolve(state, event) + fold(events)
│       ├── read.py                   # load_<aggregate> (fold-on-read)
│       └── <vo_module>.py            # aggregate-internal VOs (for example settings_validation, hazard_classification)
├── projections/
│   └── <name>.py                     # read-side projection (consumed by list_* queries)
└── features/
    ├── <verb>_<aggregate>/           # one folder per COMMAND
    │   ├── command.py
    │   ├── decider.py
    │   ├── handler.py
    │   ├── route.py
    │   ├── tool.py
    │   └── context.py                # OPTIONAL: cross-aggregate pre-load before pure decider
    ├── append_<entry>/               # entry-append variant (no decider; handler writes via per-category port)
    │   ├── command.py
    │   ├── handler.py
    │   ├── route.py
    │   └── tool.py
    └── get_<aggregate>/              # one folder per QUERY (no decider)
        ├── query.py
        ├── handler.py
        ├── route.py
        └── tool.py
```

Each slice's `__init__.py` re-exports its public surface so callers write `register_actor.bind(deps)`. Events live in the aggregate folder, not the slice: they're intrinsic facts about the aggregate's history.

Pairs Modular Monolith (BCs as macro-modules) with Vertical Slice (slices as micro-units). Aggregates stay explicit so the domain doesn't fragment into use cases.

### Three slice shapes

The slice-contract fitness function ([apps/api/tests/architecture/test_slice_contract.py](../../apps/api/tests/architecture/test_slice_contract.py)) recognises three shapes:

1. **Command slice**: `__init__, command, decider, handler, route, tool`. Default for state-changing operations that fold through a pure decider.
2. **Query slice**: `__init__, query, handler, route, tool`. No decider; reads from the aggregate or a projection.
3. **Entry-append slice** (`append_<entry>`): `__init__, command, handler, route, tool`. No decider; the handler writes directly to a typed entries store via a per-category port (`InferenceStore`, `ObservationStore`, `ActivityStore`). Today: `decision/append_inferences`, `run/append_observations`, `operation/append_activities`. New entry-append slices must be added to `_ENTRY_APPEND_SLICES` in the test.

### Optional slice files

- `context.py`: slice-local cross-aggregate pre-load. Used when a decider needs sibling-aggregate state (for example `start_run` pre-loads Asset, Method, Plan, Practice, Subject before calling the pure decider). Used by 38 slices today across `agent`, `campaign`, `caution`, `data`, `decision`, `equipment`, `operation`, `recipe`, `run`, `safety`, `subject`, `trust` (12 BCs). Lives in the slice folder, not the aggregate.

  The decider for a context-using slice takes a keyword-only `context: <X>Context` parameter immediately before `now`, where `<X>Context` is a frozen dataclass exported from the slice's `context.py` (for example `RunStartContext`, `ClearanceAmendmentContext`, `CautionSupersessionContext`). The handler builds the context by loading the sibling aggregates and passes it to the pure `decide`; the decider itself never reads from a port.

  **Signature-parity `_ = state` discard.** When a context-using decider's own aggregate state lives on the context (either the child is genesis, or `context.<aggregate>` carries the same state as `state`), the decider opens with `_ = state  # <reason>` to discard the parameter while keeping the signature aligned with single-stream deciders. Today: `regenerate_run_debrief`, `dismiss_event_in_reaction`, `add_run_to_campaign`, `remove_run_from_campaign`, `supersede_caution`, `amend_clearance`, `attach_asset_to_fixture`.

### BC-root extras

- `_projections.py`: composition-root entry point that registers the BC's projections with the projection registry. Mechanical and present in every BC that has a `projections/` directory.
- `_<aggregate>_update_handler.py`: factory that hoists shared update-handler scaffolding when n>=3 update slices on the same aggregate share the pattern (per `project_update_handler_pattern.md`). Today: 16 files across 11 BCs hosting 19 aggregate factories: `agent`, `campaign`, `equipment/{_asset,_frame,_mount}`, `operation/_procedure`, `recipe/{_method,_plan,_practice}`, `run`, `safety/{_clearance,_clearance_template}`, `subject`, `supply`, `trust`, plus `federation/_actor_update_handler.py`, which co-locates four factories (Actor / Permit / Credential / Seal) in one file (the lone exception to the one-file-per-aggregate norm).
- `_subscribers.py`: wires the BC's domain-event subscribers into the projection registry's subscriber bus. Today: `agent/_subscribers.py` (RunDebriefer + CautionDrafter) and `federation/_subscribers.py`. The pattern generalises to any BC that reacts to events from another BC.
- `_<aggregate>_dtos.py`: BC-local DTO module re-exported from `routes.py` and `tools.py`, kept out of the slice folder when several read/write slices share the same projected shape. Today: `calibration/_calibration_dtos.py`, `caution/_caution_dtos.py`, `safety/_clearance_dtos.py`, `federation/_federation_dtos.py`.
- `authorize_factory.py` (trust BC only): exports `build_authorize`, injected into the kernel by the composition root in `cora/api/main.py`. No other BC imports it.

### Private subpackages (BC-root reshape at scale)

Private `_*.py` modules stay flat at the BC root by default; the naming prefix (`_<aggregate>_<role>.py`) does the grouping. When a BC root crosses ~10 private modules and a cohesive cluster has emerged, carve that cluster into a private subpackage (`_<name>/` with a re-exporting `__init__.py`) so the root stays navigable (per `project_bc_root_layout.md`).

`equipment` is the first BC to cross the threshold (16 private modules) and the worked example:

- `equipment/_pidinst/` (`_types.py`, `_serializer.py`, `_response.py`): the PIDINST v1.0 subsystem (intermediate type tree, pure serializer, response DTOs).
- `equipment/_bodies/` (the `_*_body.py` wire DTOs): Pydantic request/response mirrors of value objects. Several are shared across aggregates (`Drawing`, `Placement`), so they cannot live in any one slice (slice independence forbids cross-slice imports); the shared home is the package.

Both re-export their public surface, so consumers import from the package (`from cora.equipment._pidinst import PidinstRecord`), not the submodules. The canonical shared-pattern files (`_bootstrap.py`, `_projections.py`, `_<aggregate>_update_handler.py`) stay flat for cross-BC consistency. Grouping the DTOs by aggregate was rejected: the shared VOs have no single aggregate owner, so per-aggregate files would force false ownership.

**Capability-dependent handlers.** When a slice depends on an external capability that may be unwired in some deployments (today: `regenerate_run_debrief` needs `kernel.llm`, which is `None` when `ANTHROPIC_API_KEY` isn't configured), the handler bundle types the field as `Handler | None`. The route guards on `None` and raises `HTTPException(503)` inline; this is the only documented exception to the "command-slice routes don't wrap handler calls" rule. Pinned by `test_route_no_inline_http_exception.py`'s `GRANDFATHERED_COMMAND_ROUTES` allowlist.

### Aggregate-internal shared modules

VOs and validation helpers consumed by the aggregate kernel **must live inside the aggregate folder**, not at the BC root. Tach treats `cora.<bc>.aggregates` and `cora.<bc>` as separate modules and the kernel cannot depend on the parent.

Examples: `equipment/aggregates/asset/settings_validation.py`, `recipe/aggregates/plan/{parameters_validation,wires_validation}.py`, `safety/aggregates/clearance/hazard_classification.py`. Feature slices import them via the longer path (`from cora.<bc>.aggregates.<aggregate>.<module> import ...`); the layering cost is paid by the consumer, not the kernel.

## Imports

Prefer **package imports** (re-exported from `__init__.py`) over submodule imports:

```python
# Preferred
from cora.access import register_actor, UnauthorizedError

# Avoid
from cora.access.features.register_actor.handler import Handler
```

The `__init__.py` is the BC's curated public surface; importing through it lets the layout reorganize without ripple edits. Submodule paths only when a symbol is intentionally not re-exported. Enforced by review.

## Naming

- **Commands**: PascalCase verb+noun in `command.py` (for example `RegisterActor`).
- **Define vs Register**: `Define<X>` for types/templates/configs (Zone, Conduit, Policy, Family: defined once, referenced as a contract). `Register<X>` for instances (Actor, Subject, Asset: recorded). Genesis event mirrors the verb (`<X>Defined` vs `<X>Registered`).
- **Queries**: PascalCase nouns in `query.py` (for example `GetActor`).
- **Decider**: pure `decide` in `decider.py`. Create-style: `decide(state, command, *, now, new_id)`. Update-style: `decide(state, command, *, now)`. Cross-aggregate-multi-stream slices (today: `add_run_to_campaign`, `remove_run_from_campaign`, `supersede_caution`, `start_run`, `amend_clearance`) return a frozen dataclass wrapping per-stream event lists (`MembershipEvents`, `AmendmentEvents`, `RunStartEvents`) instead of a single `list[<E>]`; the handler hands the named lists to `EventStore.append_streams` as one atomic batch.
- **Handler**: `bind(deps) -> Handler` in `handler.py`. Bare `Handler` is a `Protocol`; create/update slices that opt into idempotency also define `IdempotentHandler` (same shape + optional `idempotency_key`).
- **Domain errors**: PascalCase + `Error` suffix in the aggregate's `state.py` (for example `InvalidActorNameError`).
- **BC-application errors**: PascalCase + `Error` suffix in `cora/<bc>/errors.py` (for example `UnauthorizedError`). Each BC registers its own handler; same-named errors across BCs are distinct classes.
- **Domain events**: PascalCase past-tense in the aggregate's `events.py` (for example `ActorRegistered`). Same file holds the `<Aggregate>Event` discriminated union.

### Ports and adapters

A port is a `typing.Protocol` seam the domain depends on and an adapter implements.

- **Port class**: name it for its ROLE with a descriptive role noun (`EventStore`, `TokenVerifier`, `AssetLookup`, `IdGenerator`, `DoiMinter`, `EditionSerializer`, `RecipeExpander`). The role noun already signals the seam, so the generic `Port` suffix is redundant and is forbidden EXCEPT as an allowlisted carve-out, used only where stripping it leaves a bare verb, an abstract non-agent noun, or a value-object collision. Today's carve-outs: `ControlPort`, `SignaturePort` (would collide with the `Signature` value object), `PublishPort`, `PullPort`.
- **Port filename**: `snake_case(<PortClass>).py`, so the import path predicts the class (`event_store.py` -> `EventStore`, `signature_port.py` -> `SignaturePort`). A domain-named module whose stem omits a suffix the class keeps is the rejected shape.
- **Lookup-result DTO**: a `<X>Lookup` port returns a denormalized read-side row named `<X>LookupResult` (`AssetLookupResult`, `SupplyLookupResult`), never `<X>Reference`. The `Reference` suffix is reserved for genuine reference value objects (kept in `value_types.py` or under a domain name).
- **Location tier**: cross-BC ports at `cora/infrastructure/ports/`; BC-owned ports at `cora/<bc>/ports/` until a rule-of-three (3+ distinct BC consumers) promotes them; shared-kernel ports (adapter-free, 3+ consumers) at `cora/shared/ports/`.
- **Adapter class**: `<Tech><Role>` with no `Adapter` suffix (`PostgresEventStore`, `AnthropicLLM`, `InMemoryRecipeExpander`); the adapter prepends a tech token to the bare port role. File is `snake_case(<Tech><Role>).py`. BC-owned adapters live at `<bc>/adapters/`, cross-BC adapters at `infrastructure/adapters/`.
- **Import scope**: infra and shared ports import only stdlib, `typing`, and `cora.shared.*`. A BC-owned port may also import its OWN BC's aggregate value types (for example `EnclosureObserver` imports `EnclosurePermitStatus`), never another BC's internals.
- **Family subpackage**: a port family promotes to a subpackage with its own `errors.py` / `value_types.py` only when it carries a large shared catalog (federation: 4 ports + a 12-member error family + a value-type catalog). Below that bar, co-locate errors and value types in the port module (the `llm.py` / `control_port.py` shape).
- **`runtime_checkable`**: decorate a port iff an `isinstance` / `issubclass` check targets it (somewhere in src or tests); the decorator exists only to enable those checks. Enforced.
- **Injection**: a port reaches handlers by one of three paths -- a `Kernel` field (cross-BC primitives), `wire_<bc>(deps)` (BC-local ports built on `deps.pool` or route config), or the `published_artifact` orchestrator (the crypto / federation pipeline). A port absent from `Kernel` is not necessarily orphaned.
- Enforced by [test_port_naming_conventions.py](../../apps/api/tests/architecture/test_port_naming_conventions.py) (names) and [test_port_structure.py](../../apps/api/tests/architecture/test_port_structure.py) (frozen DTOs + `runtime_checkable` usage).

## Bootstrap

Constants every slice surface needs but that aren't slice-specific live in `cora/<bc>/_bootstrap.py`. Today: `SYSTEM_PRINCIPAL_ID`, canonically in `cora/infrastructure/routing.py`:

```python
# cora/access/_bootstrap.py
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
```

MCP tools import from `_bootstrap.py` (preserves per-BC naming); REST routes pull it indirectly via `get_principal_id`. The leading underscore signals BC-internal.

## Shared code

Don't extract until **three real usages with identical, stable logic** (Rule of Three). Shared primitives (errors, VOs across aggregates) live at the BC root or in `_shared/`. Cross-BC code is split into two homes, distinguished by the **purity test**:

- `cora/shared/`: modules with zero `cora.*` imports outside `cora.shared.*` itself. Pure value objects, NewType aliases, and validation helpers (Identifier VOs, identity NewTypes, bounded-text, canonical-JSON, JSON Schema). Adapter-free and side-effect-free.
- `cora/infrastructure/`: composition root, adapters, ports, event-sourcing machinery, cross-cutting concerns. Anything that depends on `ports/`, `kernel.py`, or external systems.

Layer direction: `BCs -> infrastructure -> shared`, plus `BCs -> shared` directly. `cora.shared` depends on nothing under `cora.*`. Pinned by [apps/api/tach.toml](../../apps/api/tach.toml) and architecture fitness tests.

### When the Rule of Three yields to local clarity

The 39 `aggregates/<aggregate>/read.py` files are 7-line near-clones that differ only in the stream-type constant and three import lines. Rule of Three was crossed long ago, but the duplication stays. A generic `load_aggregate(event_store, stream_type, from_stored, fold)` would save ~3 lines per call site at the cost of an extra parameter-passing chain: the caller still has to import the aggregate-specific `from_stored` / `fold` to pass them in. The wrappers are mechanical, stable, and locally legible: opening `aggregates/<aggregate>/read.py` shows the entire fold-on-read path for that aggregate without a hop. Each additional aggregate doesn't change the answer.

The same posture applies to other "mechanical near-clones" surfaces (per-aggregate `events.py` `event_type_name` / `to_payload` / `from_stored`, evolver `fold` walker): per-aggregate locality wins over a generic helper that wouldn't actually shrink the call sites.
