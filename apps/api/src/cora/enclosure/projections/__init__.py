"""Enclosure BC projections.

Single-aggregate BC, single projection: EnclosureSummaryProjection
backs `GET /enclosures` (list) and complements `GET /enclosures/{id}`
(which still uses fold-on-read for canonical state).
"""

from cora.enclosure.projections.enclosure import EnclosureSummaryProjection

__all__ = ["EnclosureSummaryProjection"]
