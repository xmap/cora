"""ByteSigner port: substrate-neutral signature production over canonical bytes.

`ByteSigner` is the sibling to `Canonicalizer`. The two are
paired by `adapter_version` (a v1 ByteSigner signs over v1
canonicalized bytes); cross-version pairing is rejected at the
port boundary via `CanonicalizationVersionMismatchError`.

The v1 adapter Ed25519-signs over `CanonicalizedBytes.bytes_` and
narrows `KeyHandle` to a `JwksKid` carrying the JWKS kid string.
Future arms can narrow `KeyHandle` differently (an X.509 chain
reference for Sigstore-keyless; a COSE_Key thumbprint for
COSE_Sign1) without changing the port surface.

`SigningTrustContext` carries the policy under which signature
verification runs (trusted keys, algorithm allowlist, validity
window, expected payload type). It is sibling to Memo 1's
`FederationTrustContext` which carries federation-tier policy
(`allowed_credentials`, `abi_tier_floor`, `required_receipt_kinds`);
the two are at different tiers and have distinct shapes.

Level note: `ByteSigner` is the low-level primitive that signs raw
canonical bytes under a key handle. The sibling `Signer` port at
`cora.infrastructure.ports.signer` is the higher-level
event-provenance signer (it canonicalizes an event payload via the
content-hash pipeline and returns the signature triple the event row
persists). They are distinct levels, not duplicates.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from cora.infrastructure.ports.canonicalizer import CanonicalizedBytes

KeyHandle = Any
"""Opaque adapter-specific key reference.

Typed as `Any` at the port boundary; each adapter narrows internally.
v1 uses `JwksKid(kid: str)`; future Sigstore arm uses an X.509 chain
reference; future COSE arm uses a COSE_Key thumbprint or CBOR bstr kid.
"""


@dataclass(frozen=True, slots=True)
class Signature:
    """Raw signature bytes plus the adapter version that produced them.

    Parallel to `CanonicalizedBytes` so `adapter_version` is the single
    dispatch key on either side. `bytes_` is the raw signature output
    (64 bytes for v1 Ed25519; variable for future arms). `signed_at`
    captures the wall-clock moment the signature was produced and is
    bound into the signature payload metadata, not the signed bytes.
    """

    bytes_: bytes
    adapter_version: str
    key_handle: KeyHandle
    signed_at: datetime


@dataclass(frozen=True, slots=True)
class SigningTrustContext:
    """Policy under which a signature verification runs.

    `trusted_signing_keys` is the frozenset of key handles the
    verifier will accept (membership-tested against the
    `Signature.key_handle` field). `algorithm_allowlist` rejects
    legacy or downgrade algorithms before any crypto runs.
    `expected_payload_type` is the URI the canonicalized bytes MUST
    have been bound to. `validity_window` is an optional pair
    `(not_before, not_after)`; `None` skips the temporal check.
    """

    trusted_signing_keys: frozenset[KeyHandle]
    algorithm_allowlist: frozenset[str]
    expected_payload_type: str
    validity_window: tuple[datetime, datetime] | None


@dataclass(frozen=True, slots=True)
class SignatureVerification:
    """Closed-enum verdict plus opaque detail string.

    Mirrors ControlPort's `Quality` + `quality_detail` pattern: the
    verdict drives downstream policy, the detail string is for
    forensics and never parsed by callers. `Unverifiable` is distinct
    from `Invalid`: `Invalid` means "the math rejected the signature";
    `Unverifiable` means "the verifier could not run the math at all"
    (key not resolvable, algorithm not implemented, transient backend
    outage).
    """

    verdict: Literal["Valid", "Invalid", "Unverifiable"]
    detail: str = ""


@runtime_checkable
class ByteSigner(Protocol):
    """Sign canonicalized bytes under a key handle; verify signatures.

    Both methods are async because production adapters are network-
    bound (Fulcio short-lived cert issuance, KMS sign, transparency-
    log inclusion). In-process adapters wrap their sync work as async.
    """

    @property
    def adapter_version(self) -> str: ...

    async def sign(
        self,
        canonicalized: CanonicalizedBytes,
        key_handle: KeyHandle,
    ) -> Signature: ...

    async def verify(
        self,
        canonicalized: CanonicalizedBytes,
        signature: Signature,
        signing_trust_context: SigningTrustContext,
    ) -> SignatureVerification: ...


class SigningKeyNotFoundError(Exception):
    """Adapter cannot resolve the supplied `key_handle`.

    Distinct from `SignatureInvalidError` so the operator can tell
    "key gone" from "key present but signature does not verify."
    Surfaces when JWKS rotation is mid-flight, the kid is not in
    the current JWKS, or an X.509 chain does not anchor against
    pinned roots.
    """

    def __init__(self, key_handle: KeyHandle, adapter_version: str) -> None:
        super().__init__(
            f"Signing key not found for key_handle={key_handle!r} "
            f"under adapter_version={adapter_version!r}"
        )
        self.key_handle = key_handle
        self.adapter_version = adapter_version


class SignatureInvalidError(Exception):
    """Signature bytes verified against canonicalized bytes and rejected.

    Reason carries the adapter-specific failure mode: Ed25519 verify
    returned False; X.509 leaf expired at sign time; SAN extension
    mismatch on a Sigstore Fulcio cert.
    """

    def __init__(self, adapter_version: str, reason: str) -> None:
        super().__init__(f"Signature invalid under adapter_version={adapter_version!r}: {reason}")
        self.adapter_version = adapter_version
        self.reason = reason


class UnsupportedSigningAlgorithmError(Exception):
    """The `KeyHandle` references an algorithm the adapter does not implement.

    Raised before any crypto runs. Used by the algorithm-allowlist
    gate inside `ByteSigner.verify` so legacy algorithms cannot
    downgrade a verification.
    """

    def __init__(self, requested_algorithm: str, adapter_version: str) -> None:
        super().__init__(
            f"Signing algorithm {requested_algorithm!r} not supported "
            f"by adapter_version={adapter_version!r}"
        )
        self.requested_algorithm = requested_algorithm
        self.adapter_version = adapter_version


class CanonicalizationVersionMismatchError(Exception):
    """Cross-version signing rejected at the port boundary.

    A v1 ByteSigner refuses to sign over v2 CanonicalizedBytes and
    vice versa: pairing is mandatory per the
    `signing_version == canonicalization_version` invariant. The
    architecture-fitness suite asserts this row-by-row on every
    signed event.
    """

    def __init__(self, canonicalized_version: str, signing_version: str) -> None:
        super().__init__(
            f"Canonicalization/signing version mismatch: "
            f"canonicalized={canonicalized_version!r} signing={signing_version!r}"
        )
        self.canonicalized_version = canonicalized_version
        self.signing_version = signing_version


def algorithms_intersection(requested: Iterable[str], allowlist: frozenset[str]) -> frozenset[str]:
    """Return the intersection of requested algorithms with an allowlist.

    Helper that adapters reuse when narrowing a candidate algorithm
    set against `SigningTrustContext.algorithm_allowlist`. Returns
    the allowed subset; an empty result means the caller must raise
    `UnsupportedSigningAlgorithmError` against the first requested
    entry.
    """
    return frozenset(requested) & allowlist


__all__ = [
    "ByteSigner",
    "CanonicalizationVersionMismatchError",
    "KeyHandle",
    "Signature",
    "SignatureInvalidError",
    "SignatureVerification",
    "SigningKeyNotFoundError",
    "SigningTrustContext",
    "UnsupportedSigningAlgorithmError",
    "algorithms_intersection",
]
