"""The `DefineLanguageModel` command -- intent dataclass for this slice.

Carries the caller-controlled fields for one catalog entry: display
name, the flattened model identity (provider / model / snapshot_pin,
the `ModelRef` primitives), serving route, optional endpoint note,
the discriminated cost-basis payload, and the two tier axes.

`language_model_id` is optional. None (the default) keeps the
`define_agent` posture: the handler mints a UUIDv7 via the injected
IdGenerator port. A caller-supplied id serves deployments that seed
the catalog from configuration and need stable ids across
environments; the handler loads that stream before deciding so the
genesis guard can reject a collision.

Enum-valued fields (`served_via`, `data_tier`, `archivability`)
travel as plain strings and are wrapped into their StrEnums by the
decider; `cost_basis` travels as the discriminated dict the decider
validates via `cost_basis_from_payload`.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DefineLanguageModel:
    """Define a new LanguageModel catalog entry (lands in Defined)."""

    name: str
    provider: str
    model: str
    served_via: str
    cost_basis: dict[str, Any]
    data_tier: str
    archivability: str
    language_model_id: UUID | None = None
    snapshot_pin: str | None = None
    endpoint_note: str | None = None
