"""Application-handler tests for the `list_at_risk_results` query slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.language_model import (
    LanguageModelNotFoundError,
    TokenPricing,
    cost_basis_to_payload,
    event_type_name,
    to_payload,
)
from cora.agent.aggregates.language_model.events import (
    LanguageModelApproved,
    LanguageModelDefined,
    LanguageModelDeprecated,
    LanguageModelEvent,
    LanguageModelRetired,
    LanguageModelRetirementAnnounced,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import list_at_risk_results
from cora.agent.features.list_at_risk_results import ListAtRiskResults
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import ModelUsageLookupResult
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 7, 10, 11, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 7, 10, 13, 0, 0, tzinfo=UTC)
_LANGUAGE_MODEL_ID = UUID("01900000-0000-7000-8000-00000000e001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DECISION_ID_A = UUID("01900000-0000-7000-8000-00000000e0a1")
_DECISION_ID_B = UUID("01900000-0000-7000-8000-00000000e0b1")

_PROVIDER = "anthropic"
_MODEL = "claude-sonnet-4-5"

_ROWS = (
    ModelUsageLookupResult(
        decision_id=_DECISION_ID_A,
        occurred_at=_T1,
        request_model=_MODEL,
        response_model=f"{_MODEL}-20250929",
        agent_id="run-debriefer",
    ),
    ModelUsageLookupResult(
        decision_id=_DECISION_ID_B,
        occurred_at=_T0,
        request_model=_MODEL,
        response_model=None,
        agent_id=None,
    ),
)


class _FakeModelUsageLookup:
    """Returns canned rows and records the identity it was asked about."""

    def __init__(self, rows: tuple[ModelUsageLookupResult, ...] = ()) -> None:
        self.rows = rows
        self.calls: list[tuple[str, str]] = []

    async def find_decisions_touching_model(
        self, *, provider: str, model: str
    ) -> tuple[ModelUsageLookupResult, ...]:
        self.calls.append((provider, model))
        return self.rows


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    model_usage_lookup: _FakeModelUsageLookup | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[],
        now=_T2,
        event_store=event_store,
        model_usage_lookup=model_usage_lookup,
        deny=deny,
    )


async def _seed_language_model(
    store: InMemoryEventStore,
    *,
    archivability: str,
    approved: bool = False,
    retirement_announced: bool = False,
    retired: bool = False,
    deprecated: bool = False,
) -> None:
    events: list[LanguageModelEvent] = [
        LanguageModelDefined(
            language_model_id=_LANGUAGE_MODEL_ID,
            name="Claude Sonnet 4.5",
            provider=_PROVIDER,
            model=_MODEL,
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
            archivability=archivability,
            occurred_at=_T0,
        )
    ]
    if approved:
        events.append(LanguageModelApproved(language_model_id=_LANGUAGE_MODEL_ID, occurred_at=_T1))
    if retirement_announced:
        events.append(
            LanguageModelRetirementAnnounced(
                language_model_id=_LANGUAGE_MODEL_ID,
                reason="Vendor sunsets the alias",
                effective_at=None,
                occurred_at=_T2,
            )
        )
    if retired:
        events.append(
            LanguageModelRetired(
                language_model_id=_LANGUAGE_MODEL_ID,
                reason="Vendor removed the endpoint",
                occurred_at=_T2,
            )
        )
    if deprecated:
        events.append(
            LanguageModelDeprecated(
                language_model_id=_LANGUAGE_MODEL_ID,
                reason="Facility withdrew approval",
                occurred_at=_T2,
            )
        )
    await store.append(
        stream_type="LanguageModel",
        stream_id=_LANGUAGE_MODEL_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=UUID(f"01900000-0000-7000-8000-00000000e1{index:02x}"),
                command_name="SeedLanguageModel",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
            for index, event in enumerate(events)
        ],
    )


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_language_model() -> None:
    deps = _build_deps()
    handler = list_at_risk_results.bind(deps)
    with pytest.raises(LanguageModelNotFoundError):
        await handler(
            ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_alias_entry_with_retirement_announced_is_at_risk_and_lists_results() -> None:
    """The flagship path: an Alias entry whose vendor announced
    retirement grades AttributableOnly, flips at_risk, and carries the
    lookup's rows queried by the entry's own model identity."""
    store = InMemoryEventStore()
    await _seed_language_model(
        store, archivability="Alias", approved=True, retirement_announced=True
    )
    lookup = _FakeModelUsageLookup(rows=_ROWS)
    deps = _build_deps(event_store=store, model_usage_lookup=lookup)
    handler = list_at_risk_results.bind(deps)

    view = await handler(
        ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.reproducibility_grade == "AttributableOnly"
    assert view.at_risk is True
    assert view.results == _ROWS
    assert lookup.calls == [(_PROVIDER, _MODEL)]


@pytest.mark.unit
async def test_pinned_entry_grades_re_executable_and_is_not_at_risk() -> None:
    """Facility-held weights stay servable regardless of the vendor's
    lifecycle, so even an announced retirement leaves at_risk false."""
    store = InMemoryEventStore()
    await _seed_language_model(
        store, archivability="Pinned", approved=True, retirement_announced=True
    )
    lookup = _FakeModelUsageLookup(rows=_ROWS)
    deps = _build_deps(event_store=store, model_usage_lookup=lookup)
    handler = list_at_risk_results.bind(deps)

    view = await handler(
        ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.reproducibility_grade == "ReExecutable"
    assert view.at_risk is False
    assert view.results == _ROWS


@pytest.mark.unit
async def test_defined_alias_entry_is_not_at_risk_but_results_stay_listed() -> None:
    """The endpoint answers for ANY status: before an announcement an
    Alias entry grades AttributableOnly with at_risk false, and the
    Decision list still comes back for pre-announcement triage."""
    store = InMemoryEventStore()
    await _seed_language_model(store, archivability="Alias")
    lookup = _FakeModelUsageLookup(rows=_ROWS)
    deps = _build_deps(event_store=store, model_usage_lookup=lookup)
    handler = list_at_risk_results.bind(deps)

    view = await handler(
        ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.at_risk is False
    assert view.reproducibility_grade == "AttributableOnly"
    assert view.results == _ROWS


@pytest.mark.unit
async def test_retired_alias_entry_is_at_risk() -> None:
    """Retirement (with or without a prior announcement) is the other
    vendor lifecycle event that turns a fragile Alias identity into
    live risk."""
    store = InMemoryEventStore()
    await _seed_language_model(store, archivability="Alias", approved=True, retired=True)
    lookup = _FakeModelUsageLookup(rows=_ROWS)
    deps = _build_deps(event_store=store, model_usage_lookup=lookup)
    handler = list_at_risk_results.bind(deps)

    view = await handler(
        ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.reproducibility_grade == "AttributableOnly"
    assert view.at_risk is True
    assert view.results == _ROWS


@pytest.mark.unit
async def test_deprecated_alias_entry_is_not_at_risk() -> None:
    """Deprecation is the FACILITY ending an entry's service life; it
    does not take the provider-side identity out of service, so even a
    fragile Alias identity stays at_risk false."""
    store = InMemoryEventStore()
    await _seed_language_model(store, archivability="Alias", approved=True, deprecated=True)
    lookup = _FakeModelUsageLookup(rows=_ROWS)
    deps = _build_deps(event_store=store, model_usage_lookup=lookup)
    handler = list_at_risk_results.bind(deps)

    view = await handler(
        ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.reproducibility_grade == "AttributableOnly"
    assert view.at_risk is False
    assert view.results == _ROWS


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = list_at_risk_results.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListAtRiskResults(language_model_id=_LANGUAGE_MODEL_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
