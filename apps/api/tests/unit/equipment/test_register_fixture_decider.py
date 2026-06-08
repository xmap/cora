"""Unit tests for the `register_fixture` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotInstantiateError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    FixtureAssetFamilyMismatchError,
    FixtureAssetNotAttachableError,
    FixtureAssetNotFoundError,
    FixtureAssetNotInstalledError,
    FixtureMappingIncompleteError,
    FixtureParameterOverridesInvalidError,
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

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))
_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _slot(
    name: str,
    *,
    cardinality: SlotCardinality = SlotCardinality.EXACTLY_1,
    required_family_ids: frozenset[UUID] | None = None,
) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(name),
        required_family_ids=required_family_ids
        if required_family_ids is not None
        else frozenset({uuid4()}),
        cardinality=cardinality,
    )


def _assembly(
    assembly_id: UUID,
    *,
    slots: frozenset[TemplateSlot] = frozenset(),
    status: AssemblyStatus = AssemblyStatus.DEFINED,
    parameter_overrides_schema: dict[str, object] | None = None,
    content_hash: str = "abc123",
) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("Detector Fixture"),
        presents_as_family_id=uuid4(),
        required_slots=slots,
        parameter_overrides_schema=parameter_overrides_schema,  # type: ignore[arg-type]
        status=status,
        content_hash=content_hash,
    )


@pytest.mark.unit
def test_decide_emits_fixture_registered_when_all_invariants_hold() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    state_context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    new_id = uuid4()
    events = register_fixture.decide(
        state=None,
        command=command,
        context=state_context,
        now=_NOW,
        new_id=new_id,
        registered_by=_TEST_ACTOR_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FixtureRegistered)
    assert event.fixture_id == new_id
    assert event.assembly_id == assembly_id
    assert event.assembly_content_hash == "abc123"
    assert event.occurred_at == _NOW
    assert event.slot_asset_bindings == command.slot_asset_bindings


@pytest.mark.unit
def test_decide_rejects_missing_assembly_with_assembly_not_found() -> None:
    target_id = uuid4()
    context = RegisterFixtureContext(assembly_state=None)
    with pytest.raises(AssemblyNotFoundError) as exc_info:
        register_fixture.decide(
            state=None,
            command=RegisterFixture(assembly_id=target_id),
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.assembly_id == target_id


@pytest.mark.unit
def test_decide_rejects_deprecated_assembly_with_cannot_instantiate() -> None:
    assembly_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, status=AssemblyStatus.DEPRECATED),
    )
    with pytest.raises(AssemblyCannotInstantiateError) as exc_info:
        register_fixture.decide(
            state=None,
            command=RegisterFixture(assembly_id=assembly_id),
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.assembly_id == assembly_id
    assert "Deprecated" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_missing_asset_with_asset_not_found() -> None:
    assembly_id = uuid4()
    slot = _slot(
        "camera",
        cardinality=SlotCardinality.ZERO_OR_MORE,
        required_family_ids=frozenset({uuid4()}),
    )
    missing_asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={missing_asset_id: None},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=missing_asset_id)},
        ),
    )
    with pytest.raises(FixtureAssetNotFoundError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == missing_asset_id


@pytest.mark.unit
def test_decide_rejects_exactly_one_slot_with_zero_bindings() -> None:
    assembly_id = uuid4()
    slot = _slot("rotary", cardinality=SlotCardinality.EXACTLY_1)
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
    )
    with pytest.raises(FixtureMappingIncompleteError) as exc_info:
        register_fixture.decide(
            state=None,
            command=RegisterFixture(assembly_id=assembly_id),
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.slot_name == "rotary"
    assert "Exactly1" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_unknown_slot_in_bindings() -> None:
    assembly_id = uuid4()
    slot = _slot(
        "camera",
        cardinality=SlotCardinality.ZERO_OR_MORE,
        required_family_ids=frozenset({uuid4()}),
    )
    rogue_asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={rogue_asset_id: frozenset({uuid4()})},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="unknown_slot", asset_id=rogue_asset_id)},
        ),
    )
    with pytest.raises(FixtureMappingIncompleteError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.slot_name == "unknown_slot"
    assert "not declared" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_family_mismatch_with_asset_family_mismatch_error() -> None:
    assembly_id = uuid4()
    slot = _slot(
        "camera",
        cardinality=SlotCardinality.EXACTLY_1,
        required_family_ids=frozenset({uuid4()}),
    )
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({uuid4()})},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    with pytest.raises(FixtureAssetFamilyMismatchError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.slot_name == "camera"
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
def test_decide_rejects_overrides_when_schema_absent_under_strict_posture() -> None:
    assembly_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, parameter_overrides_schema=None),
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        parameter_overrides={"exposure_ms": 250},
    )
    with pytest.raises(FixtureParameterOverridesInvalidError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert "exposure_ms" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_overrides_failing_schema_validation() -> None:
    assembly_id = uuid4()
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"exposure_ms": {"type": "integer"}},
        "additionalProperties": False,
    }
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, parameter_overrides_schema=schema),
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        parameter_overrides={"exposure_ms": "not-an-int"},
    )
    with pytest.raises(FixtureParameterOverridesInvalidError):
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_decommissioned_bound_asset_with_not_attachable_error() -> None:
    """Cross-aggregate guard: a Decommissioned Asset cannot be bound
    into a Fixture; mirrors AssetCannotAttachToFixtureError at the
    attach-time precondition. Fires AFTER the existence check
    (FixtureAssetNotFoundError) but BEFORE cardinality / family
    match so the operator sees the most actionable error first.
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
        lifecycle_by_asset_id={asset_id: AssetLifecycle.DECOMMISSIONED},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    with pytest.raises(FixtureAssetNotAttachableError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle == AssetLifecycle.DECOMMISSIONED.value


@pytest.mark.unit
def test_decide_skips_lifecycle_guard_when_dict_is_empty() -> None:
    """Default-empty lifecycle_by_asset_id means the handler did not
    load lifecycle info (decider-only unit tests that exercise other
    invariants leave it empty); the guard short-circuits without
    firing. Mirrors family_ids_by_asset_id's relaxed default.
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
        # lifecycle_by_asset_id intentionally omitted -> default empty
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    events = register_fixture.decide(
        state=None,
        command=command,
        context=context,
        now=_NOW,
        new_id=uuid4(),
        registered_by=_TEST_ACTOR_ID,
    )
    assert len(events) == 1
    assert isinstance(events[0], FixtureRegistered)


@pytest.mark.unit
def test_decide_rejects_orphan_bound_asset_with_not_installed_error() -> None:
    """Cross-aggregate guard: every bound Asset must currently
    be installed in some Mount. mount_id_by_asset_id with a None entry
    says 'the projection has no row for this asset_id'
    -> FixtureAssetNotInstalledError. Fires AFTER the lifecycle check
    (Decommissioned is a more fundamental constraint) and BEFORE
    cardinality / family-mismatch / parameter-overrides.
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
        lifecycle_by_asset_id={asset_id: AssetLifecycle.ACTIVE},
        mount_id_by_asset_id={asset_id: None},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    with pytest.raises(FixtureAssetNotInstalledError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
def test_decide_orphan_error_carries_sorted_first_when_multiple_orphans() -> None:
    """With multiple orphan bindings, FixtureAssetNotInstalledError must
    carry the sorted-by-str-of-UUID first id (the deterministic
    invariant). Uses concrete UUIDs whose dict insertion order does NOT
    match their stringified sort order, so a regression to e.g.
    `next(iter(...))` would catch the wrong id and fail.
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.ZERO_OR_MORE,
    )
    # Concrete ids chosen so the dict's first-inserted entry sorts LAST
    # by str(UUID). Sorted-by-str order: 11..., 22..., 33....
    asset_late = UUID("33333333-3333-7333-9333-333333333333")
    asset_mid = UUID("22222222-2222-7222-9222-222222222222")
    asset_early = UUID("11111111-1111-7111-9111-111111111111")
    asset_ids = (asset_late, asset_mid, asset_early)
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={aid: frozenset({family_id}) for aid in asset_ids},
        lifecycle_by_asset_id={aid: AssetLifecycle.ACTIVE for aid in asset_ids},
        mount_id_by_asset_id={aid: None for aid in asset_ids},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            SlotAssetBinding(slot_name="camera", asset_id=aid) for aid in asset_ids
        ),
    )
    with pytest.raises(FixtureAssetNotInstalledError) as exc_info:
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == asset_early


@pytest.mark.unit
def test_decide_skips_orphan_guard_when_mount_id_dict_is_none() -> None:
    """Pool-None test path: handler ran without a database pool, so
    mount_id_by_asset_id is None and the orphan guard is disabled.
    Mirrors install_asset / decommission_asset projection-precondition
    short-circuit pattern.
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
        lifecycle_by_asset_id={asset_id: AssetLifecycle.ACTIVE},
        mount_id_by_asset_id=None,
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    events = register_fixture.decide(
        state=None,
        command=command,
        context=context,
        now=_NOW,
        new_id=uuid4(),
        registered_by=_TEST_ACTOR_ID,
    )
    assert len(events) == 1
    assert isinstance(events[0], FixtureRegistered)


@pytest.mark.unit
def test_decide_decommissioned_guard_fires_before_orphan_guard() -> None:
    """Deterministic ordering when both guards would apply: the
    Decommissioned-lifecycle check fires first because lifecycle is
    the more fundamental constraint (an installed Decommissioned
    Asset is rarer in practice but still wrong).
    """
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
        lifecycle_by_asset_id={asset_id: AssetLifecycle.DECOMMISSIONED},
        mount_id_by_asset_id={asset_id: None},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="camera", asset_id=asset_id)},
        ),
    )
    with pytest.raises(FixtureAssetNotAttachableError):
        register_fixture.decide(
            state=None,
            command=command,
            context=context,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_TEST_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_yield_same_events() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("rotary", required_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    context = RegisterFixtureContext(
        assembly_state=_assembly(assembly_id, slots=frozenset({slot})),
        family_ids_by_asset_id={asset_id: frozenset({family_id})},
    )
    command = RegisterFixture(
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {SlotAssetBinding(slot_name="rotary", asset_id=asset_id)},
        ),
    )
    new_id = uuid4()
    events_a = register_fixture.decide(
        state=None,
        command=command,
        context=context,
        now=_NOW,
        new_id=new_id,
        registered_by=_TEST_ACTOR_ID,
    )
    events_b = register_fixture.decide(
        state=None,
        command=command,
        context=context,
        now=_NOW,
        new_id=new_id,
        registered_by=_TEST_ACTOR_ID,
    )
    assert events_a == events_b
