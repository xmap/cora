"""Compose the Operation BC's handlers from `Kernel`.

`wire_operation(deps)` is invoked once from the FastAPI lifespan and
the returned `OperationHandlers` bundle is stored on
`app.state.operation`. Routes and MCP tools pull their handler out
of that bundle. New slices add a new field on `OperationHandlers`
and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Recipe / Run / Data / Decision / Supply
(composition order matters -- innermost first):

1. `bind(deps)` -- bare handler.
2. `with_idempotency` (create-style commands only) -- Idempotency-Key
   support. Transition handlers (start / complete / abort) do NOT
   idempotency-wrap: they're update-style, strict-not-idempotent at
   the decider, and naturally guarded by event-store optimistic
   concurrency. Same convention as Run BC and Supply BC.
3. `with_tracing` -- OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

## Wired handlers

  - `register_procedure` (create-style; idempotency-wrapped)
  - `start_procedure` (transition; pre-loads target Assets)
  - `complete_procedure` (transition; via `make_procedure_update_handler` factory)
  - `abort_procedure` (transition; via factory)
  - `truncate_procedure` (transition; via factory; partial-data terminal)
  - `append_activities` (entry-shape; lazy-open + batch append)
  - `get_procedure` (query; fold-on-read)
  - `list_procedures` (query; reads from `proj_operation_procedure_summary`)

## Make_procedure_update_handler factory (rule-of-three hoist)

`complete_procedure` + `abort_procedure` + `truncate_procedure` all
use `cora.operation._procedure_update_handler.make_procedure_update_handler`
under the hood. The factory landed at the rule-of-three trigger
when truncate_procedure became the third update slice; mirrors
`_supply_update_handler` (Supply BC's hoist after 5 transitions) and
Run BC's `_update_handler.make_run_update_handler`.

## BC-internal ActivityStore wiring (mirrors Run BC's ObservationStore)

The `append_activities` slice needs a `ActivityStore` adapter.
Per the per-category-writer pattern locked at gate-review L8/L9
(Conduit's VerdictStore), the store is built LOCALLY here
from `deps.pool` (Postgres in production) or as
`InMemoryActivityStore` in `app_env=test`. NOT promoted to Kernel fields.
Mirrors how Run BC wires its ObservationStore and Decision BC wires its
InferenceStore.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.operation.acquisitions import collect, continuous, discrete
from cora.operation.adapters.control_port_config import build_control_port
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.aggregates.procedure import (
    ActivityStore,
    InMemoryActivityStore,
    PostgresActivityStore,
)
from cora.operation.conductor import Conductor, InMemoryActionRegistry
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    conduct_procedure,
    end_iteration,
    get_procedure,
    list_procedure_iterations,
    list_procedures,
    register_procedure,
    register_procedure_from_recipe,
    start_iteration,
    start_procedure,
    truncate_procedure,
)
from cora.operation.ports.control_port import ControlPort

_BC = "operation"


@dataclass(frozen=True)
class OperationHandlers:
    """The Operation BC's handler bundle, each closed over Kernel.

    Initial slices: register_procedure + get_procedure. Three FSM-
    closure transitions follow (start / complete / abort). The
    entry-shape append_activities slice arrives next (with
    BC-internal ActivityStore adapter for the per-step logbook).
    """

    register_procedure: register_procedure.IdempotentHandler
    register_procedure_from_recipe: register_procedure_from_recipe.IdempotentHandler
    start_procedure: start_procedure.Handler
    complete_procedure: complete_procedure.Handler
    abort_procedure: abort_procedure.Handler
    truncate_procedure: truncate_procedure.Handler
    start_iteration: start_iteration.Handler
    end_iteration: end_iteration.Handler
    append_activities: append_activities.Handler
    get_procedure: get_procedure.Handler
    list_procedures: list_procedures.Handler
    list_procedure_iterations: list_procedure_iterations.Handler
    conduct_procedure: conduct_procedure.Handler
    control_port: ControlPort
    """The ControlPort the Conductor talks to. Surfaced on the bundle
    so the FastAPI lifespan's teardown can call `aclose()` on it
    before the kernel pool closes - registry-routed deployments hold
    OS-level resources (aioca broadcaster, p4p Context) that must be
    released on hot-reload + test-process restart."""


def wire_operation(deps: Kernel) -> OperationHandlers:
    """Build the Operation BC handlers from shared dependencies.

    Note on the conduct_procedure / Conductor wire-up: the Conductor needs
    the FINAL (post-tracing) versions of start / complete / abort /
    append_activities so its internal calls land with the same
    observability shape as direct REST / MCP calls. We hoist those
    four bindings into locals, build the Conductor, then assemble
    the bundle. The ControlPort is materialised from
    `deps.settings.control_port_routes` via `build_control_port`:
    empty routes (the default) returns `InMemoryControlPort` (legacy
    + test convenience); populated routes returns a
    `ControlPortRegistry` with the configured substrate adapters per
    prefix. The action registry is hand-seeded with the three
    substrate-neutral scan-acquisition primitives `collect` +
    `discrete` + `continuous`. Per-deployment registry-from-config
    plumbing remains deferred.
    """
    step_store: ActivityStore = (
        PostgresActivityStore(deps.pool) if deps.pool is not None else InMemoryActivityStore()
    )
    # Recipe expansion port: default pure adapter. Per the design memo
    # ([[project-recipe-aggregate-design]] Locks), the port is
    # 2-arg pure substitution; future deployment-specific expanders
    # implement the same Protocol and bump `version` to invalidate
    # cached expansions on substantive semantic changes.
    # The PseudoAxis-aware widening threads a second method
    # `expand_pseudoaxis` onto the port; the default in-memory adapter
    # pins `version="v2-pseudoaxis-aware"` and ships with the wiring-
    # deferred `constituent_resolver`. The Plan.wiring-backed
    # constituent resolver is deferred to a follow-up slice; until
    # then any `pseudoaxis://` SetpointStep at conduct time is rejected
    # with `PartitionRuleNotFoundError` (HTTP 409) so the routing-
    # layer status mapping surfaces the deferral cleanly.
    recipe_expander = InMemoryRecipeExpander()
    start_handler = with_tracing(
        start_procedure.bind(deps),
        command_name="StartProcedure",
        bc=_BC,
    )
    complete_handler = with_tracing(
        complete_procedure.bind(deps),
        command_name="CompleteProcedure",
        bc=_BC,
    )
    abort_handler = with_tracing(
        abort_procedure.bind(deps),
        command_name="AbortProcedure",
        bc=_BC,
    )
    append_step_handler = with_tracing(
        append_activities.bind(deps, step_store=step_store),
        command_name="AppendProcedureActivities",
        bc=_BC,
    )
    control_port = build_control_port(deps.settings.control_port_routes)
    action_registry = InMemoryActionRegistry(
        {"collect": collect, "discrete": discrete, "continuous": continuous}
    )
    conductor = Conductor(
        control_port=control_port,
        append_step=append_step_handler,
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=action_registry,
        start_procedure=start_handler,
        complete_procedure=complete_handler,
        abort_procedure=abort_handler,
    )
    return OperationHandlers(
        register_procedure=with_tracing(
            with_idempotency(
                register_procedure.bind(deps),
                deps.idempotency_store,
                command_name="RegisterProcedure",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterProcedure",
            bc=_BC,
        ),
        register_procedure_from_recipe=with_tracing(
            with_idempotency(
                register_procedure_from_recipe.bind(deps, expansion_port=recipe_expander),
                deps.idempotency_store,
                command_name="RegisterProcedureFromRecipe",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterProcedureFromRecipe",
            bc=_BC,
        ),
        start_procedure=start_handler,
        complete_procedure=complete_handler,
        abort_procedure=abort_handler,
        truncate_procedure=with_tracing(
            truncate_procedure.bind(deps),
            command_name="TruncateProcedure",
            bc=_BC,
        ),
        start_iteration=with_tracing(
            start_iteration.bind(deps),
            command_name="StartProcedureIteration",
            bc=_BC,
        ),
        end_iteration=with_tracing(
            end_iteration.bind(deps),
            command_name="EndProcedureIteration",
            bc=_BC,
        ),
        append_activities=append_step_handler,
        get_procedure=with_tracing(
            get_procedure.bind(deps),
            command_name="GetProcedure",
            bc=_BC,
            kind="query",
        ),
        list_procedures=with_tracing(
            list_procedures.bind(deps),
            command_name="ListProcedures",
            bc=_BC,
            kind="query",
        ),
        list_procedure_iterations=with_tracing(
            list_procedure_iterations.bind(deps),
            command_name="ListProcedureIterations",
            bc=_BC,
            kind="query",
        ),
        conduct_procedure=with_tracing(
            conduct_procedure.bind(deps, conductor=conductor, expansion_port=recipe_expander),
            command_name="ConductProcedure",
            bc=_BC,
        ),
        control_port=control_port,
    )
