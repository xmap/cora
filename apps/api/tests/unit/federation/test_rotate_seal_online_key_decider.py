"""Unit tests for the `rotate_seal_online_key` slice's pure decider.

Live -> Live mid-lifecycle transition that swaps `online_credential_id` to a
fresh Credential. Strict-not-idempotent: rotating to the same ref the
slot already holds raises `SealCannotRotateError` (no-op rejected);
rotating against a Republishing Seal raises `SealCannotRotateError`;
rotating to a ref equal to `offline_credential_id` raises
`SealKeyCollisionError` via the `_key_separation` helper called against
the prospective post-transition state.

`new_online_credential` is handler-injected via the `CredentialLookup`
port (the handler resolves the new ref against the projection BEFORE
invoking the decider). The decider raises `CredentialNotFoundError`
on a None result, `SealKeyPurposeMismatchError` when the purpose is
not `SealOnlineSigning`, and `SealCannotRotateWithInactiveCredentialError`
when the status is not `Active`.

`rotated_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`SealOnlineKeyRotated` event as the audit denorm.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.credential import (
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.aggregates.facility import FacilityNotFoundError
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    Seal,
    SealCannotRotateError,
    SealCannotRotateWithInactiveCredentialError,
    SealCredentialNotTrustAnchorError,
    SealKeyCollisionError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
    SealOnlineKeyRotated,
    SealStatus,
)
from cora.federation.features import rotate_seal_online_key
from cora.federation.features.rotate_seal_online_key import RotateSealOnlineKey
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed101"))
_OTHER_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed102"))
_INITIALIZED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))
_CURRENT_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_NEW_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a2")


def _self_facility(
    *,
    trust_anchors: frozenset[UUID] = frozenset(
        {_CURRENT_ONLINE_KEY, _OFFLINE_KEY, _NEW_ONLINE_KEY}
    ),
) -> FacilityLookupResult:
    """Build a self-Facility lookup row anchored on the test credentials by default."""
    return FacilityLookupResult(
        id=FacilityId(facility_stream_id(FacilityCode(_FACILITY_ID))),
        code=FacilityCode(_FACILITY_ID),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(CredentialId(cid) for cid in trust_anchors),
    )


def _seal(
    status: SealStatus,
    *,
    online_credential_id: UUID = _CURRENT_ONLINE_KEY,
    offline_credential_id: UUID = _OFFLINE_KEY,
    current_head_hash: str | None = None,
    current_sequence_number: int = 0,
) -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_credential_id=online_credential_id,
        offline_credential_id=offline_credential_id,
        current_head_hash=current_head_hash,
        current_sequence_number=current_sequence_number,
        initialized_by=_INITIALIZED_BY,
        initialized_at=_NOW,
        status=status,
    )


def _command(
    new_online_credential_id: UUID = _NEW_ONLINE_KEY,
    *,
    signed_by_offline_root: bool = True,
) -> RotateSealOnlineKey:
    return RotateSealOnlineKey(
        facility_id=_FACILITY_ID,
        new_online_credential_id=new_online_credential_id,
        signed_by_offline_root=signed_by_offline_root,
    )


def _credential(
    credential_id: UUID = _NEW_ONLINE_KEY,
    *,
    purpose: str = CredentialPurpose.SEAL_ONLINE_SIGNING.value,
    status: str = CredentialStatus.ACTIVE.value,
    facility_id: str = _FACILITY_ID,
) -> CredentialLookupResult:
    return CredentialLookupResult(
        id=credential_id,
        facility_id=FacilityCode(facility_id),
        purpose=purpose,
        status=status,
    )


@pytest.mark.unit
def test_rotate_seal_online_key_emits_event_from_live() -> None:
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events == [
        SealOnlineKeyRotated(
            facility_id=_FACILITY_ID,
            new_online_credential_id=_NEW_ONLINE_KEY,
            signed_by_offline_root=True,
            rotated_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_rotate_seal_online_key_propagates_signed_by_offline_root_true() -> None:
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(signed_by_offline_root=True),
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events[0].signed_by_offline_root is True


@pytest.mark.unit
def test_rotate_seal_online_key_propagates_signed_by_offline_root_false() -> None:
    """When the operator did not obtain an offline-root countersignature,
    the event records the gesture verbatim so the audit stream can flag it."""
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(signed_by_offline_root=False),
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events[0].signed_by_offline_root is False


@pytest.mark.unit
def test_rotate_seal_online_key_raises_not_found_when_state_is_none() -> None:
    with pytest.raises(SealNotFoundError) as exc_info:
        rotate_seal_online_key.decide(
            state=None,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=_credential(),
            self_facility=_self_facility(),
        )
    assert exc_info.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_rotate_seal_online_key_raises_cannot_rotate_when_republishing() -> None:
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(SealCannotRotateError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=_credential(),
            self_facility=_self_facility(),
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.current_status is SealStatus.REPUBLISHING


@pytest.mark.unit
def test_rotate_seal_online_key_raises_cannot_rotate_when_ref_equals_current_online() -> None:
    """No-op rotation rejected: rotating to the same ref the slot already holds."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(SealCannotRotateError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(new_online_credential_id=_CURRENT_ONLINE_KEY),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=_credential(credential_id=_CURRENT_ONLINE_KEY),
            self_facility=_self_facility(),
        )
    assert exc_info.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_rotate_seal_online_key_raises_collision_when_new_ref_equals_offline() -> None:
    """Key-separation invariant: rotating to a ref equal to offline raises."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(SealKeyCollisionError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(new_online_credential_id=_OFFLINE_KEY),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=_credential(credential_id=_OFFLINE_KEY),
            self_facility=_self_facility(),
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.shared_credential_id == _OFFLINE_KEY


@pytest.mark.unit
def test_rotate_seal_online_key_captures_handler_injected_rotated_by() -> None:
    """`rotated_by` is captured verbatim from the handler, not recomputed."""
    arbitrary_principal = ActorId(uuid4())
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=_NOW,
        rotated_by=arbitrary_principal,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events[0].rotated_by == arbitrary_principal


@pytest.mark.unit
def test_rotate_seal_online_key_uses_supplied_now_for_occurred_at() -> None:
    """Non-determinism injected from handler per project_non_determinism_principle."""
    custom_now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=custom_now,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_rotate_seal_online_key_is_pure_same_inputs_same_outputs() -> None:
    state = _seal(SealStatus.LIVE)
    command = _command()
    credential = _credential()
    first = rotate_seal_online_key.decide(
        state=state,
        command=command,
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=credential,
        self_facility=_self_facility(),
    )
    second = rotate_seal_online_key.decide(
        state=state,
        command=command,
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=credential,
        self_facility=_self_facility(),
    )
    assert first == second


@pytest.mark.unit
def test_rotate_seal_online_key_actor_id_independent_of_initialized_by() -> None:
    """The rotating actor need NOT be the genesis-initializing actor; the emitted
    event records whichever id the handler injects."""
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=_NOW,
        rotated_by=_OTHER_ACTOR_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events[0].rotated_by == _OTHER_ACTOR_ID


@pytest.mark.unit
def test_rotate_seal_online_key_preserves_offline_ref_on_emitted_event() -> None:
    """The offline_credential_id is NOT carried on the emitted event payload; only
    the new online ref + actor + facility ride on SealOnlineKeyRotated."""
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert len(events) == 1
    event = events[0]
    assert event.new_online_credential_id == _NEW_ONLINE_KEY
    assert not hasattr(event, "offline_credential_id")


@pytest.mark.unit
def test_rotate_seal_online_key_emits_event_with_state_facility_id() -> None:
    """The emitted facility_id comes from state, not the command (defensive
    against caller-side facility mismatch; state is the canonical source)."""
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert events[0].facility_id == state.facility_id


@pytest.mark.unit
def test_rotate_seal_online_key_emits_single_event() -> None:
    """One domain event per successful rotation."""
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(),
        now=_NOW,
        rotated_by=_PRINCIPAL_ID,
        new_online_credential=_credential(),
        self_facility=_self_facility(),
    )
    assert len(events) == 1
    assert isinstance(events[0], SealOnlineKeyRotated)


@pytest.mark.unit
def test_rotate_seal_online_key_raises_credential_not_found_when_lookup_returns_none() -> None:
    """Unknown credential ref: the projection has no row for the new ref."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(CredentialNotFoundError):
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=None,
            self_facility=_self_facility(),
        )


