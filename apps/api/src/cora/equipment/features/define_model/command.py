"""The `DefineModel` command, intent dataclass for this slice.

Carries only what the caller controls (display name, manufacturer,
part_number, declared_families, optional initial version_tag).
Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports.

Status is implicit at definition (`Defined`) and not part of the
command; see the Model aggregate's `state.py` docstring for the
enum-in-state, str-in-event convention.

`declared_families` is REQUIRED at definition time with cardinality
at least one. Empty `frozenset()` is rejected by the decider with
`InvalidDeclaredFamiliesError`; the catalog tier without any Family
declaration has no instantiation contract.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.model import Manufacturer


@dataclass(frozen=True)
class DefineModel:
    """Define a new vendor-catalog Model with manufacturer, part_number, families."""

    name: str
    manufacturer: Manufacturer
    part_number: str
    declared_families: frozenset[UUID]
    version_tag: str | None = None
