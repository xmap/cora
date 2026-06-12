"""Per-version dispatch for ByteSigner adapters.

`SigningRegistry` is the sibling to `CanonicalizationRegistry` for
the signing side. Same shape: register by `adapter_version`, resolve
by exact-match, raise on duplicates, async-close-all on teardown.
The one shape difference: no `default_version()`. The signing
adapter is dispatched by the canonicalization version on the same
event (the matched-pair invariant); a deployment-wide signing
default would let writers pair a v1 canonicalization with a v2
signing adapter on the same event, which the row-level fitness
ban explicitly forbids.

The registry can be empty at construction. The Kernel wires
`DefaultCanonicalizationAdapter` immediately (zero injected deps)
but defers `DefaultSigningAdapter` registration until a later
stage wires concrete key sources (private key loader + public key
resolver). Empty registries are valid; `resolve()` against an
unregistered version raises
`UnsupportedCanonicalizationVersionError` exactly as the
canonicalization side does.
"""

import contextlib

from cora.infrastructure.ports.byte_signer import ByteSigner
from cora.infrastructure.ports.canonicalizer import (
    UnsupportedCanonicalizationVersionError,
)


class SigningRegistry:
    """Per-version dispatch for ByteSigner adapters."""

    def __init__(self) -> None:
        self._routes: list[tuple[str, ByteSigner]] = []
        self._closed = False

    def register(self, version: str, adapter: ByteSigner) -> None:
        """Register `adapter` under `version`. Duplicate version raises ValueError."""
        for existing_version, _ in self._routes:
            if existing_version == version:
                raise ValueError(
                    f"Signing adapter already registered for version "
                    f"{version!r}; re-registration is forbidden"
                )
        self._routes.append((version, adapter))

    def resolve(self, version: str) -> ByteSigner:
        """Return the adapter registered under `version`. Exact match only."""
        for registered_version, adapter in self._routes:
            if registered_version == version:
                return adapter
        raise UnsupportedCanonicalizationVersionError(
            requested_version=version,
            registered_versions=self.registered_versions(),
        )

    def registered_versions(self) -> tuple[str, ...]:
        """Return the tuple of registered version strings in registration order."""
        return tuple(v for v, _ in self._routes)

    async def aclose(self) -> None:
        """Close every registered adapter; idempotent."""
        if self._closed:
            return
        self._closed = True
        for _, adapter in self._routes:
            close = getattr(adapter, "aclose", None)
            if close is None:
                continue
            with contextlib.suppress(Exception):
                await close()


__all__ = ["SigningRegistry"]
