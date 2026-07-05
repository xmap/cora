"""Decider tests for `revoke_grant` (drop one principal from a Policy's allow-list)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.trust.aggregates.policy import (
    InvalidPolicyGrantRevokeReasonError,
    Policy,
    PolicyGrantRevoked,
    PolicyName,
    PolicyNotFoundError,
)
from cora.trust.features.revoke_grant import RevokePolicyGrant
from cora.trust.features.revoke_grant.decider import decide

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000f01")
_PRINCIPAL_IN = UUID("01900000-0000-7000-8000-000000000a01")
_PRINCIPAL_ABSENT = UUID("01900000-0000-7000-8000-000000000a02")
_INVOKER = UUID("01900000-0000-7000-8000-000000000099")
_CONDUIT = UUID("01900000-0000-7000-8000-000000000c01")


def _policy(*, principals: frozenset[UUID] = frozenset({_PRINCIPAL_IN})) -> Policy:
    return Policy(
        id=_POLICY_ID,
        name=PolicyName("Beam-team"),
        conduit_id=_CONDUIT,
        permitted_principal_ids=principals,
        permitted_commands=frozenset({"RegisterActor"}),
    )


@pytest.mark.unit
def test_revoke_present_principal_emits_grant_revoked() -> None:
    events = decide(
        state=_policy(),
        command=RevokePolicyGrant(
            policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="access review"
        ),
        revoked_by=_INVOKER,
        now=_NOW,
    )
    [e] = events
    assert isinstance(e, PolicyGrantRevoked)
    assert e.policy_id == _POLICY_ID
    assert e.principal_id == _PRINCIPAL_IN
    assert e.revoked_by == _INVOKER
    assert e.reason == "access review"
    assert e.occurred_at == _NOW


@pytest.mark.unit
def test_revoke_trims_reason() -> None:
    events = decide(
        state=_policy(),
        command=RevokePolicyGrant(
            policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="  trimmed  "
        ),
        revoked_by=_INVOKER,
        now=_NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.unit
def test_revoke_raises_not_found_on_empty_state() -> None:
    with pytest.raises(PolicyNotFoundError):
        decide(
            state=None,
            command=RevokePolicyGrant(
                policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="r"
            ),
            revoked_by=_INVOKER,
            now=_NOW,
        )


@pytest.mark.unit
def test_revoke_absent_principal_is_silently_idempotent() -> None:
    events = decide(
        state=_policy(),
        command=RevokePolicyGrant(
            policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_ABSENT, reason="access review"
        ),
        revoked_by=_INVOKER,
        now=_NOW,
    )
    assert events == []


@pytest.mark.parametrize("bad_reason", ["", "   ", "\n\t"])
@pytest.mark.unit
def test_revoke_rejects_whitespace_reason(bad_reason: str) -> None:
    with pytest.raises(InvalidPolicyGrantRevokeReasonError):
        decide(
            state=_policy(),
            command=RevokePolicyGrant(
                policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason=bad_reason
            ),
            revoked_by=_INVOKER,
            now=_NOW,
        )


@pytest.mark.unit
def test_revoke_rejects_too_long_reason() -> None:
    with pytest.raises(InvalidPolicyGrantRevokeReasonError):
        decide(
            state=_policy(),
            command=RevokePolicyGrant(
                policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="a" * 501
            ),
            revoked_by=_INVOKER,
            now=_NOW,
        )
