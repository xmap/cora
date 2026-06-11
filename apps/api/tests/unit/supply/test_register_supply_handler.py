"""Application-handler tests for `register_supply` slice.

In-memory event store + AllowAllAuthorize (or DenyAllAuthorize). The
idempotency-wrap is applied at wire.py and is not exercised here;
we test the bare handler returned by `register_supply.bind(deps)`.

Slice 7A adds the `facility_code` field on `RegisterSupply` and
threads `FacilityLookup.lookup_by_code` through the handler. Every
test that exercises the happy path seeds an `InMemoryFacilityLookup`
with the test slug `"aps"`; the not-found path uses an unseeded
lookup or an unknown slug.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import (
    InMemoryFacilityLookup,
)
from cora.infrastructure.kernel import Kernel
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyContainingAssetNotFoundError,
    SupplyFacilityNotFoundError,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005511")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000005512")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FACILITY_ID = UUID("01900000-0000-7000-8000-000000000fac")
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-000000000a55")


def _seeded_facility_lookup(*, code: str = "aps", status: str = "Active") -> InMemoryFacilityLookup:
    lookup = InMemoryFacilityLookup()
    lookup.register(facility_id=_FACILITY_ID, code=code, kind="Site", status=status)
    return lookup


def _seeded_asset_lookup(
    *,
    asset_id: UUID = _CONTAINING_ASSET_ID,
    name: str = "2-BM",
    tier: str = "Unit",
    lifecycle: str = "Active",
) -> InMemoryAssetLookup:
    lookup = InMemoryAssetLookup()
    lookup.register(asset_id=asset_id, name=name, tier=tier, lifecycle=lifecycle)
    return lookup


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    facility_lookup: InMemoryFacilityLookup | None = None,
    asset_lookup: InMemoryAssetLookup | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
        facility_lookup=(
            facility_lookup if facility_lookup is not None else _seeded_facility_lookup()
        ),
        asset_lookup=asset_lookup,
    )


@pytest.mark.unit
async def test_handler_returns_generated_supply_id() -> None:
    deps = _build_deps()
    handler = register_supply.bind(deps)
    result = await handler(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_supply_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Supply", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "SupplyRegistered"
    assert stored.payload == {
        "supply_id": str(_NEW_ID),
        "kind": "LiquidNitrogen",
        "name": "2-BM LN2",
        "facility_code": "aps",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterSupply"}


@pytest.mark.unit
async def test_handler_trims_kind_and_name() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(
            kind="  PhotonBeam  ",
            name="  APS storage-ring beam  ",
            facility_code="aps",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Supply", _NEW_ID)
    assert events[0].payload["kind"] == "PhotonBeam"
    assert events[0].payload["name"] == "APS storage-ring beam"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_supply.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM",
                facility_code="aps",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_supply.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM",
                facility_code="aps",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Supply", _NEW_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_raises_facility_not_found_for_unknown_code() -> None:
    """Empty FacilityLookup -> handler resolves None -> decider raises
    SupplyFacilityNotFoundError carrying the wire-level slug."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, facility_lookup=InMemoryFacilityLookup())
    handler = register_supply.bind(deps)
    with pytest.raises(SupplyFacilityNotFoundError) as exc_info:
        await handler(
            RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM LN2",
                facility_code="unseeded",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.facility_code == "unseeded"
    events, version = await store.load("Supply", _NEW_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_accepts_decommissioned_facility() -> None:
    """Decommissioned Facility is a valid binding target; the decider
    does not filter on Facility status."""
    store = InMemoryEventStore()
    deps = _build_deps(
        event_store=store,
        facility_lookup=_seeded_facility_lookup(status="Decommissioned"),
    )
    handler = register_supply.bind(deps)
    result = await handler(
        RegisterSupply(
            kind="PhotonBeam",
            name="APS beam",
            facility_code="aps",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID
    events, _ = await store.load("Supply", _NEW_ID)
    assert events[0].payload["facility_code"] == "aps"


@pytest.mark.unit
async def test_handler_threads_canonical_lookup_code_into_event() -> None:
    """The event's facility_code comes from the lookup result (canonical
    slug), not from a re-echo of the command. This pins the
    single-source-of-truth contract: if the projection ever stores a
    different canonical form, the event reflects the projection."""
    store = InMemoryEventStore()
    lookup = InMemoryFacilityLookup()
    lookup.register(
        facility_id=_FACILITY_ID,
        code=FacilityCode("aps"),
        kind="Site",
        status="Active",
    )
    deps = _build_deps(event_store=store, facility_lookup=lookup)
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Supply", _NEW_ID)
    assert events[0].payload["facility_code"] == "aps"


@pytest.mark.unit
async def test_handler_binds_containing_asset_when_provided() -> None:
    """Slice 7B: when command.containing_asset_id is non-None and the
    AssetLookup resolves, the handler folds the id onto the event
    payload under the `containing_asset_id` key."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, asset_lookup=_seeded_asset_lookup())
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
            containing_asset_id=_CONTAINING_ASSET_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Supply", _NEW_ID)
    assert events[0].payload["containing_asset_id"] == str(_CONTAINING_ASSET_ID)


@pytest.mark.unit
async def test_handler_omits_containing_asset_when_none() -> None:
    """Slice 7B: facility-scope supplies (containing_asset_id=None)
    skip the AssetLookup call entirely and OMIT the key from the
    payload (additive forward-compat convention)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(
            kind="PhotonBeam",
            name="APS storage-ring beam",
            facility_code="aps",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Supply", _NEW_ID)
    assert "containing_asset_id" not in events[0].payload


@pytest.mark.unit
async def test_handler_raises_containing_asset_not_found_for_unknown_id() -> None:
    """Empty AssetLookup -> handler resolves None -> decider raises
    SupplyContainingAssetNotFoundError carrying the wire-level id."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, asset_lookup=InMemoryAssetLookup())
    handler = register_supply.bind(deps)
    unknown_id = UUID("01900000-0000-7000-8000-0000000a5d99")
    with pytest.raises(SupplyContainingAssetNotFoundError) as exc_info:
        await handler(
            RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM LN2",
                facility_code="aps",
                containing_asset_id=unknown_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.containing_asset_id == unknown_id
    events, version = await store.load("Supply", _NEW_ID)
    assert version == 0
    assert events == []
