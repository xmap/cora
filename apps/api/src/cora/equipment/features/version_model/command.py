"""The `VersionModel` command, intent dataclass for this slice.

Multi-source transition: `Defined | Versioned -> Versioned`. Operators
issue a new `version_tag` (free text like "v2", "2026-Q3") to mark a
revision of the vendor-catalog entry.

A new version IS a new declaration: `name`, `manufacturer`,
`part_number`, `declared_families`, and `version_tag` are ALL required
at version time. The supplied values REPLACE the prior catalog entry
wholesale (no diff/merge semantics). Matches Family/Method/Plan/
Practice replace-on-version precedent.

`declared_families` must be non-empty: a catalog entry without any
Family declaration has no instantiation contract, and a re-authored
revision is no exception. Empty `frozenset()` is rejected by the
decider with `InvalidDeclaredFamiliesError`.

`version_tag` is REQUIRED for `version_model` (unlike `define_model`
where the initial label is optional). The whole point of the slice is
to issue a new label.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.model import Manufacturer


@dataclass(frozen=True)
class VersionModel:
    """Issue a new version label plus replacement catalog body for a Model."""

    model_id: UUID
    name: str
    manufacturer: Manufacturer
    part_number: str
    declared_families: frozenset[UUID]
    version_tag: str