@pytest.mark.unit
def test_rotate_seal_online_key_raises_purpose_mismatch_when_credential_is_offline_root() -> None:
    """Wrong-purpose binding: the new credential's purpose must be SealOnlineSigning."""
    state = _seal(SealStatus.LIVE)
    wrong_purpose = _credential(purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value)
    with pytest.raises(SealKeyPurposeMismatchError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=wrong_purpose,
            self_facility=_self_facility(),
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.slot == "online_credential_id"
    assert exc_info.value.credential_id == _NEW_ONLINE_KEY
    assert exc_info.value.expected_purpose == CredentialPurpose.SEAL_ONLINE_SIGNING.value
    assert exc_info.value.actual_purpose == CredentialPurpose.SEAL_OFFLINE_ROOT.value


@pytest.mark.unit
def test_rotate_seal_online_key_raises_inactive_when_credential_is_rotating() -> None:
    """Non-Active status: a Rotating credential cannot back a Seal rotation."""
    state = _seal(SealStatus.LIVE)
    rotating = _credential(status=CredentialStatus.ROTATING.value)
    with pytest.raises(SealCannotRotateWithInactiveCredentialError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=rotating,
            self_facility=_self_facility(),
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.slot == "online_credential_id"
    assert exc_info.value.credential_id == _NEW_ONLINE_KEY
    assert exc_info.value.actual_status == CredentialStatus.ROTATING.value


@pytest.mark.unit
def test_rotate_seal_online_key_raises_inactive_when_credential_is_revoked() -> None:
    """Non-Active status: a Revoked credential cannot back a Seal rotation."""
    state = _seal(SealStatus.LIVE)
    revoked = _credential(status=CredentialStatus.REVOKED.value)
    with pytest.raises(SealCannotRotateWithInactiveCredentialError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=revoked,
            self_facility=_self_facility(),
        )
    assert exc_info.value.actual_status == CredentialStatus.REVOKED.value


@pytest.mark.unit
def test_rotate_seal_online_key_rejects_credential_not_in_trust_anchors() -> None:
    """Structural cross-tenant defense (SEC-FED-01): new online credential
    id must be in self_facility.trust_anchor_credential_ids."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(SealCredentialNotTrustAnchorError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=_credential(),
            self_facility=_self_facility(
                trust_anchors=frozenset({_CURRENT_ONLINE_KEY, _OFFLINE_KEY}),
            ),
        )
    assert exc_info.value.facility_id == _FACILITY_ID
    assert exc_info.value.credential_id == _NEW_ONLINE_KEY
    assert exc_info.value.key_ref_role == "online"


@pytest.mark.unit
def test_rotate_seal_online_key_rejects_when_self_facility_missing() -> None:
    """Self-Facility lookup miss surfaces as FacilityNotFoundError."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(FacilityNotFoundError) as exc_info:
        rotate_seal_online_key.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotated_by=_PRINCIPAL_ID,
            new_online_credential=_credential(),
            self_facility=None,
        )
    assert exc_info.value.facility_id == facility_stream_id(FacilityCode(_FACILITY_ID))
