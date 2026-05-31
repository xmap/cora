"""Default v1 signing adapter: Ed25519 over canonicalized bytes.

`DefaultSigningAdapter` IS the shipped v1 signing recipe per
[[project_canonicalization_port_design]]: Ed25519 detached signature
over `CanonicalizedBytes.bytes_`, with `KeyHandle` narrowed to a
`JwksKid(kid: str)` frozen dataclass.

The adapter pairs by `adapter_version`: it refuses to sign or verify
over `CanonicalizedBytes` whose `adapter_version` does not match
`"cora/v1"`, raising `CanonicalizationVersionMismatchError`. The
architecture-fitness suite enforces the same invariant row-by-row
on stored events.

Verification verdict mapping:

  - `Valid`        : Ed25519 verify returned successfully
  - `Invalid`      : Ed25519 verify raised `InvalidSignature` (math rejected)
  - `Unverifiable` : key not in trust context, public-key bytes malformed,
                     or resolver raised (key gone, transient outage); the
                     verifier could not run the math at all

The adapter takes a private-key loader (sign-side) and a public-key
resolver (verify-side) at construction. Resolvers are call-site
specific (in-memory cache for hot verify paths, JWKS-backed for
federated paths). The constructor injection keeps the port surface
narrow and matches the existing `cora.infrastructure.signing.verify_signature`
resolver-callable shape.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cora.infrastructure.ports.canonicalization import CanonicalizedBytes
from cora.infrastructure.ports.signing import (
    CanonicalizationVersionMismatchError,
    Signature,
    SignatureVerification,
    SigningKeyNotFoundError,
    SigningTrustContext,
)

_ADAPTER_VERSION = "cora/v1"


@dataclass(frozen=True, slots=True)
class JwksKid:
    """v1 KeyHandle: opaque JWKS kid string.

    Frozen so it hashes consistently for `SigningTrustContext.trusted_signing_keys`
    membership tests. The `kid` is the same string the JWKS adapter
    maps to a public key; the adapter's resolver callable does the
    lookup at verify time.
    """

    kid: str


class DefaultSigningAdapter:
    """v1 signing adapter: Ed25519 detached signature over PAE bytes."""

    def __init__(
        self,
        *,
        private_key_loader: Callable[[JwksKid], Awaitable[bytes]],
        public_key_resolver: Callable[[str], Awaitable[bytes]],
        clock: Callable[[], datetime],
    ) -> None:
        self._private_key_loader = private_key_loader
        self._public_key_resolver = public_key_resolver
        self._clock = clock

    @property
    def adapter_version(self) -> str:
        return _ADAPTER_VERSION

    async def sign(
        self,
        canonicalized: CanonicalizedBytes,
        key_handle: JwksKid,
    ) -> Signature:
        self._require_matching_version(canonicalized)
        try:
            private_bytes = await self._private_key_loader(key_handle)
        except KeyError as exc:
            raise SigningKeyNotFoundError(
                key_handle=key_handle, adapter_version=_ADAPTER_VERSION
            ) from exc
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        signature_bytes = private_key.sign(canonicalized.bytes_)
        return Signature(
            bytes_=signature_bytes,
            adapter_version=_ADAPTER_VERSION,
            key_handle=key_handle,
            signed_at=self._clock(),
        )

    async def verify(
        self,
        canonicalized: CanonicalizedBytes,
        signature: Signature,
        signing_trust_context: SigningTrustContext,
    ) -> SignatureVerification:
        self._require_matching_version(canonicalized)
        if signature.adapter_version != _ADAPTER_VERSION:
            raise CanonicalizationVersionMismatchError(
                canonicalized_version=canonicalized.adapter_version,
                signing_version=signature.adapter_version,
            )
        if signature.key_handle not in signing_trust_context.trusted_signing_keys:
            return SignatureVerification(
                verdict="Unverifiable",
                detail=f"key_handle={signature.key_handle!r} not in trust context",
            )
        kid = self._extract_kid(signature.key_handle)
        try:
            public_key_bytes = await self._public_key_resolver(kid)
        except KeyError as exc:
            return SignatureVerification(
                verdict="Unverifiable",
                detail=f"public key not resolvable for kid={kid!r}: {exc}",
            )
        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except ValueError as exc:
            return SignatureVerification(
                verdict="Unverifiable",
                detail=f"public key bytes malformed for kid={kid!r}: {exc}",
            )
        try:
            public_key.verify(signature.bytes_, canonicalized.bytes_)
        except InvalidSignature:
            return SignatureVerification(
                verdict="Invalid",
                detail=f"Ed25519 verify rejected signature for kid={kid!r}",
            )
        return SignatureVerification(verdict="Valid")

    @staticmethod
    def _require_matching_version(canonicalized: CanonicalizedBytes) -> None:
        if canonicalized.adapter_version != _ADAPTER_VERSION:
            raise CanonicalizationVersionMismatchError(
                canonicalized_version=canonicalized.adapter_version,
                signing_version=_ADAPTER_VERSION,
            )

    @staticmethod
    def _extract_kid(key_handle: object) -> str:
        if isinstance(key_handle, JwksKid):
            return key_handle.kid
        raise SigningKeyNotFoundError(key_handle=key_handle, adapter_version=_ADAPTER_VERSION)


__all__ = ["DefaultSigningAdapter", "JwksKid"]
