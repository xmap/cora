"""Per-version dispatch for Canonicalizer adapters.

`CanonicalizationRegistry` is the deployment-wide dispatch table:
every adapter registered under its `adapter_version` string is the
verification path for events that carry that version. The default
version is established at Kernel construction and stays immutable
for the lifetime of the deployment.

Modelled after `cora.operation.adapters.control_port_registry.ControlPortRegistry`
but with EXACT-version-match (not longest-prefix-match): the
`adapter_version` string is an identity, not an address space.
Duplicate-version `register()` raises `ValueError` per the locked
anti-hook (no silent replacement; that would let a deployment
re-register `"cora/v1"` with a non-default adapter and silently
break verification).

`default_version()` is the WRITE-side dispatch handle. All new
content_hash sites resolve via the default; only VERIFY-side sites
resolve by the per-event recorded version. The default is set at
construction and exposed read-only.
"""

import contextlib

from cora.infrastructure.ports.canonicalizer import (
    Canonicalizer,
    UnsupportedCanonicalizationVersionError,
)


class CanonicalizationRegistry:
    """Per-version dispatch for Canonicalizer adapters.

    Construct, register one or more adapters by `adapter_version`
    string, optionally set the deployment-wide default version,
    then resolve at read- or write-time. Kernel construction is the
    single shipped registration site; production startup registers
    `DefaultCanonicalizationAdapter` under `"cora/v1"` and sets the
    default to `"cora/v1"`.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, Canonicalizer]] = []
        self._default: str | None = None
        self._closed = False

    def register(self, version: str, adapter: Canonicalizer) -> None:
        """Register `adapter` under `version`. Duplicate version raises ValueError."""
        for existing_version, _ in self._routes:
            if existing_version == version:
                raise ValueError(
                    f"Canonicalization adapter already registered for version "
                    f"{version!r}; re-registration is forbidden"
                )
        self._routes.append((version, adapter))

    def set_default(self, version: str) -> None:
        """Set the deployment-wide default version. Must already be registered."""
        if not any(v == version for v, _ in self._routes):
            raise UnsupportedCanonicalizationVersionError(
                requested_version=version,
                registered_versions=self.registered_versions(),
            )
        self._default = version

    def resolve(self, version: str) -> Canonicalizer:
        """Return the adapter registered under `version`. Exact match only."""
        for registered_version, adapter in self._routes:
            if registered_version == version:
                return adapter
        raise UnsupportedCanonicalizationVersionError(
            requested_version=version,
            registered_versions=self.registered_versions(),
        )

    def default_version(self) -> str:
        """Return the deployment-wide default canonicalization version."""
        if self._default is None:
            raise UnsupportedCanonicalizationVersionError(
                requested_version="<default not set>",
                registered_versions=self.registered_versions(),
            )
        return self._default

    def registered_versions(self) -> tuple[str, ...]:
        """Return the tuple of registered version strings in registration order."""
        return tuple(v for v, _ in self._routes)

    async def aclose(self) -> None:
        """Close every registered adapter; idempotent.

        Suppresses per-adapter close errors so one flaky adapter
        cannot strand its siblings. Mirrors the ControlPortRegistry
        lifecycle.
        """
        if self._closed:
            return
        self._closed = True
        for _, adapter in self._routes:
            close = getattr(adapter, "aclose", None)
            if close is None:
                continue
            with contextlib.suppress(Exception):
                await close()


__all__ = ["CanonicalizationRegistry"]
