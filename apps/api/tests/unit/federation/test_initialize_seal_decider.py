"""Unit tests for the `initialize_seal` slice's pure decider.

Pin the singleton-genesis guard, key-separation invariant via the
shared helper, facility_id trim-before-capture, the genesis defaults
(current_head_hash=None, current_sequence_number=0 land via the
evolver not the event), purity (same inputs -> same outputs), and
handler-injected `now` / `initialized_by` capture per the
non-determinism principle.

Pass-3 wiring: the decider now consumes two `CredentialLookupResult`
snapshots (one per slot) and partitions on `purpose` / `status` for
the cross-aggregate purpose-binding and status-Active checks.
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
    InvalidSealFacilityIdError,
    Seal,
    SealAlreadyExistsError,
    SealCannotInitializeWithInactiveCredentialError,
    SealCredentialNotTrustAnchorError,
    SealKeyCollisionError,
    SealKeyPurposeMismatchError,
    SealStatus,
)
from cora.federation.features import initialize_seal
from cora.federation.features.initialize_seal import InitializeSeal
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed101"))
_OTHER_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed102"))
_FACILITY_ID = "aps-2bm"
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b1")


def _self_facility(
    *,
    trust_anchors: frozenset[UUID] = frozenset({_ONLINE_KEY_REF, _OFFLINE_KEY_REF}),
) -> FacilityLookupResult:
    """Build a self-Facility lookup row anchored on the test credentials by default."""
    return FacilityLookupResult(
        id=FacilityId(facility_stream_id(FacilityCode(_FACILITY_ID))),
        code=FacilityCode(_FACILITY_ID),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(CredentialId(cid) for cid in trust_anchors),
    )


def _command(**overrides: object) -> InitializeSeal:
    base: dict[str, object] = {
        "facility_id": _FACILITY_ID,
        "online_credential_id": _ONLINE_KEY_REF,
        "offline_credential_id": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return InitializeSeal(**base)  # type: ignore[arg-type]


def _online_cred(
    credential_id: UUID = _ONLINE_KEY_REF,
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


def _offline_cred(
    credential_id: UUID = _OFFLINE_KEY_REF,
    *,
    purpose: str = CredentialPurpose.SEAL_OFFLINE_ROOT.value,
    status: str = CredentialStatus.ACTIVE.value,
    facility_id: str = _FACILITY_ID,
) -> CredentialLookupResult:
    return CredentialLookupResult(
        id=credential_id,
        facility_id=FacilityCode(facility_id),
        purpose=purpose,
        status=status,
    )


def _existing_state() -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_credential_id=_ONLINE_KEY_REF,
        offline_credential_id=_OFFLINE_KEY_REF,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by=_PRINCIPAL_ID,
        initialized_at=_NOW,
        status=SealStatus.LIVE,
    )


@pytest.mark.unit
def test_initialize_seal_emits_event_for_valid_command() -> None:
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by=_PRINCIPAL_ID,
        online_credential=_online_cred(),
        offline_credential=_offline_cred(),
        self_facility=_self_facility(),
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == _FACILITY_ID
    assert event.online_credential_id == _ONLINE_KEY_REF
    assert event.offline_credential_id == _OFFLINE_KEY_REF
    assert event.initialized_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_initialize_seal_rejects_non_canonical_facility_id() -> None:
    """Padded facility_id is rejected (canonical form required) so the
    cross-facility binding check compares against `command.facility_id`
    directly without auto-normalization that could mask a peer-facility
    credential drift."""
    with pytest.raises(InvalidSealFacilityIdError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(facility_id="  aps-2bm  "),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.value == "  aps-2bm  "


@pytest.mark.unit
def test_initialize_seal_raises_already_exists_when_state_present() -> None:
    """Singleton guard: a non-None Seal state surfaces SealAlreadyExistsError."""
    with pytest.raises(SealAlreadyExistsError) as exc:
        initialize_seal.decide(
            state=_existing_state(),
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_initialize_seal_rejects_empty_facility_id() -> None:
    with pytest.raises(InvalidSealFacilityIdError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(facility_id=""),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.value == ""


@pytest.mark.unit
def test_initialize_seal_rejects_whitespace_only_facility_id() -> None:
    with pytest.raises(InvalidSealFacilityIdError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(facility_id="   "),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.value == "   "


@pytest.mark.unit
def test_initialize_seal_raises_collision_when_keys_equal() -> None:
    """Key-separation invariant: online_credential_id == offline_credential_id rejects
    via the shared `verify_key_separation` helper per sec-4 AH#15."""
    shared = uuid4()
    with pytest.raises(SealKeyCollisionError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(online_credential_id=shared, offline_credential_id=shared),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(credential_id=shared),
            offline_credential=_offline_cred(credential_id=shared),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.shared_credential_id == shared


@pytest.mark.unit
def test_initialize_seal_rejects_non_canonical_before_collision_check() -> None:
    """Canonical-form validation fires BEFORE key-separation; padded input
    is rejected via InvalidSealFacilityIdError even when keys would also
    collide. Keeps the failure mode unambiguous."""
    shared = uuid4()
    with pytest.raises(InvalidSealFacilityIdError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(
                facility_id="  aps-2bm  ",
                online_credential_id=shared,
                offline_credential_id=shared,
            ),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(credential_id=shared),
            offline_credential=_offline_cred(credential_id=shared),
            self_facility=_self_facility(),
        )
    assert exc.value.value == "  aps-2bm  "


@pytest.mark.unit
def test_initialize_seal_accepts_distinct_keys() -> None:
    """Happy path: distinct refs sail through the key-separation check."""
    new_online = UUID("01900000-0000-7000-8000-00000000aaa1")
    new_offline = UUID("01900000-0000-7000-8000-00000000bbb2")
    events = initialize_seal.decide(
        state=None,
        command=_command(
            online_credential_id=new_online,
            offline_credential_id=new_offline,
        ),
        now=_NOW,
        initialized_by=_PRINCIPAL_ID,
        online_credential=_online_cred(credential_id=new_online),
        offline_credential=_offline_cred(credential_id=new_offline),
        self_facility=_self_facility(trust_anchors=frozenset({new_online, new_offline})),
    )
    assert events[0].online_credential_id != events[0].offline_credential_id


@pytest.mark.unit
def test_initialize_seal_is_pure_same_inputs_same_outputs() -> None:
    online = _online_cred()
    offline = _offline_cred()
    first = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by=_PRINCIPAL_ID,
        online_credential=online,
        offline_credential=offline,
        self_facility=_self_facility(),
    )
    second = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by=_PRINCIPAL_ID,
        online_credential=online,
        offline_credential=offline,
        self_facility=_self_facility(),
    )
    assert first == second


