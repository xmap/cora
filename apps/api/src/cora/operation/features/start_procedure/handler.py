"""Application handler for the `start_procedure` slice.

Update-style handler with a custom body (NOT the update-handler
factory): the start_procedure flow pre-loads the target Assets and
(for Phase-of-Run Procedures) the parent Run's Method.needed_supplies
satisfaction to build a `ProcedureStartContext` for the decider's
Decommissioned + Supply gates. The factory at
`cora.infrastructure.update_handler` doesn't support cross-aggregate
context loads; same reason `start_run`'s handler is custom.

## Pre-load order

1. `load_procedure(procedure_id)` -> if None, `ProcedureNotFoundError`
2. For each `asset_id` in `procedure.target_asset_ids`:
   `load_asset(asset_id)` -> if None, `AssetNotFoundError` (Equipment-
   BC error, globally registered as 404 by Equipment's routes.py)
3. If `state.parent_run_id is not None` (Phase-of-Run), resolve the
   parent's needs chain: `load_run -> load_plan -> load_practice ->
   load_method`. Then if `method.needed_supplies` is non-empty,
   invoke `deps.supply_lookup.find_supplies_by_kind(...)` and thread
   the satisfaction map into the context. Standalone Procedures (no
   parent_run_id) skip this entire chain; Capability-level
   needed_supplies is a Watch item per
   [[project_supply_preflight_gate_design]].

Loads run sequentially; could be optimized to async-gather later but
not the bottleneck at MVP scale (target_asset_ids is small for any
realistic procedure: typically 1-5).

## What's NOT pre-loaded

Decision (Decision BC integration deferred). Documented as known gap.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny, SupplyLookupResult
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import (
    ProcedureNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.context import ProcedureStartContext
from cora.operation.features.start_procedure.decider import decide
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.plan import PlanNotFoundError, load_plan
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.run.aggregates.run import RunNotFoundError, load_run

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "StartProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare start_procedure handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: StartProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """start_procedure handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: StartProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_procedure handler closed over the shared deps."""

    async def handler(
        command: StartProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "start_procedure.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "start_procedure.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.procedure_id)
        state = fold([from_stored(s) for s in stored])
        if state is None:
            raise ProcedureNotFoundError(command.procedure_id)

        assets: dict[UUID, Asset] = {}
        for asset_id in sorted(state.target_asset_ids, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        # cross-BC Enclosure pre-flight gate per
        # [[project_enclosure_stage1_design]]: each Asset in scope declares
        # the Enclosure (access-gated volume) it is located in via
        # `located_in_enclosure_id`; the gate collects those across the
        # widened scope and fetches their permit status by id. Scope is
        # `target_asset_ids` AND each Asset's `controller_id` back-
        # reference, mirroring Run's scope expansion so a Procedure
        # targeting a stage whose controller sits in its own Enclosure
        # honors that gate too. Per L-pre-1 (always-derive-from-Asset-
        # chain), the Procedure does NOT declare an explicit needed-
        # enclosure list; the located-in chain IS the declaration. Empty
        # set is Permit-by-default. The decider partitions each row on
        # `permit_status == "Permitted" AND lifecycle == "Active"`.
        # Facility-envelope Procedures (empty target_asset_ids) pass with
        # an empty scope and the gate trivially passes.
        scoped_asset_ids: frozenset[UUID] = state.target_asset_ids | frozenset(
            asset.controller_id for asset in assets.values() if asset.controller_id is not None
        )

        # cross-BC ancestor-chain widening (chain-walk Slice 6, mirrors
        # start_run Slice 5): widen the scope up the Asset parent_id
        # chain so an Enclosure bound to an ANCESTOR of a target Asset
        # gates this Procedure. Without this, the enclosure pre-flight
        # gate's L-pre-1 "derive scope from the Asset chain" is
        # decorative on the Procedure path: an Enclosure bound to the
        # beamline Unit never matches a Procedure targeting only a Device
        # under it. The walk returns the inclusive closure and EVERY
        # ancestor enters the scope regardless of its own lifecycle: the
        # containing Asset's lifecycle is the wrong source of truth for
        # whether a physical interlock is live. The Enclosure gate's
        # source of truth is the ENCLOSURE's own lifecycle
        # (`find_by_ids` returns only Active Enclosures; the decider
        # fails any non-(Permitted-and-Active) row), so a retired
        # Enclosure is dropped at the right layer while an
        # Active+NotPermitted Enclosure on a Decommissioned ancestor Asset
        # still correctly REFUSES the Procedure (decommission_asset has no
        # Enclosure cascade; filtering Decommissioned ancestors here would
        # silently suppress that interlock). The walk reads only
        # Equipment's Asset projection, terminates at the facility-rooted
        # root (never the Federation Facility axis), and raises
        # AncestorWalkDepthExceededError on a parent_id cycle / over-deep
        # chain rather than under-scoping the gate; that error is left
        # intentionally unmapped (a 500: data corruption, not client-
        # fixable). The Procedure path widens only the Enclosure gate (it
        # has no clearance / caution lookups); start_run additionally
        # feeds the same widened scope to those two.
        ancestor_rows = await deps.asset_lookup.ancestors_of(scoped_asset_ids)
        scoped_asset_ids = scoped_asset_ids | frozenset(row.id for row in ancestor_rows)

        located_in_enclosure_ids = frozenset(
            row.located_in_enclosure_id
            for row in ancestor_rows
            if row.located_in_enclosure_id is not None
        )
        referencing_enclosures = tuple(
            await deps.enclosure_lookup.find_by_ids(enclosure_ids=located_in_enclosure_ids)
        )

        # cross-BC Supply preflight per
        # [[project_supply_preflight_gate_design]]: for Phase-of-Run
        # Procedures, resolve parent_run_id -> Run -> Plan -> Practice
        # -> Method, then load the satisfaction snapshot for
        # method.needed_supplies. Standalone Procedures (no
        # parent_run_id) pass the gate trivially with an empty
        # snapshot. Capability-level needed_supplies for standalone
        # Procedures is a Watch item.
        needed_supplies_snapshot: frozenset[str] = frozenset()
        needed_supplies_satisfaction: dict[str, tuple[SupplyLookupResult, ...]] = {}
        if state.parent_run_id is not None:
            # Strict load chain (mirrors start_run.handler): a missing
            # aggregate anywhere in parent_run -> plan -> practice ->
            # method is corruption, not a happy path. Raise rather
            # than silently bypass the Supply gate.
            parent_run = await load_run(deps.event_store, state.parent_run_id)
            if parent_run is None:
                raise RunNotFoundError(state.parent_run_id)
            plan = await load_plan(deps.event_store, parent_run.plan_id)
            if plan is None:
                raise PlanNotFoundError(parent_run.plan_id)
            practice = await load_practice(deps.event_store, plan.practice_id)
            if practice is None:
                raise PracticeNotFoundError(plan.practice_id)
            method = await load_method(deps.event_store, practice.method_id)
            if method is None:
                raise MethodNotFoundError(practice.method_id)
            if method.needed_supplies:
                needed_supplies_snapshot = method.needed_supplies
                satisfaction = await deps.supply_lookup.find_supplies_by_kind(
                    kinds=method.needed_supplies,
                )
                needed_supplies_satisfaction = {
                    kind: tuple(refs) for kind, refs in satisfaction.items()
                }

        # BEAM-1 cross-BC beam-availability pre-flight read (mirror of
        # start_run): ask the injected lookup for the live shutter +
        # FES-permit state at the start instant. The default Kernel
        # lookup (AllBeamOpenLookup) returns all-open so the decider's
        # beam gate passes trivially; the production ControlPort-backed
        # adapter reads the configured PVs live and fails closed on a
        # bad read.
        beam_availability = await deps.beam_availability_lookup.read_beam_availability()

        context = ProcedureStartContext(
            assets=assets,
            needed_supplies_satisfaction=needed_supplies_satisfaction,
            referencing_enclosures=referencing_enclosures,
            beam_availability=beam_availability,
        )

        now = deps.clock.now()
        domain_events = decide(
            state=state,
            command=command,
            context=context,
            needed_supplies_snapshot=needed_supplies_snapshot,
            now=now,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.procedure_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "start_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            target_asset_count=len(assets),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
