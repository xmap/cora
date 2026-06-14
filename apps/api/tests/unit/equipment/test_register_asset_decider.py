"""Unit tests for the `register_asset` slice's pure decider.

Covers the create-style invariants (state empty, name validation)
plus the anchoring XOR rule: a root Asset (parent_id=None) must bind
`facility_code`; a non-root (with parent_id) must NOT bind one.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyExistsError,
    AssetName,
    AssetOwner,
    AssetOwnerAlreadyPresentError,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    AssetRegistered,
    AssetTier,
    InvalidAssetNameError,
    InvalidAssetParentError,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _facility_result(code: str = "cora") -> FacilityLookupResult:
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(),
    )


@pytest.mark.unit
def test_decide_emits_asset_registered_for_facility_rooted_root() -> None:
    new_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="2-BM", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=_facility_result("cora"),
    )
    assert events == [
        AssetRegistered(
            asset_id=new_id,
            name="2-BM",
            tier="Unit",
            parent_id=None,
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
            facility_code=FacilityCode("cora"),
        )
    ]


@pytest.mark.unit
def test_decide_emits_asset_registered_for_child_with_parent() -> None:
    new_id = uuid4()
    parent_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(name="Eiger", tier=AssetTier.DEVICE, parent_id=parent_id),
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events == [
        AssetRegistered(
            asset_id=new_id,
            name="Eiger",
            tier="Device",
            parent_id=parent_id,
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        )
    ]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    parent_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(name="  Eiger-2X-9M  ", tier=AssetTier.DEVICE, parent_id=parent_id),
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].name == "Eiger-2X-9M"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidAssetNameError):
        register_asset.decide(
            state=None,
            command=RegisterAsset(name="", tier=AssetTier.UNIT, parent_id=uuid4()),
            now=_NOW,
            new_id=uuid4(),
            commissioned_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Asset(
        id=uuid4(),
        name=AssetName("2-BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    with pytest.raises(AssetAlreadyExistsError) as exc_info:
        register_asset.decide(
            state=existing,
            command=RegisterAsset(name="Other", tier=AssetTier.UNIT, parent_id=uuid4()),
            now=_NOW,
            new_id=uuid4(),
            commissioned_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )
    assert exc_info.value.asset_id == existing.id


# ---------- Anchoring XOR rule: exactly one of {parent_id, facility_code} ----------


@pytest.mark.unit
def test_decide_rejects_root_without_facility_code() -> None:
    """A root Asset (parent_id=None) MUST bind a facility_code (its
    owning Federation Facility). Supplying neither violates the
    anchoring rule."""
    with pytest.raises(InvalidAssetParentError) as exc_info:
        register_asset.decide(
            state=None,
            command=RegisterAsset(name="Orphan", tier=AssetTier.UNIT, parent_id=None),
            now=_NOW,
            new_id=uuid4(),
            commissioned_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )
    assert "facility_code" in str(exc_info.value)


@pytest.mark.unit
def test_decide_rejects_child_that_also_binds_facility_code() -> None:
    """A non-root Asset (with parent_id) must NOT also bind
    facility_code; children inherit facility scope through the tree."""
    parent_id = uuid4()
    with pytest.raises(InvalidAssetParentError) as exc_info:
        register_asset.decide(
            state=None,
            command=RegisterAsset(
                name="Eiger",
                tier=AssetTier.DEVICE,
                parent_id=parent_id,
                facility_code="cora",
            ),
            now=_NOW,
            new_id=uuid4(),
            commissioned_by=_TEST_ACTOR_ID,
            facility_lookup_result=_facility_result("cora"),
        )
    assert str(parent_id) in str(exc_info.value)


@pytest.mark.unit
def test_decide_carries_drawing_through_to_emitted_event() -> None:
    """Happy path: an optional Drawing supplied on the command rides
    the AssetRegistered event without modification."""
    drawing = Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A")
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Microscope-2BM-A",
            tier=AssetTier.COMPONENT,
            parent_id=uuid4(),
            drawing=drawing,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].drawing == drawing


@pytest.mark.unit
def test_decide_defaults_drawing_to_none_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Microscope",
            tier=AssetTier.COMPONENT,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].drawing is None


@pytest.mark.unit
def test_decide_propagates_model_id_to_emitted_event() -> None:
    """Happy path: an optional model_id supplied on the command rides
    the AssetRegistered event verbatim. The decider does NOT load the
    Model snapshot per Lock B; the handler is the seam that enforces
    existence."""
    model_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Microscope-2BM-A",
            tier=AssetTier.COMPONENT,
            parent_id=uuid4(),
            model_id=model_id,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].model_id == model_id


@pytest.mark.unit
def test_decide_defaults_model_id_to_none_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Microscope",
            tier=AssetTier.COMPONENT,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].model_id is None


@pytest.mark.unit
def test_decide_propagates_controller_id_to_emitted_event() -> None:
    """Happy path: an optional controller_id supplied on the command
    rides the AssetRegistered event verbatim. The decider does NOT load
    the controller Asset snapshot (eventual-consistency); the handler
    does not enforce existence either, mirroring the parent_id /
    fixture_id back-reference precedents."""
    controller_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Rotary",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
            controller_id=controller_id,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].controller_id == controller_id


@pytest.mark.unit
def test_decide_defaults_controller_id_to_none_when_omitted() -> None:
    """Stages with sealed-in or unmodelled controllers default to
    controller_id=None (the dominant case at v1)."""
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Sample_top_X",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].controller_id is None


@pytest.mark.unit
def test_decide_propagates_located_in_enclosure_id_to_emitted_event() -> None:
    """Happy path: an optional located_in_enclosure_id supplied on the
    command rides the AssetRegistered event verbatim. The decider does
    NOT load the Enclosure snapshot (eventual-consistency) and applies
    no validation, mirroring the controller_id / parent_id precedents."""
    located_in_enclosure_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Aerotech_ABRS_rotary",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
            located_in_enclosure_id=located_in_enclosure_id,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].located_in_enclosure_id == located_in_enclosure_id


@pytest.mark.unit
def test_decide_defaults_located_in_enclosure_id_to_none_when_omitted() -> None:
    """Assets registered without an enclosure default to
    located_in_enclosure_id=None (the additive-default case)."""
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Sample_top_X",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].located_in_enclosure_id is None


@pytest.mark.unit
def test_decide_passes_alternate_identifiers_through_to_emitted_event() -> None:
    """Happy path: a non-empty `alternate_identifiers` set on the
    command rides the AssetRegistered event verbatim. The decider does
    NOT validate (kind, value) cross-Asset uniqueness in v1 per Lock F."""
    identifiers = frozenset(
        {
            AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="ANT130L-12345"),
            AlternateIdentifier(
                kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-2BM-RS-001"
            ),
        }
    )
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="APS-2BM-RotaryStage",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
            alternate_identifiers=identifiers,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].alternate_identifiers == identifiers


@pytest.mark.unit
def test_decide_defaults_alternate_identifiers_to_empty_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Stage",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].alternate_identifiers == frozenset()


@pytest.mark.unit
def test_register_asset_with_zero_owners_succeeds() -> None:
    """Aggregate-level cardinality is 0-n; an empty owners frozenset
    is valid at registration."""
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="2-BM",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
            owners=frozenset(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=_facility_result("cora"),
    )
    assert events[0].owners == frozenset()


@pytest.mark.unit
def test_register_asset_with_one_owner_succeeds() -> None:
    owner = AssetOwner(
        name=AssetOwnerName("HZB"),
        contact=AssetOwnerContact("ops@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="HZB-Instrument",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
            owners=frozenset({owner}),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=_facility_result("cora"),
    )
    assert events[0].owners == frozenset({owner})


@pytest.mark.unit
def test_register_asset_with_three_owners_succeeds() -> None:
    owners = frozenset(
        {
            AssetOwner(name=AssetOwnerName("HZB")),
            AssetOwner(name=AssetOwnerName("APS")),
            AssetOwner(name=AssetOwnerName("ESRF")),
        }
    )
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Shared-Instrument",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
            owners=owners,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=_facility_result("cora"),
    )
    assert events[0].owners == owners


@pytest.mark.unit
def test_register_asset_with_duplicate_owner_names_raises_already_present_error() -> None:
    """Two AssetOwner VOs in the same payload sharing `name` (with
    different optional fields so the frozenset doesn't dedupe them at
    the type level) must surface as AssetOwnerAlreadyPresentError."""
    first = AssetOwner(name=AssetOwnerName("HZB"), contact=AssetOwnerContact("a@hzb.de"))
    second = AssetOwner(name=AssetOwnerName("HZB"), contact=AssetOwnerContact("b@hzb.de"))
    with pytest.raises(AssetOwnerAlreadyPresentError) as exc_info:
        register_asset.decide(
            state=None,
            command=RegisterAsset(
                name="X",
                tier=AssetTier.UNIT,
                parent_id=uuid4(),
                owners=frozenset({first, second}),
            ),
            now=_NOW,
            new_id=uuid4(),
            commissioned_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )
    assert exc_info.value.name.value == "HZB"


@pytest.mark.unit
def test_register_asset_emits_owners_in_payload() -> None:
    owners = frozenset({AssetOwner(name=AssetOwnerName("HZB"))})
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="X",
            tier=AssetTier.UNIT,
            parent_id=uuid4(),
            owners=owners,
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert isinstance(events[0], AssetRegistered)
    assert events[0].owners == owners


@pytest.mark.unit
def test_decide_defaults_owners_to_empty_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Stage",
            tier=AssetTier.DEVICE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert events[0].owners == frozenset()


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    parent_id = uuid4()
    command = RegisterAsset(name="Stage", tier=AssetTier.DEVICE, parent_id=parent_id)
    first = register_asset.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    second = register_asset.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    assert first == second
