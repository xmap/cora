"""Unit tests for the `register_asset` slice's pure decider.

Covers the create-style invariants (state empty, name validation)
plus the hierarchy rule (Enterprise null-parent, others required).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.asset import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    Asset,
    AssetAlreadyExistsError,
    AssetLevel,
    AssetName,
    AssetRegistered,
    InvalidAssetNameError,
    InvalidAssetParentError,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_asset_registered_for_enterprise_with_null_parent() -> None:
    new_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(name="ANL", level=AssetLevel.ENTERPRISE, parent_id=None),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        AssetRegistered(
            asset_id=new_id,
            name="ANL",
            level="Enterprise",
            parent_id=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_asset_registered_for_site_with_parent() -> None:
    new_id = uuid4()
    parent_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(name="APS", level=AssetLevel.SITE, parent_id=parent_id),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        AssetRegistered(
            asset_id=new_id,
            name="APS",
            level="Site",
            parent_id=parent_id,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    parent_id = uuid4()
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(name="  Eiger-2X-9M  ", level=AssetLevel.DEVICE, parent_id=parent_id),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Eiger-2X-9M"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidAssetNameError):
        register_asset.decide(
            state=None,
            command=RegisterAsset(name="", level=AssetLevel.SITE, parent_id=uuid4()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Asset(
        id=uuid4(),
        name=AssetName("APS"),
        level=AssetLevel.SITE,
        parent_id=uuid4(),
    )
    with pytest.raises(AssetAlreadyExistsError) as exc_info:
        register_asset.decide(
            state=existing,
            command=RegisterAsset(name="Other", level=AssetLevel.SITE, parent_id=uuid4()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.asset_id == existing.id


# ---------- Hierarchy rule (the 5b-locked invariant) ----------


@pytest.mark.unit
def test_decide_rejects_enterprise_with_non_null_parent() -> None:
    """Enterprise is the root level — supplying a parent violates the
    single-parent-tree contract. Pin so a future relaxation that
    treats Enterprise as just-another-level (for example, for federated
    multi-Enterprise setups) is a deliberate change."""
    parent_id = uuid4()
    with pytest.raises(InvalidAssetParentError) as exc_info:
        register_asset.decide(
            state=None,
            command=RegisterAsset(
                name="Federated-ANL",
                level=AssetLevel.ENTERPRISE,
                parent_id=parent_id,
            ),
            now=_NOW,
            new_id=uuid4(),
        )
    assert "Enterprise" in str(exc_info.value)
    assert str(parent_id) in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "level",
    [
        AssetLevel.SITE,
        AssetLevel.AREA,
        AssetLevel.UNIT,
        AssetLevel.COMPONENT,
        AssetLevel.DEVICE,
    ],
)
def test_decide_rejects_non_enterprise_with_null_parent(level: AssetLevel) -> None:
    """All non-Enterprise levels MUST have a parent. Five wrong-state
    cases tested explicitly so a future relaxation has to flip every
    parametrized case deliberately."""
    with pytest.raises(InvalidAssetParentError) as exc_info:
        register_asset.decide(
            state=None,
            command=RegisterAsset(name="Any", level=level, parent_id=None),
            now=_NOW,
            new_id=uuid4(),
        )
    assert level.value in str(exc_info.value)


@pytest.mark.unit
def test_decide_carries_drawing_through_to_emitted_event() -> None:
    """Happy path: an optional Drawing supplied on the command rides
    the AssetRegistered event without modification."""
    drawing = Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A")
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="Microscope-2BM-A",
            level=AssetLevel.COMPONENT,
            parent_id=uuid4(),
            drawing=drawing,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].drawing == drawing


@pytest.mark.unit
def test_decide_defaults_drawing_to_none_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="APS",
            level=AssetLevel.SITE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
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
            level=AssetLevel.COMPONENT,
            parent_id=uuid4(),
            model_id=model_id,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].model_id == model_id


@pytest.mark.unit
def test_decide_defaults_model_id_to_none_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="APS",
            level=AssetLevel.SITE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].model_id is None


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
            level=AssetLevel.DEVICE,
            parent_id=uuid4(),
            alternate_identifiers=identifiers,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].alternate_identifiers == identifiers


@pytest.mark.unit
def test_decide_defaults_alternate_identifiers_to_empty_when_omitted() -> None:
    events = register_asset.decide(
        state=None,
        command=RegisterAsset(
            name="APS",
            level=AssetLevel.SITE,
            parent_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].alternate_identifiers == frozenset()


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    parent_id = uuid4()
    command = RegisterAsset(name="APS", level=AssetLevel.SITE, parent_id=parent_id)
    first = register_asset.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = register_asset.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
