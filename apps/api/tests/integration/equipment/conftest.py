"""Integration-test fixtures scoped to the Equipment BC.

Provides Protocol-conforming test doubles for ports that the Equipment
BC wires through `wire_equipment(deps)` onto `app.state.equipment.*`,
so route-level tests can swap the inert Stub for a failure-inducing
double without touching the kernel.

Currently exposes:

- `RaisingPersistentIdentifierMinter`: a `PersistentIdentifierMinter`-conforming class whose `mint`
  unconditionally raises `PersistentIdentifierMintError` with the
  reason `"upstream stub failure"`. Used by the 502-path test on
  `POST /assets/{asset_id}/assign-persistent-identifier` to verify
  the upstream-mint-failure exception handler wires correctly
  (per slice F Section 13.2 + Locks L11 + L19).
- `raising_persistent_identifier_minter`: function-scoped pytest fixture returning a
  fresh `RaisingPersistentIdentifierMinter` instance for tests that override
  `app.state.equipment.persistent_identifier_minter`.
"""

import pytest

from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMintError

pytestmark = pytest.mark.timeout(60, method="thread")


class RaisingPersistentIdentifierMinter:
    """Protocol-conforming `PersistentIdentifierMinter` whose `mint` always raises.

    Mirrors the `StubPersistentIdentifierMinter` shape but inverts the contract: every
    invocation raises `PersistentIdentifierMintError` with the reason
    `"upstream stub failure"`. The route layer maps this to HTTP 502
    via the standard exception-handler registration in the Equipment
    BC, so route-tier tests can assert the upstream-failure path is
    wired correctly without bringing a real DataCite adapter or a
    network double into the loop.
    """

    async def mint(
        self,
        *,
        scheme: PersistentIdentifierScheme,
        suffix: str | None,
    ) -> PersistentIdentifier:
        raise PersistentIdentifierMintError(
            scheme=scheme,
            reason="upstream stub failure",
        )


@pytest.fixture
def raising_persistent_identifier_minter() -> RaisingPersistentIdentifierMinter:
    return RaisingPersistentIdentifierMinter()
