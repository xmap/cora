"""SecretStore port: vault-tier seam for federation credential material.

The Federation BC's `Credential` aggregate stores opaque references
(`secret_ref: str`, `public_material_ref: str`) on the event stream and
projection rows. The actual secret bytes never appear in events,
payloads, projections, or logs; resolution happens behind this port at
the handler tier.

This is the AH#6 invariant from `project_federation_port_design.md`:
secret material is opaque-by-reference everywhere except inside
`SecretStore.load`. Adapters are responsible for wrapping concrete
backends (filesystem keyring, HashiCorp Vault, AWS Secrets Manager,
cloud KMS) without leaking bytes upstream.

## Convention

Mirrors the consumer-shaped port pattern used by `Authorize`,
`ClearanceLookup`, and `Signer`: a single `Protocol` with named
methods (per PEP 544 + the typing-community guidance cited in
`Authorize`); typed errors as plain `Exception` subclasses with
HTTP-status mapping called out in their docstrings; an in-memory
adapter sibling at
`cora.infrastructure.adapters.in_memory_secret_store` for tests and
dev.

Async methods even when the in-memory adapter could be sync, because
production backends (Vault, KMS) are network-bound and the consumer
contract must not change with the backend.

## What is NOT here

  - The reference format / opacity contract: callers MUST treat
    `ref: str` as opaque. The Credential aggregate is the only producer
    of refs today; future production adapters MAY mint refs out of band
    (KMS resource names, Vault paths) and the aggregate stores them
    verbatim.
  - Rotation choreography. Two-staged rotation lives on the Credential
    aggregate (`rotation_pending_secret_ref`); the port has no opinion.
  - Public-key resolution for verification. That lives on the
    verification path (see `cora.infrastructure.signing`), not on this
    port, because read-time resolution composes differently from
    write-time storage.

## Error model

Two adapter-tier errors:

  - `SecretNotFoundError` (HTTP 404): the ref does not resolve to any
    stored secret. May indicate a typo, a revoked secret, or a missing
    rotation step.
  - `SecretStoreError` (HTTP 500): the backend is unreachable or
    misbehaving. Transient or systemic; callers MAY retry.

`revoke` is intentionally idempotent (no error on missing ref) so that
rotation-abort and revoke flows can be re-driven safely.
"""

from typing import Protocol


class SecretNotFoundError(Exception):
    """The `ref` does not resolve to any stored secret.

    Intended to surface as HTTP 404 at the route layer once a consumer
    wires this port (no handler is registered today; the SecretStore
    seam is reserved, not yet consumed). The caller asked for material
    that the vault has no record of: a typo, a revoked secret, or a
    rotation step that never landed.
    """

    def __init__(self, ref: str) -> None:
        super().__init__(f"Secret not found: {ref!r}")
        self.ref = ref


class SecretStoreError(Exception):
    """The secret store backend is unreachable or misbehaving.

    Intended to surface as HTTP 500 once a consumer wires this port (no
    handler is registered today). The failure is opaque to the caller
    and not addressable by a routine retry. Adapters with a configured
    fallback MAY catch this internally before it reaches the caller.
    """

    def __init__(self, backend: str, detail: str = "") -> None:
        super().__init__(
            f"Secret store backend {backend!r} unavailable" + (f": {detail}" if detail else "")
        )
        self.backend = backend
        self.detail = detail


class SecretStore(Protocol):
    """Vault-tier port for federation credential material.

    Three named operations: `store`, `load`, `revoke`. Callers pass
    opaque string refs and (for store) raw bytes; the adapter owns the
    backend-specific encoding. The aggregate never sees bytes; the
    route layer never sees bytes; only the handler call site that
    needs material to mint a federation packet calls `load` and uses
    the bytes locally before they go out of scope.
    """

    async def store(self, ref: str, secret: bytes) -> None:
        """Persist `secret` under `ref`.

        Overwrite semantics are adapter-defined; the in-memory adapter
        overwrites. Rotation flows mint a new ref rather than rewriting
        an existing one, so overwrite collisions are not load-bearing
        in practice.

        Raises `SecretStoreError` if the backend is unreachable.
        """
        ...

    async def load(self, ref: str) -> bytes:
        """Resolve `ref` to the raw secret bytes.

        Raises `SecretNotFoundError` if the ref is unknown.
        Raises `SecretStoreError` if the backend is unreachable.
        """
        ...

    async def revoke(self, ref: str) -> None:
        """Remove the secret stored under `ref`.

        Idempotent: revoking an unknown ref is a no-op, not an error,
        so that rotation-abort and revoke flows can be re-driven
        safely.

        Raises `SecretStoreError` if the backend is unreachable.
        """
        ...


__all__ = [
    "SecretNotFoundError",
    "SecretStore",
    "SecretStoreError",
]
