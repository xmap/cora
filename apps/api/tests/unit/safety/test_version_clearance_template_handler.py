"""Application-handler tests for `version_clearance_template` slice.

Covers:
  - happy path: seed event store with one `ClearanceTemplateDefined` +
    one `ClearanceTemplateActivated` for the template (state is Active
    v1), seed lookup with parent template in the same facility, and
    invoke with `new_version=2`; assert append is called with one
    `ClearanceTemplateVersioned` event
  - empty stream -> `ClearanceTemplateNotFoundError`; no append
  - state still Draft -> `ClearanceTemplateCannotVersionError`
  - parent lookup miss -> `ClearanceTemplateNotFoundError` keyed by
    `supersedes_template_id`
  - parent template in a different facility ->
    `ClearanceTemplateFacilityMismatchError`
  - Authz Deny -> `UnauthorizedError`; no lookup call, no append
  - `versioned_by` on the event payload equals `ActorId(principal_id)`
"""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_clearance_template_lookup import (
    InMemoryClearanceTemplateLookup,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateActivated,
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateDefined,
    ClearanceTemplateFacilityMismatchError,
    ClearanceTemplateNotFoundError,
    event_type_name,
    to_payload,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import version_clearance_template
from cora.safety.features.version_clearance_template import VersionClearanceTemplate
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000ce101")
_SECOND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000ce102")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000ce103")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000ce104")

_CHILD_TEMPLATE_ID = UUID("01900000-0000-7000-8000-0000000ce201")
_PARENT_TEMPLATE_ID = UUID("01900000-0000-7000-8000-0000000ce200")

_FACILITY_CODE = "cora"
_OTHER_FACILITY_CODE = "maxiv"
_CHILD_TEMPLATE_CODE = "esaf.standard"
_PARENT_TEMPLATE_CODE = "esaf.legacy"
_TEMPLATE_TITLE = "Experiment Safety Assessment Form"

