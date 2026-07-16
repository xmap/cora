"""Application-handler tests for the `announce_language_model_retirement` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.language_model import (
    LanguageModelCannotAnnounceRetirementError,
    LanguageModelNotFoundError,
    TokenPricing,
    cost_basis_to_payload,
    event_type_name,
    to_payload,
)
from cora.agent.aggregates.language_model.events import (
    LanguageModelApproved,
    LanguageModelDefined,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import announce_language_model_retirement
from cora.agent.features.announce_language_model_retirement import (
    AnnounceLanguageModelRetirement,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 7, 10, 11, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
_EFFECTIVE_AT = datetime(2026, 9, 30, 0, 0, 0, tzinfo=UTC)
_LANGUAGE_MODEL_ID = UUID("01900000-0000-7000-8000-00000000d101")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d102")
_APPROVE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d103")
_ANNOUNCE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d104")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_ANNOUNCE_EVENT_ID],
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


async def _seed_approved_language_model(store: InMemoryEventStore) -> None:
    await _seed_defined_language_model(store)
    approved = LanguageModelApproved(language_model_id=_LANGUAGE_MODEL_ID, occurred_at=_T0)
    await store.append(
        stream_type="LanguageModel",
        stream_id=_LANGUAGE_MODEL_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(approved),
                payload=to_payload(approved),
                occurred_at=approved.occurred_at,
                event_id=_APPROVE_EVENT_ID,
                command_name="ApproveLanguageModel",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_announces_retirement_for_an_approved_language_model() -> None:
    store = InMemoryEventStore()
    await _seed_approved_language_model(store)
    deps = _build_deps(event_store=store)
    handler = announce_language_model_retirement.bind(deps)
    await handler(
        AnnounceLanguageModelRetirement(
            language_model_id=_LANGUAGE_MODEL_ID,
            reason="vendor sunset notice",
            effective_at=_EFFECTIVE_AT,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("LanguageModel", _LANGUAGE_MODEL_ID)
    assert version == 3
    assert events[-1].event_type == "LanguageModelRetirementAnnounced"
    assert events[-1].payload["reason"] == "vendor sunset notice"
    assert events[-1].payload["effective_at"] == _EFFECTIVE_AT.isoformat()


@pytest.mark.unit
async def test_handler_announce_without_date_appends_none_effective_at() -> None:
    store = InMemoryEventStore()
    await _seed_approved_language_model(store)
    deps = _build_deps(event_store=store)
    handler = announce_language_model_retirement.bind(deps)
    await handler(
        AnnounceLanguageModelRetirement(
            language_model_id=_LANGUAGE_MODEL_ID, reason="warning without a date"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("LanguageModel", _LANGUAGE_MODEL_ID)
    assert events[-1].payload["effective_at"] is None


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_language_model() -> None:
    deps = _build_deps()
    handler = announce_language_model_retirement.bind(deps)
    with pytest.raises(LanguageModelNotFoundError):
        await handler(
            AnnounceLanguageModelRetirement(
                language_model_id=_LANGUAGE_MODEL_ID, reason="vendor sunset"
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_announce_when_not_yet_approved() -> None:
    store = InMemoryEventStore()
    await _seed_defined_language_model(store)
    deps = _build_deps(event_store=store)
    handler = announce_language_model_retirement.bind(deps)
    with pytest.raises(LanguageModelCannotAnnounceRetirementError):
        await handler(
            AnnounceLanguageModelRetirement(
                language_model_id=_LANGUAGE_MODEL_ID, reason="vendor sunset"
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = announce_language_model_retirement.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AnnounceLanguageModelRetirement(
                language_model_id=_LANGUAGE_MODEL_ID, reason="vendor sunset"
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
    await _seed_approved_language_model(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = announce_language_model_retirement.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AnnounceLanguageModelRetirement(
                language_model_id=_LANGUAGE_MODEL_ID, reason="vendor sunset"
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("LanguageModel", _LANGUAGE_MODEL_ID)
    assert version == 2
    assert len(events) == 2
    assert events[-1].event_type == "LanguageModelApproved"
