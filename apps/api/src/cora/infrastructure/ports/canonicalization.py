"""Canonicalization port: substrate-neutral content-hash production.

`CanonicalizationPort` lifts the shipped v1 recipe (stdlib json sort-keys
+ DSSE PAE + SHA-256) into a swappable port surface. The v1 adapter
delegates byte-for-byte to `cora.infrastructure.content_hash` helpers;
future adapters at versions like `"cora/v2-cose"` can ride alongside
v1 without invalidating any shipped `content_hash` on Method,
Plan, CalibrationRevision, or signed DecisionRegistered.

The `adapter_version` field on `CanonicalizedBytes` is mandatory and
travels with the bytes for the lifetime of the artifact: the verifier
dispatches on it via `CanonicalizationRegistry.resolve(version)`,
never on a deployment-wide default. See
[[project_canonicalization_port_design]] for the lock memo.

Errors are co-located here per the port-pattern convention: they are
adapter-tier, not HTTP-mapped, and handlers capture them into event
payload metadata per the non-determinism principle.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CanonicalizedBytes:
    """Canonical wire bytes plus the adapter version that produced them.

    `payload_type` is the URI the bytes were canonicalized under (and
    bound into the PAE wrapper at v1). `adapter_version` MUST be set
    explicitly; there is no inferred default per the locked invariant
    on the value-type boundary.
    """

    bytes_: bytes
    adapter_version: str
    payload_type: str


@runtime_checkable
class CanonicalizationPort(Protocol):
    """Produce wire-canonical bytes and round-trip-verify content hashes.

    Sibling to SigningPort. The two are paired by `adapter_version`
    (a v1 SigningPort signs over v1 canonicalized bytes); cross-version
    pairing is rejected at the signing-port boundary via
    `CanonicalizationVersionMismatchError`.
    """

    @property
    def adapter_version(self) -> str: ...

    def canonicalize(self, payload_type: str, payload: Any) -> CanonicalizedBytes: ...

    def verify_content_hash(self, payload_type: str, payload: Any, claimed_hash: str) -> bool: ...


class CanonicalizationFailedError(Exception):
    """Input payload could not be canonicalized under the adapter's allowlist.

    v1 raises this when the recursive canonicalize pass encounters a
    type outside the closed allowlist (`UUID | str | int | bool | None
    | dict[str, primitive] | list[primitive] | enum | rfc3339-string`).
    Decimal, NaN float, bytes leaf, datetime-not-pre-stringified, and
    unhashable types all surface here. Reason carries the offending
    type or value so audits can replay the failure.
    """

    def __init__(self, payload_type: str, adapter_version: str, reason: str) -> None:
        super().__init__(
            f"Canonicalization failed for payload_type={payload_type!r} "
            f"under adapter_version={adapter_version!r}: {reason}"
        )
        self.payload_type = payload_type
        self.adapter_version = adapter_version
        self.reason = reason


class ContentHashMismatchError(Exception):
    """Round-trip content-hash verification rejected a payload.

    Raised by `verify_content_hash` only when the caller opts for
    raise-on-mismatch instead of the default bool return. Carries
    both hashes for forensic comparison and the adapter version that
    recomputed the hash.
    """

    def __init__(
        self,
        payload_type: str,
        claimed_hash: str,
        recomputed_hash: str,
        adapter_version: str,
    ) -> None:
        super().__init__(
            f"Content hash mismatch for payload_type={payload_type!r} "
            f"under adapter_version={adapter_version!r}: "
            f"claimed={claimed_hash!r} recomputed={recomputed_hash!r}"
        )
        self.payload_type = payload_type
        self.claimed_hash = claimed_hash
        self.recomputed_hash = recomputed_hash
        self.adapter_version = adapter_version


class UnsupportedCanonicalizationVersionError(Exception):
    """`CanonicalizationRegistry.resolve` was asked for an unregistered version.

    Carries the requested version plus the set of registered versions
    so operator diagnostics can immediately see the deployment surface
    without rerunning the resolver.
    """

    def __init__(self, requested_version: str, registered_versions: Iterable[str]) -> None:
        registered_tuple = tuple(registered_versions)
        super().__init__(
            f"Canonicalization adapter not registered for version "
            f"{requested_version!r}; registered={registered_tuple!r}"
        )
        self.requested_version = requested_version
        self.registered_versions = registered_tuple


__all__ = [
    "CanonicalizationFailedError",
    "CanonicalizationPort",
    "CanonicalizedBytes",
    "ContentHashMismatchError",
    "UnsupportedCanonicalizationVersionError",
]