_DEFINED_AT = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_ACTIVATED_AT = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    clearance_template_lookup: InMemoryClearanceTemplateLookup | None = None,
) -> Kernel:
    """Build the in-memory Kernel and slot in a custom
    `ClearanceTemplateLookup` via `dataclasses.replace` (the shared
    `build_deps` helper does not thread this port yet)."""
    deps = _build_deps_shared(
        ids=[_EVENT_ID, _SECOND_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )
    if clearance_template_lookup is not None:
        deps = dataclasses.replace(
            deps,
            clearance_template_lookup=clearance_template_lookup,
        )
    return deps


def _command(
    *,
    template_id: UUID = _CHILD_TEMPLATE_ID,
    new_version: int = 2,
    supersedes_template_id: UUID = _PARENT_TEMPLATE_ID,
) -> VersionClearanceTemplate:
    return VersionClearanceTemplate(
        template_id=template_id,
        new_version=new_version,
        supersedes_template_id=supersedes_template_id,
    )


async def _seed_active_template(
    store: InMemoryEventStore,
    *,
    template_id: UUID = _CHILD_TEMPLATE_ID,
    facility_code: str = _FACILITY_CODE,
    code: str = _CHILD_TEMPLATE_CODE,
    title: str = _TEMPLATE_TITLE,
) -> None:
    """Seed a `ClearanceTemplateDefined` + `ClearanceTemplateActivated`
    pair so the loaded state is Active at version 1."""
    defined = ClearanceTemplateDefined(
        template_id=template_id,
        facility_code=facility_code,
        code=code,
        title=title,
        occurred_at=_DEFINED_AT,
        defined_by=_PRINCIPAL_ID,
    )
    activated = ClearanceTemplateActivated(
        template_id=template_id,
        occurred_at=_ACTIVATED_AT,
        activated_by=_PRINCIPAL_ID,
    )
    defined_envelope = to_new_event(
        event_type=event_type_name(defined),
        payload=to_payload(defined),
        occurred_at=defined.occurred_at,
        event_id=uuid4(),
        command_name="DefineClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    activated_envelope = to_new_event(
        event_type=event_type_name(activated),
        payload=to_payload(activated),
        occurred_at=activated.occurred_at,
        event_id=uuid4(),
        command_name="ActivateClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=0,
        events=[defined_envelope, activated_envelope],
    )


async def _seed_draft_template(
    store: InMemoryEventStore,
    *,
    template_id: UUID = _CHILD_TEMPLATE_ID,
    facility_code: str = _FACILITY_CODE,
    code: str = _CHILD_TEMPLATE_CODE,
    title: str = _TEMPLATE_TITLE,
) -> None:
    """Seed only `ClearanceTemplateDefined` so the loaded state is Draft."""
    defined = ClearanceTemplateDefined(
        template_id=template_id,
        facility_code=facility_code,
        code=code,
        title=title,
        occurred_at=_DEFINED_AT,
        defined_by=_PRINCIPAL_ID,
    )
    envelope = to_new_event(
        event_type=event_type_name(defined),
        payload=to_payload(defined),
        occurred_at=defined.occurred_at,
        event_id=uuid4(),
        command_name="DefineClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=0,
        events=[envelope],
    )


def _seed_parent_lookup(
    *,
    parent_id: UUID = _PARENT_TEMPLATE_ID,
    facility_code: str = _FACILITY_CODE,
    code: str = _PARENT_TEMPLATE_CODE,
    status: str = "Active",
    version: int = 1,
) -> InMemoryClearanceTemplateLookup:
    lookup = InMemoryClearanceTemplateLookup()
    lookup.register(
        parent_id,
        facility_code=facility_code,
        code=code,
        status=status,
        version=version,
    )
    return lookup


@pytest.mark.unit
async def test_handler_appends_single_versioned_event_on_happy_path() -> None:
    store = InMemoryEventStore()
    await _seed_active_template(store)
    lookup = _seed_parent_lookup()
    deps = _build_deps(event_store=store, clearance_template_lookup=lookup)

    handler = version_clearance_template.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    # Two seeded events (Defined + Activated) + the appended Versioned.
    assert version == 3
    assert len(events) == 3
    stored = events[-1]
    assert stored.event_type == "ClearanceTemplateVersioned"
    assert stored.event_id == _EVENT_ID
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.occurred_at == _NOW
    assert stored.payload["template_id"] == str(_CHILD_TEMPLATE_ID)
    assert stored.payload["new_version"] == 2
    assert stored.payload["supersedes_template_id"] == str(_PARENT_TEMPLATE_ID)


@pytest.mark.unit
async def test_handler_raises_not_found_when_stream_is_empty() -> None:
    store = InMemoryEventStore()
    lookup = _seed_parent_lookup()
    deps = _build_deps(event_store=store, clearance_template_lookup=lookup)

    handler = version_clearance_template.bind(deps)
    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID

    # No event appended on the empty stream.
    events, version = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_template_still_draft() -> None:
    store = InMemoryEventStore()
    await _seed_draft_template(store)
    lookup = _seed_parent_lookup()
    deps = _build_deps(event_store=store, clearance_template_lookup=lookup)

    handler = version_clearance_template.bind(deps)
    with pytest.raises(ClearanceTemplateCannotVersionError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID

    # Only the seeded Defined event remains; no Versioned appended.
    events, version = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["ClearanceTemplateDefined"]


@pytest.mark.unit
async def test_handler_raises_not_found_when_parent_lookup_misses() -> None:
    store = InMemoryEventStore()
    await _seed_active_template(store)
    # Empty lookup: no parent registered, lookup returns None.
    empty_lookup = InMemoryClearanceTemplateLookup()
    deps = _build_deps(event_store=store, clearance_template_lookup=empty_lookup)

    handler = version_clearance_template.bind(deps)
    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Parent miss is keyed by supersedes_template_id, not by the child id.
    assert exc_info.value.template_id == _PARENT_TEMPLATE_ID

    # Only the seeded Defined + Activated remain; no Versioned appended.
    events, version = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "ClearanceTemplateDefined",
        "ClearanceTemplateActivated",
    ]


@pytest.mark.unit
async def test_handler_raises_facility_mismatch_when_parent_in_other_facility() -> None:
    store = InMemoryEventStore()
    await _seed_active_template(store, facility_code=_FACILITY_CODE)
    lookup = _seed_parent_lookup(facility_code=_OTHER_FACILITY_CODE)
    deps = _build_deps(event_store=store, clearance_template_lookup=lookup)

    handler = version_clearance_template.bind(deps)
    with pytest.raises(ClearanceTemplateFacilityMismatchError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID
    assert exc_info.value.template_facility_code.value == _FACILITY_CODE
    assert exc_info.value.parent_facility_code.value == _OTHER_FACILITY_CODE

    # Only the seeded Defined + Activated remain; no Versioned appended.
    events, version = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "ClearanceTemplateDefined",
        "ClearanceTemplateActivated",
    ]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)

    handler = version_clearance_template.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_lookup_or_append_when_denied() -> None:
    """A class that records every lookup call so the test can
    assert that the deny path short-circuits BEFORE the cross-aggregate
    parent resolution runs."""

    class _RecordingLookup:
        def __init__(self) -> None:
            self.calls: list[UUID] = []

        async def lookup(self, template_id: UUID) -> None:
            self.calls.append(template_id)
            return None

    store = InMemoryEventStore()
    await _seed_active_template(store)
    recording_lookup = _RecordingLookup()
    deps = _build_deps_shared(
        ids=[_EVENT_ID, _SECOND_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    deps = dataclasses.replace(
        deps,
        clearance_template_lookup=recording_lookup,  # type: ignore[arg-type]
    )

    handler = version_clearance_template.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Authorize raised before the handler reached the lookup or append.
    assert recording_lookup.calls == []
    events, version = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "ClearanceTemplateDefined",
        "ClearanceTemplateActivated",
    ]


@pytest.mark.unit
async def test_handler_threads_principal_id_onto_versioned_by() -> None:
    store = InMemoryEventStore()
    await _seed_active_template(store)
    lookup = _seed_parent_lookup()
    deps = _build_deps(event_store=store, clearance_template_lookup=lookup)

    handler = version_clearance_template.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("ClearanceTemplate", _CHILD_TEMPLATE_ID)
    stored = events[-1]
    assert stored.event_type == "ClearanceTemplateVersioned"
    assert UUID(stored.payload["versioned_by"]) == _PRINCIPAL_ID
