"""Application handler for the `inspect_plan_binding` query slice.

Pre-loads the same upstream entities `define_plan` loads
(Practice -> Method -> Capability -> per-Asset -> per-Family),
then assembles an `InspectPlanBindingView` instead of emitting
events.

The load fan-out mirrors `define_plan.handler` exactly so the
preview diagnostic reflects what `define_plan` would actually
see at validation time. NotFound errors raised here use the same
exception classes `define_plan` raises and are HTTP-mapped by
`recipe/routes.py` to 404.

When `method.capability_id` is None (legacy Method shape), the
affordance guard is skipped; the view reports
`BindingStatus.MISSING_CAPABILITY` and leaves
`capability_required_affordances` + `missing_affordances` empty.
Matches `define_plan` decider's existing behaviour.

Query handlers do NOT emit `causation_id` log fields.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.equipment.aggregates.family import (
    Affordance,
    FamilyNotFoundError,
    list_asset_ids_in_families,
    list_family_ids,
    load_family,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.capability import CapabilityNotFoundError, load_capability
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.inspect_plan_binding.query import InspectPlanBinding
from cora.recipe.features.inspect_plan_binding.view import (
    BindingStatus,
    CandidateAsset,
    InspectPlanBindingView,
    MissingAffordanceCandidates,
    WiredAsset,
)

_QUERY_NAME = "InspectPlanBinding"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every inspect_plan_binding handler implements."""

    async def __call__(
        self,
        query: InspectPlanBinding,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> InspectPlanBindingView: ...


def bind(deps: Kernel) -> Handler:
    """Build an inspect_plan_binding handler closed over the shared deps."""

    async def handler(
        query: InspectPlanBinding,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> InspectPlanBindingView:
        _log.info(
            "inspect_plan_binding.start",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            asset_count=len(query.asset_ids),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "inspect_plan_binding.denied",
                query_name=_QUERY_NAME,
                practice_id=str(query.practice_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        practice = await load_practice(deps.event_store, query.practice_id)
        if practice is None:
            raise PracticeNotFoundError(query.practice_id)

        method = await load_method(deps.event_store, practice.method_id)
        if method is None:
            raise MethodNotFoundError(practice.method_id)

        assets_in_order = sorted(query.asset_ids, key=str)
        assets: dict[UUID, Asset] = {}
        for asset_id in assets_in_order:
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        capability = None
        family_affordances: dict[UUID, frozenset[Affordance]] = {}
        union_families: frozenset[UUID] = frozenset(
            fid for asset in assets.values() for fid in asset.family_ids
        )
        missing_family_ids = method.needed_family_ids - union_families

        if method.capability_id is not None:
            capability = await load_capability(deps.event_store, method.capability_id)
            if capability is None:
                raise CapabilityNotFoundError(method.capability_id)

            for family_id in sorted(union_families, key=str):
                family = await load_family(deps.event_store, family_id)
                if family is None:
                    raise FamilyNotFoundError(family_id)
                family_affordances[family_id] = family.affordances

        if capability is not None:
            union_affordances: frozenset[Affordance] = frozenset(
                affordance
                for asset in assets.values()
                for family_id in asset.family_ids
                for affordance in family_affordances.get(family_id, frozenset())
            )
            missing_affordances = capability.required_affordances - union_affordances
            required_affordances = capability.required_affordances
        else:
            missing_affordances = frozenset[Affordance]()
            required_affordances = frozenset[Affordance]()

        if capability is None:
            binding_status = BindingStatus.MISSING_CAPABILITY
        elif missing_family_ids:
            binding_status = BindingStatus.MISSING_FAMILIES
        elif missing_affordances:
            binding_status = BindingStatus.MISSING_AFFORDANCES
        else:
            binding_status = BindingStatus.SATISFIED

        wired_assets = tuple(
            WiredAsset(
                asset_id=asset_id,
                asset_name=assets[asset_id].name.value,
                condition=(
                    None
                    if assets[asset_id].partition_rule is not None
                    else assets[asset_id].condition
                ),
                lifecycle=assets[asset_id].lifecycle,
                family_ids=assets[asset_id].family_ids,
                contributed_affordances=frozenset(
                    affordance
                    for family_id in assets[asset_id].family_ids
                    for affordance in family_affordances.get(family_id, frozenset())
                ),
            )
            for asset_id in assets_in_order
        )

        # Per-missing-affordance candidate enumeration. Projection-backed:
        # skipped gracefully when no pool is configured (in-memory test
        # mode mirroring get_plan's pool-optional pattern). Loads every
        # Family aggregate (pilot scale ~9 Families; watch item for
        # Family-affordance projection upgrade at scale).
        missing_affordance_candidates: tuple[MissingAffordanceCandidates, ...] = ()
        if deps.pool is not None and missing_affordances:
            missing_affordance_candidates = await _load_candidates(
                deps,
                missing_affordances=missing_affordances,
                wired_asset_ids=frozenset(query.asset_ids),
            )

        view = InspectPlanBindingView(
            practice_id=query.practice_id,
            method_id=method.id,
            capability_id=method.capability_id,
            method_needed_family_ids=method.needed_family_ids,
            capability_required_affordances=required_affordances,
            wired_assets=wired_assets,
            missing_family_ids=missing_family_ids,
            missing_affordances=missing_affordances,
            missing_affordance_candidates=missing_affordance_candidates,
            binding_status=binding_status,
        )

        _log.info(
            "inspect_plan_binding.success",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            binding_status=binding_status.value,
            asset_count=len(query.asset_ids),
            missing_family_count=len(missing_family_ids),
            missing_affordance_count=len(missing_affordances),
            missing_affordance_candidate_count=sum(
                len(entry.candidates) for entry in missing_affordance_candidates
            ),
        )
        return view

    return handler


async def _load_candidates(
    deps: Kernel,
    *,
    missing_affordances: frozenset[Affordance],
    wired_asset_ids: frozenset[UUID],
) -> tuple[MissingAffordanceCandidates, ...]:
    """Enumerate facility Assets that could cover each missing affordance.

    Projection-backed: load every non-Deprecated Family from the
    summary projection, fold its aggregate state to read `affordances`,
    bucket the Family by each missing affordance it declares. Then for
    each bucket, query the membership projection for member Assets,
    exclude already-wired ones, load each Asset for name / condition
    / lifecycle, and narrow `contributing_family_ids` to the
    candidate's Families that contribute the affordance under
    consideration. Deprecated Families are pre-filtered at the SQL
    layer so they never surface as candidate sources (operator can
    still see Deprecated wired Families via `wired_assets`; they're
    excluded only from the discovery enumeration).

    Caller-guarded: only called when `deps.pool is not None` AND
    `missing_affordances` is non-empty.
    """
    assert deps.pool is not None  # caller-guaranteed
    family_ids = await list_family_ids(deps.pool)

    # Bucket Families by which missing affordance they declare.
    # Family is None case: a projection row points at a Family stream
    # that doesn't exist (projection lag / bookmark drift on replay /
    # hypothetical hard-delete). The main fan-out for wired Assets
    # raises FamilyNotFoundError in this case because every wired
    # asset_id was supplied by the caller and must resolve; here we
    # tolerate the orphan row because dropping a stale candidate from
    # the enumeration is preferable to failing the whole diagnostic.
    families_per_affordance: dict[Affordance, set[UUID]] = {
        affordance: set() for affordance in missing_affordances
    }
    for family_id in family_ids:
        family = await load_family(deps.event_store, family_id)
        if family is None:
            continue
        for affordance in missing_affordances:
            if affordance in family.affordances:
                families_per_affordance[affordance].add(family_id)

    # For each bucket, find candidate Assets (members of any bucketed
    # Family, minus already-wired) and shape them into the view.
    asset_cache: dict[UUID, Asset] = {}

    async def _get_asset(asset_id: UUID) -> Asset | None:
        if asset_id not in asset_cache:
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                return None
            asset_cache[asset_id] = asset
        return asset_cache[asset_id]

    entries: list[MissingAffordanceCandidates] = []
    for affordance in sorted(missing_affordances, key=lambda a: a.value):
        contributing_families = families_per_affordance[affordance]
        candidates: list[CandidateAsset] = []
        if contributing_families:
            candidate_ids = await list_asset_ids_in_families(deps.pool, contributing_families)
            for asset_id in candidate_ids:
                if asset_id in wired_asset_ids:
                    continue
                asset = await _get_asset(asset_id)
                if asset is None:
                    continue
                contributing_subset = asset.family_ids & contributing_families
                candidates.append(
                    CandidateAsset(
                        asset_id=asset_id,
                        asset_name=asset.name.value,
                        condition=(None if asset.partition_rule is not None else asset.condition),
                        lifecycle=asset.lifecycle,
                        contributing_family_ids=frozenset(contributing_subset),
                    )
                )
        entries.append(
            MissingAffordanceCandidates(
                affordance=affordance,
                candidates=tuple(candidates),
            )
        )
    return tuple(entries)
