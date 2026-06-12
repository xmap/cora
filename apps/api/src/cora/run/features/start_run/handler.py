"""Application handler for the `start_run` slice.

Eleventh instance of the create-style template body, second instance
that pre-loads upstream aggregate state (after `define_plan` in
6e-1). Per gate-review Q2 / Q5, this is the canonical pattern for
cross-aggregate validation in CORA.

## Pre-load order (Plan → Method via Practice → each bound Asset → Subject?)

1. `load_plan(plan_id)` → if None, `PlanNotFoundError`
2. `load_practice(plan.practice_id)` → if None, `PracticeNotFoundError`
   (defensive — Plan was bound against a real Practice; if Practice
   has somehow disappeared from the stream, that's serious corruption)
3. `load_method(practice.method_id)` → if None, `MethodNotFoundError`
4. For each `asset_id` in `plan.asset_ids`: `load_asset(asset_id)`
   → if None, `AssetNotFoundError` (Equipment-BC error, globally
   registered as 404 by Equipment's routes.py)
5. If `command.subject_id is not None`: `load_subject(subject_id)`
   → if None, `SubjectNotFoundError`

Loads run sequentially; could be optimized to async-gather later
but not the bottleneck at MVP scale.

The handler resolves `needed_family_ids` from the loaded Method
and passes it to the decider as a plain frozenset (so the decider
doesn't need a Method reference; cleaner separation). Decider
re-validates the capability superset against current Asset state
(gate-review Q5).

## What's NOT pre-loaded

Decision (Decision BC not shipped) — documented gate-review Q3 gap.
Lands when Decision BC ships.

## Supply satisfaction pre-load

If `method.needed_supplies` is non-empty, the handler invokes
`deps.supply_lookup.find_supplies_by_kind(kinds=method.needed_supplies)`
to get every non-Decommissioned Supply per kind, and threads the
mapping into `RunStartContext.needed_supplies_satisfaction`. The
decider gates on at-least-one-AVAILABLE per kind per
[[project_supply_preflight_gate_design]]. Empty needed_supplies
short-circuits: no port call, decider sees empty satisfaction map,
gate trivially passes.

## Atomic co-write when started into a campaign

If `command.campaign_id` is set, the new Run's genesis events AND the
Campaign's `CampaignRunAdded` membership event are committed in ONE
Postgres transaction via `EventStore.append_streams` (Run stream +
Campaign stream). All-or-nothing: either both streams commit or a
`ConcurrencyError` rolls back the whole batch, so a Run can never exist
referencing a campaign that never recorded the membership (and vice
versa). Started without a campaign, the handler takes the ordinary
single-stream `append` path. See [[project_cross_bc_atomic_writes]].
"""

from typing import Protocol
from uuid import UUID

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    load_campaign,
)
from cora.campaign.aggregates.campaign import (
    event_type_name as campaign_event_type_name,
)
from cora.campaign.aggregates.campaign import (
    to_payload as campaign_to_payload,
)
from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny, SupplyLookupResult
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.plan import PlanNotFoundError, load_plan
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.run.aggregates.run import event_type_name, to_payload
from cora.run.errors import UnauthorizedError
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.context import RunStartContext
from cora.run.features.start_run.decider import decide
from cora.shared.json_merge_patch import merge_patch
from cora.subject.aggregates.subject import SubjectNotFoundError, load_subject

