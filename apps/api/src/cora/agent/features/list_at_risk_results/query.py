"""The `ListAtRiskResults` query -- intent dataclass for this read slice.

Mirrors `GetAgent`: queries are dataclasses just like commands, naming
the read intent and carrying only what the caller controls. The
application handler adds context (correlation_id, principal_id) at
call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListAtRiskResults:
    """Enumerate the Decisions whose recorded LLM calls touched the
    given catalog entry's model identity, graded for reproducibility."""

    language_model_id: UUID
