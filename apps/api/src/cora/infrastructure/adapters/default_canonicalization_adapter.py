"""Default v1 canonicalization adapter delegating to the shipped helpers.

`DefaultCanonicalizationAdapter` IS the shipped v1 recipe per
[[project_canonicalization_port_design]]: NFC + sort-keys JSON +
DSSE PAE + SHA-256. The adapter is a thin wrapper around
`cora.infrastructure.content_hash` helpers; bit-identical output
is guaranteed because they share the implementation.

Constraint on `payload_type`: the v1 adapter accepts ONLY URIs that
match the `application/vnd.cora.<kebab-event-type>+json` scheme. Any
other payload_type raises `CanonicalizationFailedError` before any
canonicalization runs. This anchors the v1 recipe to the CORA event-
type vocabulary; future arms (CBOR, COSE_Sign1) may accept different
URI schemes.

The `adapter_version` is the literal string `"cora/v1"`. This string
IS the version identity; never derived from package metadata or
config.
"""

from typing import Any

from cora.infrastructure.content_hash import (
    canonical_body_bytes,
    compute_content_hash,
    pae_bytes,
)
from cora.infrastructure.ports.canonicalization import (
    CanonicalizationFailedError,
    CanonicalizedBytes,
)

_PAYLOAD_TYPE_PREFIX = "application/vnd.cora."
_PAYLOAD_TYPE_SUFFIX = "+json"
_ADAPTER_VERSION = "cora/v1"


class DefaultCanonicalizationAdapter:
    """v1 canonicalization adapter: stdlib json sort-keys + DSSE PAE + SHA-256."""

    @property
    def adapter_version(self) -> str:
        return _ADAPTER_VERSION

    def canonicalize(self, payload_type: str, payload: Any) -> CanonicalizedBytes:
        self._validate_payload_type(payload_type)
        try:
            body_bytes = canonical_body_bytes(payload)
            wrapped = pae_bytes(payload_type, body_bytes)
        except (TypeError, ValueError) as exc:
            raise CanonicalizationFailedError(
                payload_type=payload_type,
                adapter_version=_ADAPTER_VERSION,
                reason=str(exc),
            ) from exc
        return CanonicalizedBytes(
            bytes_=wrapped,
            adapter_version=_ADAPTER_VERSION,
            payload_type=payload_type,
        )

    def verify_content_hash(self, payload_type: str, payload: Any, claimed_hash: str) -> bool:
        self._validate_payload_type(payload_type)
        try:
            recomputed = compute_content_hash(payload_type, payload)
        except (TypeError, ValueError) as exc:
            raise CanonicalizationFailedError(
                payload_type=payload_type,
                adapter_version=_ADAPTER_VERSION,
                reason=str(exc),
            ) from exc
        return recomputed == claimed_hash

    @staticmethod
    def _validate_payload_type(payload_type: str) -> None:
        if not payload_type.startswith(_PAYLOAD_TYPE_PREFIX) or not payload_type.endswith(
            _PAYLOAD_TYPE_SUFFIX
        ):
            raise CanonicalizationFailedError(
                payload_type=payload_type,
                adapter_version=_ADAPTER_VERSION,
                reason=(
                    f"v1 adapter accepts only {_PAYLOAD_TYPE_PREFIX}<kebab>"
                    f"{_PAYLOAD_TYPE_SUFFIX} URIs"
                ),
            )


__all__ = ["DefaultCanonicalizationAdapter"]
