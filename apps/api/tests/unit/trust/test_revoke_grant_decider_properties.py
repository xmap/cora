"""Property-based tests for `revoke_grant.decide` (Trust BC).

Complements the example-based `test_revoke_grant_decider.py` with
universal claims across generated inputs. The decider is a pure
set-membership removal

    (state, command, now, revoked_by) -> list[PolicyGrantRevoked]

Load-bearing properties:

  - state=None always raises `PolicyNotFoundError` carrying
    command.policy_id (existence guard).
  - Silent idempotence is total: if the target principal is NOT in the
    permitted set, the result is always [] (no event), for any otherwise
    valid inputs.
  - Membership present + valid reason emits exactly one
    `PolicyGrantRevoked` (policy_id=state.id, revoked_principal_id=the
    target, revoked_by/occurred_at threaded verbatim).
  - A blank / whitespace-only / overlong reason always raises
    `InvalidPolicyGrantRevokeReasonError`, and the check precedes the
    membership no-op (a bad reason raises even when the principal is
    absent), so the length contract cannot be bypassed via the idempotent
    path.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_CONDUIT_ID = UUID("01900000-0000-7000-8000-0000000ac001")

# Reasons Hypothesis may generate that pass the 1-REASON_MAX_LENGTH-after-trim
# contract. printable_ascii_text(min_size=1) can still be all-whitespace, so we
# filter to a non-empty trim.
_valid_reasons = printable_ascii_text(min_size=1, max_size=64).filter(lambda s: bool(s.strip()))


def _policy(policy_id: UUID, permitted: frozenset[UUID]) -> Policy:
    return Policy(
        id=policy_id,
        name=PolicyName("Beam-team"),
        conduit_id=_CONDUIT_ID,
        permitted_principal_ids=permitted,
        permitted_commands=frozenset({"HoldRun"}),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    reason=_valid_reasons,
    revoked_by=st.uuids(),
    now=aware_datetimes(),
)
def test_none_state_always_raises_not_found(
    policy_id: UUID,
    principal_id: UUID,
    reason: str,
    revoked_by: UUID,
    now: datetime,
) -> None:
    with pytest.raises(PolicyNotFoundError) as exc:
        revoke_grant.decide(
            state=None,
            command=RevokeGrant(policy_id=policy_id, principal_id=principal_id, reason=reason),
            now=now,
            revoked_by=revoked_by,
        )
    assert exc.value.policy_id == policy_id


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    permitted=st.frozensets(st.uuids(), max_size=5),
    principal_id=st.uuids(),
    reason=_valid_reasons,
    revoked_by=st.uuids(),
    now=aware_datetimes(),
)
def test_absent_principal_is_always_noop(
    policy_id: UUID,
    permitted: frozenset[UUID],
    principal_id: UUID,
    reason: str,
    revoked_by: UUID,
    now: datetime,
) -> None:
    """If the target principal is not permitted, the result is always []."""
    assume(principal_id not in permitted)
    events = revoke_grant.decide(
        state=_policy(policy_id, permitted),
        command=RevokeGrant(policy_id=policy_id, principal_id=principal_id, reason=reason),
        now=now,
        revoked_by=revoked_by,
    )
    assert events == []


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    others=st.frozensets(st.uuids(), max_size=4),
    reason=_valid_reasons,
    revoked_by=st.uuids(),
    now=aware_datetimes(),
)
def test_present_principal_emits_single_event(
    policy_id: UUID,
    principal_id: UUID,
    others: frozenset[UUID],
    reason: str,
    revoked_by: UUID,
    now: datetime,
) -> None:
    permitted = others | {principal_id}
    events = revoke_grant.decide(
        state=_policy(policy_id, permitted),
        command=RevokeGrant(policy_id=policy_id, principal_id=principal_id, reason=reason),
        now=now,
        revoked_by=revoked_by,
    )
    assert events == [
        PolicyGrantRevoked(
            policy_id=policy_id,
            revoked_principal_id=principal_id,
            revoked_by=revoked_by,
            reason=reason.strip(),
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    permitted=st.frozensets(st.uuids(), max_size=5),
    principal_id=st.uuids(),
    revoked_by=st.uuids(),
    now=aware_datetimes(),
    pad=st.integers(min_value=1, max_value=3),
)
def test_overlong_reason_always_raises_even_when_absent(
    policy_id: UUID,
    permitted: frozenset[UUID],
    principal_id: UUID,
    revoked_by: UUID,
    now: datetime,
    pad: int,
) -> None:
    """The reason-length check precedes the membership no-op, so a bad
    reason raises regardless of whether the principal is present."""
    assume(principal_id not in permitted)
    with pytest.raises(InvalidPolicyGrantRevokeReasonError):
        revoke_grant.decide(
            state=_policy(policy_id, permitted),
            command=RevokeGrant(
                policy_id=policy_id,
                principal_id=principal_id,
                reason="x" * (REASON_MAX_LENGTH + pad),
            ),
            now=now,
            revoked_by=revoked_by,
        )


@pytest.mark.unit
@given(
    policy_id=st.uuids(),
    principal_id=st.uuids(),
    reason=_valid_reasons,
    revoked_by=st.uuids(),
    now=aware_datetimes(),
)
def test_is_pure_same_input_same_output(
    policy_id: UUID,
    principal_id: UUID,
    reason: str,
    revoked_by: UUID,
    now: datetime,
) -> None:
    state = _policy(policy_id, frozenset({principal_id}))
    command = RevokeGrant(policy_id=policy_id, principal_id=principal_id, reason=reason)
    first = revoke_grant.decide(state=state, command=command, now=now, revoked_by=revoked_by)
    second = revoke_grant.decide(state=state, command=command, now=now, revoked_by=revoked_by)
    assert first == second
