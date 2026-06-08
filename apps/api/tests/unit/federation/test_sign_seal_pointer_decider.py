"""Unit tests for the `sign_seal_pointer` slice's pure decider.

Pin the FSM single-source guard (Live is the only legal source),
the not-found branch, head-hash shape validation (empty / whitespace
new_head_hash), the strict-monotonic sequence-number guard, purity
(same inputs -> same outputs), and the handler-injected
`signed_by` / `now` capture per the non-determinism
principle (capture, don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import (
    InvalidSealHeadHashError,
    Seal,
    SealCannotSignError,
    SealNotFoundError,
    SealPointerSigned,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.features import sign_seal_pointer
from cora.federation.features.sign_seal_pointer import SignSealPointer
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fec001"))
_OTHER_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fec002"))
_INITIALIZED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))
_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_PRIOR_HEAD_HASH = "a" * 64
_NEW_HEAD_HASH = "b" * 64


def _seal(
    status: SealStatus,
    *,
    current_head_hash: str | None = _PRIOR_HEAD_HASH,
    current_sequence_number: int = 1,
) -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_credential_id=_ONLINE_KEY,
        offline_credential_id=_OFFLINE_KEY,
        current_head_hash=current_head_hash,
        current_sequence_number=current_sequence_number,
        initialized_by=_INITIALIZED_BY,
        initialized_at=_NOW,
        status=status,
    )


def _command(
    *,
    new_head_hash: str = _NEW_HEAD_HASH,
    new_sequence_number: int = 2,
) -> SignSealPointer:
    return SignSealPointer(
        facility_id=_FACILITY_ID,
        new_head_hash=new_head_hash,
        new_sequence_number=new_sequence_number,
    )


@pytest.mark.unit
def test_sign_seal_pointer_emits_event_when_state_is_live() -> None:
    state = _seal(SealStatus.LIVE)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    assert events == [
        SealPointerSigned(
            facility_id=_FACILITY_ID,
            head_hash=_NEW_HEAD_HASH,
            sequence_number=2,
            signed_at=_NOW,
            signed_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_sign_seal_pointer_raises_not_found_when_state_is_none() -> None:
    with pytest.raises(SealNotFoundError):
        sign_seal_pointer.decide(
            state=None,
            command=_command(),
            now=_NOW,
            signed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_sign_seal_pointer_raises_cannot_sign_when_republishing() -> None:
    """Single-source: signing from Republishing rejects with cannot-sign."""
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(SealCannotSignError) as exc:
        sign_seal_pointer.decide(
            state=state,
            command=_command(),
            now=_NOW,
            signed_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.current_status is SealStatus.REPUBLISHING


@pytest.mark.unit
def test_sign_seal_pointer_rejects_empty_new_head_hash() -> None:
    """`new_head_hash` must be non-empty after trimming."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(InvalidSealHeadHashError) as exc:
        sign_seal_pointer.decide(
            state=state,
            command=_command(new_head_hash=""),
            now=_NOW,
            signed_by=_PRINCIPAL_ID,
        )
    assert "new_head_hash" in exc.value.reason


@pytest.mark.unit
def test_sign_seal_pointer_rejects_whitespace_new_head_hash() -> None:
    """Whitespace-only `new_head_hash` is structurally empty after trim."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(InvalidSealHeadHashError) as exc:
        sign_seal_pointer.decide(
            state=state,
            command=_command(new_head_hash="   \t  "),
            now=_NOW,
            signed_by=_PRINCIPAL_ID,
        )
    assert "new_head_hash" in exc.value.reason


@pytest.mark.unit
def test_sign_seal_pointer_trims_new_head_hash_before_capture() -> None:
    """Decider trims surrounding whitespace before stamping head_hash."""
    state = _seal(SealStatus.LIVE)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(new_head_hash=f"  {_NEW_HEAD_HASH}  "),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].head_hash == _NEW_HEAD_HASH


@pytest.mark.unit
def test_sign_seal_pointer_raises_sequence_regression_when_seq_equals_prior() -> None:
    """`new_sequence_number` must strictly exceed prior; equality rejects."""
    state = _seal(SealStatus.LIVE, current_sequence_number=5)
    with pytest.raises(SealSequenceNumberRegressionError) as exc:
        sign_seal_pointer.decide(
            state=state,
            command=_command(new_sequence_number=5),
            now=_NOW,
            signed_by=_PRINCIPAL_ID,
        )
    assert exc.value.prior_sequence_number == 5
    assert exc.value.proposed_sequence_number == 5


@pytest.mark.unit
def test_sign_seal_pointer_raises_sequence_regression_when_seq_lower_than_prior() -> None:
    """A lower-than-prior sequence number is also a regression."""
    state = _seal(SealStatus.LIVE, current_sequence_number=5)
    with pytest.raises(SealSequenceNumberRegressionError) as exc:
        sign_seal_pointer.decide(
            state=state,
            command=_command(new_sequence_number=3),
            now=_NOW,
            signed_by=_PRINCIPAL_ID,
        )
    assert exc.value.prior_sequence_number == 5
    assert exc.value.proposed_sequence_number == 3


@pytest.mark.unit
def test_sign_seal_pointer_accepts_strict_increment_from_genesis_zero() -> None:
    """First post-genesis signing: prior is 0, proposed is 1 -> accepted."""
    state = _seal(SealStatus.LIVE, current_head_hash=None, current_sequence_number=0)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(new_sequence_number=1),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].sequence_number == 1


@pytest.mark.unit
def test_sign_seal_pointer_accepts_large_sequence_jump() -> None:
    """Any strictly-greater sequence number is accepted (no max-step rule)."""
    state = _seal(SealStatus.LIVE, current_sequence_number=2)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(new_sequence_number=2_000_000),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    assert events[0].sequence_number == 2_000_000


@pytest.mark.unit
def test_sign_seal_pointer_is_pure_same_inputs_same_outputs() -> None:
    state = _seal(SealStatus.LIVE)
    first = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    second = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_sign_seal_pointer_captures_handler_injected_actor_id_verbatim() -> None:
    """The decider records the handler-injected actor id without synthesising."""
    state = _seal(SealStatus.LIVE)
    injected = ActorId(uuid4())
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=_NOW,
        signed_by=injected,
    )
    assert events[0].signed_by == injected


@pytest.mark.unit
def test_sign_seal_pointer_captures_handler_injected_now_verbatim() -> None:
    """`now` is injected from the handler's clock; decider records it on both
    `signed_at` and `occurred_at` (mirrors Calibration revision `established_at`)."""
    state = _seal(SealStatus.LIVE)
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=custom_now,
        signed_by=_PRINCIPAL_ID,
    )
    assert events[0].signed_at == custom_now
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_sign_seal_pointer_actor_id_independent_of_initialized_by() -> None:
    """The signing actor need NOT be the Seal's initialising actor."""
    state = _seal(SealStatus.LIVE)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=_NOW,
        signed_by=_OTHER_ACTOR_ID,
    )
    assert events[0].signed_by == _OTHER_ACTOR_ID
    assert state.initialized_by == _INITIALIZED_BY


@pytest.mark.unit
def test_sign_seal_pointer_reuses_facility_id_from_state() -> None:
    """Transitions reuse the facility id from state; only genesis mints identity."""
    state = _seal(SealStatus.LIVE)
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=_NOW,
        signed_by=_PRINCIPAL_ID,
    )
    assert events[0].facility_id == state.facility_id
