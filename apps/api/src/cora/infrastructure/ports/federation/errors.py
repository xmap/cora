"""Federation port-tier error family.

Mirrors the ControlPort error-family pattern: every error carries
identifying context as keyword fields so logs and decider captures
do not string-parse. None of these are HTTP-mapped at the port tier;
the BC's route layer wraps them into HTTP responses per
`cora.federation.routes` exception handlers.

`UnauthorizedError` lives in `cora.federation.errors` (BC-tier), NOT
here, because it maps to HTTP 403 and is operator-facing; port-tier
keeps the system-shaped errors that the verifier and adapter recipes
raise.
"""

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.federation.value_types import (
    ArtifactReference,
    PublicationStatus,
    StageName,
)


class FederationPermitNotFoundError(Exception):
    """Port-tier 404-shaped: a permit lookup missed.

    `lookup_kind` discriminates inbound-vs-outbound lookup paths so
    the decider can route the diagnostic to the right operator
    workflow.
    """

    def __init__(self, permit_id: UUID, lookup_kind: str) -> None:
        super().__init__(
            f"Federation permit not found: permit_id={permit_id!r} lookup_kind={lookup_kind!r}"
        )
        self.permit_id = permit_id
        self.lookup_kind = lookup_kind


class FederationSignatureInvalidError(Exception):
    """Verification ran the math and the artifact failed a stage.

    `failed_stage` names which stage of `VerificationOutcome.stage_results`
    flipped to `fail`; recoverable diagnostic for the operator.
    """

    def __init__(self, content_hash: bytes, envelope_kind: str, failed_stage: StageName) -> None:
        super().__init__(
            f"Federation signature invalid: envelope_kind={envelope_kind!r} "
            f"failed_stage={failed_stage!r} content_hash={content_hash.hex()}"
        )
        self.content_hash = content_hash
        self.envelope_kind = envelope_kind
        self.failed_stage = failed_stage


class FederationSignerUntrustedError(Exception):
    """Math passed but the resolved key is not in our trust anchor.

    Distinct from `FederationSignatureInvalidError` so the operator
    can tell "the math failed" from "the math passed but the signer
    is not allowed."
    """

    def __init__(self, content_hash: bytes, envelope_kind: str, attempted_key_ref: str) -> None:
        super().__init__(
            f"Federation signer untrusted: envelope_kind={envelope_kind!r} "
            f"attempted_key_ref={attempted_key_ref!r} content_hash={content_hash.hex()}"
        )
        self.content_hash = content_hash
        self.envelope_kind = envelope_kind
        self.attempted_key_ref = attempted_key_ref


class FederationPublicationContentDriftError(Exception):
    """TOCTOU defense: fetched bytes do not hash to the referenced content.

    SLSA subject-digest binding analog. The pull adapter MUST raise
    this before signature verification runs; serving bytes whose
    hash does not match the reference is a content-drift attack
    that signature checking would silently mask.
    """

    def __init__(self, reference_content_hash: bytes, fetched_content_hash: bytes) -> None:
        super().__init__(
            f"Federation publication content drift: "
            f"reference={reference_content_hash.hex()} fetched={fetched_content_hash.hex()}"
        )
        self.reference_content_hash = reference_content_hash
        self.fetched_content_hash = fetched_content_hash


class FederationCredentialRevokedError(Exception):
    """The signing credential for this artifact has been revoked.

    Surfaces when verify-time policy intersects the credential's
    revocation timeline; distinct from `SignerUntrustedError` so the
    operator can distinguish "never trusted" from "trusted then
    revoked."
    """

    def __init__(self, credential_id: UUID, revoked_at: datetime) -> None:
        super().__init__(
            f"Federation credential revoked: credential_id={credential_id!r} "
            f"revoked_at={revoked_at.isoformat()}"
        )
        self.credential_id = credential_id
        self.revoked_at = revoked_at


class FederationRetryExhaustedError(Exception):
    """Adapter exhausted its retry policy.

    Decider records the attempt count and the class of the final
    error so post-mortems do not require log archaeology.
    """

    def __init__(self, reference: ArtifactReference, attempts: int, last_error_class: str) -> None:
        super().__init__(
            f"Federation retry exhausted after {attempts} attempts: "
            f"last_error_class={last_error_class!r} "
            f"source_facility_id={reference.source_facility_id!r}"
        )
        self.reference = reference
        self.attempts = attempts
        self.last_error_class = last_error_class


