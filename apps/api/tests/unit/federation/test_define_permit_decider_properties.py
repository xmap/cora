"""Property-based tests for `define_permit.decide` (Federation BC).

Mirrors the Access / Trust decider-PBT pattern on the most invariant-
rich Federation create-style command. Universal claims across
generated inputs:

  - state=None + valid OutboundTerms command emits a single
    PermitDefined with the injected ids / now and trimmed
    peer_facility_id.
  - state=Permit always raises PermitAlreadyExistsError, regardless
    of command.
  - expires_at <= now always raises InvalidPermitScopeError.
  - Direction.OUTBOUND with InboundTerms (and vice versa) always
    raises InvalidPermitScopeError.
  - Pure: same (state, command, now, new_id, defined_by)
    returns the same events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    InboundTerms,
    InvalidPermitScopeError,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitAlreadyExistsError,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import define_permit
from cora.federation.features.define_permit import DefinePermit
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID

_PEER_FACILITY = printable_ascii_text(min_size=1, max_size=64)
_PAYLOAD_TYPE = printable_ascii_text(min_size=1, max_size=32)
_ARTIFACT_KIND = printable_ascii_text(min_size=1, max_size=32)
_ABI_TIER = st.sampled_from(list(AbiTier))


def _scope_ref() -> ScopeRef:
    return ScopeRef(kind="dataset", name="public", qualifier=None)


def _outbound_terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({_scope_ref()}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _inbound_terms() -> InboundTerms:
    return InboundTerms(inbound_allowed_artifact_kinds=frozenset({"dataset"}))


def _command(
    *,
    peer_facility_id: str,
    direction: Direction,
    expires_at: datetime,
    credential_id: UUID,
    payload_type: str,
    artifact_kind: str,
    abi_tier: AbiTier,
    terms: OutboundTerms | InboundTerms,
) -> DefinePermit:
    return DefinePermit(
        peer_facility_id=peer_facility_id,
        direction=direction,
        allowed_credential_ids=frozenset({credential_id}),
        allowed_payload_types=frozenset({payload_type}),
        allowed_artifact_kinds=frozenset({artifact_kind}),
        abi_tier_floor=abi_tier,
        expires_at=expires_at,
        terms=terms,
    )


def _existing_permit(permit_id: UUID, actor_id: UUID) -> Permit:
    return Permit(
        id=permit_id,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({actor_id}),
        allowed_payload_types=frozenset({"application/json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
        defined_by=ActorId(actor_id),
        defined_at=datetime(2026, 1, 1, tzinfo=UTC),
        status=PermitStatus.DEFINED,
        terms=_outbound_terms(),
    )


@pytest.mark.unit
@given(
    peer_facility_id=_PEER_FACILITY,
    payload_type=_PAYLOAD_TYPE,
    artifact_kind=_ARTIFACT_KIND,
    abi_tier=_ABI_TIER,
    now=aware_datetimes(),
    new_id=st.uuids(),
    actor_id=st.uuids(),
    credential_id=st.uuids(),
)
def test_define_permit_emits_exactly_one_event_with_injected_fields(
    peer_facility_id: str,
    payload_type: str,
    artifact_kind: str,
    abi_tier: AbiTier,
    now: datetime,
    new_id: UUID,
    actor_id: UUID,
    credential_id: UUID,
) -> None:
    """Empty stream + valid OUTBOUND command -> single PermitDefined."""
    expires_at = now + timedelta(days=30)
    terms = _outbound_terms()
    command = _command(
        peer_facility_id=peer_facility_id,
        direction=Direction.OUTBOUND,
        expires_at=expires_at,
        credential_id=credential_id,
        payload_type=payload_type,
        artifact_kind=artifact_kind,
        abi_tier=abi_tier,
        terms=terms,
    )
    events = define_permit.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        defined_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.permit_id == new_id
    assert event.occurred_at == now
    assert event.defined_by == actor_id
    assert event.peer_facility_id == peer_facility_id
    assert event.direction is Direction.OUTBOUND
    assert event.terms == terms


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    peer_facility_id=_PEER_FACILITY,
    payload_type=_PAYLOAD_TYPE,
    artifact_kind=_ARTIFACT_KIND,
    abi_tier=_ABI_TIER,
    now=aware_datetimes(),
    new_id=st.uuids(),
    actor_id=st.uuids(),
    credential_id=st.uuids(),
)
def test_define_permit_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    peer_facility_id: str,
    payload_type: str,
    artifact_kind: str,
    abi_tier: AbiTier,
    now: datetime,
    new_id: UUID,
    actor_id: UUID,
    credential_id: UUID,
) -> None:
    """Any non-None state -> PermitAlreadyExistsError, regardless of command."""
    command = _command(
        peer_facility_id=peer_facility_id,
        direction=Direction.OUTBOUND,
        expires_at=now + timedelta(days=30),
        credential_id=credential_id,
        payload_type=payload_type,
        artifact_kind=artifact_kind,
        abi_tier=abi_tier,
        terms=_outbound_terms(),
    )
    with pytest.raises(PermitAlreadyExistsError) as exc:
        define_permit.decide(
            state=_existing_permit(existing_id, actor_id),
            command=command,
            now=now,
            new_id=new_id,
            defined_by=ActorId(actor_id),
        )
    assert exc.value.permit_id == existing_id


@pytest.mark.unit
@given(
    peer_facility_id=_PEER_FACILITY,
    payload_type=_PAYLOAD_TYPE,
    artifact_kind=_ARTIFACT_KIND,
    abi_tier=_ABI_TIER,
    now=aware_datetimes(),
    new_id=st.uuids(),
    actor_id=st.uuids(),
    credential_id=st.uuids(),
    backshift_seconds=st.integers(min_value=0, max_value=86_400 * 365),
)
def test_define_permit_with_expired_at_in_past_always_raises_invalid_scope(
    peer_facility_id: str,
    payload_type: str,
    artifact_kind: str,
    abi_tier: AbiTier,
    now: datetime,
    new_id: UUID,
    actor_id: UUID,
    credential_id: UUID,
    backshift_seconds: int,
) -> None:
    """expires_at <= now -> InvalidPermitScopeError."""
    expires_at = now - timedelta(seconds=backshift_seconds)
    command = _command(
        peer_facility_id=peer_facility_id,
        direction=Direction.OUTBOUND,
        expires_at=expires_at,
        credential_id=credential_id,
        payload_type=payload_type,
        artifact_kind=artifact_kind,
        abi_tier=abi_tier,
        terms=_outbound_terms(),
    )
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=ActorId(actor_id),
        )


@pytest.mark.unit
@given(
    peer_facility_id=_PEER_FACILITY,
    payload_type=_PAYLOAD_TYPE,
    artifact_kind=_ARTIFACT_KIND,
    abi_tier=_ABI_TIER,
    now=aware_datetimes(),
    new_id=st.uuids(),
    actor_id=st.uuids(),
    credential_id=st.uuids(),
    direction=st.sampled_from(list(Direction)),
)
def test_define_permit_with_direction_mismatched_terms_always_raises(
    peer_facility_id: str,
    payload_type: str,
    artifact_kind: str,
    abi_tier: AbiTier,
    now: datetime,
    new_id: UUID,
    actor_id: UUID,
    credential_id: UUID,
    direction: Direction,
) -> None:
    """Direction does not match type(terms) -> InvalidPermitScopeError.

    Outbound direction with InboundTerms, or Inbound direction with
    OutboundTerms, must always fail the direction-mirror invariant.
    """
    terms: OutboundTerms | InboundTerms = (
        _inbound_terms() if direction is Direction.OUTBOUND else _outbound_terms()
    )
    command = _command(
        peer_facility_id=peer_facility_id,
        direction=direction,
        expires_at=now + timedelta(days=30),
        credential_id=credential_id,
        payload_type=payload_type,
        artifact_kind=artifact_kind,
        abi_tier=abi_tier,
        terms=terms,
    )
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=ActorId(actor_id),
        )


@pytest.mark.unit
@given(
    peer_facility_id=_PEER_FACILITY,
    payload_type=_PAYLOAD_TYPE,
    artifact_kind=_ARTIFACT_KIND,
    abi_tier=_ABI_TIER,
    now=aware_datetimes(),
    new_id=st.uuids(),
    actor_id=st.uuids(),
    credential_id=st.uuids(),
)
def test_define_permit_is_pure_same_input_same_output(
    peer_facility_id: str,
    payload_type: str,
    artifact_kind: str,
    abi_tier: AbiTier,
    now: datetime,
    new_id: UUID,
    actor_id: UUID,
    credential_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    assume(now < datetime.max.replace(tzinfo=UTC) - timedelta(days=31))
    expires_at = now + timedelta(days=30)
    command = _command(
        peer_facility_id=peer_facility_id,
        direction=Direction.OUTBOUND,
        expires_at=expires_at,
        credential_id=credential_id,
        payload_type=payload_type,
        artifact_kind=artifact_kind,
        abi_tier=abi_tier,
        terms=_outbound_terms(),
    )
    first = define_permit.decide(
        state=None, command=command, now=now, new_id=new_id, defined_by=ActorId(actor_id)
    )
    second = define_permit.decide(
        state=None, command=command, now=now, new_id=new_id, defined_by=ActorId(actor_id)
    )
    assert first == second
