"""The `WithdrawClearanceTemplate` command -- intent dataclass for this slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class WithdrawClearanceTemplate:
    """Withdraw a clearance template (`Draft | Active | Deprecated -> Withdrawn`)."""

    template_id: UUID
    reason: str


__all__ = ["WithdrawClearanceTemplate"]
