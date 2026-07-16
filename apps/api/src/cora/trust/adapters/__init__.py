"""Adapters Trust BC ships for cross-BC ports.

- `PostgresConsequenceLookup` implementing `ConsequenceLookup` (consumed by Run
  BC's `stop_run` handler for the consequence gate: is this action co-signed by a
  Granted Ratification?).
"""

from cora.trust.adapters.postgres_consequence_lookup import PostgresConsequenceLookup

__all__ = ["PostgresConsequenceLookup"]
