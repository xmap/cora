"""Tests for the shared authorization decision seam.

The seam exists so the gate and the query slices cannot drift apart as
conjuncts are added. Two properties carry that guarantee and are the
reason these tests exist rather than testing `evaluate` twice over:
every result names the conjuncts it consulted, and both context arms
reach the same verdict while the Policy is the only conjunct.
"""

from uuid import UUID

import pytest

from cora.infrastructure.ports import Allow, Conjunct, Deny, PrincipalLiveness
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
def test_both_contexts_agree_when_the_resolved_arm_adds_nothing(
    request_override: dict[str, object],
) -> None:
    """The divergence guard, rebuilt after it failed to fire.

    It was written to fail the moment a conjunct landed on the resolved
    arm, and it did not: liveness landed with a `None` default, so
    `ResolvedContext(policy=...)` kept consulting the Policy alone and
    the guard stayed green through the very change it was watching for.

    A default-valued field cannot be the trip wire, so the assertion is
    now about a stated condition rather than about construction: when the
    resolved arm consults nothing extra, the two arms must agree. The
    NEXT conjunct is caught by its own divergence test below, which is
    the pattern each new conjunct must follow.
    """
    request = _request(**request_override)  # pyright: ignore[reportArgumentType]

    resolved = decide_authorization(request, ResolvedContext(policy=_policy()))
    policy_only = decide_authorization(request, PolicyOnlyContext(policy=_policy()))

    assert type(resolved) is type(policy_only)
    assert resolved.evaluated == policy_only.evaluated


@pytest.mark.unit
def test_resolved_arm_diverges_from_the_hypothetical_once_liveness_is_known() -> None:
    """The arms MUST differ here, and that difference is the design.

    A deactivated principal is refused on the live request path and
    reported as permitted by the hypothetical one, because the query
    slices deliberately do not disclose another principal's switch. The
    asymmetry is safe only because `evaluated` says which questions each
    answer actually asked, so this pins the divergence AND the label that
    makes it honest.
    """
    request = _request()

    resolved = decide_authorization(
        request,
        ResolvedContext(policy=_policy(), liveness=PrincipalLiveness.DEACTIVATED),
    )
    policy_only = decide_authorization(request, PolicyOnlyContext(policy=_policy()))

    assert isinstance(resolved, Deny)
    assert isinstance(policy_only, Allow)
    assert Conjunct.LIVENESS in resolved.evaluated
    assert Conjunct.LIVENESS not in policy_only.evaluated


@pytest.mark.unit
def test_a_result_with_no_stated_conjuncts_decided_on_nothing() -> None:
    """The permissive fallback's honest report, pinned so it stays true."""
    assert Allow().evaluated == frozenset()
    assert Deny(reason="denied").evaluated == frozenset()


@pytest.mark.unit
def test_unwired_liveness_leaves_the_conjunct_unevaluated() -> None:
    """No lookup means the question was never asked, and the verdict says so.

    The distinction this pins is between "asked and passed" and "never
    asked". A deployment with no lookup wired must not produce a verdict
    that names Liveness, or the audit record claims a check that did not
    run.
    """
    result = decide_authorization(_request(), ResolvedContext(policy=_policy()))

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY})


@pytest.mark.unit
def test_active_principal_is_permitted_and_liveness_is_named() -> None:
    result = decide_authorization(
        _request(),
        ResolvedContext(policy=_policy(), liveness=PrincipalLiveness.ACTIVE),
    )

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY, Conjunct.LIVENESS})


@pytest.mark.unit
@pytest.mark.parametrize(
    ("liveness", "remedy"),
    [
        (PrincipalLiveness.DEACTIVATED, "reactivate_actor"),
        (PrincipalLiveness.UNREGISTERED, "register_actor"),
    ],
)
def test_switched_off_principal_is_refused_with_its_remedy(
    liveness: PrincipalLiveness, remedy: str
) -> None:
    """A denial names the cause AND the command that clears it.

    A gate that says only "no" costs a beamtime shift to diagnose, so
    both refusal paths are pinned to keep carrying their own fix.
    """
    result = decide_authorization(
        _request(),
        ResolvedContext(policy=_policy(), liveness=liveness),
    )

    assert isinstance(result, Deny)
    assert remedy in result.reason
    assert result.evaluated == frozenset({Conjunct.POLICY, Conjunct.LIVENESS})


@pytest.mark.unit
def test_policy_denial_hides_liveness_from_an_unpermitted_principal() -> None:
    """Policy runs first so the gate is not a liveness oracle.

    A principal the Policy refuses learns nothing about whether it also
    exists or has been switched off. Were the order reversed, anyone able
    to provoke a denial could enumerate which principals are registered
    and which an operator has disabled.
    """
    result = decide_authorization(
        _request(principal_id=_STRANGER),
        ResolvedContext(policy=_policy(), liveness=PrincipalLiveness.DEACTIVATED),
    )

    assert isinstance(result, Deny)
    assert "deactivated" not in result.reason.lower()
    assert result.evaluated == frozenset({Conjunct.POLICY})


@pytest.mark.unit
def test_liveness_never_turns_a_policy_denial_into_a_grant() -> None:
    """Liveness only ever narrows. Pinned as a property, not an example.

    Every liveness value is run against a request the Policy refuses, so
    a future edit that returns Allow from the liveness arm fails here
    rather than in production.
    """
    for liveness in PrincipalLiveness:
        result = decide_authorization(
            _request(command_name="StopRun"),
            ResolvedContext(policy=_policy(), liveness=liveness),
        )

        assert isinstance(result, Deny), liveness


@pytest.mark.unit
def test_policy_only_context_ignores_liveness_entirely() -> None:
    """The hypothetical arm cannot carry liveness, by construction.

    `PolicyOnlyContext` has no liveness field, so the query slices cannot
    start disclosing whether another principal is switched off. This test
    pins the shape rather than the behaviour: if someone adds the field,
    the constructor call below still compiles and this test is the place
    that argues why they should not.
    """
    result = decide_authorization(_request(), PolicyOnlyContext(policy=_policy()))

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY})
