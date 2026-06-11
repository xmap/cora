"""Property-based tests for `assign_asset_persistent_id.decide`.

Required PBT per the `test_decider_changes_require_paired_pbt`
architecture fitness. Mirrors the sibling
`test_add_asset_alternate_identifier_decider_properties.py` shape:
Hypothesis strategies generate `(scheme, value)` pairs spanning the
full closed `PersistentIdentifierScheme` enum and asset lifecycles
spanning all non-Decommissioned values, plus prior-state variants
(absent vs already-assigned).

Properties asserted (per memo section 13.5):
  - emits_one_event: purity + single-event invariant on the happy path
  - decommissioned_always_raises_forbidden: lifecycle gate per L8
  - state_persistent_id_set_always_raises_already_assigned: set-once per L3 + L7
  - emitted_event_matches_resolved_persistent_id: event-shape invariant per L6
  - decider_deterministic_given_state_and_args: purity (no clock, no minter)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssigned,
    AssetPersistentIdAssignmentForbiddenError,
    AssetTier,
)
from cora.equipment.features import assign_asset_persistent_id
from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.shared.identifier import (
    PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

if TYPE_CHECKING:
    from uuid import UUID

pytestmark = pytest.mark.timeout(60, method="thread")

_NON_DECOMMISSIONED_LIFECYCLE = st.sampled_from(
    [lc for lc in AssetLifecycle if lc is not AssetLifecycle.DECOMMISSIONED]
)
_SCHEME = st.sampled_from(list(PersistentIdentifierScheme))
_VALID_VALUE = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
)
_DT_BASE = datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)


@st.composite
def _persistent_identifier(draw: st.DrawFn) -> PersistentIdentifier:
    return PersistentIdentifier(scheme=draw(_SCHEME), value=draw(_VALID_VALUE))


def _asset(
    asset_id: UUID,
    *,
    lifecycle: AssetLifecycle,
    persistent_id: PersistentIdentifier | None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Detector-X"),
        tier=AssetTier.DEVICE,
        parent_id=asset_id,  # any UUID; non-root requires non-null
        lifecycle=lifecycle,
        persistent_id=persistent_id,
    )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_assign_with_valid_inputs_emits_one_event(
    asset_id: UUID,
    persistent_id: PersistentIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Happy path: absent persistent_id on any non-Decommissioned state
    -> single AssetPersistentIdAssigned event carrying the injected
    timestamp and resolved scheme + value."""
    state = _asset(asset_id, lifecycle=lifecycle, persistent_id=None)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignAssetPersistentId(asset_id=asset_id, scheme=persistent_id.scheme)
    events = assign_asset_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    assert events == [
        AssetPersistentIdAssigned(
            asset_id=asset_id,
            persistent_id_scheme=persistent_id.scheme.value,
            persistent_id_value=persistent_id.value,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_assign_with_decommissioned_lifecycle_always_raises_forbidden(
    asset_id: UUID,
    persistent_id: PersistentIdentifier,
    seconds_offset: int,
) -> None:
    """Lifecycle gate fires regardless of whether persistent_id is
    already assigned: Decommissioned + any persistent_id command ->
    AssetPersistentIdAssignmentForbiddenError. Per L8."""
    state = _asset(
        asset_id,
        lifecycle=AssetLifecycle.DECOMMISSIONED,
        persistent_id=None,
    )
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignAssetPersistentId(asset_id=asset_id, scheme=persistent_id.scheme)
    with pytest.raises(AssetPersistentIdAssignmentForbiddenError) as exc:
        assign_asset_persistent_id.decide(
            state,
            command,
            persistent_id=persistent_id,
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.attempted == persistent_id
    assert "Decommissioned" in exc.value.reason


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    current=_persistent_identifier(),
    attempted=_persistent_identifier(),
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_assign_with_state_persistent_id_set_always_raises_already_assigned(
    asset_id: UUID,
    current: PersistentIdentifier,
    attempted: PersistentIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Set-once: once state.persistent_id is set, BOTH same-value and
    different-value retries raise AssetPersistentIdAlreadyAssignedError
    in any non-Decommissioned lifecycle. Per L3 + L7."""
    state = _asset(asset_id, lifecycle=lifecycle, persistent_id=current)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignAssetPersistentId(asset_id=asset_id, scheme=attempted.scheme)
    with pytest.raises(AssetPersistentIdAlreadyAssignedError) as exc:
        assign_asset_persistent_id.decide(
            state,
            command,
            persistent_id=attempted,
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.current == current
    assert exc.value.attempted == attempted


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_emitted_event_scheme_and_value_match_resolved_persistent_id(
    asset_id: UUID,
    persistent_id: PersistentIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Event-shape invariant per L6: the emitted event's
    persistent_id_scheme and persistent_id_value are the byte-for-byte
    StrEnum value and trimmed string from the resolved VO. No
    translation, no normalization at the decider."""
    state = _asset(asset_id, lifecycle=lifecycle, persistent_id=None)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignAssetPersistentId(asset_id=asset_id, scheme=persistent_id.scheme)
    events = assign_asset_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssetPersistentIdAssigned)
    assert event.persistent_id_scheme == persistent_id.scheme.value
    assert event.persistent_id_value == persistent_id.value
    assert event.asset_id == asset_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    other=_persistent_identifier(),
    lifecycle=_NON_DECOMMISSIONED_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_decider_is_deterministic_given_state_and_args(
    asset_id: UUID,
    persistent_id: PersistentIdentifier,
    other: PersistentIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Purity: two calls with identical (state, asset_id,
    persistent_id, now) return identical events. No hidden clock, no
    minter call, no id leakage. Restricted to non-Decommissioned with
    absent prior persistent_id so the happy-path branch is exercised."""
    assume(persistent_id != other)
    state = _asset(asset_id, lifecycle=lifecycle, persistent_id=None)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignAssetPersistentId(asset_id=asset_id, scheme=persistent_id.scheme)
    first = assign_asset_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    second = assign_asset_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    assert first == second


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_state_none_always_raises_asset_not_found(
    asset_id: UUID,
    persistent_id: PersistentIdentifier,
    seconds_offset: int,
) -> None:
    """state=None -> AssetNotFoundError regardless of persistent_id or now."""
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignAssetPersistentId(asset_id=asset_id, scheme=persistent_id.scheme)
    with pytest.raises(AssetNotFoundError) as exc:
        assign_asset_persistent_id.decide(
            None,
            command,
            persistent_id=persistent_id,
            now=now,
        )
    assert exc.value.asset_id == asset_id
