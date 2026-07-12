"""The `RetireLanguageModel` command -- intent dataclass for this slice.

Ends a catalog entry's service life on the VENDOR side (`Approved |
RetirementAnnounced -> Retired`). Terminal: retired entries cannot be
revived. Reachable directly from Approved because providers remove
models without notice; `reason` is optional for the same reason (an
unannounced removal may arrive with no vendor statement at all, and a
None preserves any earlier announcement's reason on the folded
state). 1-500 chars after trim if provided.

The retiring actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RetireLanguageModel:
    """Retire a LanguageModel (`Approved | RetirementAnnounced -> Retired`)."""

    language_model_id: UUID
    reason: str | None = None
