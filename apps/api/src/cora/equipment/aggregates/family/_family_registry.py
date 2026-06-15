"""Deterministic Family stream id derivation.

A Family is cross-facility vocabulary: a `Camera` defined at APS 2-BM
and a `Camera` defined at MAX IV name the same device class. For
`Assembly.content_hash` to converge across facilities (it serializes
each slot's `required_family_ids`), the underlying Family ids must be
derived from the name, not minted at random per facility. This mirrors
`role_stream_id` (see
`aggregates/role/_role_registry.py`).

The namespace UUID is derived from `uuid5(NAMESPACE_DNS, 'cora.family')`
once at lock-time and hardcoded so re-derivation is deterministic
without re-running the seed path. Operators verifying the derivation
can recompute it from the same string seed.

`family_stream_id(name)` NFC-normalizes then lower-cases `name.value` before uuid5 so two
facilities (and a second `define_family` on the same case-insensitive
name) converge on one stream; the duplicate define then collides on
`expected_version=0` at the event store, surfacing as
`ConcurrencyError` -> 409. Uniqueness is enforced by the deterministic
stream id, not a projection index; a `LOWER(name)` unique index on
`proj_equipment_family_summary` (as on the Role projection) is a
possible future belt-and-suspenders, not present today.
"""

import unicodedata
from typing import Final
from uuid import UUID, uuid5

from cora.equipment.aggregates.family.state import FamilyName

_FAMILY_NAMESPACE: Final[UUID] = UUID("14ce275b-7d45-54b0-887e-972a88c69d98")


def family_stream_id(name: FamilyName) -> UUID:
    """Derive the deterministic stream_id for a Family from its name.

    NFC-normalizes then lower-cases the name, so case and Unicode
    spelling (composed vs decomposed accents) are presentation, not
    identity: two facilities naming the same Family cannot fork on a
    spelling that renders identically. Mirrors `model_stream_id`.
    """
    return uuid5(_FAMILY_NAMESPACE, unicodedata.normalize("NFC", name.value).lower())


__all__ = [
    "family_stream_id",
]
