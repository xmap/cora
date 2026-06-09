"""Adapters Enclosure BC ships for cross-BC ports.

- `PostgresEnclosureLookup` implementing
  `cora.infrastructure.ports.EnclosureLookup` (consumed by other BCs
  asking whether an enclosure is currently permitted, and by
  asset-binding queries via `find_for_assets`).
"""

from cora.enclosure.adapters.postgres_enclosure_lookup import PostgresEnclosureLookup

__all__ = ["PostgresEnclosureLookup"]