@pytest.mark.unit
def test_initialize_seal_uses_handler_injected_actor_id_verbatim() -> None:
    injected = ActorId(uuid4())
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by=injected,
        online_credential=_online_cred(),
        offline_credential=_offline_cred(),
        self_facility=_self_facility(),
    )
    assert events[0].initialized_by == injected


@pytest.mark.unit
def test_initialize_seal_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=custom_now,
        initialized_by=_PRINCIPAL_ID,
        online_credential=_online_cred(),
        offline_credential=_offline_cred(),
        self_facility=_self_facility(),
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_initialize_seal_records_distinct_principals_independently() -> None:
    """Two calls with different injected actor ids capture each one
    verbatim on the emitted event."""
    first = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by=_PRINCIPAL_ID,
        online_credential=_online_cred(),
        offline_credential=_offline_cred(),
        self_facility=_self_facility(),
    )
    second = initialize_seal.decide(
        state=None,
        command=_command(),
        now=_NOW,
        initialized_by=_OTHER_PRINCIPAL_ID,
        online_credential=_online_cred(),
        offline_credential=_offline_cred(),
        self_facility=_self_facility(),
    )
    assert first[0].initialized_by == _PRINCIPAL_ID
    assert second[0].initialized_by == _OTHER_PRINCIPAL_ID


