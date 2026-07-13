"""Budget BC read-side projections.

One projection today: `AllocationSummaryProjection` maintains
`proj_budget_allocation_summary`, the by-status read model the
`PostgresAllocationLookup` adapter answers the envelope gate from.
"""

from cora.budget.projections.allocation import AllocationSummaryProjection

__all__ = ["AllocationSummaryProjection"]
