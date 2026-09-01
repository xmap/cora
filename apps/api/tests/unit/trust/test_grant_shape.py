"""The one rule deciding which grant shape a `define_policy` caller sent.

`_grant_shape.resolve` is shared by `POST /policies` and the
`define_policy` MCP tool. Each surface has contract tests, but those
exercise only their own copy of the call; these pin the rule itself, so
a change to it cannot be green in one surface's suite and wrong in the
other's.

The distinction that carries the weight: ABSENT (`None`) is not
supplied, EMPTY is supplied and means deny-all. Collapsing the two would
turn a body that forgot its grants into a silently permissive or
silently empty policy instead of a refusal.
"""

from uuid import UUID

import pytest

from cora.trust.features.define_policy import _grant_shape
from cora.trust.features.define_policy._grant_shape import GrantShape

_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")


@pytest.mark.unit
def test_a_grants_mapping_alone_resolves_to_exact() -> None:
    assert (
        _grant_shape.resolve(
            grants={_PRINCIPAL: ["RegisterActor"]},
            permitted_principal_ids=None,
            permitted_commands=None,
        )
        is GrantShape.EXACT
    )


@pytest.mark.unit
def test_the_two_lists_alone_resolve_to_cross_product() -> None:
    assert (
        _grant_shape.resolve(
            grants=None,
            permitted_principal_ids=[_PRINCIPAL],
            permitted_commands=["RegisterActor"],
        )
        is GrantShape.CROSS_PRODUCT
    )


@pytest.mark.unit
def test_an_empty_grants_mapping_is_supplied_not_absent() -> None:
    """Empty means deny-all, and deny-all is a thing a caller may mean."""
    assert (
        _grant_shape.resolve(
            grants={},
            permitted_principal_ids=None,
            permitted_commands=None,
        )
        is GrantShape.EXACT
    )


@pytest.mark.unit
def test_two_empty_lists_are_supplied_not_absent() -> None:
    assert (
        _grant_shape.resolve(
            grants=None,
            permitted_principal_ids=[],
            permitted_commands=[],
        )
        is GrantShape.CROSS_PRODUCT
    )


@pytest.mark.unit
def test_both_shapes_at_once_is_refused() -> None:
    """Never resolved by preference: the two grant materially different
    sets, so picking one silently would over- or under-grant."""
    with pytest.raises(ValueError, match="not both"):
        _grant_shape.resolve(
            grants={_PRINCIPAL: ["RegisterActor"]},
            permitted_principal_ids=[_PRINCIPAL],
            permitted_commands=["RegisterActor"],
        )


@pytest.mark.unit
def test_an_empty_mapping_alongside_empty_lists_is_still_refused() -> None:
    """Both-supplied is about presence, not content.

    Empty containers are the case a `if grants and pair` truthiness
    check would wave through, and it would then fall to whichever branch
    happened to be first.
    """
    with pytest.raises(ValueError, match="not both"):
        _grant_shape.resolve(
            grants={},
            permitted_principal_ids=[],
            permitted_commands=[],
        )


@pytest.mark.unit
def test_neither_shape_is_refused() -> None:
    with pytest.raises(ValueError, match="Provide 'grants'"):
        _grant_shape.resolve(
            grants=None,
            permitted_principal_ids=None,
            permitted_commands=None,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("principal_ids", "command_names"),
    [
        ([_PRINCIPAL], None),
        (None, ["RegisterActor"]),
        ([], None),
        (None, []),
    ],
)
def test_half_the_pair_is_refused(
    principal_ids: list[UUID] | None, command_names: list[str] | None
) -> None:
    """One list without the other cross-products into nothing.

    Silently treating the missing half as empty would yield a deny-all
    policy from a body that plainly meant to grant something.
    """
    with pytest.raises(ValueError, match="Provide 'grants'"):
        _grant_shape.resolve(
            grants=None,
            permitted_principal_ids=principal_ids,
            permitted_commands=command_names,
        )
