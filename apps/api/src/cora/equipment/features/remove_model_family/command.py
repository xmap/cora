"""The `RemoveModelFamily` command, intent dataclass for this slice.

Targeted-mutation: incremental removal of a single Family from the
Model's `declared_families` set. Sibling of `add_model_family`.

The operational pattern is "vendor firmware update drops support for
a technique" or "catalog entry no longer advertises a Family";
`version_model` remains the path when a revision genuinely re-authors
the catalog entry (matches the Family/Method/Plan/Practice
replace-on-version precedent).

`model_id` is the target Model aggregate. `family_id` is the Family
being undeclared. Unlike `add_model_family`, the handler does NOT
resolve the Family against the Family registry: removal only
requires that `family_id` already sits in `declared_families` (the
Family may have been deprecated or deleted, and removal still
proceeds).

Strict-not-idempotent: removing a Family not in `declared_families`
raises `ModelFamilyNotPresentError` (same precedent as
`add_model_family` and `remove_asset_family`).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveModelFamily:
    """Remove a Family from an existing model's `declared_families` set."""

    model_id: UUID
    family_id: UUID
