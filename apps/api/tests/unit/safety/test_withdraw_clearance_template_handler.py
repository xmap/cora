"""Application-handler tests for `withdraw_clearance_template` slice.

Covers:
  - happy path from Draft (stream has only ClearanceTemplateDefined):
    one ClearanceTemplateWithdrawn appended at expected_version=1 with
    the envelope (event_id, correlation_id, principal_id, occurred_at)
    threaded from the deps clock + id generator + caller-supplied ids
  - happy path from Active (Defined + Activated): one
    ClearanceTemplateWithdrawn appended at expected_version=2
  - happy path from Deprecated (Defined + Activated + Deprecated): one
    ClearanceTemplateWithdrawn appended at expected_version=3
  - already Withdrawn (Defined + Activated + Withdrawn) raises
    ClearanceTemplateCannotWithdrawError; no extra event appended
  - empty stream -> raises ClearanceTemplateNotFoundError; no event
    appended (stream stays at version 0)
  - Authz Deny -> raises UnauthorizedError; no event appended (stream
    stays at the seeded version)
  - withdrawn_by on the appended event payload equals
    ActorId(principal_id)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateActivated,
    ClearanceTemplateCannotWithdrawError,
    ClearanceTemplateDefined,
    ClearanceTemplateDeprecated,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateWithdrawn,
    event_type_name,
    to_payload,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import withdraw_clearance_template
from cora.safety.features.withdraw_clearance_template import WithdrawClearanceTemplate
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_WITHDRAW_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c2b01")
_SECOND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c2b02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000c2b03")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000c2b04")
_SEED_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c2b05")
_SEED_ACTIVATED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c2b06")
_SEED_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c2b07")
_SEED_WITHDRAWN_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c2b08")

_FACILITY_CODE = "cora"
_TEMPLATE_CODE = "esaf.standard"
_TEMPLATE_TITLE = "Experiment Safety Assessment Form"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_WITHDRAW_EVENT_ID, _SECOND_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_defined(
    store: InMemoryEventStore,
    *,
    template_id: UUID,
    facility_code: str = _FACILITY_CODE,
    code: str = _TEMPLATE_CODE,
    title: str = _TEMPLATE_TITLE,
) -> None:
    """Seed the in-memory event store with one ClearanceTemplateDefined
    event so fold-on-read reconstructs the aggregate in Draft status."""
    event = ClearanceTemplateDefined(
        template_id=template_id,
        facility_code=facility_code,
        code=code,
        title=title,
        occurred_at=_NOW,
        defined_by=_PRINCIPAL_ID,
        version=1,
        supersedes_template_id=None,
        external_ref=None,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=_SEED_DEFINED_EVENT_ID,
        command_name="DefineClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_activated(
    store: InMemoryEventStore,
    *,
    template_id: UUID,
) -> None:
    """Append a ClearanceTemplateActivated event so the aggregate folds
    to Active status (stream version 2)."""
    event = ClearanceTemplateActivated(
        template_id=template_id,
        occurred_at=_NOW,
        activated_by=_PRINCIPAL_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=_SEED_ACTIVATED_EVENT_ID,
        command_name="ActivateClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=1,
        events=[new_event],
    )


async def _seed_deprecated(
    store: InMemoryEventStore,
    *,
    template_id: UUID,
) -> None:
    """Append a ClearanceTemplateDeprecated event so the aggregate folds
    to Deprecated status (stream version 3)."""
    event = ClearanceTemplateDeprecated(
        reason="Superseded",
        template_id=template_id,
        occurred_at=_NOW,
        deprecated_by=_PRINCIPAL_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=_SEED_DEPRECATED_EVENT_ID,
        command_name="DeprecateClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=2,
        events=[new_event],
    )


async def _seed_withdrawn(
    store: InMemoryEventStore,
    *,
    template_id: UUID,
) -> None:
    """Append a ClearanceTemplateWithdrawn event so the aggregate folds
    to Withdrawn status (stream version 3)."""
    event = ClearanceTemplateWithdrawn(
        reason="policy change",
        template_id=template_id,
        occurred_at=_NOW,
        withdrawn_by=_PRINCIPAL_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=_SEED_WITHDRAWN_EVENT_ID,
        command_name="WithdrawClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=2,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_appends_withdrawn_event_from_draft_at_expected_version_one() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = withdraw_clearance_template.bind(deps)

    result = await handler(
        WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is None

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 2  # ClearanceTemplateDefined + ClearanceTemplateWithdrawn
    assert len(events) == 2
    withdrawn = events[1]
    assert withdrawn.event_type == "ClearanceTemplateWithdrawn"
    assert withdrawn.event_id == _WITHDRAW_EVENT_ID
    assert withdrawn.correlation_id == _CORRELATION_ID
    assert withdrawn.principal_id == _PRINCIPAL_ID
    assert withdrawn.occurred_at == _NOW
    assert withdrawn.payload["template_id"] == str(template_id)
    assert withdrawn.payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_handler_appends_withdrawn_event_from_active_at_expected_version_two() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    await _seed_activated(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = withdraw_clearance_template.bind(deps)

    await handler(
        WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 3
    assert len(events) == 3
    assert events[2].event_type == "ClearanceTemplateWithdrawn"
    assert events[2].event_id == _WITHDRAW_EVENT_ID


@pytest.mark.unit
async def test_handler_appends_withdrawn_event_from_deprecated_at_expected_version_three() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    await _seed_activated(store, template_id=template_id)
    await _seed_deprecated(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = withdraw_clearance_template.bind(deps)

    await handler(
        WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 4
    assert len(events) == 4
    assert events[3].event_type == "ClearanceTemplateWithdrawn"
    assert events[3].event_id == _WITHDRAW_EVENT_ID


@pytest.mark.unit
async def test_handler_threads_principal_id_onto_withdrawn_by() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = withdraw_clearance_template.bind(deps)

    await handler(
        WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("ClearanceTemplate", template_id)
    assert UUID(events[1].payload["withdrawn_by"]) == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_raises_cannot_withdraw_when_already_withdrawn() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    await _seed_activated(store, template_id=template_id)
    await _seed_withdrawn(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = withdraw_clearance_template.bind(deps)

    with pytest.raises(ClearanceTemplateCannotWithdrawError):
        await handler(
            WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 3
    assert len(events) == 3
    assert events[-1].event_type == "ClearanceTemplateWithdrawn"
    assert events[-1].event_id == _SEED_WITHDRAWN_EVENT_ID


@pytest.mark.unit
async def test_handler_raises_not_found_when_stream_is_empty() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = withdraw_clearance_template.bind(deps)

    missing_template_id = uuid4()
    with pytest.raises(ClearanceTemplateNotFoundError):
        await handler(
            WithdrawClearanceTemplate(reason="policy change", template_id=missing_template_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("ClearanceTemplate", missing_template_id)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    deny_deps = _build_deps(event_store=store, deny=True)
    handler = withdraw_clearance_template.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    deny_deps = _build_deps(event_store=store, deny=True)
    handler = withdraw_clearance_template.bind(deny_deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            WithdrawClearanceTemplate(reason="policy change", template_id=template_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "ClearanceTemplateDefined"
