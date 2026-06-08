"""Shared seed helpers for the Federation aggregate lifecycle handler tests.

Each transition slice's handler test (Permit: activate / suspend /
resume / revoke; Credential: start / complete / abort rotation,
revoke) needs to seed an aggregate at a specific FSM status against
an InMemoryEventStore. The helpers keep per-test files focused on
assertions rather than re-encoding the same seed dance.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    CredentialPurpose,
    CredentialRegistered,
    CredentialRevoked,
    CredentialRotationStarted,
)
from cora.federation.aggregates.credential import (
    event_type_name as credential_event_type_name,
)
from cora.federation.aggregates.credential import (
    to_payload as credential_to_payload,
)
from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    PermitActivated,
    PermitDefined,
    PermitSuspended,
    ReadScope,
    ScopeRef,
    event_type_name,
    to_payload,
)
from cora.federation.aggregates.seal import (
    SealInitialized,
    SealRepublishingStarted,
)
from cora.federation.aggregates.seal import (
    event_type_name as seal_event_type_name,
)
from cora.federation.aggregates.seal import (
    to_payload as seal_to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId

_DEFAULT_SEAL_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a1")
_DEFAULT_SEAL_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b1")


def _default_terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="alpha")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


async def seed_defined_permit(
    store: InMemoryEventStore,
    *,
    permit_id: UUID,
    genesis_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    expires_at: datetime,
) -> None:
    """Append a single `PermitDefined` event to a fresh Permit stream."""
    genesis = PermitDefined(
        permit_id=permit_id,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({UUID("01900000-0000-7000-8000-00000000c001")}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=expires_at,
        defined_by=ActorId(principal_id),
        terms=_default_terms(),
        occurred_at=defined_at,
    )
    await store.append(
        stream_type="Permit",
        stream_id=permit_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=genesis_event_id,
                command_name="DefinePermit",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_active_permit(
    store: InMemoryEventStore,
    *,
    permit_id: UUID,
    genesis_event_id: UUID,
    activate_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    activated_at: datetime,
    expires_at: datetime,
) -> None:
    """Seed Defined then Activated; stream version ends at 2."""
    await seed_defined_permit(
        store,
        permit_id=permit_id,
        genesis_event_id=genesis_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        defined_at=defined_at,
        expires_at=expires_at,
    )
    activated = PermitActivated(
        permit_id=permit_id,
        activated_by=ActorId(principal_id),
        occurred_at=activated_at,
    )
    await store.append(
        stream_type="Permit",
        stream_id=permit_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(activated),
                payload=to_payload(activated),
                occurred_at=activated.occurred_at,
                event_id=activate_event_id,
                command_name="ActivatePermit",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_suspended_permit(
    store: InMemoryEventStore,
    *,
    permit_id: UUID,
    genesis_event_id: UUID,
    activate_event_id: UUID,
    suspend_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    activated_at: datetime,
    suspended_at: datetime,
    expires_at: datetime,
) -> None:
    """Seed Defined then Activated then Suspended; stream version ends at 3."""
    await seed_active_permit(
        store,
        permit_id=permit_id,
        genesis_event_id=genesis_event_id,
        activate_event_id=activate_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        defined_at=defined_at,
        activated_at=activated_at,
        expires_at=expires_at,
    )
    suspended = PermitSuspended(
        permit_id=permit_id,
        suspended_by=ActorId(principal_id),
        occurred_at=suspended_at,
    )
    await store.append(
        stream_type="Permit",
        stream_id=permit_id,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(suspended),
                payload=to_payload(suspended),
                occurred_at=suspended.occurred_at,
                event_id=suspend_event_id,
                command_name="SuspendPermit",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_active_credential(
    store: InMemoryEventStore,
    *,
    credential_id: UUID,
    genesis_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    registered_at: datetime,
    expires_at: datetime | None,
    facility_id: str = "aps-2bm",
    audience: str = "peer-acme",
    purpose: CredentialPurpose = CredentialPurpose.SIGNING,
    secret_ref: str = "vault://current/v1",
    public_material_ref: str | None = "vault://current/pub/v1",
) -> None:
    """Append a single `CredentialRegistered` event so the credential lands in `Active`."""
    genesis = CredentialRegistered(
        credential_id=credential_id,
        facility_id=facility_id,
        audience=audience,
        purpose=purpose,
        secret_ref=secret_ref,
        public_material_ref=public_material_ref,
        expires_at=expires_at,
        registered_by=ActorId(principal_id),
        occurred_at=registered_at,
    )
    await store.append(
        stream_type="Credential",
        stream_id=credential_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=credential_event_type_name(genesis),
                payload=credential_to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=genesis_event_id,
                command_name="RegisterCredential",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_rotating_credential(
    store: InMemoryEventStore,
    *,
    credential_id: UUID,
    genesis_event_id: UUID,
    rotation_started_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    registered_at: datetime,
    rotation_started_at: datetime,
    expires_at: datetime | None,
    pending_secret_ref: str = "vault://pending/v2",
    pending_public_material_ref: str | None = "vault://pending/pub/v2",
) -> None:
    """Seed Registered (Active) then RotationStarted; stream version ends at 2."""
    await seed_active_credential(
        store,
        credential_id=credential_id,
        genesis_event_id=genesis_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        registered_at=registered_at,
        expires_at=expires_at,
    )
    started = CredentialRotationStarted(
        credential_id=credential_id,
        pending_secret_ref=pending_secret_ref,
        pending_public_material_ref=pending_public_material_ref,
        rotation_started_by=ActorId(principal_id),
        occurred_at=rotation_started_at,
    )
    await store.append(
        stream_type="Credential",
        stream_id=credential_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=credential_event_type_name(started),
                payload=credential_to_payload(started),
                occurred_at=started.occurred_at,
                event_id=rotation_started_event_id,
                command_name="StartCredentialRotation",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_revoked_credential(
    store: InMemoryEventStore,
    *,
    credential_id: UUID,
    genesis_event_id: UUID,
    revoke_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    registered_at: datetime,
    revoked_at: datetime,
    expires_at: datetime | None,
) -> None:
    """Seed Registered (Active) then Revoked; stream version ends at 2."""
    await seed_active_credential(
        store,
        credential_id=credential_id,
        genesis_event_id=genesis_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        registered_at=registered_at,
        expires_at=expires_at,
    )
    revoked = CredentialRevoked(
        credential_id=credential_id,
        revoked_by=ActorId(principal_id),
        occurred_at=revoked_at,
    )
    await store.append(
        stream_type="Credential",
        stream_id=credential_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=credential_event_type_name(revoked),
                payload=credential_to_payload(revoked),
                occurred_at=revoked.occurred_at,
                event_id=revoke_event_id,
                command_name="RevokeCredential",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_live_seal(
    store: InMemoryEventStore,
    *,
    stream_id: UUID,
    genesis_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    initialized_at: datetime,
    facility_id: str = "aps-2bm",
    online_credential_id: UUID = _DEFAULT_SEAL_ONLINE_KEY_REF,
    offline_credential_id: UUID = _DEFAULT_SEAL_OFFLINE_KEY_REF,
) -> None:
    """Append a single `SealInitialized` event so the Seal lands in `Live`."""
    genesis = SealInitialized(
        facility_id=facility_id,
        online_credential_id=online_credential_id,
        offline_credential_id=offline_credential_id,
        initialized_by=ActorId(principal_id),
        occurred_at=initialized_at,
    )
    await store.append(
        stream_type="Seal",
        stream_id=stream_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=seal_event_type_name(genesis),
                payload=seal_to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=genesis_event_id,
                command_name="InitializeSeal",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_republishing_seal(
    store: InMemoryEventStore,
    *,
    stream_id: UUID,
    genesis_event_id: UUID,
    start_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    initialized_at: datetime,
    republishing_started_at: datetime,
    facility_id: str = "aps-2bm",
) -> None:
    """Seed Initialized (Live) then RepublishingStarted; stream version ends at 2."""
    await seed_live_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=genesis_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        initialized_at=initialized_at,
        facility_id=facility_id,
    )
    started = SealRepublishingStarted(
        facility_id=facility_id,
        started_by=ActorId(principal_id),
        occurred_at=republishing_started_at,
    )
    await store.append(
        stream_type="Seal",
        stream_id=stream_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=seal_event_type_name(started),
                payload=seal_to_payload(started),
                occurred_at=started.occurred_at,
                event_id=start_event_id,
                command_name="StartSealRepublishing",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


__all__ = [
    "seed_active_credential",
    "seed_active_permit",
    "seed_defined_permit",
    "seed_live_seal",
    "seed_republishing_seal",
    "seed_revoked_credential",
    "seed_rotating_credential",
    "seed_suspended_permit",
]
