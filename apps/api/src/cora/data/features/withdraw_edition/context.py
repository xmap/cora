"""Cross-aggregate context the `withdraw_edition` decider validates against.

`WithdrawEditionContext` is empty today: the withdraw decider reads
only the loaded `Edition` state (passed separately) plus the command.
The PersistentIdentifierMinter tombstone side effect happens at the handler, not the
decider, so no captured port result needs threading through context.

The context class exists for shape-symmetry with the other Edition
transition slices (seal / publish carry real captured-input contexts)
and to leave a clean extension point if a future withdraw guard needs
a pre-loaded peer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WithdrawEditionContext:
    """Empty context placeholder for the withdraw_edition decider."""
