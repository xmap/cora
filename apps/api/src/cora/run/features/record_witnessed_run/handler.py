"""Application handler for the `record_witnessed_run` slice: the witnessed genesis.

Trimmed sibling of `start_run/handler.py`'s pre-load + scope-widening +
cross-BC lookup sequence (Plan -> Practice -> Method -> Assets -> Subject,
then controller + ancestor-chain widening, then clearance / enclosure /
caution / supply / beam reads). This is a second, independent copy rather
than a shared helper: hoisting the assembly is worth doing once a third
caller creates a genuine rule-of-three pressure, which this slice does not
yet justify on its own (see the commit history for the reasoning).

Not wrapped in `with_idempotency`: the Run id is fresh and random per
call, so there is no retry key to collapse against. Dedup against a
repeated substrate observation (the PV re-reporting the same capture's
begin) is the RunTranslator runtime's own edge-triggered state, not this
handler's concern.

Per the roadmap's anti-scope: no REST route, no MCP tool reach this
handler (see `route.py` / `tool.py`, both stubs). The authorized path in
is the bound handler on `RunHandlers.record_witnessed_run`, called only by
the in-process RunTranslator runtime as a seeded Agent principal.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny, SupplyLookupResult
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.plan import PlanNotFoundError, load_plan
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.run.aggregates.run import event_type_name, to_payload
from cora.run.errors import UnauthorizedError
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run.context import RunWitnessedStartContext
from cora.run.features.record_witnessed_run.decider import decide
from cora.shared.json_merge_patch import merge_patch
from cora.subject.aggregates.subject import SubjectNotFoundError, load_subject

_STREAM_TYPE = "Run"
_COMMAND_NAME = "RecordWitnessedRun"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every record_witnessed_run handler implements."""

    async def __call__(
        self,
        command: RecordWitnessedRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a record_witnessed_run handler closed over the shared deps."""

    async def handler(
        command: RecordWitnessedRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "record_witnessed_run.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            capture_code=command.capture_code,
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
                "record_witnessed_run.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        plan = await load_plan(deps.event_store, command.plan_id)
        if plan is None:
            raise PlanNotFoundError(command.plan_id)

        practice = await load_practice(deps.event_store, plan.practice_id)
        if practice is None:
            raise PracticeNotFoundError(plan.practice_id)

        method = await load_method(deps.event_store, practice.method_id)
        if method is None:
            raise MethodNotFoundError(practice.method_id)

        assets: dict[UUID, Asset] = {}
        for asset_id in sorted(plan.asset_ids, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        subject = None
        if command.subject_id is not None:
            subject = await load_subject(deps.event_store, command.subject_id)
            if subject is None:
                raise SubjectNotFoundError(command.subject_id)

        new_id = deps.id_generator.new_id()

        # Same controller + ancestor-chain widening as start_run/handler.py:
        # see that module's docstring comment for the full rationale.
        scoped_asset_ids = plan.asset_ids | {
            asset.controller_id for asset in assets.values() if asset.controller_id is not None
        }
        ancestor_rows = await deps.asset_lookup.ancestors_of(scoped_asset_ids)
        scoped_asset_ids = scoped_asset_ids | {row.id for row in ancestor_rows}

        referencing_clearances = tuple(
            await deps.clearance_lookup.find_covering(
                run_id=new_id,
                subject_id=command.subject_id,
                asset_ids=scoped_asset_ids,
            )
        )

        located_in_enclosure_ids = frozenset(
            row.located_in_enclosure_id
            for row in ancestor_rows
            if row.located_in_enclosure_id is not None
        )
        referencing_enclosures = tuple(
            await deps.enclosure_lookup.find_by_ids(enclosure_ids=located_in_enclosure_ids)
        )

        active_cautions = tuple(
            await deps.caution_lookup.find_active_in_scope(
                asset_ids=scoped_asset_ids,
                procedure_ids=frozenset(),
            )
        )

        needed_supplies_satisfaction: dict[str, tuple[SupplyLookupResult, ...]] = {}
        if method.needed_supplies:
            satisfaction = await deps.supply_lookup.find_supplies_by_kind(
                kinds=method.needed_supplies,
            )
            needed_supplies_satisfaction = {
                kind: tuple(refs) for kind, refs in satisfaction.items()
            }

        # Same BEAM-1 read as start_run/handler.py. Witnessed here, not
        # enforced: the decider's witness_safety_envelope records this
        # reading on the emitted RunStarted rather than gating on it.
        beam_availability = await deps.beam_availability_lookup.read()

        context = RunWitnessedStartContext(
            plan=plan,
            subject=subject,
            assets=assets,
            referencing_clearances=referencing_clearances,
            active_cautions=active_cautions,
            needed_supplies_satisfaction=needed_supplies_satisfaction,
            referencing_enclosures=referencing_enclosures,
            beam_availability=beam_availability,
        )

        now = deps.clock.now()

        # No override_parameters on this command: the Plan's own defaults
        # govern, unmodified. merge_patch against an empty patch is the
        # identity operation, kept for symmetry with start_run's merge so
        # the Method schema validation sees the same shape either path.
        effective_parameters = merge_patch(plan.default_parameters, {})

        run_decision = decide(
            state=None,
            command=command,
            context=context,
            needed_family_ids_snapshot=method.needed_family_ids,
            needed_supplies_snapshot=method.needed_supplies,
            effective_parameters=effective_parameters,
            method_parameters_schema=method.parameters_schema,
            now=now,
            new_id=new_id,
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
            for event in run_decision.run_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "record_witnessed_run.success",
            command_name=_COMMAND_NAME,
            run_id=str(new_id),
            plan_id=str(command.plan_id),
            capture_code=command.capture_code,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