@pytest.mark.unit
def test_initialize_seal_raises_not_found_when_online_credential_missing() -> None:
    """Online ref unresolved by projection -> CredentialNotFoundError
    (per the start_run -> PlanNotFoundError precedent)."""
    with pytest.raises(CredentialNotFoundError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=None,
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.credential_id == _ONLINE_KEY_REF


@pytest.mark.unit
def test_initialize_seal_raises_not_found_when_offline_credential_missing() -> None:
    """Offline ref unresolved by projection -> CredentialNotFoundError."""
    with pytest.raises(CredentialNotFoundError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=None,
            self_facility=_self_facility(),
        )
    assert exc.value.credential_id == _OFFLINE_KEY_REF


@pytest.mark.unit
def test_initialize_seal_raises_purpose_mismatch_when_online_wrong_purpose() -> None:
    """Online slot must carry purpose 'SealOnlineSigning'."""
    with pytest.raises(SealKeyPurposeMismatchError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(purpose=CredentialPurpose.SIGNING.value),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.slot == "online_credential_id"
    assert exc.value.credential_id == _ONLINE_KEY_REF
    assert exc.value.expected_purpose == CredentialPurpose.SEAL_ONLINE_SIGNING.value
    assert exc.value.actual_purpose == CredentialPurpose.SIGNING.value


@pytest.mark.unit
def test_initialize_seal_raises_purpose_mismatch_when_offline_wrong_purpose() -> None:
    """Offline slot must carry purpose 'SealOfflineRoot'."""
    with pytest.raises(SealKeyPurposeMismatchError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.slot == "offline_credential_id"
    assert exc.value.credential_id == _OFFLINE_KEY_REF
    assert exc.value.expected_purpose == CredentialPurpose.SEAL_OFFLINE_ROOT.value
    assert exc.value.actual_purpose == CredentialPurpose.SEAL_ONLINE_SIGNING.value


@pytest.mark.unit
def test_initialize_seal_raises_inactive_when_online_status_rotating() -> None:
    """Online slot must carry status 'Active'; Rotating rejected."""
    with pytest.raises(SealCannotInitializeWithInactiveCredentialError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(status=CredentialStatus.ROTATING.value),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.slot == "online_credential_id"
    assert exc.value.credential_id == _ONLINE_KEY_REF
    assert exc.value.actual_status == CredentialStatus.ROTATING.value


@pytest.mark.unit
def test_initialize_seal_raises_inactive_when_offline_status_revoked() -> None:
    """Offline slot must carry status 'Active'; Revoked rejected."""
    with pytest.raises(SealCannotInitializeWithInactiveCredentialError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(status=CredentialStatus.REVOKED.value),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.slot == "offline_credential_id"
    assert exc.value.credential_id == _OFFLINE_KEY_REF
    assert exc.value.actual_status == CredentialStatus.REVOKED.value


@pytest.mark.unit
def test_initialize_seal_rejects_online_credential_not_in_trust_anchors() -> None:
    """Structural cross-tenant defense (SEC-FED-01): online credential id
    must be in self_facility.trust_anchor_credential_ids."""
    with pytest.raises(SealCredentialNotTrustAnchorError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(trust_anchors=frozenset({_OFFLINE_KEY_REF})),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _ONLINE_KEY_REF
    assert exc.value.key_ref_role == "online"


@pytest.mark.unit
def test_initialize_seal_rejects_offline_credential_not_in_trust_anchors() -> None:
    """Structural cross-tenant defense (SEC-FED-01): offline credential id
    must be in self_facility.trust_anchor_credential_ids."""
    with pytest.raises(SealCredentialNotTrustAnchorError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(trust_anchors=frozenset({_ONLINE_KEY_REF})),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _OFFLINE_KEY_REF
    assert exc.value.key_ref_role == "offline"


@pytest.mark.unit
def test_initialize_seal_rejects_when_no_credentials_in_trust_anchors() -> None:
    """Both credentials absent from the trust-anchor set: the online check
    fires first per the decider's declared order. The previous
    `online_vs_offline` defense-in-depth check collapses under the
    structural-fold rewrite because set-membership against the same
    Facility is per-credential, not cross-credential."""
    with pytest.raises(SealCredentialNotTrustAnchorError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(trust_anchors=frozenset()),
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _ONLINE_KEY_REF
    assert exc.value.key_ref_role == "online"


@pytest.mark.unit
def test_initialize_seal_rejects_when_self_facility_missing() -> None:
    """Self-Facility lookup miss surfaces as FacilityNotFoundError; the
    bootstrap should always seed the row so this fires only on misconfig."""
    with pytest.raises(FacilityNotFoundError) as exc:
        initialize_seal.decide(
            state=None,
            command=_command(),
            now=_NOW,
            initialized_by=_PRINCIPAL_ID,
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=None,
        )
    assert exc.value.facility_id == facility_stream_id(FacilityCode(_FACILITY_ID))
