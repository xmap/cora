"""Application-handler tests for `deprecate_clearance_template` slice.

Covers:
  - happy path: pre-seed a ClearanceTemplateDefined + ClearanceTemplateActivated
    pair on the stream (state is Active), bind the handler, invoke it; assert
    the store now carries a single ClearanceTemplateDeprecated event at
    expected_version=2 with the envelope (event_id, correlation_id,
    principal_id, occurred_at) threaded from the deps clock + id generator +
    caller-supplied ids
  - empty stream -> raises ClearanceTemplateNotFoundError; no event appended
    (stream stays at version 0)
  - Authz Deny -> raises UnauthorizedError; no event appended (stream stays
    at the seeded version)
  - deprecated_by on the appended event payload equals ActorId(principal_id)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateActivated,
    ClearanceTemplateDefined,
    ClearanceTemplateNotFoundError,
    event_type_name,
    to_payload,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import deprecate_clearance_template
from cora.safety.features.deprecate_clearance_template import DeprecateClearanceTemplate
from cora.shared.deprecation import DeprecationReason
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_DEPRECATE_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d2b01")
_SECOND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d2b02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000d2b03")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000d2b04")
_DEFINED_SEED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d2b05")
_ACTIVATED_SEED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d2b06")

_FACILITY_CODE = "cora"
_TEMPLATE_CODE = "esaf.standard"
_TEMPLATE_TITLE = "Experiment Safety Assessment Form"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_DEPRECATE_EVENT_ID, _SECOND_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_active(
    store: InMemoryEventStore,
    *,
    template_id: UUID,
    facility_code: str = _FACILITY_CODE,
    code: str = _TEMPLATE_CODE,
    title: str = _TEMPLATE_TITLE,
) -> None:
    """Seed the in-memory event store with ClearanceTemplateDefined +
    ClearanceTemplateActivated so fold-on-read reconstructs the aggregate
    in Active status (the only deprecatable state)."""
    defined = ClearanceTemplateDefined(
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
    activated = ClearanceTemplateActivated(
        template_id=template_id,
        occurred_at=_NOW,
        activated_by=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(defined),
                payload=to_payload(defined),
                occurred_at=defined.occurred_at,
                event_id=_DEFINED_SEED_EVENT_ID,
                command_name="DefineClearanceTemplate",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            ),
            to_new_event(
                event_type=event_type_name(activated),
                payload=to_payload(activated),
                occurred_at=activated.occurred_at,
                event_id=_ACTIVATED_SEED_EVENT_ID,
                command_name="ActivateClearanceTemplate",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            ),
        ],
    )


@pytest.mark.unit
async def test_handler_appends_deprecated_event_at_expected_version_two() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_active(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = deprecate_clearance_template.bind(deps)

    result = await handler(
        DeprecateClearanceTemplate(reason=DeprecationReason.SUPERSEDED, template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is None

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 3  # Defined + Activated + Deprecated
    assert len(events) == 3
    deprecated = events[2]
    assert deprecated.event_type == "ClearanceTemplateDeprecated"
    assert deprecated.event_id == _DEPRECATE_EVENT_ID
    assert deprecated.correlation_id == _CORRELATION_ID
    assert deprecated.principal_id == _PRINCIPAL_ID
    assert deprecated.occurred_at == _NOW
    assert deprecated.payload["template_id"] == str(template_id)
    assert deprecated.payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_handler_threads_principal_id_onto_deprecated_by() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_active(store, template_id=template_id)
    deps = _build_deps(event_store=store)
    handler = deprecate_clearance_template.bind(deps)

    await handler(
        DeprecateClearanceTemplate(reason=DeprecationReason.SUPERSEDED, template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("ClearanceTemplate", template_id)
    assert UUID(events[2].payload["deprecated_by"]) == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_raises_not_found_when_stream_is_empty() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = deprecate_clearance_template.bind(deps)

    missing_template_id = uuid4()
    with pytest.raises(ClearanceTemplateNotFoundError):
        await handler(
            DeprecateClearanceTemplate(
                reason=DeprecationReason.SUPERSEDED, template_id=missing_template_id
            ),
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
    await _seed_active(store, template_id=template_id)
    deny_deps = _build_deps(event_store=store, deny=True)
    handler = deprecate_clearance_template.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DeprecateClearanceTemplate(
                reason=DeprecationReason.SUPERSEDED, template_id=template_id
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_active(store, template_id=template_id)
    deny_deps = _build_deps(event_store=store, deny=True)
    handler = deprecate_clearance_template.bind(deny_deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DeprecateClearanceTemplate(
                reason=DeprecationReason.SUPERSEDED, template_id=template_id
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 2
    assert len(events) == 2
    assert events[0].event_type == "ClearanceTemplateDefined"
    assert events[1].event_type == "ClearanceTemplateActivated"
