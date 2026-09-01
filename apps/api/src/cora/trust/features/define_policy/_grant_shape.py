"""Which of the two accepted grant shapes a caller supplied.

`POST /policies` and the `define_policy` MCP tool both accept either an
exact `grants` mapping or the `permitted_principal_ids` /
`permitted_commands` pair that cross-products into one. The rule for
deciding which was meant lives here, once, because it is a
security-relevant rule with two call sites: the two surfaces are
otherwise free to drift, and a divergence would be invisible (each
surface's contract tests exercise only its own copy) right up until one
of them let a caller ask for a narrow mapping and receive a
cross-product.

Only the RULE is shared, not the refusal. The REST surface needs its
refusal raised inside a Pydantic validator so FastAPI renders a 422; the
MCP tool raises from its own translation step. Both call `resolve` and
let their own layer shape the error.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import UUID


class GrantShape(StrEnum):
    """Which shape the caller actually supplied."""

    EXACT = "exact"
    CROSS_PRODUCT = "cross_product"


BOTH_SHAPES_MESSAGE = (
    "Give either 'grants' or the permitted_principal_ids/permitted_commands pair, not both."
)
NEITHER_SHAPE_MESSAGE = (
    "Provide 'grants', or both 'permitted_principal_ids' and 'permitted_commands'."
)


def resolve(
    *,
    grants: Mapping[UUID, Sequence[str]] | None,
    permitted_principal_ids: Sequence[UUID] | None,
    permitted_commands: Sequence[str] | None,
) -> GrantShape:
    """Name the supplied shape, or raise `ValueError` if it is ambiguous.

    Absent is `None`; EMPTY is a supplied shape meaning deny-all, so an
    empty mapping or an empty pair of lists resolves rather than raising.
    Distinguishing the two is the whole reason these are `| None` and not
    defaulted to empty containers.

    Both shapes at once is refused rather than resolved: the pair form
    grants every listed principal every listed command, so silently
    preferring one would let a caller receive far more, or far less, than
    the shape they had in mind. Neither is refused too, since a policy
    with no grant shape at all is a typo, not a request for deny-all,
    which either shape can state explicitly when it is meant.
    """
    pair_given = permitted_principal_ids is not None or permitted_commands is not None
    if grants is not None:
        if pair_given:
            raise ValueError(BOTH_SHAPES_MESSAGE)
        return GrantShape.EXACT
    if permitted_principal_ids is None or permitted_commands is None:
        raise ValueError(NEITHER_SHAPE_MESSAGE)
    return GrantShape.CROSS_PRODUCT


__all__ = [
    "BOTH_SHAPES_MESSAGE",
    "NEITHER_SHAPE_MESSAGE",
    "GrantShape",
    "resolve",
]
