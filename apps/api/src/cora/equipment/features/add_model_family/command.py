"""The `AddModelFamily` command, intent dataclass for this slice.

Targeted-mutation: incremental add of a single Family to the
Model's `declared_families` set. Sibling of `remove_model_family`.

The operational pattern is "vendor firmware update declares an
additional Family" rather than a wholesale re-author; `version_model`
remains the path when a revision genuinely re-authors the catalog
entry (matches the Family/Method/Plan/Practice replace-on-version
precedent).

`model_id` is the target Model aggregate. `family_id` is the Family
being declared; the handler resolves it against the Family registry
(cross-BC lookup mirrors `define_model`'s `list_family_ids` pattern)
and raises `FamilyNotFoundError` if it does not resolve.

Strict-not-idempotent: re-adding a Family already in
`declared_families` raises `ModelFamilyAlreadyPresentError` (same
precedent as `add_asset_family` and `activate_asset`).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddModelFamily:
    """Add a Family to an existing model's `declared_families` set."""

    model_id: UUID
    family_id: UUID
