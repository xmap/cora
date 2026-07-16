"""The `ApproveLanguageModel` command -- intent dataclass for this slice.

Promotes a Defined catalog entry to Approved: the facility's
governance act, after which the entry is usable for its declared data
tier and the pricing bridge may feed from it. Source set is
`{Defined}` only; re-approving any other status raises
`LanguageModelCannotApproveError` (resurrecting a retiring or
terminal entry must never happen silently).

No reason field: approval rationale, when it matters, lives in a
Decision, not on the fact. The approving actor's identity lives on
the event envelope (`StoredEvent.principal_id`); no actor field on
the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ApproveLanguageModel:
    """Approve a Defined LanguageModel (`Defined -> Approved`)."""

    language_model_id: UUID