class FederationCircuitOpenError(Exception):
    """Circuit-breaker open for the source facility.

    Pull adapter returns this without making the network call,
    based on a prior cluster of failures. Decider records and
    surfaces a `Retry-After` to the caller.
    """

    def __init__(self, source_facility_id: UUID, opened_at: datetime) -> None:
        super().__init__(
            f"Federation circuit open for source_facility_id={source_facility_id!r} "
            f"since {opened_at.isoformat()}"
        )
        self.source_facility_id = source_facility_id
        self.opened_at = opened_at


class FederationRateLimitExceededError(Exception):
    """Peer rate-limited us; carries advertised retry-after as seconds.

    Opaque seconds at the port; the BC's route layer translates to
    an HTTP `Retry-After` header on the upstream response when
    propagating to the operator.
    """

    def __init__(self, source_facility_id: UUID, retry_after_seconds: int) -> None:
        super().__init__(
            f"Federation rate limit exceeded for source_facility_id={source_facility_id!r}; "
            f"retry_after_seconds={retry_after_seconds}"
        )
        self.source_facility_id = source_facility_id
        self.retry_after_seconds = retry_after_seconds


class FederationAdoptionWindowClosedError(Exception):
    """The publication is past its adoption window.

    `publication_status` discriminates the closing reason:
    Yanked | Withdrawn | Expired | AbiTierObsoleteOrRemoved. The
    verifier raises this BEFORE returning `Verified` so a yanked
    artifact can never be adopted via a stale reference.
    """

    def __init__(self, content_hash: bytes, publication_status: PublicationStatus) -> None:
        super().__init__(
            f"Federation adoption window closed: status={publication_status!r} "
            f"content_hash={content_hash.hex()}"
        )
        self.content_hash = content_hash
        self.publication_status = publication_status


class FederationReceiptMissingError(Exception):
    """Required receipt kinds absent on a receipt-bearing envelope.

    Per sec-1: raised when `FederationTrustContext.required_receipt_kinds`
    is non-empty AND `envelope.receipts` does not contain at least
    one receipt of each required kind. Closes the receipt-suppression
    downgrade vector where an empty receipts tuple would silently
    bypass transparency-log evidence on receipt-bearing arms.
    """

    def __init__(
        self,
        content_hash: bytes,
        envelope_kind: str,
        required_receipt_kinds: Iterable[str],
        observed_receipt_kinds: Iterable[str],
    ) -> None:
        required_tuple = tuple(sorted(required_receipt_kinds))
        observed_tuple = tuple(sorted(observed_receipt_kinds))
        super().__init__(
            f"Federation receipt missing: envelope_kind={envelope_kind!r} "
            f"required={required_tuple!r} observed={observed_tuple!r} "
            f"content_hash={content_hash.hex()}"
        )
        self.content_hash = content_hash
        self.envelope_kind = envelope_kind
        self.required_receipt_kinds = required_tuple
        self.observed_receipt_kinds = observed_tuple


class NoAdapterForFacilityError(Exception):
    """`FederationRegistry` has no adapter registered for this facility prefix.

    Mirrors `NoAdapterForAddressError` in ControlPort; the operator
    sees the missing prefix from logs alone, without having to
    reconstruct routing from config.
    """

    def __init__(self, source_facility_id: UUID) -> None:
        super().__init__(
            f"No federation adapter registered for source_facility_id={source_facility_id!r}"
        )
        self.source_facility_id = source_facility_id


class FederationCanonicalizationMismatchError(Exception):
    """Cross-canonicalization-profile drift detected.

    Bridges Memo 1 and Memo 3: the verifier raises this when the
    expected canonicalization profile (per the trust context's
    `payload_type` allowlist) does not match the profile observed
    on the artifact's `canonicalization_version`. Distinct from
    signature-invalid because the signature would correctly verify
    against the wrong profile.
    """

    def __init__(
        self,
        content_hash: bytes,
        expected_canonicalization_profile_id: str,
        observed_profile_id: str,
    ) -> None:
        super().__init__(
            f"Federation canonicalization mismatch: "
            f"expected={expected_canonicalization_profile_id!r} "
            f"observed={observed_profile_id!r} "
            f"content_hash={content_hash.hex()}"
        )
        self.content_hash = content_hash
        self.expected_canonicalization_profile_id = expected_canonicalization_profile_id
        self.observed_profile_id = observed_profile_id


__all__ = [
    "FederationAdoptionWindowClosedError",
    "FederationCanonicalizationMismatchError",
    "FederationCircuitOpenError",
    "FederationCredentialRevokedError",
    "FederationPermitNotFoundError",
    "FederationPublicationContentDriftError",
    "FederationRateLimitExceededError",
    "FederationReceiptMissingError",
    "FederationRetryExhaustedError",
    "FederationSignatureInvalidError",
    "FederationSignerUntrustedError",
    "NoAdapterForFacilityError",
]
