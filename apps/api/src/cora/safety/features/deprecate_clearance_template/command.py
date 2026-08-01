"""The `DeprecateClearanceTemplate` command -- intent dataclass for this slice."""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateClearanceTemplate:
    """Deprecate an Active clearance template (`Active -> Deprecated`)."""

    template_id: UUID
    reason: DeprecationReason


__all__ = ["DeprecateClearanceTemplate"]
