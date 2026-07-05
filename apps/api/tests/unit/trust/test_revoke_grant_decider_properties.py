"""Property-based tests for `revoke_grant.decide` (Trust BC, Policy).

Complements the example-based `policy/test_revoke_grant_decider.py` with
universal claims across generated inputs. The decider is a pure set-membership
removal

    (state, command, revoked_by, now) -> list[PolicyGrantRevoked]

Load-bearing properties:

  - state=None always raises `PolicyNotFoundError` carrying command.policy_id.
  - A principal not in the permitted set always returns [] (silently
    idempotent; no event, no error).
  - A principal in the permitted set + a valid reason emits exactly one
    PolicyGrantRevoked (policy_id=state.id, principal_id + revoked_by threaded,
    reason trimmed, occurred_at=now).
  - Blank / overlong reason always raises `InvalidPolicyGrantRevokeReasonError`.
  - Pure: same (state, command, revoked_by, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.policy import (
    InvalidPolicyGrantRevokeReasonError,
    Policy,
    PolicyGrantRevoked,
    PolicyName,
    PolicyNotFoundError,
)
from cora.trust.features.revoke_grant import RevokePolicyGrant
from cora.trust.features.revoke_grant.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH)


def _policy(*, policy_id: UUID, principals: frozenset[UUID]) -> Policy:
    return Policy(
        id=policy_id,
        name=PolicyName("Beam-team"),
        conduit_id=policy_id,
        permitted_principal_ids=principals,
        permitted_commands=frozenset({"RegisterActor"}),
    )


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    revoked_by=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_revoke_with_none_state_always_raises_not_found(
    policy_id: UUID,
    principal_id: UUID,
    revoked_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `PolicyNotFoundError` carrying command.policy_id."""
    with pytest.raises(PolicyNotFoundError) as exc:
        decide(
            state=None,
            command=RevokePolicyGrant(
                policy_id=policy_id, permitted_principal_id=principal_id, reason=reason
            ),
            revoked_by=revoked_by,
            now=now,
        )
    assert exc.value.policy_id == policy_id


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    revoked_by=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_revoke_absent_principal_always_returns_empty(
    policy_id: UUID,
    principal_id: UUID,
    revoked_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A principal not in the permitted set is a silent no-op ([])."""
    events = decide(
        state=_policy(policy_id=policy_id, principals=frozenset()),
        command=RevokePolicyGrant(
            policy_id=policy_id, permitted_principal_id=principal_id, reason=reason
        ),
        revoked_by=revoked_by,
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    revoked_by=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_revoke_present_principal_emits_single_event(
    policy_id: UUID,
    principal_id: UUID,
    revoked_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A permitted principal + valid reason emits one PolicyGrantRevoked, reason trimmed."""
    events = decide(
        state=_policy(policy_id=policy_id, principals=frozenset({principal_id})),
        command=RevokePolicyGrant(
            policy_id=policy_id, permitted_principal_id=principal_id, reason=reason
        ),
        revoked_by=revoked_by,
        now=now,
    )
    assert events == [
        PolicyGrantRevoked(
            policy_id=policy_id,
            principal_id=principal_id,
            revoked_by=revoked_by,
            reason=reason.strip(),
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    revoked_by=st.uuids(),
    reason=st.one_of(
        st.text(alphabet=" \t\n", min_size=0, max_size=5),
        printable_ascii_text(min_size=REASON_MAX_LENGTH + 1, max_size=REASON_MAX_LENGTH + 20),
    ),
    now=aware_datetimes(),
)
def test_revoke_blank_or_overlong_reason_always_raises(
    policy_id: UUID,
    principal_id: UUID,
    revoked_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Blank or overlong reason (after trim) raises before any emit."""
    assume(not reason.strip() or len(reason.strip()) > REASON_MAX_LENGTH)
    with pytest.raises(InvalidPolicyGrantRevokeReasonError):
        decide(
            state=_policy(policy_id=policy_id, principals=frozenset({principal_id})),
            command=RevokePolicyGrant(
                policy_id=policy_id, permitted_principal_id=principal_id, reason=reason
            ),
            revoked_by=revoked_by,
            now=now,
        )


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    revoked_by=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_revoke_is_pure_same_input_same_output(
    policy_id: UUID,
    principal_id: UUID,
    revoked_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _policy(policy_id=policy_id, principals=frozenset({principal_id}))
    command = RevokePolicyGrant(
        policy_id=policy_id, permitted_principal_id=principal_id, reason=reason
    )
    first = decide(state=state, command=command, revoked_by=revoked_by, now=now)
    second = decide(state=state, command=command, revoked_by=revoked_by, now=now)
    assert first == second
