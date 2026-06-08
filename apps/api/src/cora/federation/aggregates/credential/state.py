"""Credential aggregate state, enums, and domain errors.

A `Credential` is a per-facility material binding for one of six
purposes (signing, verification, authentication, encryption, seal
online-signing, seal offline-root). Per
[[project_federation_port_design]] Memo 1 the aggregate holds only
opaque pointers to actual secret material; the bytes themselves live
in a `SecretStore` adapter behind the `secret_ref` handle.

Key invariants:

  - `secret_ref` is an opaque pointer (URI / KMS handle / vault path)
    of type `str`. The aggregate MUST NEVER carry the raw secret
    bytes; that would tunnel secrets through the event log and
    projections, which violates AH#6 of the locked design.
  - Lifecycle is a 3-state FSM with a rotation overlay: `Active`
    accepts `rotation_started` (moves to `Rotating` and populates
    pending refs); `Rotating` accepts either `rotation_completed`
    (promotes pending to current, returns to `Active`) or
    `rotation_aborted` (clears pending, returns to `Active`). Both
    `Active` and `Rotating` accept `revoked` (terminal).
  - `purpose` is closed at 6 arms per Memo 1 Q4: the four generic
    purposes (Signing, Verification, Authentication, Encryption)
    plus the two seal purposes (SealOnlineSigning, SealOfflineRoot)
    that the Seal aggregate's `verify_key_separation` rule depends on.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.identity import ActorId


class CredentialPurpose(StrEnum):
    """The role this credential plays in federation traffic.

    Six arms locked at Memo 1 Q4:

      - `Signing`: credential signs outbound payloads (manifests,
        receipts, attestations).
      - `Verification`: credential verifies inbound payloads signed
        by peer facilities.
      - `Authentication`: credential authenticates the local facility
        to a peer at connection setup.
      - `Encryption`: credential decrypts inbound payloads or wraps
        outbound payloads.
      - `SealOnlineSigning`: credential signs seal pointer updates
        online; rotated frequently. Referenced by
        `Seal.online_credential_id`.
      - `SealOfflineRoot`: credential is the offline root of trust
        for the seal; rotated rarely and held offline. Referenced by
        `Seal.offline_credential_id`.

    The two seal purposes are distinct enum values rather than a
    single `Seal` arm so the `verify_key_separation` guard in `Seal`
    can statically detect a same-purpose collision between the
    online and offline references.
    """

    SIGNING = "Signing"
    VERIFICATION = "Verification"
    AUTHENTICATION = "Authentication"
    ENCRYPTION = "Encryption"
    SEAL_ONLINE_SIGNING = "SealOnlineSigning"
    SEAL_OFFLINE_ROOT = "SealOfflineRoot"


class CredentialStatus(StrEnum):
    """Lifecycle status of a Credential.

    Three values per Memo 1:

      - `Active`: credential is in service for its declared purpose.
      - `Rotating`: a rotation is in flight; the aggregate now
        carries both the current and a pending pair of refs.
        Completes back to `Active` (promoting pending to current)
        or aborts back to `Active` (discarding pending).
      - `Revoked`: terminal. The credential is no longer usable; no
        further transitions are valid.
    """

    ACTIVE = "Active"
    ROTATING = "Rotating"
    REVOKED = "Revoked"


# ---------------------------------------------------------------------------
# Domain validation errors
# ---------------------------------------------------------------------------


class InvalidCredentialSecretRefError(ValueError):
    """The supplied opaque-pointer / identity field is empty or whitespace-only.

    Re-used across the Credential aggregate for every field-shape
    violation: today the genesis fields (`facility_id`, `audience`,
    `secret_ref`) and the rotation field (`new_secret_ref`). The
    `field_name` argument keeps the message and the captured attribute
    accurate to whichever field actually tripped, so the error does
    not lie about which input was bad.

    The aggregate does not validate any pointer's resolvability (that
    is the SecretStore adapter's concern); it only rejects
    structurally empty handles which would silently bind nothing.
    """

    def __init__(self, field_name: str, value: str) -> None:
        super().__init__(
            f"Credential {field_name} must be non-empty after trimming (got: {value!r})"
        )
        self.field_name = field_name
        self.value = value


class CredentialExpiredError(Exception):
    """A transition was attempted on a credential past its expires_at.

    Raised by deciders before allowing rotation, signing, or other
    purpose-specific use. Revocation is still valid past expiry so an
    expired credential can be terminally retired without first being
    restored.
    """

    def __init__(self, credential_id: UUID, expires_at: datetime) -> None:
        super().__init__(f"Credential {credential_id} expired at {expires_at.isoformat()}")
        self.credential_id = credential_id
        self.expires_at = expires_at


class CredentialAlreadyExistsError(Exception):
    """Attempted to register a credential whose stream already has events.

    Per [[project_genesis_error_classes]] this class stays un-hoisted;
    per-BC isinstance routing in the federation BC's exception handler
    outweighs the small saving from a generic alias.
    """

    def __init__(self, credential_id: UUID) -> None:
        super().__init__(f"Credential {credential_id} already exists")
        self.credential_id = credential_id


class CredentialNotFoundError(Exception):
    """Attempted an operation on a credential whose stream has no events."""

    def __init__(self, credential_id: UUID) -> None:
        super().__init__(f"Credential {credential_id} not found")
        self.credential_id = credential_id


class CredentialCannotRotateError(Exception):
    """A rotation transition is not valid from the current status.

    Fires when `rotation_started` is dispatched against a credential
    already in `Rotating` or `Revoked`, when `rotation_completed` or
    `rotation_aborted` is dispatched against a credential not in
    `Rotating`, or when the pending refs required by the completion
    transition are absent.
    """

    def __init__(
        self,
        credential_id: UUID,
        current_status: CredentialStatus,
        attempted: str,
    ) -> None:
        super().__init__(
            f"Credential {credential_id} cannot {attempted} from status {current_status.value}"
        )
        self.credential_id = credential_id
        self.current_status = current_status
        self.attempted = attempted


class CredentialCannotRevokeError(Exception):
    """Revoke was attempted on an already-revoked credential.

    Idempotent re-revocation could be silently absorbed, but a loud
    error surfaces operator intent mismatches (two operators racing
    to revoke the same compromised credential).
    """

    def __init__(self, credential_id: UUID) -> None:
        super().__init__(f"Credential {credential_id} is already revoked")
        self.credential_id = credential_id


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Credential:
    """Aggregate root: a per-facility credential binding.

    `secret_ref` is an OPAQUE POINTER (URI, KMS ARN, vault path)
    handed off to the `SecretStore` adapter at use time. The aggregate
    MUST NEVER carry the raw secret bytes; doing so would tunnel
    secret material through the event log and projections. The same
    discipline applies to `rotation_pending_secret_ref` while a
    rotation is in flight.

    `public_material_ref` is the public counterpart (verification key,
    encryption-public-key, certificate handle) when the purpose has
    one. `None` for purposes that are symmetric or where the public
    half lives elsewhere.

    `expires_at` is OPTIONAL: seal online-signing credentials may
    declare a hard expiry; offline-root credentials may not. Deciders
    check `expires_at` against `now()` before allowing purpose-specific
    use; revocation past expiry is still valid. `expires_at` stays on
    state because it is a contractual upper bound, domain-meaningful,
    and not envelope-derivable.

    Per [[project_fold_symmetry_design]] the genesis envelope
    `occurred_at` is folded onto state as `registered_at` alongside
    the identity denorm `registered_by`. The aggregate now carries
    both the moment of registration and the actor that performed it,
    so the projection-tier `CredentialLifecycleTimestamps` VO no
    longer needs to surface `registered_at` (Path C reversal for this
    field; the rotation-started timestamp still lives on the
    projection because it is mutable per rotation). `registered_by`
    is type-annotated as `ActorId` so the fold-symmetry fitness test
    can detect attribution fields structurally.
    """

    id: UUID
    facility_id: str
    audience: str
    purpose: CredentialPurpose
    secret_ref: str
    public_material_ref: str | None
    expires_at: datetime | None
    registered_by: ActorId
    registered_at: datetime
    rotation_pending_secret_ref: str | None
    rotation_pending_public_material_ref: str | None
    status: CredentialStatus
