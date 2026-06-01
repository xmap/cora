"""The `DeprecateModel` command, intent dataclass for this slice.

Multi-source transition: `Defined | Versioned -> Deprecated`. Carries
the target `model_id` plus an operator-supplied `reason` (1-500 chars
after trimming, validated via `ModelDeprecationReason` at the decider).

`reason` is REQUIRED. Deprecation is an authoring signal that informs
later operators why the catalog entry should not be reused for new
Assets; recording a rationale keeps that signal actionable. Existing
Assets bound to the Model continue to function (deprecation is not a
runtime gate).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeprecateModel:
    """Mark an existing model as no longer recommended for new Assets."""

    model_id: UUID
    reason: str
