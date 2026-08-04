"""Tests for the shared authorization decision seam.

The seam exists so the gate and the query slices cannot drift apart as
conjuncts are added. Two properties carry that guarantee and are the
reason these tests exist rather than testing `evaluate` twice over:
every result names the conjuncts it consulted, and both context arms
reach the same verdict while the Policy is the only conjunct.
"""

from uuid import UUID

import pytest

from cora.infrastructure.ports import Allow, Conjunct, Deny
from cora.trust._authorization_decision import (
    AuthorizationRequest,
    PolicyOnlyContext,
    ResolvedContext,
    decide_authorization,
)
from cora.trust.aggregates.policy import Policy, PolicyName

_POLICY_ID = UUID("01900000-0000-7000-8000-000000000f01")
_PERMITTED = UUID("01900000-0000-7000-8000-000000000a01")
_STRANGER = UUID("01900000-0000-7000-8000-000000000a02")
_CONDUIT = UUID("01900000-0000-7000-8000-000000000c01")
_OTHER_CONDUIT = UUID("01900000-0000-7000-8000-000000000c02")
_SURFACE = UUID("01900000-0000-7000-8000-0000000005f1")
_OTHER_SURFACE = UUID("01900000-0000-7000-8000-0000000005f2")


def _policy() -> Policy:
    return Policy(
        id=_POLICY_ID,
        name=PolicyName("Beam-team"),
        conduit_id=_CONDUIT,
        surface_id=_SURFACE,
        permitted_principal_ids=frozenset({_PERMITTED}),
        permitted_commands=frozenset({"StartRun"}),
    )


def _request(
    *,
    principal_id: UUID = _PERMITTED,
    command_name: str = "StartRun",
    conduit_id: UUID = _CONDUIT,
    surface_id: UUID = _SURFACE,
) -> AuthorizationRequest:
    return AuthorizationRequest(
        principal_id=principal_id,
        command_name=command_name,
        conduit_id=conduit_id,
        surface_id=surface_id,
    )


@pytest.mark.unit
def test_resolved_context_permits_a_request_the_policy_covers() -> None:
    result = decide_authorization(_request(), ResolvedContext(policy=_policy()))

    assert isinstance(result, Allow)


@pytest.mark.unit
def test_policy_only_context_permits_the_same_request() -> None:
    result = decide_authorization(_request(), PolicyOnlyContext(policy=_policy()))

    assert isinstance(result, Allow)


@pytest.mark.unit
@pytest.mark.parametrize(
    "request_override",
    [
        pytest.param({"principal_id": _STRANGER}, id="principal-not-permitted"),
        pytest.param({"command_name": "StopRun"}, id="command-not-permitted"),
        pytest.param({"conduit_id": _OTHER_CONDUIT}, id="conduit-mismatch"),
        pytest.param({"surface_id": _OTHER_SURFACE}, id="surface-mismatch"),
    ],
)
def test_resolved_context_refuses_what_the_policy_does_not_cover(
    request_override: dict[str, object],
) -> None:
    result = decide_authorization(
        _request(**request_override),  # pyright: ignore[reportArgumentType]
        ResolvedContext(policy=_policy()),
    )

    assert isinstance(result, Deny)


@pytest.mark.unit
def test_every_decision_names_the_conjuncts_it_consulted() -> None:
    """Partiality is a return value, so a caller cannot fail to report it."""
    permitted = decide_authorization(_request(), ResolvedContext(policy=_policy()))
    refused = decide_authorization(
        _request(principal_id=_STRANGER), ResolvedContext(policy=_policy())
    )

    assert permitted.evaluated == frozenset({Conjunct.POLICY})
    assert refused.evaluated == frozenset({Conjunct.POLICY})


@pytest.mark.unit
@pytest.mark.parametrize(
    "request_override",
    [
        pytest.param({}, id="permitted"),
        pytest.param({"principal_id": _STRANGER}, id="principal-not-permitted"),
        pytest.param({"command_name": "StopRun"}, id="command-not-permitted"),
        pytest.param({"conduit_id": _OTHER_CONDUIT}, id="conduit-mismatch"),
        pytest.param({"surface_id": _OTHER_SURFACE}, id="surface-mismatch"),
    ],
)
def test_both_contexts_agree_while_policy_is_the_only_conjunct(
    request_override: dict[str, object],
) -> None:
    """The divergence guard.

    Today the arms must agree, because the Policy is all either can
    consult. When a conjunct lands on the resolved arm this test is
    expected to fail, and that failure is the prompt to state what the
    hypothetical arm does instead of letting it silently fall behind.
    """
    request = _request(**request_override)  # pyright: ignore[reportArgumentType]

    resolved = decide_authorization(request, ResolvedContext(policy=_policy()))
    policy_only = decide_authorization(request, PolicyOnlyContext(policy=_policy()))

    assert type(resolved) is type(policy_only)
    assert resolved.evaluated == policy_only.evaluated


@pytest.mark.unit
def test_a_result_with_no_stated_conjuncts_decided_on_nothing() -> None:
    """The permissive fallback's honest report, pinned so it stays true."""
    assert Allow().evaluated == frozenset()
    assert Deny(reason="denied").evaluated == frozenset()
