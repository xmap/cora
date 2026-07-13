"""Budget BC side-effecting subscribers.

One Reaction today: `AllocationSealerSubscriber` closes the books on
a campaign-bound Active allocation when its Campaign closes.
"""

from cora.budget.subscribers.allocation_sealer import (
    AllocationSealerSubscriber,
    make_allocation_sealer_subscriber,
)

__all__ = [
    "AllocationSealerSubscriber",
    "make_allocation_sealer_subscriber",
]
