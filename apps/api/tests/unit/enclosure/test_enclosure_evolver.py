"""Enclosure evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureDecommissioned,
    EnclosureLifecycle,
    EnclosureName,
    EnclosurePermitObserved,
    EnclosurePermitStatus,
    EnclosureRegistered,
    evolve,
    fold,
)
from cora.shared.identity import ActorId, MonitorSourceId

_ENCLOSURE_ID = EnclosureId(UUID("01900000-0000-7000-8000-00000000e001"))
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-00000000a001")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac01"))
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-000000000c01"))
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_OBSERVED_AT = datetime(2026, 6, 8, 12, 5, 0, tzinfo=UTC)
_DECOMMISSIONED_AT = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)


def _genesis() -> EnclosureRegistered:
    return EnclosureRegistered(
        enclosure_id=_ENCLOSURE_ID,
        name="2-BM Hutch A",
        containing_asset_id=_CONTAINING_ASSET_ID,
        registered_by=_ACTOR_ID,
        occurred_at=_REGISTERED_AT,
    )


# ---------- genesis arm ----------


@pytest.mark.unit
def test_fold_genesis_lands_active_with_unknown_permit() -> None:
    state = fold([_genesis()])
    assert state == Enclosure(
        id=_ENCLOSURE_ID,
        name=EnclosureName("2-BM Hutch A"),
        containing_asset_id=_CONTAINING_ASSET_ID,
        permit_status=EnclosurePermitStatus.UNKNOWN,
        lifecycle=EnclosureLifecycle.ACTIVE,
        registered_at=_REGISTERED_AT,
        registered_by=_ACTOR_ID,
        decommissioned_at=None,
        decommissioned_by=None,
    )


# ---------- permit-observation arm ----------


@pytest.mark.unit
def test_fold_genesis_then_permit_observed_transitions_permit_status_preserves_other_fields() -> (
    None
):
    state = fold(
        [
            _genesis(),
            EnclosurePermitObserved(
                enclosure_id=_ENCLOSURE_ID,
                from_status="Unknown",
                to_status="Permitted",
                reason="search-and-secure complete",
                trigger="Monitor",
                triggered_by=_MONITOR_SOURCE_ID,
                occurred_at=_OBSERVED_AT,
                monitor_ref="psm:hutch-a",
            ),
        ]
    )
    assert state is not None
    assert state.permit_status is EnclosurePermitStatus.PERMITTED
    # Every other field preserved: envelope is NOT folded to state.
    assert state.id == _ENCLOSURE_ID
    assert state.name == EnclosureName("2-BM Hutch A")
    assert state.containing_asset_id == _CONTAINING_ASSET_ID
    assert state.lifecycle is EnclosureLifecycle.ACTIVE
    assert state.registered_at == _REGISTERED_AT
    assert state.registered_by == _ACTOR_ID
    assert state.decommissioned_at is None
    assert state.decommissioned_by is None


# ---------- decommission arm ----------


@pytest.mark.unit
def test_fold_decommission_transitions_lifecycle_and_preserves_permit_status() -> None:
    state = fold(
        [
            _genesis(),
            EnclosurePermitObserved(
                enclosure_id=_ENCLOSURE_ID,
                from_status="Unknown",
                to_status="NotPermitted",
                reason="door open",
                trigger="Monitor",
                triggered_by=_MONITOR_SOURCE_ID,
                occurred_at=_OBSERVED_AT,
                monitor_ref="psm:hutch-a",
            ),
            EnclosureDecommissioned(
                enclosure_id=_ENCLOSURE_ID,
                reason="hutch retired",
                triggered_by=_ACTOR_ID,
                occurred_at=_DECOMMISSIONED_AT,
            ),
        ]
    )
    assert state is not None
    assert state.lifecycle is EnclosureLifecycle.DECOMMISSIONED
    assert state.decommissioned_at == _DECOMMISSIONED_AT
    assert state.decommissioned_by == _ACTOR_ID
    # Permit status preserved as audit trail across the terminal transition.
    assert state.permit_status is EnclosurePermitStatus.NOT_PERMITTED
    # Identity + address preserved.
    assert state.id == _ENCLOSURE_ID
    assert state.name == EnclosureName("2-BM Hutch A")
    assert state.containing_asset_id == _CONTAINING_ASSET_ID
    assert state.registered_at == _REGISTERED_AT
    assert state.registered_by == _ACTOR_ID


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    """Empty event stream folds to None, mirroring the Facility precedent."""
    assert fold([]) is None


@pytest.mark.unit
def test_evolve_permit_observed_to_unknown_preserves_other_fields() -> None:
    """`to_status="Unknown"` round-trips through the evolver; covers the third enum arm."""
    state = fold(
        [
            _genesis(),
            EnclosurePermitObserved(
                enclosure_id=_ENCLOSURE_ID,
                from_status="Permitted",
                to_status="Unknown",
                reason="monitor link lost",
                trigger="Monitor",
                triggered_by=_MONITOR_SOURCE_ID,
                occurred_at=_OBSERVED_AT,
                monitor_ref="psm:hutch-a",
            ),
        ]
    )
    assert state is not None
    assert state.permit_status is EnclosurePermitStatus.UNKNOWN
    assert state.id == _ENCLOSURE_ID
    assert state.name == EnclosureName("2-BM Hutch A")
    assert state.containing_asset_id == _CONTAINING_ASSET_ID
    assert state.lifecycle is EnclosureLifecycle.ACTIVE
    assert state.registered_at == _REGISTERED_AT
    assert state.registered_by == _ACTOR_ID
    assert state.decommissioned_at is None
    assert state.decommissioned_by is None


@pytest.mark.unit
def test_evolve_permit_observed_on_none_state_raises_value_error() -> None:
    """Transition events on empty state raise ValueError via `require_state`."""
    with pytest.raises(ValueError):
        evolve(
            None,
            EnclosurePermitObserved(
                enclosure_id=_ENCLOSURE_ID,
                from_status="Unknown",
                to_status="Permitted",
                reason="search-and-secure complete",
                trigger="Monitor",
                triggered_by=_MONITOR_SOURCE_ID,
                occurred_at=_OBSERVED_AT,
                monitor_ref="psm:hutch-a",
            ),
        )


@pytest.mark.unit
def test_evolve_decommission_on_none_state_raises_value_error() -> None:
    """Terminal transition on empty state raises ValueError via `require_state`."""
    with pytest.raises(ValueError):
        evolve(
            None,
            EnclosureDecommissioned(
                enclosure_id=_ENCLOSURE_ID,
                reason="hutch retired",
                triggered_by=_ACTOR_ID,
                occurred_at=_DECOMMISSIONED_AT,
            ),
        )