_STREAM_TYPE = "Run"
_CAMPAIGN_STREAM_TYPE = "Campaign"
_COMMAND_NAME = "StartRun"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare start_run handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.
    """

    async def __call__(
        self,
        command: StartRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """start_run handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: StartRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_run handler closed over the shared deps."""

    async def handler(
        command: StartRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "start_run.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            subject_id=str(command.subject_id) if command.subject_id is not None else None,
            raid=command.raid,
            override_key_count=len(command.override_parameters),
            trigger_source=command.trigger_source,
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
                "start_run.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load cross-aggregate context (gate-review Q2 / Q5 pattern).
        plan = await load_plan(deps.event_store, command.plan_id)
        if plan is None:
            raise PlanNotFoundError(command.plan_id)

        practice = await load_practice(deps.event_store, plan.practice_id)
        if practice is None:
            # Defensive: Plan was bound against a real Practice; if
            # Practice has disappeared from the stream, that's serious
            # corruption. Surface as PracticeNotFoundError → 404.
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

        # if the caller wants the Run to land as a Campaign
        # member at start time, pre-load the Campaign + its stream
        # version. The decider gates on Campaign status; the handler
        # writes the inverse CampaignRunAdded event to the Campaign
        # stream atomically with RunStarted on the Run stream via
        # EventStore.append_streams.
        campaign = None
        campaign_version = 0
        if command.campaign_id is not None:
            campaign = await load_campaign(deps.event_store, command.campaign_id)
            if campaign is None:
                raise CampaignNotFoundError(command.campaign_id)
            _, campaign_version = await deps.event_store.load(
                _CAMPAIGN_STREAM_TYPE, command.campaign_id
            )

        # Allocate the new Run id BEFORE the clearance lookup so the
        # Safety projection query can match Clearances bound to this
        # specific Run id (RunBinding coverage). The same id flows
        # into the decider + the genesis event.
        new_id = deps.id_generator.new_id()

        # Cross-BC scope expansion: when an Asset carries a
        # `controller_id` back-reference to its drive-electronics
        # controller (per the controller-as-Asset design), a Caution
        # or Clearance targeted at the controller is operationally
        # relevant to every Plan that targets a driven stage. The
        # lookup ports query `target_id = ANY(asset_ids)`; without
        # expansion, controller-scoped warnings stay invisible to
        # Plans that target only the stage. Expand once here so both
        # downstream lookups see the same Run scope. Already-loaded
        # Assets are in `assets`; observation `controller_id` is free.
        # `controller_id` (one-hop) is expanded here; the `parent_id`
        # ancestor chain is expanded just below via the chain walk;
        # `fixture_id` traversal is left as a separate design call.
        #
        # Snapshot-vs-gate asymmetry: the controller Asset itself is
        # NOT loaded into `assets` (only Plan-bound stage Assets are),
        # so a Decommissioned controller silently passes the
        # `RunPlanAssetDecommissionedError` lifecycle gate above while
        # its Cautions and Clearances still surface through the
        # widened scope. Intentional. Snapshot semantics (Caution
        # warn, Clearance authorize) widen freely; lifecycle gating
        # stays anchored to Plan-bound Assets, with the stage's
        # lifecycle the right gate for stage-targeting Plans.
        scoped_asset_ids = plan.asset_ids | {
            asset.controller_id for asset in assets.values() if asset.controller_id is not None
        }

        # cross-BC ancestor-chain widening (chain-walk Slice 5): widen
        # the scope up the Asset `parent_id` chain so an Enclosure,
        # Clearance, or Caution bound to an ANCESTOR of a Plan-bound
        # Asset gates / warns this Run. Without this, the enclosure
        # pre-flight gate's L-pre-1 "derive scope from the Asset chain"
        # is decorative: an Enclosure bound to the 2-BM beamline Unit
        # never matches a Plan that binds only a Device under it. The
        # walk returns the inclusive ancestor closure (the inputs plus
        # every ancestor), and EVERY ancestor enters the scope regardless
        # of its own lifecycle. We deliberately do NOT filter ancestors
        # on `lifecycle`: the containing Asset's lifecycle is the wrong
        # source of truth for whether a physical interlock is live. Each
        # downstream gate owns its own lifecycle semantics on the widened
        # scope. For the safety-critical Enclosure gate that source of
        # truth is the ENCLOSURE's own lifecycle: `find_for_assets`
        # returns only Active Enclosures and the decider fails any
        # non-(Permitted-and-Active) row, so a retired Enclosure is
        # dropped at the right layer while an Active+NotPermitted
        # Enclosure on a Decommissioned ancestor Asset still correctly
        # REFUSES the Run (a Decommissioned containing Asset does not
        # retire its interlock; decommission_asset has no Enclosure
        # cascade). Filtering Decommissioned ancestors here instead would
        # silently suppress that Enclosure and admit the Run into an
        # un-permitted hutch. Plan-bound Assets keep their own
        # `RunPlanAssetDecommissionedError` gate above. The walk reads
        # only Equipment's Asset projection and terminates at the
        # facility-rooted root, never the Federation Facility axis; a
        # `parent_id` cycle or an over-deep chain raises
        # `AncestorWalkDepthExceededError` rather than under-scoping the
        # gate (failing loud beats admitting a Run an unreached ancestor's
        # Enclosure should refuse). That error is left intentionally
        # unmapped at the route layer: a parent_id cycle is server-side
        # data corruption, not a client-fixable request, so a 500 (with
        # the stack trace in the server log) is the right operator signal,
        # not a 4xx the caller could retry.
        ancestor_rows = await deps.asset_lookup.ancestors_of(scoped_asset_ids)
        scoped_asset_ids = scoped_asset_ids | {row.id for row in ancestor_rows}

        # cross-BC clearance gate: query Safety's
        # clearance projection for every clearance whose bindings
        # reference this Run's scope. Decider partitions on Active.
        referencing_clearances = tuple(
            await deps.clearance_lookup.find_referencing_run(
                run_id=new_id,
                subject_id=command.subject_id,
                asset_ids=scoped_asset_ids,
            )
        )

        # cross-BC enclosure pre-flight gate per
        # [[project_enclosure_stage1_design]]: derive the set of
        # referencing Enclosures from `scoped_asset_ids` via
        # `EnclosureLookup.find_for_assets`. Per L-pre-1 (always-
        # derive-from-Asset-chain), the Method does NOT declare an
        # explicit needed-enclosure list; the chain IS the declaration.
        # Empty result is Permit-by-default (no Enclosure binds any
        # bound Asset). The decider partitions each row on
        # `permit_status == "Permitted" AND lifecycle == "Active"`.
        referencing_enclosures = tuple(
            await deps.enclosure_lookup.find_for_assets(asset_ids=scoped_asset_ids)
        )

        # cross-BC caution snapshot: query the Caution
        # projection for Active cautions referencing the Run's scope.
        # NON-BLOCKING by construction (anti-pattern #5: cautions
        # WARN, never BLOCK; that authority belongs to Safety BC
        # Clearance). The decider only embeds the snapshot in the
        # RunStarted event payload (anti-pattern #7: ack lives on the
        # consumption event, not per-operator on the Caution
        # aggregate). `procedure_ids=frozenset()` because a Run has
        # no Procedure scope today; forward-compat for procedure-
        # driven runs (Watch item for the start_procedure consumer).
        active_cautions = tuple(
            await deps.caution_lookup.find_active_for_run(
                asset_ids=scoped_asset_ids,
                procedure_ids=frozenset(),
            )
        )

        # cross-BC Supply satisfaction snapshot per
        # [[project_supply_preflight_gate_design]]: for every kind in
        # Method.needed_supplies, load every non-Decommissioned Supply
        # so the decider can gate on at-least-one-AVAILABLE per kind.
        # Empty needed_supplies short-circuits the port call.
        needed_supplies_satisfaction: dict[str, tuple[SupplyLookupResult, ...]] = {}
        if method.needed_supplies:
            satisfaction = await deps.supply_lookup.find_supplies_by_kind(
                kinds=method.needed_supplies,
            )
            needed_supplies_satisfaction = {
                kind: tuple(refs) for kind, refs in satisfaction.items()
            }

        context = RunStartContext(
            plan=plan,
            subject=subject,
            assets=assets,
            referencing_clearances=referencing_clearances,
            active_cautions=active_cautions,
            needed_supplies_satisfaction=needed_supplies_satisfaction,
            referencing_enclosures=referencing_enclosures,
            campaign=campaign,
        )

        now = deps.clock.now()

        # 6g-c: resolve effective_parameters by merging Plan defaults
        # with the command's overrides (RFC 7396). The merged dict is
        # what governs this Run; it gets validated against the
        # Method's parameters_schema by the decider.
        effective_parameters = merge_patch(plan.default_parameters, command.override_parameters)

        decision = decide(
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
            for event in decision.run_events
        ]

        if decision.campaign_events:
            # cross-aggregate atomic write. The decider built
            # both event lists (FCIS: cross-aggregate event construction
            # belongs in the pure decider per the amend_clearance
            # precedent + N9 gate-review nit). Handler routes them to
            # EventStore.append_streams as a single atomic batch:
            # commit together or roll back together on ConcurrencyError.
            assert command.campaign_id is not None  # decider invariant
            campaign_membership_events = [
                to_new_event(
                    event_type=campaign_event_type_name(event),
                    payload=campaign_to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=deps.id_generator.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    principal_id=principal_id,
                )
                for event in decision.campaign_events
            ]
            await deps.event_store.append_streams(
                [
                    StreamAppend(
                        stream_type=_STREAM_TYPE,
                        stream_id=new_id,
                        expected_version=0,
                        events=new_events,
                    ),
                    StreamAppend(
                        stream_type=_CAMPAIGN_STREAM_TYPE,
                        stream_id=command.campaign_id,
                        expected_version=campaign_version,
                        events=campaign_membership_events,
                    ),
                ]
            )
        else:
            await deps.event_store.append(
                stream_type=_STREAM_TYPE,
                stream_id=new_id,
                expected_version=0,
                events=new_events,
            )

        _log.info(
            "start_run.success",
            command_name=_COMMAND_NAME,
            run_id=str(new_id),
            plan_id=str(command.plan_id),
            subject_id=str(command.subject_id) if command.subject_id is not None else None,
            raid=command.raid,
            method_id=str(method.id),
            override_key_count=len(command.override_parameters),
            effective_key_count=len(effective_parameters),
            schema_present=method.parameters_schema is not None,
            trigger_source=command.trigger_source,
            campaign_id=str(command.campaign_id) if command.campaign_id is not None else None,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
