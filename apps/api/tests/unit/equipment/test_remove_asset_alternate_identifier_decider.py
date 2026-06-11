"""Unit tests for the `remove_asset_alternate_identifier` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlternateIdentifierNotPresentError,
    AssetAlternateIdentifierRemoved,
    AssetCannotAddAlternateIdentifierError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import remove_asset_alternate_identifier
from cora.equipment.features.remove_asset_alternate_identifier import (
    RemoveAssetAlternateIdentifier,
)
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
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
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        alternate_identifiers=alternate_identifiers,
    )


@pytest.mark.unit
def test_decide_emits_event_when_removing_existing_identifier() -> None:
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    state = _asset(alternate_identifiers=frozenset({identifier}))
    events = remove_asset_alternate_identifier.decide(
        state=state,
        command=RemoveAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=identifier),
        now=_NOW,
    )
    assert events == [
        AssetAlternateIdentifierRemoved(
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
        remove_asset_alternate_identifier.decide(
            state=None,
            command=RemoveAssetAlternateIdentifier(
                asset_id=target_id, alternate_identifier=identifier
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_not_present_when_pair_missing() -> None:
    """Strict-not-idempotent: removing a non-existent (kind, value) pair raises."""
    existing = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    missing = AlternateIdentifier(kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-0042")
    state = _asset(alternate_identifiers=frozenset({existing}))
    with pytest.raises(AssetAlternateIdentifierNotPresentError) as exc_info:
        remove_asset_alternate_identifier.decide(
            state=state,
            command=RemoveAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=missing),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.identifier == missing


@pytest.mark.unit
def test_decide_raises_not_present_when_kind_differs_but_value_matches() -> None:
    """Exact (kind, value) pair match: same value under a different kind
    is not considered the same identifier."""
    existing = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="ABC-9")
    same_value_other_kind = AlternateIdentifier(
        kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="ABC-9"
    )
    state = _asset(alternate_identifiers=frozenset({existing}))
    with pytest.raises(AssetAlternateIdentifierNotPresentError):
        remove_asset_alternate_identifier.decide(
            state=state,
            command=RemoveAssetAlternateIdentifier(
                asset_id=state.id, alternate_identifier=same_value_other_kind
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_removes_only_matched_pair_when_multiple_exist() -> None:
    """The decider's job is to emit the AssetAlternateIdentifierRemoved
    event with the matched pair; the evolver removes by pair, leaving
    siblings."""
    a = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="A")
    b = AlternateIdentifier(kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="B")
    c = AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="C")
    state = _asset(alternate_identifiers=frozenset({a, b, c}))
    events = remove_asset_alternate_identifier.decide(
        state=state,
        command=RemoveAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=b),
        now=_NOW,
    )
    assert events == [
        AssetAlternateIdentifierRemoved(
            asset_id=state.id,
            alternate_identifier=b,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_decommissioned() -> None:
    """Lifecycle guard mirrors `remove_asset_port`: a Decommissioned
    asset is out of inventory; identifier changes are not allowed.
    Uses the shared `AssetCannotAddAlternateIdentifierError` class
    (same class as the add decider, per state.py:317-342)."""
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")
    state = _asset(
        lifecycle=AssetLifecycle.DECOMMISSIONED,
        alternate_identifiers=frozenset({identifier}),
    )
    with pytest.raises(AssetCannotAddAlternateIdentifierError) as exc_info:
        remove_asset_alternate_identifier.decide(
            state=state,
            command=RemoveAssetAlternateIdentifier(
                asset_id=state.id, alternate_identifier=identifier
            ),
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
    state. Symmetric with `remove_asset_port`."""
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="x")
    state = _asset(lifecycle=lifecycle, alternate_identifiers=frozenset({identifier}))
    events = remove_asset_alternate_identifier.decide(
        state=state,
        command=RemoveAssetAlternateIdentifier(asset_id=state.id, alternate_identifier=identifier),
        now=_NOW,
    )
    assert len(events) == 1
