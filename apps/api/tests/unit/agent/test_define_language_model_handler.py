"""Application-handler tests for the `define_language_model` slice.

Single-stream genesis: every successful call writes ONE
`LanguageModelDefined` event on the LanguageModel stream. The slice's
wrinkle over the plain create-style template is the optional
caller-supplied `language_model_id`: the handler loads the target
stream first so a collision trips the decider's genesis guard.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.language_model import (
    LanguageModelAlreadyExistsError,
    LanguageModelDefined,
    event_type_name,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import define_language_model
from cora.agent.features.define_language_model import DefineLanguageModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000b001")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b002")
_SUPPLIED_ID = UUID("01900000-0000-7000-8000-00000000b003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_TOKEN_COST = {
    "kind": "TokenPricing",
    "input_per_mtok": 3.0,
    "output_per_mtok": 15.0,
    "cache_write_per_mtok": 3.75,
    "cache_read_per_mtok": 0.3,
}


def _build_deps(
    *,
    ids: list[UUID] | None = None,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        # define_language_model consumes 2 ids on the minted path:
        # new language_model_id + 1 event_id. Caller-supplied-id tests
        # pass ids=[_EVENT_ID] only.
        ids=ids if ids is not None else [_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> DefineLanguageModel:
    base: dict[str, object] = {
        "name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "served_via": "Argo",
        "cost_basis": dict(_TOKEN_COST),
        "data_tier": "Internal",
        "archivability": "Alias",
    }
    base.update(overrides)
    return DefineLanguageModel(**base)  # type: ignore[arg-type]


async def _seed_language_model(store: InMemoryEventStore, language_model_id: UUID) -> None:
    event = LanguageModelDefined(
        language_model_id=language_model_id,
        name="Seeded Entry",
        provider="anthropic",
        model="claude-sonnet-4-6",
        snapshot_pin=None,
        served_via="Argo",
        endpoint_note=None,
        cost_basis=dict(_TOKEN_COST),
        data_tier="Internal",
        archivability="Alias",
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="LanguageModel",
        stream_id=language_model_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefineLanguageModel",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_returns_generated_language_model_id() -> None:
    deps = _build_deps()
    handler = define_language_model.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_uses_caller_supplied_language_model_id() -> None:
    """A command-carried id is used verbatim; the IdGenerator only mints
    the event envelope id."""
    store = InMemoryEventStore()
    deps = _build_deps(ids=[_EVENT_ID], event_store=store)
    handler = define_language_model.bind(deps)
    result = await handler(
        _command(language_model_id=_SUPPLIED_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _SUPPLIED_ID
    events, version = await store.load("LanguageModel", _SUPPLIED_ID)
    assert version == 1
    assert len(events) == 1


@pytest.mark.unit
async def test_handler_appends_single_defined_event_to_language_model_stream() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_language_model.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("LanguageModel", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "LanguageModelDefined"


@pytest.mark.unit
async def test_handler_event_carries_full_command() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_language_model.bind(deps)
    await handler(
        _command(
            snapshot_pin="claude-sonnet-4-6-20261101",
            endpoint_note="Argo prod gateway",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("LanguageModel", _NEW_ID)
    payload = events[0].payload
    assert payload["language_model_id"] == str(_NEW_ID)
    assert payload["name"] == "Claude Sonnet 4.6"
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "claude-sonnet-4-6"
    assert payload["snapshot_pin"] == "claude-sonnet-4-6-20261101"
    assert payload["served_via"] == "Argo"
    assert payload["endpoint_note"] == "Argo prod gateway"
    assert payload["cost_basis"] == _TOKEN_COST
    assert payload["data_tier"] == "Internal"
    assert payload["archivability"] == "Alias"
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_handler_propagates_envelope_fields() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_language_model.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("LanguageModel", _NEW_ID)
    stored = events[0]
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.principal_id == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_supplied_id_collision_raises_already_exists() -> None:
    """The handler loads the target stream, so re-defining a
    caller-supplied id trips the decider's genesis guard instead of
    surfacing a raw concurrency error."""
    store = InMemoryEventStore()
    await _seed_language_model(store, _SUPPLIED_ID)
    deps = _build_deps(ids=[_EVENT_ID], event_store=store)
    handler = define_language_model.bind(deps)
    with pytest.raises(LanguageModelAlreadyExistsError):
        await handler(
            _command(language_model_id=_SUPPLIED_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("LanguageModel", _SUPPLIED_ID)
    assert version == 1
    assert len(events) == 1


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = define_language_model.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_stream() -> None:
    """Authorize-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_language_model.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("LanguageModel", _NEW_ID)
    assert version == 0
    assert events == []
