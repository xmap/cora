"""Read repository for the LanguageModel aggregate.

`load_language_model(event_store, language_model_id) -> LanguageModel | None`
mirrors `load_agent` / `load_caution` / `load_supply`. Used by the
update-style handlers (approve / announce-retirement / retire /
deprecate load the target entry before the decider) and the
`list_at_risk_results` read slice.
"""

from uuid import UUID

from cora.agent.aggregates.language_model.events import from_stored
from cora.agent.aggregates.language_model.evolver import fold
from cora.agent.aggregates.language_model.state import LanguageModel
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "LanguageModel"


async def load_language_model(
    event_store: EventStore, language_model_id: UUID
) -> LanguageModel | None:
    """Load and fold a LanguageModel's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, language_model_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
