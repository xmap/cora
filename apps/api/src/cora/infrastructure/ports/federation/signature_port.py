"""SignaturePort: federation-tier verify-and-sign over SignatureEnvelope.

Per arch-2 (SignaturePort delegates to SigningPort): this port owns
envelope construction + receipt hooks + credential resolution. Raw
signature math (`Ed25519.sign`, `ECDSA.sign`) lives on
`SigningPort` at the kernel tier (Memo 3). The architecture-fitness
test `tests/architecture/test_signature_port_delegates_to_signing_port.py`
will land alongside the first wire-tier adapter and assert that
every `SignaturePort.sign` adapter calls a method on a `SigningPort`
instance for the underlying signature math, never invoking crypto
libraries (`cryptography.hazmat`, `nacl`, `pyca`) directly.

`canonicalized` is `CanonicalizedBytes` (from the kernel SigningPort
module), NOT raw `bytes`; this prevents bypassing the canonicalization
recipe.

Per AH#9: SignaturePort.sign MUST NOT accept raw key material. The
adapter resolves the signing credential from
`trust_context.allowed_credentials` via SecretStore and delegates
to SigningPort. No `sign_with_raw_key` variant.

Rejected: per-family Protocols (`DsseSignaturePort`,
`CoseSignaturePort`, `PgpSignaturePort`). One Protocol over the
tagged-union `SignatureEnvelope`; per-family parse and per-arm
crypto recipes live inside `cora/federation/adapters/<family>_signature_port.py`.
"""

from typing import Protocol, runtime_checkable

from cora.infrastructure.ports.canonicalization import CanonicalizedBytes
from cora.infrastructure.ports.federation.value_types import (
    FederationTrustContext,
    PublishedArtifact,
    SignatureEnvelope,
    VerificationOutcome,
)


@runtime_checkable
class SignaturePort(Protocol):
    """Verify a SignatureEnvelope; build a fresh envelope over canonical bytes."""

    async def verify(
        self,
        artifact: PublishedArtifact,
        trust_context: FederationTrustContext,
    ) -> VerificationOutcome: ...

    async def sign(
        self,
        canonicalized: CanonicalizedBytes,
        trust_context: FederationTrustContext,
    ) -> SignatureEnvelope: ...


__all__ = ["SignaturePort"]
