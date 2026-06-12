"""In-memory Ed25519 adapter for the `Signer` event-provenance port.

`InMemorySigner` is the first adapter for `cora.infrastructure.ports.signer.Signer`.
It generates an Ed25519 keypair on construction, canonicalizes an event
payload via the shared content-hash pipeline (the exact bytes
`cora.infrastructure.signing.verify_signature` recomputes), and signs.
A row signed here round-trips through the verify path in the same
process via `resolve_public_key`.

It signs for any `actor_id` with its single in-process key; production
overrides this with a KMS / Sigstore-keyless adapter that resolves a
per-actor key. The key is ephemeral (regenerated per construction), so
signatures do not verify across process restarts, which is the reason
production wires a durable backend. Mirrors the in-memory-by-default
posture of `InMemorySignaturePort`, but unlike that stub this adapter
performs real Ed25519 signing.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cora.infrastructure.signing import event_type_to_payload_type
from cora.shared.content_hash import canonical_body_bytes, pae_bytes

_SIGNING_VERSION = "cora/v1"
_KID = "in-memory/ed25519"


class InMemorySigner:
    """Ed25519 `Signer` adapter backed by a single ephemeral in-process keypair."""

    def __init__(self) -> None:
        self._private_key = Ed25519PrivateKey.generate()
        self._public_key_bytes = self._private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self._kid = _KID

    @property
    def kid(self) -> str:
        return self._kid

    @property
    def public_key_bytes(self) -> bytes:
        return self._public_key_bytes

    async def sign(
        self,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        actor_id: UUID,
    ) -> tuple[bytes, str, str]:
        """Ed25519-sign the PAE-wrapped canonical payload; return (sig, kid, version)."""
        _ = actor_id  # single in-process key signs for every actor
        payload_type = event_type_to_payload_type(event_type)
        signature = self._private_key.sign(pae_bytes(payload_type, canonical_body_bytes(payload)))
        return signature, self._kid, _SIGNING_VERSION

    async def resolve_public_key(self, kid: str) -> bytes:
        """Resolve the raw Ed25519 public key for `kid`, shaped for `verify_signature`."""
        if kid != self._kid:
            raise KeyError(kid)
        return self._public_key_bytes


__all__ = ["InMemorySigner"]
