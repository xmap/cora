"""PolicyName VO + the pure `evaluate` Policy Decision Point function.

Two distinct concerns sharing this file because they're both
state.py-level and the file is small. Split when one set of tests
grows past ~10.
"""

from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports import Allow, Deny
from cora.trust.aggregates.policy import (
    InvalidPolicyNameError,
    Policy,
    PolicyName,
    evaluate,
)

# ---------- PolicyName VO ----------


@pytest.mark.unit
def test_policy_name_accepts_normal_string() -> None:
    name = PolicyName("Beam-team")
    assert name.value == "Beam-team"


@pytest.mark.unit
def test_policy_name_trims_whitespace() -> None:
    name = PolicyName("  Beam-team  ")
    assert name.value == "Beam-team"


@pytest.mark.unit
def test_policy_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidPolicyNameError):
        PolicyName("")


@pytest.mark.unit
def test_policy_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidPolicyNameError):
        PolicyName("   \t\n   ")


@pytest.mark.unit
def test_policy_name_rejects_too_long() -> None:
    with pytest.raises(InvalidPolicyNameError):
        PolicyName("a" * 201)


@pytest.mark.unit
def test_policy_name_accepts_max_length() -> None:
    name = PolicyName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_policy_name_is_frozen() -> None:
    name = PolicyName("Beam-team")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- evaluate (pure Policy Decision Point) ----------

_PRINCIPAL_OK = UUID("01900000-0000-7000-8000-000000000a01")
_PRINCIPAL_OTHER = UUID("01900000-0000-7000-8000-000000000a02")
_CONDUIT_OK = UUID("01900000-0000-7000-8000-000000000c01")
_CONDUIT_OTHER = UUID("01900000-0000-7000-8000-000000000c02")


def _policy(
    *,
    conduit_id: UUID = _CONDUIT_OK,
    principals: frozenset[UUID] = frozenset({_PRINCIPAL_OK}),
    commands: frozenset[str] = frozenset({"RegisterActor"}),
) -> Policy:
    return Policy(
        id=uuid4(),
        name=PolicyName("Test"),
        conduit_id=conduit_id,
        permitted_principal_ids=principals,
        permitted_commands=commands,
    )


@pytest.mark.unit
def test_evaluate_allows_when_all_three_match() -> None:
    result = evaluate(
        _policy(),
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
    )
    assert isinstance(result, Allow)


@pytest.mark.unit
def test_evaluate_denies_when_conduit_does_not_match() -> None:
    result = evaluate(
        _policy(),
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OTHER,
    )
    assert isinstance(result, Deny)
    assert "conduit" in result.reason.lower()


@pytest.mark.unit
def test_evaluate_denies_when_principal_not_permitted() -> None:
    result = evaluate(
        _policy(),
        principal_id=_PRINCIPAL_OTHER,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
    )
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()
    assert str(_PRINCIPAL_OTHER) in result.reason


@pytest.mark.unit
def test_evaluate_denies_when_command_not_permitted() -> None:
    result = evaluate(
        _policy(),
        principal_id=_PRINCIPAL_OK,
        command_name="DropDatabase",
        conduit_id=_CONDUIT_OK,
    )
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()
    assert "DropDatabase" in result.reason


@pytest.mark.unit
def test_evaluate_denies_with_empty_permitted_principal_ids() -> None:
    """Empty allow-list policy denies every principal (deny-all-by-construction)."""
    result = evaluate(
        _policy(principals=frozenset()),
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
    )
    assert isinstance(result, Deny)


@pytest.mark.unit
def test_evaluate_denies_with_empty_permitted_commands() -> None:
    result = evaluate(
        _policy(commands=frozenset()),
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
    )
    assert isinstance(result, Deny)


@pytest.mark.unit
def test_evaluate_check_order_conduit_first() -> None:
    """Conduit-mismatch check fires before principal/command checks (cheapest
    test, scopes the policy). A request with all three wrong should report
    the conduit mismatch, not the others."""
    result = evaluate(
        _policy(),
        principal_id=_PRINCIPAL_OTHER,
        command_name="DropDatabase",
        conduit_id=_CONDUIT_OTHER,
    )
    assert isinstance(result, Deny)
    assert "conduit" in result.reason.lower()


@pytest.mark.unit
def test_evaluate_is_pure_same_inputs_same_outputs() -> None:
    policy = _policy()
    first = evaluate(
        policy,
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
    )
    second = evaluate(
        policy,
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
    )
    assert isinstance(first, Allow)
    assert isinstance(second, Allow)


# ---------- surface binding: strict match (nil-surface fold is inert) ----------


_SURFACE_HTTP = UUID("00000000-0000-0000-0000-000000000020")
_SURFACE_MCP = UUID("00000000-0000-0000-0000-000000000021")
_NIL_SURFACE = UUID(int=0)


def _nil_surface_policy() -> Policy:
    """A policy folded to nil surface (only the retired V1 bootstrap seed)."""
    return Policy(
        id=uuid4(),
        name=PolicyName("nil surface"),
        conduit_id=_CONDUIT_OK,
        permitted_principal_ids=frozenset({_PRINCIPAL_OK}),
        permitted_commands=frozenset({"RegisterActor"}),
        surface_id=_NIL_SURFACE,
    )


def _http_policy() -> Policy:
    """A policy bound to a specific HTTP surface."""
    return Policy(
        id=uuid4(),
        name=PolicyName("HTTP"),
        conduit_id=_CONDUIT_OK,
        permitted_principal_ids=frozenset({_PRINCIPAL_OK}),
        permitted_commands=frozenset({"RegisterActor"}),
        surface_id=_SURFACE_HTTP,
    )


@pytest.mark.unit
def test_nil_surface_policy_denies_real_surface_call() -> None:
    """The nil-as-wildcard fold was removed at the V1 sunset: a policy
    folded to nil surface (only the retired V1 bootstrap seed) now
    strict-denies every real arrival surface and is operationally
    inert."""
    policy = _nil_surface_policy()
    for call_surface in (_SURFACE_HTTP, _SURFACE_MCP):
        result = evaluate(
            policy,
            principal_id=_PRINCIPAL_OK,
            command_name="RegisterActor",
            conduit_id=_CONDUIT_OK,
            surface_id=call_surface,
        )
        assert isinstance(result, Deny), f"nil-surface policy must deny surface={call_surface}"
        assert "surface" in result.reason.lower()


@pytest.mark.unit
def test_surface_bound_policy_allows_matching_surface() -> None:
    """A surface-bound policy allows a call arriving on that surface."""
    policy = _http_policy()
    allow = evaluate(
        policy,
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
        surface_id=_SURFACE_HTTP,
    )
    assert isinstance(allow, Allow)


@pytest.mark.unit
def test_surface_bound_policy_denies_wrong_surface() -> None:
    """An HTTP-bound policy denies an MCP call's surface_id."""
    policy = _http_policy()
    result = evaluate(
        policy,
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
        surface_id=_SURFACE_MCP,
    )
    assert isinstance(result, Deny)
    assert "surface" in result.reason.lower()


@pytest.mark.unit
def test_surface_bound_policy_denies_nil_surface_call() -> None:
    """An HTTP-bound policy denies a nil-surface call. Strict equality
    in both directions: the nil sentinel never matches a real surface."""
    policy = _http_policy()
    result = evaluate(
        policy,
        principal_id=_PRINCIPAL_OK,
        command_name="RegisterActor",
        conduit_id=_CONDUIT_OK,
        surface_id=_NIL_SURFACE,
    )
    assert isinstance(result, Deny)
    assert "surface" in result.reason.lower()
