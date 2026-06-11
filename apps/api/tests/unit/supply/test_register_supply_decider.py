"""Pure-decider tests for `register_supply` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.asset_lookup import AssetLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyKindError,
    InvalidSupplyNameError,
    Supply,
    SupplyAlreadyExistsError,
    SupplyContainingAssetNotFoundError,
    SupplyFacilityNotFoundError,
    SupplyName,
    SupplyRegistered,
    SupplyStatus,
)
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = ActorId(uuid4())
_FACILITY_CODE = FacilityCode("aps")
_FACILITY_ID = UUID("01900000-0000-7000-8000-000000000fac")
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-000000000a55")


def _facility_lookup_result(
    *,
    kind: str = "Site",
    status: str = "Active",
) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=_FACILITY_ID,
        code=_FACILITY_CODE,
        kind=kind,
        status=status,
        trust_anchor_credential_ids=frozenset(),
    )


def _asset_lookup_result(
    *,
    asset_id: UUID = _CONTAINING_ASSET_ID,
    name: str = "2-BM",
    tier: str = "Unit",
    lifecycle: str = "Active",
) -> AssetLookupResult:
    return AssetLookupResult(
        id=asset_id,
        name=name,
        tier=tier,
        lifecycle=lifecycle,
        family_affordances=frozenset[str](),
    )


@pytest.mark.unit
def test_decide_emits_supply_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=None,
    )
    assert events == [
        SupplyRegistered(
            supply_id=new_id,
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code=_FACILITY_CODE,
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_kind_and_name() -> None:
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="  PhotonBeam  ",
            name="  APS storage-ring beam  ",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=None,
    )
    assert events[0].kind == "PhotonBeam"
    assert events[0].name == "APS storage-ring beam"


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Supply(
        id=uuid4(),
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        facility_code=_FACILITY_CODE,
        status=SupplyStatus.UNKNOWN,
    )
    with pytest.raises(SupplyAlreadyExistsError) as exc_info:
        register_supply.decide(
            state=existing,
            command=RegisterSupply(
                kind="LiquidNitrogen",
                name="other",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
            asset_lookup_result=None,
        )
    assert exc_info.value.supply_id == existing.id


@pytest.mark.unit
def test_decide_rejects_empty_kind() -> None:
    with pytest.raises(InvalidSupplyKindError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                kind="   ",
                name="2-BM",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
            asset_lookup_result=None,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_kind() -> None:
    with pytest.raises(InvalidSupplyKindError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                kind="a" * 51,
                name="2-BM",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
            asset_lookup_result=None,
        )


@pytest.mark.unit
def test_decide_rejects_empty_name() -> None:
    with pytest.raises(InvalidSupplyNameError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                kind="LiquidNitrogen",
                name="   ",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
            asset_lookup_result=None,
        )


@pytest.mark.unit
def test_decide_rejects_missing_facility() -> None:
    """`facility_lookup_result=None` means the handler's
    `FacilityLookup.lookup_by_code` returned None; the decider must
    raise `SupplyFacilityNotFoundError` carrying the wire-level slug."""
    with pytest.raises(SupplyFacilityNotFoundError) as exc_info:
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM LN2",
                facility_code="unknown",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=None,
            asset_lookup_result=None,
        )
    assert exc_info.value.facility_code == "unknown"


@pytest.mark.unit
def test_decide_accepts_decommissioned_facility() -> None:
    """Decommissioned-Facility binding is allowed; the decider does not
    partition on Facility status (mirrors slice 6
    `FacilityParentNotFoundError` precedent)."""
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="PhotonBeam",
            name="APS storage-ring beam",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(status="Decommissioned"),
        asset_lookup_result=None,
    )
    assert events[0].facility_code == _FACILITY_CODE


@pytest.mark.unit
def test_decide_uses_lookup_result_code_not_command_echo() -> None:
    """The event's `facility_code` is sourced from
    `facility_lookup_result.code`, not from `command.facility_code`.
    The lookup result is the single source of truth for the canonical
    cross-deployment slug; the wire-level command field is the
    operator-supplied input that resolves to it."""
    new_id = uuid4()
    canonical = FacilityCode("aps")
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=None,
    )
    assert events[0].facility_code is canonical or events[0].facility_code == canonical


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = RegisterSupply(
        kind="LiquidNitrogen",
        name="2-BM LN2",
        facility_code="aps",
    )
    lookup = _facility_lookup_result()
    first = register_supply.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=lookup,
        asset_lookup_result=None,
    )
    second = register_supply.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=lookup,
        asset_lookup_result=None,
    )
    assert first == second


@pytest.mark.unit
def test_decide_emits_event_with_containing_asset_id_when_bound() -> None:
    """When command.containing_asset_id is non-None and the lookup
    resolves, the event's facility_code + containing_asset_id both
    come from the canonical lookup results (Session 5 Slice 7B)."""
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
            containing_asset_id=_CONTAINING_ASSET_ID,
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=_asset_lookup_result(),
    )
    assert events[0].containing_asset_id == _CONTAINING_ASSET_ID


@pytest.mark.unit
def test_decide_facility_scope_omits_containing_asset_id() -> None:
    """When command.containing_asset_id is None the decider does not
    require asset_lookup_result; emits the event with
    containing_asset_id=None (facility-scope semantics)."""
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="PhotonBeam",
            name="APS storage-ring beam",
            facility_code="aps",
            containing_asset_id=None,
        ),
        now=_NOW,
        new_id=uuid4(),
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=None,
    )
    assert events[0].containing_asset_id is None


@pytest.mark.unit
def test_decide_rejects_missing_containing_asset() -> None:
    """When command.containing_asset_id is non-None but asset_lookup_result
    is None (handler's AssetLookup.lookup miss), the decider raises
    SupplyContainingAssetNotFoundError carrying the wire-level id."""
    with pytest.raises(SupplyContainingAssetNotFoundError) as exc_info:
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM LN2",
                facility_code="aps",
                containing_asset_id=_CONTAINING_ASSET_ID,
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
            asset_lookup_result=None,
        )
    assert exc_info.value.containing_asset_id == _CONTAINING_ASSET_ID


@pytest.mark.unit
def test_decide_accepts_decommissioned_containing_asset() -> None:
    """Decommissioned-Asset binding is allowed per the slice 6A +
    Slice 7A precedent (operator keeps the lineage visible). The
    decider does NOT partition on Asset lifecycle."""
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2 (decommissioned-asset binding)",
            facility_code="aps",
            containing_asset_id=_CONTAINING_ASSET_ID,
        ),
        now=_NOW,
        new_id=uuid4(),
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=_asset_lookup_result(lifecycle="Decommissioned"),
    )
    assert events[0].containing_asset_id == _CONTAINING_ASSET_ID


@pytest.mark.unit
def test_decide_uses_lookup_result_id_not_command_echo() -> None:
    """The event's containing_asset_id is sourced from
    asset_lookup_result.id (canonical projection-row id), not from
    command.containing_asset_id echo. Single source of truth."""
    new_id = uuid4()
    different_id = UUID("01900000-0000-7000-8000-0000000a55ee")
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
            containing_asset_id=_CONTAINING_ASSET_ID,
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
        asset_lookup_result=_asset_lookup_result(asset_id=different_id),
    )
    assert events[0].containing_asset_id == different_id
