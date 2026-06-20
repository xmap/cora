"""Tests for `warn_if_verdict_log_dormant` (Trust boot-time check).

The check makes a silent gap loud: when real authz is enabled but the
per-Conduit Verdict audit log cannot populate (handlers route through the
nil-sentinel conduit, which has no open verdict logbook until conduit
injection lands), it warns at startup instead of logging an empty audit
trail. These pin the three branches: off -> silent, on+dormant -> warn,
on+wired -> silent.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import structlog

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust._bootstrap import warn_if_verdict_log_dormant
from cora.trust.aggregates.conduit import (
    LOGBOOK_KIND_VERDICT,
    ConduitDefined,
    ConduitLogbookOpened,
    event_type_name,
    to_payload,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000000000d2")
_DORMANT_EVENT = "trust_authorize.verdict_log_dormant"


def _warned(logs: Sequence[Mapping[str, object]]) -> bool:
    return any(entry.get("event") == _DORMANT_EVENT for entry in logs)


async def _seed_nil_conduit_with_open_verdict_logbook(store: InMemoryEventStore) -> None:
    """Seed a Conduit at the nil-sentinel id with an open verdict logbook
    (the wired state conduit injection would eventually produce)."""
    defined = ConduitDefined(
        conduit_id=NIL_SENTINEL_ID,
        name="Nil conduit",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    opened = ConduitLogbookOpened(
        conduit_id=NIL_SENTINEL_ID,
        logbook_id=_LOGBOOK_ID,
        kind=LOGBOOK_KIND_VERDICT,
        schema=LogbookSchema(fields={"x": LogbookFieldSpec(type="string")}),
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=event_type_name(e),
            payload=to_payload(e),
            occurred_at=e.occurred_at,
            event_id=uuid4(),
            command_name="DefineConduit",
            correlation_id=uuid4(),
            principal_id=uuid4(),
        )
        for e in (defined, opened)
    ]
    await store.append("Conduit", NIL_SENTINEL_ID, expected_version=0, events=events)


@pytest.mark.unit
async def test_no_warning_when_authz_is_off() -> None:
    """trust_policy_id None = AllowAll: no decisions to record, so no
    dormancy warning."""
    deps = build_deps(trust_policy_id=None)
    with structlog.testing.capture_logs() as logs:
        await warn_if_verdict_log_dormant(deps)
    assert not _warned(logs)


@pytest.mark.unit
async def test_warns_when_authz_on_but_verdict_log_cannot_populate() -> None:
    """trust_policy_id set + no verdict logbook on the nil conduit (the
    current reality): the audit log would silently stay empty, so warn."""
    deps = build_deps(trust_policy_id=_POLICY_ID)
    with structlog.testing.capture_logs() as logs:
        await warn_if_verdict_log_dormant(deps)
    assert _warned(logs)


@pytest.mark.unit
async def test_no_warning_when_nil_conduit_has_open_verdict_logbook() -> None:
    """No false alarm: when the conduit handlers use does have an open
    verdict logbook, the audit log can populate, so stay silent."""
    store = InMemoryEventStore()
    await _seed_nil_conduit_with_open_verdict_logbook(store)
    deps = build_deps(trust_policy_id=_POLICY_ID, event_store=store)
    with structlog.testing.capture_logs() as logs:
        await warn_if_verdict_log_dormant(deps)
    assert not _warned(logs)
