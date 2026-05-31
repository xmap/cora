"""Federation port-tier package.

Three Protocols (`PublishPort`, `PullPort`, `SignaturePort`) co-located
in this sub-package because the value-type catalog plus the 12-error
family is more than one file's worth and mirrors
`cora/infrastructure/observability/` shape.

The fourth federation-relevant port (`SecretStore`) is a kernel-tier
sibling at `cora.infrastructure.ports.secret_store` (consumed by any
BC needing key/secret material, not federation-exclusive).

All wire-tier vocabulary (DSSE, COSE, JWS, Sigstore, Fulcio, Rekor,
SCITT, JWKS, CBOR) is owned by the adapters under
`cora/federation/adapters/*` and `cora/infrastructure/adapters/*`.
The port tier here stays substrate-neutral.
"""

from cora.infrastructure.ports.federation.errors import (
    FederationAdoptionWindowClosedError,
    FederationCanonicalizationMismatchError,
    FederationCircuitOpenError,
    FederationCredentialRevokedError,
    FederationPermitNotFoundError,
    FederationPublicationContentDriftError,
    FederationRateLimitExceededError,
    FederationReceiptMissingError,
    FederationRetryExhaustedError,
    FederationSignatureInvalidError,
    FederationSignerUntrustedError,
    NoAdapterForFacilityError,
)
from cora.infrastructure.ports.federation.publish_port import PublishPort
from cora.infrastructure.ports.federation.pull_port import PullPort
from cora.infrastructure.ports.federation.signature_port import SignaturePort
from cora.infrastructure.ports.federation.value_types import (
    ArtifactReference,
    AssistedBy,
    CoDevelopedBy,
    CoseSign1ScittEnvelope,
    CredentialRef,
    DcoEntry,
    DsseSigstoreKeylessEnvelope,
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    FetchProvenance,
    PublicationStatus,
    PublishedArtifact,
    PublishReceipt,
    PulledArtifact,
    Receipt,
    Rejected,
    RejectionReason,
    SignatureEnvelope,
    SignedOffBy,
    StageName,
    StageResult,
    UnverifiabilityReason,
    Unverifiable,
    VerificationOutcome,
    Verified,
)

__all__ = [
    "ArtifactReference",
    "AssistedBy",
    "CoDevelopedBy",
    "CoseSign1ScittEnvelope",
    "CredentialRef",
    "DcoEntry",
    "DsseSigstoreKeylessEnvelope",
    "DsseStaticJwksEnvelope",
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
    "FederationTrustContext",
    "FetchProvenance",
    "NoAdapterForFacilityError",
    "PublicationStatus",
    "PublishPort",
    "PublishReceipt",
    "PublishedArtifact",
    "PullPort",
    "PulledArtifact",
    "Receipt",
    "Rejected",
    "RejectionReason",
    "SignatureEnvelope",
    "SignaturePort",
    "SignedOffBy",
    "StageName",
    "StageResult",
    "UnverifiabilityReason",
    "Unverifiable",
    "VerificationOutcome",
    "Verified",
]
