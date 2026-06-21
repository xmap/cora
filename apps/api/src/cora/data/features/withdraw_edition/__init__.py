"""`withdraw_edition`: tombstones a Published Edition.

Calls `PersistentIdentifierMinter.tombstone` (the DOI stays Findable as a tombstone
page; it is NOT deleted, per DataCite DOI-immutability), then emits
`EditionWithdrawn`. Withdrawn is terminal: re-withdraw is rejected
with `EditionCannotWithdrawError`. The mandatory withdrawal reason is
recorded forever on the tombstone.
"""

from cora.data.features.withdraw_edition.handler import Handler, bind
from cora.data.features.withdraw_edition.route import router

__all__ = ["Handler", "bind", "router"]
