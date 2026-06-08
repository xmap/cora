"""Application-handler tests for the `rotate_seal_online_key` slice.

Pins the cross-BC atomic write: every successful `rotate_seal_online_key`
call writes ONE `SealOnlineKeyRotated` event on the Seal stream AND
ONE `DecisionRegistered` audit event on the Decision stream via
`EventStore.append_streams`. Mirrors the `revoke_credential` cross-BC
mid-lifecycle pattern: a security-touching action whose audit emission
is atomic with the domain event.

The Seal stream's expected version on append is the loaded version (1
after genesis), not zero (Seal must already have been initialized).
The Decision stream is fresh (expected version zero).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.credential import (
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    SealCannotRotateError,
    SealCannotRotateWithInactiveCredentialError,
    SealKeyCollisionError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import rotate_seal_online_key
from cora.federation.features.rotate_seal_online_key import RotateSealOnlineKey
from cora.infrastructure.adapters.in_memory_credential_lookup import (
    InMemoryCredentialLookup,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import (
    InMemoryFacilityLookup,
)
from cora.infrastructure.kernel import Kernel
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_live_seal,
    seed_republishing_seal,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_CODE = "aps-2bm"
_STREAM_ID = seal_stream_id(_FACILITY_CODE)
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed201")
_REPUBLISHING_STARTED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed202")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed205")
_SEAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed206")
_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed207")
_FOLLOWUP_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed208")
_FOLLOWUP_SEAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed209")
_FOLLOWUP_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed20a")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CURRENT_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_NEW_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a2")


def _build_lookup(
    *,
    register_default: bool = True,
    purpose: str = CredentialPurpose.SEAL_ONLINE_SIGNING.value,
    status: str = CredentialStatus.ACTIVE.value,
    new_online_credential_id: UUID = _NEW_ONLINE_KEY,
) -> InMemoryCredentialLookup:
    """Build an `InMemoryCredentialLookup` seeded for the happy path.

    Default: the new online ref resolves to an Active SealOnlineSigning
    credential. Tests asserting the missing / wrong-purpose / inactive
    paths override `register_default=False` (no seed) or pass alternate
    `purpose` / `status` strings.
    """
    lookup = InMemoryCredentialLookup()
    if register_default:
        lookup.register(
            credential_id=new_online_credential_id,
            facility_id=_FACILITY_CODE,
            purpose=purpose,
            status=status,
        )
    return lookup


def _build_facility_lookup(
    *,
    trust_anchors: frozenset[UUID] = frozenset(
        {_CURRENT_ONLINE_KEY, _OFFLINE_KEY, _NEW_ONLINE_KEY}
    ),
) -> InMemoryFacilityLookup:
    """Seed an `InMemoryFacilityLookup` row for the test's self-Facility.

    Default trust-anchor set covers the current online, offline, and
    new online credentials so the Slice 6 Sub-Slice C structural set-
    membership check passes on the happy path.
    """
    lookup = InMemoryFacilityLookup()
    lookup.register(
        facility_id=facility_stream_id(FacilityCode(_FACILITY_CODE)),
        code=_FACILITY_CODE,
        kind="Site",
        trust_anchor_credential_ids=trust_anchors,
    )
    return lookup


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
    credential_lookup: InMemoryCredentialLookup | None = None,
    facility_lookup: InMemoryFacilityLookup | None = None,
) -> Kernel:
    # rotate_seal_online_key consumes 3 ids per successful call:
    #   1) decision_id (fresh Decision stream id)
    #   2) seal event_id (one SealOnlineKeyRotated event)
    #   3) decision event_id (one DecisionRegistered event)
    return _build_deps_shared(
        ids=(ids if ids is not None else [_DECISION_ID, _SEAL_EVENT_ID, _DECISION_EVENT_ID]),
        now=_T2,
        event_store=event_store,
        deny=deny,
        credential_lookup=(credential_lookup if credential_lookup is not None else _build_lookup()),
        facility_lookup=(
            facility_lookup if facility_lookup is not None else _build_facility_lookup()
        ),
    )


def _command(
    new_online_credential_id: UUID = _NEW_ONLINE_KEY,
    *,
    signed_by_offline_root: bool = True,
) -> RotateSealOnlineKey:
    return RotateSealOnlineKey(
        facility_code=_FACILITY_CODE,
        new_online_credential_id=new_online_credential_id,
        signed_by_offline_root=signed_by_offline_root,
    )


async def _seed_live(store: InMemoryEventStore) -> None:
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_code=_FACILITY_CODE,
        online_credential_id=_CURRENT_ONLINE_KEY,
        offline_credential_id=_OFFLINE_KEY,
    )


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_appends_event_from_live() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Seal", _STREAM_ID)
    assert version == 2
    transition = events[-1]
    assert transition.event_type == "SealOnlineKeyRotated"
    assert transition.payload["facility_id"] == _FACILITY_CODE
    assert transition.payload["new_online_credential_id"] == str(_NEW_ONLINE_KEY)
    assert transition.payload["signed_by_offline_root"] is True
    assert transition.payload["rotated_by"] == str(_PRINCIPAL_ID)
    assert transition.correlation_id == _CORRELATION_ID
    assert transition.causation_id is None


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_propagates_signed_by_offline_root_false() -> None:
    """The handler threads `command.signed_by_offline_root` verbatim onto
    the emitted event payload so the audit stream records the operator
    gesture exactly."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    await handler(
        _command(signed_by_offline_root=False),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Seal", _STREAM_ID)
    assert events[-1].payload["signed_by_offline_root"] is False


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_appends_to_both_seal_and_decision_streams() -> None:
    """Cross-BC atomic write: SealOnlineKeyRotated on Seal stream AND
    DecisionRegistered on Decision stream via append_streams."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal_events, seal_version = await store.load("Seal", _STREAM_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)

    assert seal_version == 2  # genesis + rotate
    assert decision_version == 1  # fresh Decision stream
    assert len(seal_events) == 2
    assert len(decision_events) == 1
    assert seal_events[-1].event_type == "SealOnlineKeyRotated"
    assert decision_events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_decision_audit_carries_actor_and_choice() -> None:
    """The co-written DecisionRegistered audit pins decided_by == principal_id,
    context == 'SealOnlineKeyRotated', and choice == facility_code for
    cross-stream correlation."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    decision_events, _ = await store.load("Decision", _DECISION_ID)
    payload = decision_events[0].payload
    assert payload["decision_id"] == str(_DECISION_ID)
    assert payload["decided_by"] == str(_PRINCIPAL_ID)
    assert payload["context"] == "SealOnlineKeyRotated"
    assert payload["choice"] == _FACILITY_CODE
    assert payload["occurred_at"] == _T2.isoformat()


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_propagates_envelope_to_both_streams() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal_events, _ = await store.load("Seal", _STREAM_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    seal_rotate = seal_events[-1]
    decision_audit = decision_events[0]
    assert seal_rotate.correlation_id == _CORRELATION_ID
    assert seal_rotate.causation_id is None
    assert decision_audit.correlation_id == _CORRELATION_ID
    assert decision_audit.causation_id is None


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_propagates_causation_id() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    causation_id = UUID("01900000-0000-7000-8000-0000000000cc")
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation_id,
    )

    seal_events, _ = await store.load("Seal", _STREAM_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert seal_events[-1].causation_id == causation_id
    assert decision_events[0].causation_id == causation_id


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_not_found_for_uninitialized_seal() -> None:
    deps = _build_deps(event_store=InMemoryEventStore())
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_cannot_rotate_when_republishing() -> None:
    """Strict-not-idempotent: rotating against a Republishing Seal raises."""
    store = InMemoryEventStore()
    await seed_republishing_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_REPUBLISHING_STARTED_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_code=_FACILITY_CODE,
    )
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealCannotRotateError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 2  # untouched seed (Initialized + RepublishingStarted)


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_cannot_rotate_on_noop_rotation() -> None:
    """Strict-not-idempotent: re-rotating to the same online ref raises."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealCannotRotateError):
        await handler(
            _command(new_online_credential_id=_CURRENT_ONLINE_KEY),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 1  # untouched seed


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_collision_when_ref_equals_offline() -> None:
    """Key-separation invariant: rotating to a ref equal to offline raises.

    The lookup is seeded with the offline ref as a valid Active
    SealOnlineSigning credential so the decider passes the purpose /
    status checks and reaches the key-separation step that raises.
    """
    store = InMemoryEventStore()
    await _seed_live(store)
    lookup = _build_lookup(register_default=False)
    lookup.register(
        credential_id=_OFFLINE_KEY,
        facility_id=_FACILITY_CODE,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    deps = _build_deps(event_store=store, credential_lookup=lookup)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealKeyCollisionError) as exc_info:
        await handler(
            _command(new_online_credential_id=_OFFLINE_KEY),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.shared_credential_id == _OFFLINE_KEY
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 1  # untouched seed


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_strict_not_idempotent_raises_on_re_rotate() -> None:
    """After a successful rotation the slot holds the new ref; re-rotating to
    that same ref MUST raise (no-op rejected) and MUST NOT write to either stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_first = await store.load("Seal", _STREAM_ID)
    assert version_after_first == 2

    deps2 = _build_deps(
        event_store=store,
        ids=[
            _FOLLOWUP_DECISION_ID,
            _FOLLOWUP_SEAL_EVENT_ID,
            _FOLLOWUP_DECISION_EVENT_ID,
        ],
    )
    handler2 = rotate_seal_online_key.bind(deps2)
    with pytest.raises(SealCannotRotateError):
        await handler2(
            _command(new_online_credential_id=_NEW_ONLINE_KEY),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Seal", _STREAM_ID)
    assert version_after_reject == 2  # untouched after re-rotate rejection
    _, followup_decision_version = await store.load("Decision", _FOLLOWUP_DECISION_ID)
    assert followup_decision_version == 0  # no second Decision stream landed


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on EITHER stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, seal_version = await store.load("Seal", _STREAM_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 1  # untouched: just the SealInitialized seed
    assert decision_version == 0
    assert decision_events == []


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_records_principal_as_rotated_by() -> None:
    """The handler injects the request envelope's `principal_id` as
    `rotated_by` on the emitted event (audit anchor for the
    operator gesture), regardless of who initialized the seal."""
    store = InMemoryEventStore()
    # Seed Initialized BY a different actor; the rotator should still be
    # recorded as the invoking principal.
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_code=_FACILITY_CODE,
        online_credential_id=_CURRENT_ONLINE_KEY,
        offline_credential_id=_OFFLINE_KEY,
    )
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Seal", _STREAM_ID)
    assert events[-1].payload["rotated_by"] == str(_PRINCIPAL_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert decision_events[0].payload["decided_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_targets_deterministic_stream_id() -> None:
    """The handler derives the stream UUID via `seal_stream_id(facility_code)`;
    the rotation event lands on that same deterministic stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    expected_stream_id = seal_stream_id(_FACILITY_CODE)
    events, version = await store.load("Seal", expected_stream_id)
    assert version == 2
    assert events[-1].event_type == "SealOnlineKeyRotated"


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_credential_not_found_when_unseeded() -> None:
    """Unknown credential ref: the `CredentialLookup` returns None, and the
    decider raises `CredentialNotFoundError` before writing either stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    lookup = _build_lookup(register_default=False)
    deps = _build_deps(event_store=store, credential_lookup=lookup)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(CredentialNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, seal_version = await store.load("Seal", _STREAM_ID)
    _, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 1  # genesis seed untouched
    assert decision_version == 0


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_purpose_mismatch_for_offline_ref() -> None:
    """Wrong-purpose credential: the resolved row has purpose SealOfflineRoot,
    so the decider raises `SealKeyPurposeMismatchError` and writes nothing."""
    store = InMemoryEventStore()
    await _seed_live(store)
    lookup = _build_lookup(purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value)
    deps = _build_deps(event_store=store, credential_lookup=lookup)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealKeyPurposeMismatchError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.credential_id == _NEW_ONLINE_KEY
    assert exc_info.value.actual_purpose == CredentialPurpose.SEAL_OFFLINE_ROOT.value
    _, seal_version = await store.load("Seal", _STREAM_ID)
    _, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 1
    assert decision_version == 0


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_inactive_when_credential_is_rotating() -> None:
    """Non-Active credential: a Rotating status raises
    `SealCannotRotateWithInactiveCredentialError` and writes nothing."""
    store = InMemoryEventStore()
    await _seed_live(store)
    lookup = _build_lookup(status=CredentialStatus.ROTATING.value)
    deps = _build_deps(event_store=store, credential_lookup=lookup)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealCannotRotateWithInactiveCredentialError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.credential_id == _NEW_ONLINE_KEY
    assert exc_info.value.actual_status == CredentialStatus.ROTATING.value
    _, seal_version = await store.load("Seal", _STREAM_ID)
    _, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 1
    assert decision_version == 0


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_inactive_when_credential_is_revoked() -> None:
    """Non-Active credential: a Revoked status raises
    `SealCannotRotateWithInactiveCredentialError` and writes nothing."""
    store = InMemoryEventStore()
    await _seed_live(store)
    lookup = _build_lookup(status=CredentialStatus.REVOKED.value)
    deps = _build_deps(event_store=store, credential_lookup=lookup)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealCannotRotateWithInactiveCredentialError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.actual_status == CredentialStatus.REVOKED.value
    _, seal_version = await store.load("Seal", _STREAM_ID)
    assert seal_version == 1
