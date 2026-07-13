"""Budget BC adapters (production implementations of neutral ports).

`PostgresAllocationLookup` implements
`cora.infrastructure.ports.allocation_lookup.AllocationLookup` over
`proj_budget_allocation_summary`.
"""

from cora.budget.adapters.postgres_allocation_lookup import PostgresAllocationLookup

__all__ = ["PostgresAllocationLookup"]
