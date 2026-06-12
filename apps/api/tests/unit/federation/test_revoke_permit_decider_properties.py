"""Property-based tests for `revoke_permit.decide` (Federation BC).

Complements the example-based `test_revoke_permit_decider.py` with
universal claims across generated inputs. The decider is a pure
no-reason-required FSM terminal transition

    (state, command, now, revoked_by) -> list[PermitRevoked]

Load-bearing properties:

  - state=None always raises `PermitNotFoundError` carrying
    command.permit_id (existence / genesis guard).
  - The source-state partition is total over `PermitStatus`: every
    non-Revoked status (Defined, Active, Suspended) emits exactly one
    `PermitRevoked` (permit_id=state.id, occurred_at=now,
    revoked_by=<injected>); the sole Revoked status raises
    `PermitCannotRevokeError` carrying state.id + the current status,
    so a future status value cannot silently fall through.
  - The emitted event's permit_id is `state.id`, never
    command.permit_id; revoked_by + now are threaded verbatim from the
    handler-injected args (capture-don't-recompute).
  - Pure: same (state, command, now, revoked_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitCannotRevokeError,
    PermitNotFoundError,
    PermitRevoked,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import revoke_permit
from cora.federation.features.revoke_permit import RevokePermit
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_DEFINED_BY_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed002"))
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed004")

_REVOCABLE_SOURCES = (
    PermitStatus.DEFINED,
    PermitStatus.ACTIVE,
    PermitStatus.SUSPENDED,
)
_DISALLOWED_SOURCES = tuple(s for s in PermitStatus if s not in frozenset(_REVOCABLE_SOURCES))


def _outbound_terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="public", qualifier=None)}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _permit(*, permit_id: UUID, status: PermitStatus, now: datetime) -> Permit:
    return Permit(
        id=permit_id,
        peer_facility_code=FacilityCode("aps-2bm"),
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({_CREDENTIAL_ID}),
        allowed_payload_types=frozenset({"application/json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=now,
        defined_by=_DEFINED_BY_ACTOR_ID,
        defined_at=now,
        status=status,
        terms=_outbound_terms(),
    )


@pytest.mark.unit
@given(permit_id=st.uuids(), now=aware_datetimes(), revoked_by=st.uuids())
def test_revoke_with_none_state_always_raises_not_found(
    permit_id: UUID,
    now: datetime,
    revoked_by: UUID,
) -> None:
    """Empty stream always raises `PermitNotFoundError` carrying command.permit_id."""
    with pytest.raises(PermitNotFoundError) as exc:
        revoke_permit.decide(
            state=None,
            command=RevokePermit(permit_id=permit_id),
            now=now,
            revoked_by=revoked_by,
        )
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    source=st.sampled_from(_REVOCABLE_SOURCES),
    now=aware_datetimes(),
    revoked_by=st.uuids(),
)
def test_revoke_from_any_non_revoked_source_emits_single_event(
    permit_id: UUID,
    source: PermitStatus,
    now: datetime,
    revoked_by: UUID,
) -> None:
    """Every non-Revoked source revokes, emitting one PermitRevoked."""
    events = revoke_permit.decide(
        state=_permit(permit_id=permit_id, status=source, now=now),
        command=RevokePermit(permit_id=permit_id),
        now=now,
        revoked_by=revoked_by,
    )
    assert events == [
        PermitRevoked(
            permit_id=permit_id,
            revoked_by=revoked_by,
            occurred_at=now,
            reason=None,
        )
    ]


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    revoked_by=st.uuids(),
)
def test_revoke_from_revoked_source_always_raises_cannot_revoke(
    permit_id: UUID,
    source: PermitStatus,
    now: datetime,
    revoked_by: UUID,
) -> None:
    """The sole disallowed source (Revoked) raises, carrying state.id + status."""
    with pytest.raises(PermitCannotRevokeError) as exc:
        revoke_permit.decide(
            state=_permit(permit_id=permit_id, status=source, now=now),
            command=RevokePermit(permit_id=permit_id),
            now=now,
            revoked_by=revoked_by,
        )
    assert exc.value.permit_id == permit_id
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_permit_id=st.uuids(),
    command_permit_id=st.uuids(),
    now=aware_datetimes(),
    revoked_by=st.uuids(),
)
def test_revoke_uses_state_id_not_command_permit_id(
    state_permit_id: UUID,
    command_permit_id: UUID,
    now: datetime,
    revoked_by: UUID,
) -> None:
    """The emitted event's permit_id is state.id, not command.permit_id."""
    assume(state_permit_id != command_permit_id)
    events = revoke_permit.decide(
        state=_permit(permit_id=state_permit_id, status=PermitStatus.ACTIVE, now=now),
        command=RevokePermit(permit_id=command_permit_id),
        now=now,
        revoked_by=revoked_by,
    )
    assert events[0].permit_id == state_permit_id


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    now=aware_datetimes(),
    revoked_by=st.uuids(),
    reason=printable_ascii_text(max_size=64),
)
def test_revoke_threads_injected_now_revoked_by_and_reason_onto_event(
    permit_id: UUID,
    now: datetime,
    revoked_by: UUID,
    reason: str,
) -> None:
    """now, revoked_by, and reason are captured verbatim onto the event."""
    events = revoke_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.DEFINED, now=now),
        command=RevokePermit(permit_id=permit_id, reason=reason),
        now=now,
        revoked_by=revoked_by,
    )
    event = events[0]
    assert event.occurred_at == now
    assert event.revoked_by == revoked_by
    assert event.reason == reason


@pytest.mark.unit
@given(permit_id=st.uuids(), now=aware_datetimes(), revoked_by=st.uuids())
def test_revoke_is_pure_same_input_same_output(
    permit_id: UUID,
    now: datetime,
    revoked_by: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _permit(permit_id=permit_id, status=PermitStatus.ACTIVE, now=now)
    command = RevokePermit(permit_id=permit_id)
    first = revoke_permit.decide(state=state, command=command, now=now, revoked_by=revoked_by)
    second = revoke_permit.decide(state=state, command=command, now=now, revoked_by=revoked_by)
    assert first == second
