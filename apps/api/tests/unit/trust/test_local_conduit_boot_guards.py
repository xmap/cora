"""Tests for the two `trust_conduit_id` boot guards.

`verify_local_conduit_seed_present` and `verify_local_conduit_matches_policy`
exist so `trust_conduit_id` cannot be misconfigured into looking wired while
populating nothing. Both are no-ops when `trust_conduit_id` is unset -- the
default, and every existing deployment's behaviour before this setting
existed.

Same failure this whole area keeps re-learning: asking for a control and
silently not getting one. Two ways that happens here -- the configured
Conduit doesn't exist or has no open verdict logbook, or the configured
Policy governs a different Conduit -- and both refuse to boot rather than
degrade silently.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust._bootstrap import (
    verify_local_conduit_matches_policy,
    verify_local_conduit_seed_present,
)
from cora.trust.aggregates.conduit import (
    LOGBOOK_KIND_VERDICT,
    ConduitDefined,
    ConduitLogbookOpened,
)
from cora.trust.aggregates.conduit import (
    event_type_name as conduit_event_type_name,
)
from cora.trust.aggregates.conduit import (
    to_payload as conduit_to_payload,
)
from tests._authz import seed_policy
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 8, 31, 14, 0, 0, tzinfo=UTC)
_CONDUIT_ID = UUID("01900000-0000-7000-8000-0000000000e1")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000000000e2")
_OTHER_CONDUIT_ID = UUID("01900000-0000-7000-8000-0000000000e3")
_POLICY_ID = UUID("01900000-0000-7000-8000-0000000000e4")


async def _seed_conduit(
    store: InMemoryEventStore,
    *,
    conduit_id: UUID = _CONDUIT_ID,
    with_open_logbook: bool = True,
) -> None:
    events: list[ConduitDefined | ConduitLogbookOpened] = [
        ConduitDefined(
            conduit_id=conduit_id,
            name="Test conduit",
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
            occurred_at=_NOW,
        )
    ]
    if with_open_logbook:
        events.append(
            ConduitLogbookOpened(
                conduit_id=conduit_id,
                logbook_id=_LOGBOOK_ID,
                kind=LOGBOOK_KIND_VERDICT,
                schema=LogbookSchema(fields={"x": LogbookFieldSpec(type="string")}),
                occurred_at=_NOW,
            )
        )
    new_events = [
        to_new_event(
            event_type=conduit_event_type_name(e),
            payload=conduit_to_payload(e),
            occurred_at=e.occurred_at,
            event_id=uuid4(),
            command_name="DefineConduit",
            correlation_id=uuid4(),
            principal_id=uuid4(),
        )
        for e in events
    ]
    await store.append("Conduit", conduit_id, expected_version=0, events=new_events)


# --- verify_local_conduit_seed_present -----------------------------------


@pytest.mark.unit
async def test_no_op_when_trust_conduit_id_is_unset() -> None:
    """Default: every existing deployment's behaviour, unchanged."""
    deps = build_deps(trust_conduit_id=None)
    await verify_local_conduit_seed_present(deps)  # must not raise


@pytest.mark.unit
async def test_refuses_boot_when_configured_conduit_stream_is_missing() -> None:
    deps = build_deps(trust_conduit_id=_CONDUIT_ID)
    with pytest.raises(RuntimeError, match="no Conduit stream exists"):
        await verify_local_conduit_seed_present(deps)


@pytest.mark.unit
async def test_refuses_boot_when_configured_conduit_has_no_open_verdict_logbook() -> None:
    store = InMemoryEventStore()
    await _seed_conduit(store, with_open_logbook=False)
    deps = build_deps(trust_conduit_id=_CONDUIT_ID, event_store=store)
    with pytest.raises(RuntimeError, match="no open verdict logbook"):
        await verify_local_conduit_seed_present(deps)


@pytest.mark.unit
async def test_boots_when_configured_conduit_has_an_open_verdict_logbook() -> None:
    store = InMemoryEventStore()
    await _seed_conduit(store, with_open_logbook=True)
    deps = build_deps(trust_conduit_id=_CONDUIT_ID, event_store=store)
    await verify_local_conduit_seed_present(deps)  # must not raise


# --- verify_local_conduit_matches_policy ---------------------------------


@pytest.mark.unit
async def test_no_op_when_trust_conduit_id_is_unset_even_with_a_policy() -> None:
    deps = build_deps(trust_policy_id=_POLICY_ID, trust_conduit_id=None)
    await verify_local_conduit_matches_policy(deps)  # must not raise


@pytest.mark.unit
async def test_no_op_when_trust_policy_id_is_unset_even_with_a_conduit() -> None:
    deps = build_deps(trust_policy_id=None, trust_conduit_id=_CONDUIT_ID)
    await verify_local_conduit_matches_policy(deps)  # must not raise


@pytest.mark.unit
async def test_refuses_boot_when_the_policy_governs_a_different_conduit() -> None:
    """The lockout this guard exists to prevent: every command would be
    denied at the conduit check before principal or command are consulted."""
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids=[uuid4()],
        permitted_commands=["RegisterActor"],
        conduit_id=_OTHER_CONDUIT_ID,
    )
    deps = build_deps(
        trust_policy_id=_POLICY_ID,
        trust_conduit_id=_CONDUIT_ID,
        event_store=store,
    )
    with pytest.raises(RuntimeError, match="a different one"):
        await verify_local_conduit_matches_policy(deps)


@pytest.mark.unit
async def test_boots_when_the_policy_governs_the_configured_conduit() -> None:
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids=[uuid4()],
        permitted_commands=["RegisterActor"],
        conduit_id=_CONDUIT_ID,
    )
    deps = build_deps(
        trust_policy_id=_POLICY_ID,
        trust_conduit_id=_CONDUIT_ID,
        event_store=store,
    )
    await verify_local_conduit_matches_policy(deps)  # must not raise


@pytest.mark.unit
async def test_no_op_when_the_configured_policy_stream_is_missing() -> None:
    """A missing policy stream is verify_bootstrap_seed_present's concern
    (or an operator's, for a custom policy) -- this guard must not also
    raise on it, or the two error messages would compete over one cause."""
    deps = build_deps(trust_policy_id=_POLICY_ID, trust_conduit_id=_CONDUIT_ID)
    await verify_local_conduit_matches_policy(deps)  # must not raise


@pytest.mark.unit
async def test_nil_conduit_matches_a_nil_bound_policy() -> None:
    """Today's every existing deployment: both nil is a legitimate match,
    not just the sentinel value colliding with itself."""
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids=[uuid4()],
        permitted_commands=["RegisterActor"],
        conduit_id=NIL_SENTINEL_ID,
    )
    deps = build_deps(
        trust_policy_id=_POLICY_ID,
        trust_conduit_id=NIL_SENTINEL_ID,
        event_store=store,
    )
    await verify_local_conduit_matches_policy(deps)  # must not raise
