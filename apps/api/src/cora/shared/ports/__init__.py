"""Shared-kernel ports: cross-BC port surfaces shared across multiple consumers.

Ports land here once the rule-of-three trigger has fired: 3+ distinct
aggregate consumers (across 2 or more BCs) all need the same Protocol
shape. The first ports promoted to shared:

  - `DoiMinter` + `PersistentIdentifierMintError`: minting and
    tombstoning persistent identifiers for any PID-bearing aggregate.
    Consumers (today): Asset (Equipment), Fixture (Equipment),
    Edition (Data) -- 3 aggregates across 2 BCs.
"""

from cora.shared.ports.doi_minter import (
    DoiMinter,
    PersistentIdentifierMintError,
)

__all__ = [
    "DoiMinter",
    "PersistentIdentifierMintError",
]
