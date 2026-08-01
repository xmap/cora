"""The `DeprecateModel` command, intent dataclass for this slice.

Multi-source transition: `Defined | Versioned -> Deprecated`. Carries
the target `model_id` plus a closed `DeprecationReason`.

`reason` is REQUIRED. Deprecation is an authoring signal that informs
later operators why the catalog entry should not be reused for new
Assets, and whether Assets already bound to it are still trustworthy.
Existing
Assets bound to the Model continue to function (deprecation is not a
runtime gate).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateModel:
    """Mark an existing model as no longer recommended for new Assets."""

    model_id: UUID
    reason: DeprecationReason
