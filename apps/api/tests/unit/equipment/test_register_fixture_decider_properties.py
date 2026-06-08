"""Property-based tests for `register_fixture.decide`."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotInstantiateError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    FixtureAssetNotInstalledError,
    SlotCardinality,
    SlotName,
    TemplateSlot,
)
from cora.equipment.aggregates.asset import AssetLifecycle
from cora.equipment.aggregates.fixture import (
    FixtureRegistered,
    SlotAssetBinding,
)
from cora.equipment.features import register_fixture
from cora.equipment.features.register_fixture import (
    RegisterFixture,
    RegisterFixtureContext,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


def _slot_zero_or_more(family_id: UUID) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.ZERO_OR_MORE,
    )


def _assembly(
    assembly_id: UUID,
    *,
    slots: frozenset[TemplateSlot] = frozenset(),
    status: AssemblyStatus = AssemblyStatus.DEFINED,
) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("X"),
        presents_as_family_id=uuid4(),
        required_slots=slots,
        status=status,
        content_hash="a" * 64,
    )


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_none_assembly_always_raises_not_found(now: datetime) -> None:
    target = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc_info:
        register_fixture.decide(
            state=None,
            command=RegisterFixture(assembly_id=target),
            context=RegisterFixtureContext(assembly_state=None),
            now=now,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.assembly_id == target


@pytest.mark.unit
@given(now=aware_datetimes())
def test_decide_deprecated_assembly_always_raises_cannot_instantiate(
    now: datetime,
) -> None:
    assembly_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, status=AssemblyStatus.DEPRECATED),
    )
    with pytest.raises(AssemblyCannotInstantiateError) as exc_info:
        register_fixture.decide(
            state=None,
            command=RegisterFixture(assembly_id=assembly_id),
            context=context,
            now=now,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.assembly_id == assembly_id


@pytest.mark.unit
@given(
    status=st.sampled_from((AssemblyStatus.DEFINED, AssemblyStatus.VERSIONED)),
    binding_count=st.integers(min_value=0, max_value=5),
    now=aware_datetimes(),
)
def test_decide_zero_or_more_slot_accepts_any_binding_count(
    status: AssemblyStatus,
    binding_count: int,
    now: datetime,
) -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot_zero_or_more(family_id)
    asset_ids = [uuid4() for _ in range(binding_count)]
    asset_family_ids: dict[UUID, frozenset[UUID] | None] = {
        aid: frozenset({family_id}) for aid in asset_ids
    }
    bindings = frozenset(SlotAssetBinding(slot_name="camera", asset_id=aid) for aid in asset_ids)
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot}), status=status),
        family_ids_by_asset_id=asset_family_ids,
    )
    events = register_fixture.decide(
        state=None,
        command=RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=bindings,
        ),
        context=context,
        now=now,
        new_id=uuid4(),
        registered_by=_TEST_ACTOR_ID,
    )
    assert len(events) == 1
    assert isinstance(events[0], FixtureRegistered)


@pytest.mark.unit
@given(
    orphan_ids=st.lists(st.uuids(), min_size=2, max_size=5, unique=True).map(frozenset),
    now=aware_datetimes(),
)
def test_decide_orphan_error_always_carries_sorted_first_id(
    orphan_ids: frozenset[UUID],
    now: datetime,
) -> None:
    """When several bindings are orphans, the raised
    `FixtureAssetNotInstalledError.asset_id` is the smallest by
    `str(UUID)` regardless of dict/frozenset iteration order. A
    regression to `next(iter(orphans))` would fail this property
    because frozenset iteration is not stringified-order.
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.ZERO_OR_MORE,
    )
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={aid: frozenset({family_id}) for aid in orphan_ids},
        lifecycle_by_asset_id={aid: AssetLifecycle.ACTIVE for aid in orphan_ids},
        mount_id_by_asset_id={aid: None for aid in orphan_ids},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            SlotAssetBinding(slot_name="camera", asset_id=aid) for aid in orphan_ids
        ),
    )
    with pytest.raises(FixtureAssetNotInstalledError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == sorted(orphan_ids, key=str)[0]


@pytest.mark.unit
@given(now=aware_datetimes(), new_id=st.uuids())
def test_decide_is_pure_same_inputs_yield_same_events(
    now: datetime,
    new_id: UUID,
) -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot = TemplateSlot(
        slot_name=SlotName("rotary"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset({SlotAssetBinding(slot_name="rotary", asset_id=asset_id)}),
    )
    events_a = register_fixture.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        registered_by=_TEST_ACTOR_ID,
    )
    events_b = register_fixture.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        registered_by=_TEST_ACTOR_ID,
    )
    assert events_a == events_b
