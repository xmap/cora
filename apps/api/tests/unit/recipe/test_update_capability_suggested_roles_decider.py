"""Unit tests for `update_capability_suggested_roles` decider (Layer 3 3E)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotUpdateSuggestedRolesError,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilitySuggestedRolesUpdated,
)
from cora.recipe.features import update_capability_suggested_roles
from cora.recipe.features.update_capability_suggested_roles import (
    UpdateCapabilitySuggestedRoles,
)

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _capability(
    cid: UUID,
    *,
    status: CapabilityStatus = CapabilityStatus.DEFINED,
    suggested_role_ids: frozenset[UUID] = frozenset(),
) -> Capability:
    return Capability(
        id=cid,
        code=CapabilityCode("cora.capability.acquire"),
        name=CapabilityName("Acquire"),
        status=status,
        suggested_role_ids=suggested_role_ids,
    )


@pytest.mark.unit
def test_decide_emits_event_when_capability_is_defined() -> None:
    cid = uuid4()
    rid_a = uuid4()
    rid_b = uuid4()
    state = _capability(cid)
    events = update_capability_suggested_roles.decide(
        state=state,
        command=UpdateCapabilitySuggestedRoles(
            capability_id=cid, suggested_role_ids=frozenset({rid_a, rid_b})
        ),
        now=_NOW,
    )
    assert events == [
        CapabilitySuggestedRolesUpdated(
            capability_id=cid,
            suggested_role_ids=frozenset({rid_a, rid_b}),
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_capability_is_versioned() -> None:
    """Versioned Capabilities accept suggested_roles updates."""
    cid = uuid4()
    state = _capability(cid, status=CapabilityStatus.VERSIONED)
    events = update_capability_suggested_roles.decide(
        state=state,
        command=UpdateCapabilitySuggestedRoles(
            capability_id=cid, suggested_role_ids=frozenset({uuid4()})
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_rejects_deprecated() -> None:
    cid = uuid4()
    state = _capability(cid, status=CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotUpdateSuggestedRolesError) as exc:
        update_capability_suggested_roles.decide(
            state=state,
            command=UpdateCapabilitySuggestedRoles(
                capability_id=cid, suggested_role_ids=frozenset({uuid4()})
            ),
            now=_NOW,
        )
    assert exc.value.capability_id == cid
    assert exc.value.current_status is CapabilityStatus.DEPRECATED


@pytest.mark.unit
def test_decide_rejects_missing_capability() -> None:
    cid = uuid4()
    with pytest.raises(CapabilityNotFoundError) as exc:
        update_capability_suggested_roles.decide(
            state=None,
            command=UpdateCapabilitySuggestedRoles(
                capability_id=cid, suggested_role_ids=frozenset()
            ),
            now=_NOW,
        )
    assert exc.value.capability_id == cid


@pytest.mark.unit
def test_decide_emits_event_for_empty_set_replacement() -> None:
    """Wholesale-replace shape: empty input clears the set."""
    cid = uuid4()
    state = _capability(cid, suggested_role_ids=frozenset({uuid4(), uuid4()}))
    events = update_capability_suggested_roles.decide(
        state=state,
        command=UpdateCapabilitySuggestedRoles(capability_id=cid, suggested_role_ids=frozenset()),
        now=_NOW,
    )
    assert events[0].suggested_role_ids == frozenset()


@pytest.mark.unit
def test_decide_emits_event_for_identical_payload() -> None:
    """Wholesale-replace is NOT strict-not-idempotent at the decider:
    re-publishing the same set still emits an event (treated as a
    valid editorial-republish; idempotency-key semantics live at the
    cross-BC layer if desired)."""
    cid = uuid4()
    rid_a = uuid4()
    existing = frozenset({rid_a})
    state = _capability(cid, suggested_role_ids=existing)
    events = update_capability_suggested_roles.decide(
        state=state,
        command=UpdateCapabilitySuggestedRoles(capability_id=cid, suggested_role_ids=existing),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    cid = uuid4()
    state = _capability(cid)
    rid = uuid4()
    cmd = UpdateCapabilitySuggestedRoles(capability_id=cid, suggested_role_ids=frozenset({rid}))
    first = update_capability_suggested_roles.decide(state=state, command=cmd, now=_NOW)
    second = update_capability_suggested_roles.decide(state=state, command=cmd, now=_NOW)
    assert first == second
