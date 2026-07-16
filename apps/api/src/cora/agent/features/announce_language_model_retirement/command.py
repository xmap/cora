"""The `AnnounceLanguageModelRetirement` command -- intent dataclass for this slice.

Records the VENDOR's lifecycle fact for an Approved catalog entry
(`Approved -> RetirementAnnounced`): the provider announced this model
will cease to exist. The entry stays servable until retired, and the
at-risk-results projection is live from this moment.

`reason` is REQUIRED (1-500 chars after trim): the announcement always
carries vendor context worth auditing. `effective_at` is the vendor's
announced cutoff; None when the vendor gave a warning but no date.

The announcing actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AnnounceLanguageModelRetirement:
    """Announce a LanguageModel's retirement (`Approved -> RetirementAnnounced`)."""

    language_model_id: UUID
    reason: str
    effective_at: datetime | None = None
