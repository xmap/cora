"""Adapters Decision BC ships for cross-BC ports.

- `PostgresSpendLookup` implementing `SpendLookup` (consumed by the
  budget gate at the LLM producers' seams). Decision BC ships it
  because it owns the durable spend fact: `entries_decision_inferences`.
"""

from cora.decision.adapters.postgres_spend_lookup import PostgresSpendLookup

__all__ = ["PostgresSpendLookup"]
