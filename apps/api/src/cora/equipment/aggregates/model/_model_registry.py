"""Deterministic Model stream id derivation.

A Model is a vendor catalog entry: the same manufacturer plus part
number names the same product at every facility. For two facilities to
converge on one Model identity, the id is derived from the vendor key
rather than minted at random. This mirrors `family_stream_id` and
`role_stream_id`.

The namespace UUID is `uuid5(NAMESPACE_DNS, 'cora.model')`, computed
once at lock-time and hardcoded so re-derivation is deterministic.

Placeholder guard: a Model whose part number is the
`PLACEHOLDER_PART_NUMBER` sentinel is not yet identified. Two genuinely
different units both recorded with that placeholder must stay distinct,
so the derivation falls back to the caller's random id instead of
colliding them on one deterministic stream. Once the real part number
is confirmed, the Model re-registers under its derived id.
"""

import unicodedata
from typing import Final
from uuid import UUID, uuid5

from cora.equipment.aggregates.model.state import Manufacturer, PartNumber

_MODEL_NAMESPACE: Final[UUID] = UUID("80ac1aef-8d97-54e2-ae52-22b33b29b3a8")

PLACEHOLDER_PART_NUMBER: Final[str] = "unknown-pending-confirmation"


def is_placeholder_part_number(part_number: PartNumber) -> bool:
    """True when the part number is the not-yet-confirmed sentinel."""
    return part_number.value.strip().lower() == PLACEHOLDER_PART_NUMBER


def _canonical_model_key(manufacturer_name: str, part_number: str) -> str:
    """Injective canonical join of the vendor key.

    Manufacturer name is case-folded (organizational identity, not a
    SKU); part number is case-preserved (vendor SKUs are case-sensitive).
    Both are NFC-normalized so composed vs decomposed Unicode cannot fork
    identity. The length prefix plus ASCII unit separator (0x1f, which
    cannot appear in trimmed bounded text) make the join injective:
    ("Aero", "techX") and ("Aerotech", "X") cannot collide.
    """
    mfr = unicodedata.normalize("NFC", manufacturer_name).lower()
    part = unicodedata.normalize("NFC", part_number)
    return f"{len(mfr)}:{mfr}\x1f{part}"


def model_stream_id(
    manufacturer: Manufacturer,
    part_number: PartNumber,
    *,
    new_id: UUID,
) -> UUID:
    """Derive the deterministic Model stream id from the vendor key.

    Returns the caller's random `new_id` for the placeholder sentinel
    (distinct unconfirmed Models must not collide); otherwise a uuid5
    over the canonical (manufacturer name, part number) key.
    """
    if is_placeholder_part_number(part_number):
        return new_id
    return uuid5(
        _MODEL_NAMESPACE,
        _canonical_model_key(manufacturer.name.value, part_number.value),
    )


__all__ = [
    "PLACEHOLDER_PART_NUMBER",
    "is_placeholder_part_number",
    "model_stream_id",
]
