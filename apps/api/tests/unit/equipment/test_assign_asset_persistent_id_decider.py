"""Unit tests for the `assign_asset_persistent_id` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssigned,
    AssetPersistentIdAssignmentForbiddenError,
)
from cora.equipment.features import assign_asset_persistent_id
from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    persistent_id: PersistentIdentifier | None = None,
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-X"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        persistent_id=persistent_id,
    )


def _doi(value: str = "10.5281/zenodo.1234567") -> PersistentIdentifier:
    return PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value=value)


def _handle(value: str = "20.500.12613/12345") -> PersistentIdentifier:
    return PersistentIdentifier(scheme=PersistentIdentifierScheme.HANDLE, value=value)


def _cmd(asset_id: object) -> AssignAssetPersistentId:
    return AssignAssetPersistentId(
        asset_id=asset_id,  # type: ignore[arg-type]
        scheme=PersistentIdentifierScheme.DOI,
    )


def test_decider_with_no_prior_assign_emits_one_event() -> None:
    state = _asset()
    identifier = _doi()
    events = assign_asset_persistent_id.decide(
        state,
        _cmd(state.id),
        persistent_id=identifier,
        now=_NOW,
    )
    assert events == [
        AssetPersistentIdAssigned(
            asset_id=state.id,
            persistent_id_scheme=identifier.scheme.value,
            persistent_id_value=identifier.value,
            occurred_at=_NOW,
        )
    ]


def test_decider_with_decommissioned_asset_raises_assignment_forbidden_error() -> None:
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    identifier = _doi()
    with pytest.raises(AssetPersistentIdAssignmentForbiddenError) as exc_info:
        assign_asset_persistent_id.decide(
            state,
            _cmd(state.id),
            persistent_id=identifier,
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.attempted == identifier
    assert "Decommissioned" in exc_info.value.reason


def test_decider_with_already_assigned_same_value_raises_already_assigned_error() -> None:
    """Set-once is keyed on the slot, not the value: a retry with the
    same (scheme, value) collapses to AssetPersistentIdAlreadyAssignedError."""
    existing = _doi("10.5281/zenodo.1234567")
    state = _asset(persistent_id=existing)
    with pytest.raises(AssetPersistentIdAlreadyAssignedError) as exc_info:
        assign_asset_persistent_id.decide(
            state,
            _cmd(state.id),
            persistent_id=existing,
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current == existing
    assert exc_info.value.attempted == existing


def test_decider_with_already_assigned_different_value_raises_already_assigned_error() -> None:
    existing = _doi("10.5281/zenodo.1111111")
    attempted = _doi("10.5281/zenodo.2222222")
    state = _asset(persistent_id=existing)
    with pytest.raises(AssetPersistentIdAlreadyAssignedError) as exc_info:
        assign_asset_persistent_id.decide(
            state,
            _cmd(state.id),
            persistent_id=attempted,
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current == existing
    assert exc_info.value.attempted == attempted


def test_decider_with_already_assigned_different_scheme_raises_already_assigned_error() -> None:
    existing = _doi("10.5281/zenodo.1234567")
    attempted = _handle("20.500.12613/12345")
    state = _asset(persistent_id=existing)
    with pytest.raises(AssetPersistentIdAlreadyAssignedError) as exc_info:
        assign_asset_persistent_id.decide(
            state,
            _cmd(state.id),
            persistent_id=attempted,
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current == existing
    assert exc_info.value.attempted == attempted


def test_decider_with_none_state_raises_asset_not_found_error() -> None:
    target_id = uuid4()
    identifier = _doi()
    with pytest.raises(AssetNotFoundError) as exc_info:
        assign_asset_persistent_id.decide(
            None,
            _cmd(target_id),
            persistent_id=identifier,
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id
