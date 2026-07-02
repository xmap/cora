"""Unit tests for the `revoke_grant` slice's pure decider.

Set-membership removal of one principal from a Policy's permitted set.
Silently idempotent (no event when the principal is already absent);
the only rejection is `PolicyNotFoundError`. `reason` is REQUIRED and
validated defensively at the decider (1-`REASON_MAX_LENGTH` after trim).

`revoked_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`PolicyGrantRevoked` event as the audit denorm.

Symmetry: `principal_id` is a bare UUID, so a human grant and an agent
grant are removed by the identical code path (paper invariant I1).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.policy import (
    InvalidPolicyGrantRevokeReasonError,
    Policy,
    PolicyGrantRevoked,
    PolicyName,
    PolicyNotFoundError,
)
from cora.trust.features import revoke_grant
from cora.trust.features.revoke_grant import RevokeGrant

_NOW = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-0000000ab001")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-0000000ab002")
_HUMAN = UUID("01900000-0000-7000-8000-0000000ab010")
_AGENT = UUID("01900000-0000-7000-8000-0000000ab011")
_REVOKED_BY = UUID("01900000-0000-7000-8000-0000000ab099")
_REASON = "agent decommissioned"


def _policy(*permitted: UUID) -> Policy:
    return Policy(
        id=_POLICY_ID,
        name=PolicyName("Beam-team"),
        conduit_id=_CONDUIT_ID,
        permitted_principal_ids=frozenset(permitted),
        permitted_commands=frozenset({"HoldRun"}),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )


def _command(principal_id: UUID = _AGENT, reason: str = _REASON) -> RevokeGrant:
    return RevokeGrant(policy_id=_POLICY_ID, principal_id=principal_id, reason=reason)


@pytest.mark.unit
def test_revoke_grant_removes_present_principal() -> None:
    events = revoke_grant.decide(
        state=_policy(_HUMAN, _AGENT),
        command=_command(_AGENT),
        now=_NOW,
        revoked_by=_REVOKED_BY,
    )
    assert events == [
        PolicyGrantRevoked(
            policy_id=_POLICY_ID,
            revoked_principal_id=_AGENT,
            revoked_by=_REVOKED_BY,
            reason=_REASON,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_revoke_grant_is_silently_idempotent_when_principal_absent() -> None:
    """Set-membership: revoking an absent principal returns [] (no event)."""
    events = revoke_grant.decide(
        state=_policy(_HUMAN),  # _AGENT not present
        command=_command(_AGENT),
        now=_NOW,
        revoked_by=_REVOKED_BY,
    )
    assert events == []


@pytest.mark.unit
def test_revoke_grant_rejects_when_state_is_none() -> None:
    with pytest.raises(PolicyNotFoundError) as exc_info:
        revoke_grant.decide(
            state=None,
            command=_command(),
            now=_NOW,
            revoked_by=_REVOKED_BY,
        )
    assert exc_info.value.policy_id == _POLICY_ID


@pytest.mark.unit
@pytest.mark.parametrize("bad_reason", ["", "   ", "\t\n"])
def test_revoke_grant_rejects_blank_reason(bad_reason: str) -> None:
    with pytest.raises(InvalidPolicyGrantRevokeReasonError):
        revoke_grant.decide(
            state=_policy(_AGENT),
            command=_command(reason=bad_reason),
            now=_NOW,
            revoked_by=_REVOKED_BY,
        )


@pytest.mark.unit
def test_revoke_grant_rejects_overlong_reason() -> None:
    with pytest.raises(InvalidPolicyGrantRevokeReasonError):
        revoke_grant.decide(
            state=_policy(_AGENT),
            command=_command(reason="x" * (REASON_MAX_LENGTH + 1)),
            now=_NOW,
            revoked_by=_REVOKED_BY,
        )


@pytest.mark.unit
def test_revoke_grant_trims_reason_onto_event() -> None:
    events = revoke_grant.decide(
        state=_policy(_AGENT),
        command=_command(reason="  padded reason  "),
        now=_NOW,
        revoked_by=_REVOKED_BY,
    )
    assert len(events) == 1
    assert events[0].reason == "padded reason"


@pytest.mark.unit
def test_revoke_grant_captures_handler_injected_revoked_by() -> None:
    arbitrary = uuid4()
    events = revoke_grant.decide(
        state=_policy(_AGENT),
        command=_command(),
        now=_NOW,
        revoked_by=arbitrary,
    )
    assert events[0].revoked_by == arbitrary


@pytest.mark.unit
def test_revoke_grant_uses_supplied_now_for_occurred_at() -> None:
    custom_now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
    events = revoke_grant.decide(
        state=_policy(_AGENT),
        command=_command(),
        now=custom_now,
        revoked_by=_REVOKED_BY,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_revoke_grant_uses_state_id_not_command_policy_id() -> None:
    """The emitted event's policy_id is state.id."""
    events = revoke_grant.decide(
        state=_policy(_AGENT),
        command=_command(),
        now=_NOW,
        revoked_by=_REVOKED_BY,
    )
    assert events[0].policy_id == _POLICY_ID


@pytest.mark.unit
def test_revoke_grant_human_and_agent_use_same_path() -> None:
    """Actor symmetry: revoking a human grant and an agent grant differ
    only in the bare UUID, never in code path or event shape."""
    human_events = revoke_grant.decide(
        state=_policy(_HUMAN, _AGENT),
        command=_command(_HUMAN),
        now=_NOW,
        revoked_by=_REVOKED_BY,
    )
    agent_events = revoke_grant.decide(
        state=_policy(_HUMAN, _AGENT),
        command=_command(_AGENT),
        now=_NOW,
        revoked_by=_REVOKED_BY,
    )
    assert human_events[0].revoked_principal_id == _HUMAN
    assert agent_events[0].revoked_principal_id == _AGENT
    # Same event type, same shape modulo the principal.
    assert type(human_events[0]) is type(agent_events[0])


@pytest.mark.unit
def test_revoke_grant_is_pure_same_inputs_same_outputs() -> None:
    state = _policy(_AGENT)
    command = _command()
    first = revoke_grant.decide(state=state, command=command, now=_NOW, revoked_by=_REVOKED_BY)
    second = revoke_grant.decide(state=state, command=command, now=_NOW, revoked_by=_REVOKED_BY)
    assert first == second
