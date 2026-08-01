"""Application-handler tests for the `deprecate_language_model` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.language_model import (
    LanguageModelCannotDeprecateError,
    LanguageModelNotFoundError,
    TokenPricing,
    cost_basis_to_payload,
    event_type_name,
    to_payload,
)
from cora.agent.aggregates.language_model.events import (
    LanguageModelDefined,
    LanguageModelDeprecated,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import deprecate_language_model
from cora.agent.features.deprecate_language_model import DeprecateLanguageModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.deprecation import DeprecationReason
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 7, 10, 11, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
_LANGUAGE_MODEL_ID = UUID("01900000-0000-7000-8000-00000000d301")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d302")
_DEPRECATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d303")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_DEPRECATE_EVENT_ID],
        now=_T1,
        event_store=event_store,
        deny=deny,
    )


async def _seed_defined_language_model(store: InMemoryEventStore) -> None:
    genesis = LanguageModelDefined(
        language_model_id=_LANGUAGE_MODEL_ID,
        name="Claude Sonnet 4.6",
        provider="anthropic",
        model="claude-sonnet-4-6",
        snapshot_pin=None,
        served_via="Argo",
        endpoint_note=None,
        cost_basis=cost_basis_to_payload(
            TokenPricing(
                input_per_mtok=3.0,
                output_per_mtok=15.0,
                cache_write_per_mtok=3.75,
                cache_read_per_mtok=0.3,
            )
        ),
        data_tier="Internal",
        archivability="Alias",
        occurred_at=_T0,
    )
    await store.append(
        stream_type="LanguageModel",
        stream_id=_LANGUAGE_MODEL_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_GENESIS_EVENT_ID,
                command_name="DefineLanguageModel",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_deprecates_a_defined_language_model_with_reason() -> None:
    store = InMemoryEventStore()
    await _seed_defined_language_model(store)
    deps = _build_deps(event_store=store)
    handler = deprecate_language_model.bind(deps)
    await handler(
        DeprecateLanguageModel(
            language_model_id=_LANGUAGE_MODEL_ID, reason=DeprecationReason.SUPERSEDED
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("LanguageModel", _LANGUAGE_MODEL_ID)
    assert version == 2
    assert events[-1].event_type == "LanguageModelDeprecated"
    assert events[-1].payload["reason"] == "Superseded"


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_language_model() -> None:
    deps = _build_deps()
    handler = deprecate_language_model.bind(deps)
    with pytest.raises(LanguageModelNotFoundError):
        await handler(
            DeprecateLanguageModel(
                language_model_id=_LANGUAGE_MODEL_ID, reason=DeprecationReason.SUPERSEDED
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated() -> None:
    store = InMemoryEventStore()
    await _seed_defined_language_model(store)
    deprecated = LanguageModelDeprecated(
        language_model_id=_LANGUAGE_MODEL_ID, reason="Superseded", occurred_at=_T1
    )
    await store.append(
        stream_type="LanguageModel",
        stream_id=_LANGUAGE_MODEL_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(deprecated),
                payload=to_payload(deprecated),
                occurred_at=deprecated.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000d399"),
                command_name="DeprecateLanguageModel",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = deprecate_language_model.bind(deps)
    with pytest.raises(LanguageModelCannotDeprecateError):
        await handler(
            DeprecateLanguageModel(
                language_model_id=_LANGUAGE_MODEL_ID, reason=DeprecationReason.SUPERSEDED
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = deprecate_language_model.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DeprecateLanguageModel(
                language_model_id=_LANGUAGE_MODEL_ID, reason=DeprecationReason.SUPERSEDED
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT mutate the LanguageModel stream.

    Mirrors the Agent transition-handler deny-no-write tests; the
    authorize check must precede the event-store load + append.
    """
    store = InMemoryEventStore()
    await _seed_defined_language_model(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = deprecate_language_model.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DeprecateLanguageModel(
                language_model_id=_LANGUAGE_MODEL_ID, reason=DeprecationReason.SUPERSEDED
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("LanguageModel", _LANGUAGE_MODEL_ID)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "LanguageModelDefined"
