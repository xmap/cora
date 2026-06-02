"""The `RegisterAsset` command, intent dataclass for this slice.

Carries the caller-controlled fields: the asset's display name,
its hierarchical level, its parent_id (None only for
Enterprise-level roots, enforced by the decider), an optional
Drawing reference, and an optional `model_id` Model-binding ref.
Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports, matching the cross-BC create-style command
shape locked in Access / Trust / Subject / Equipment.

`level` is typed as `AssetLevel` (the StrEnum) so callers cannot
pass an invalid value; the route's Pydantic body and the MCP
tool's argument schema both enforce this at the API boundary.

`parent_id` is `UUID | None`, required for non-Enterprise
levels, must be null for Enterprise. Eventual-consistency stance
for the parent ref: the decider does NOT verify the referenced
parent Asset exists in the event store (same precedent as Trust's
Conduit zone refs).

`model_id` is `UUID | None`, optional reference to the Model
catalog entry this Asset is an instance of. Set ONCE at
registration per the model-binding design memo (Lock A); rebind
path is decommission + re-register. The handler verifies the
referenced Model stream exists before invoking the decider
(`ModelNotFoundError` -> 404); the decider does NOT need a Model
snapshot because the genesis Asset's families set is empty so the
subset invariant is vacuously satisfied at registration (Lock B).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates.asset import AssetLevel


@dataclass(frozen=True)
class RegisterAsset:
    """Register a new asset.

    Carries the display name, hierarchical level, parent_id, optional
    Drawing reference, and optional `model_id` Model-binding ref.
    """

    name: str
    level: AssetLevel
    parent_id: UUID | None
    drawing: Drawing | None = None
    model_id: UUID | None = None
