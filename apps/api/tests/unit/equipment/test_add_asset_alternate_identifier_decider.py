"""Unit tests for the `add_asset_alternate_identifier` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    Asset,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierAlreadyPresentError,
    AssetCannotAddAlternateIdentifierError,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    InvalidAlternateIdentifierValueError,
)
from cora.equipment.features import add_asset_alternate_identifier
from cora.equipment.features.add_asset_alternate_identifier import (
    AddAssetAlternateIdentifier,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    alternate_identifiers: frozenset[AlternateIdentifier] = frozenset(),
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-X"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        alternate_identifiers=alternate_identifiers,
    )


@pytest.mark.unit
def test_decide_emits_event_when_adding_first_identifier() -> None:
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    state = _asset()
    events = add_asset_alternate_identifier.decide(
        state=state,
        command=AddAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=identifier),
        now=_NOW,
    )
    assert events == [
        AssetAlternateIdentifierAdded(
            asset_id=state.id,
            alternate_identifier=identifier,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    with pytest.raises(AssetNotFoundError) as exc_info:
        add_asset_alternate_identifier.decide(
            state=None,
            command=AddAssetAlternateIdentifier(
                asset_id=target_id, alternate_identifier=identifier
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_already_present_when_pair_exists() -> None:
    """Strict-not-idempotent: re-adding the same (kind, value) pair raises."""
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    state = _asset(alternate_identifiers=frozenset({identifier}))
    with pytest.raises(AssetAlternateIdentifierAlreadyPresentError) as exc_info:
        add_asset_alternate_identifier.decide(
            state=state,
            command=AddAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=identifier),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.identifier == identifier


@pytest.mark.unit
def test_decide_allows_same_value_under_different_kind() -> None:
    """Uniqueness keyed on the full (kind, value) pair: the same value
    under a different kind is a distinct identifier."""
    existing = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="ABC-9")
    same_value_other_kind = AlternateIdentifier(
        kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="ABC-9"
    )
    state = _asset(alternate_identifiers=frozenset({existing}))
    events = add_asset_alternate_identifier.decide(
        state=state,
        command=AddAssetAlternateIdentifier(
            asset_id=state.id, alternate_identifier=same_value_other_kind
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_propagates_invalid_value_error_from_vo() -> None:
    """Empty value surfaces as InvalidAlternateIdentifierValueError at
    VO construction time (mapped to HTTP 400 by the BC's exception
    handler)."""
    with pytest.raises(InvalidAlternateIdentifierValueError):
        AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="   ")


@pytest.mark.unit
def test_decide_rejects_decommissioned() -> None:
    """Lifecycle guard mirrors `add_asset_port`: a Decommissioned
    asset is out of inventory; identifier changes are not allowed."""
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotAddAlternateIdentifierError) as exc_info:
        add_asset_alternate_identifier.decide(
            state=state,
            command=AddAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=identifier),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.kind is AlternateIdentifierKind.SERIAL_NUMBER
    assert exc_info.value.value == "XYZ-001"
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_succeeds_for_every_non_decommissioned_lifecycle(
    lifecycle: AssetLifecycle,
) -> None:
    """Lifecycle-independence holds across every non-Decommissioned
    state. Symmetric with `add_asset_port`."""
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="x")
    state = _asset(lifecycle=lifecycle)
    events = add_asset_alternate_identifier.decide(
        state=state,
        command=AddAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=identifier),
        now=_NOW,
    )
    assert len(events) == 1
