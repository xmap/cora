"""Stub DataCite-style minter for tests and credential-less environments.

Deterministic: given a (scheme, suffix) pair, returns a stable
`PersistentIdentifier` built from a fixed test prefix. When suffix is
None, generates a UUID-based suffix so each call still returns a
distinct value.

Never raises `PersistentIdentifierMintError`. Tests asserting the
route's 502 path inject a separate raising stub fixture.

Wired by `wire_equipment(deps)` when no DataCite credentials are
present (the dev / test default), mirroring the `AllowAllAuthorize`
plus `AlwaysCoveredClearanceLookup` test-bypass convention: a stub
adapter is a real adapter that returns inert values, distinct from a
None / disabled port (which would force every caller to None-check).
The stub is always wired; only the implementation varies.

The stub prefixes (`10.0000` for DOI, `20.500.0000` for Handle) are
reserved in the corresponding registration systems for testing
purposes and do not resolve to anything real. Hard-coded so the stub
is deterministic without a config dependency: tests can construct
`StubPersistentIdentifierMinter()` directly without a Settings object.
"""

from uuid import uuid4

from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

_STUB_DOI_PREFIX = "10.0000/cora-stub"
_STUB_HANDLE_PREFIX = "20.500.0000/cora-stub"


class StubPersistentIdentifierMinter:
    """Returns a deterministic test-only PersistentIdentifier."""

    async def mint(
        self,
        *,
        scheme: PersistentIdentifierScheme,
        suffix: str | None,
    ) -> PersistentIdentifier:
        local = suffix if suffix is not None else str(uuid4())
        prefix = (
            _STUB_DOI_PREFIX if scheme is PersistentIdentifierScheme.DOI else _STUB_HANDLE_PREFIX
        )
        return PersistentIdentifier(scheme=scheme, value=f"{prefix}/{local}")

    async def tombstone(
        self,
        pid: PersistentIdentifier,
        reason: str,
    ) -> None:
        """No-op tombstone arm: stub adapter never reaches DataCite."""
        _ = (pid, reason)


__all__ = ["StubPersistentIdentifierMinter"]
