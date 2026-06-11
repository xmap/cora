"""Shared Pydantic wire-format mirror of the `RoleRequirement` VO.

Hoisted at the first importer (`add_method_required_role`); the
remove-side slice carries only the role_name and does not need this
body. The naming follows the precedent set by `_asset_owner_body`
(AssetOwner), `_drawing_body` (Drawing), `_placement_body`
(Placement), and `_alternate_identifier_body` (AlternateIdentifier).

`RoleRequirement` is a frozen dataclass at the domain layer
(`cora.recipe.aggregates.method.state.RoleRequirement`); this body
is purely the wire shape Pydantic parses, with a `to_domain()` method
that constructs the domain VO. The nested `PortRequirementBody` is
the wire mirror for `PortRequirement`. The trim/length checks
re-execute inside the domain VO's `__post_init__`; the Pydantic
constraints here are the first line of defense at the HTTP/MCP
boundary so malformed requests reject early as 422 rather than
slipping into the decider as 400.
"""

from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cora.equipment.aggregates.asset import PortDirection
from cora.recipe.aggregates.method import (
    ROLE_NAME_MAX_LENGTH,
    ROLE_PORT_NAME_MAX_LENGTH,
    ROLE_PORT_SIGNAL_TYPE_MAX_LENGTH,
    PortRequirement,
    RoleName,
    RoleRequirement,
)


class PortRequirementBody(BaseModel):
    """Wire format for a `PortRequirement` value object."""

    port_name: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_PORT_NAME_MAX_LENGTH,
        description=(
            "Exact (case-sensitive, after trimming) port name the "
            "bound Asset must expose on its `ports` set. Glob/regex "
            "matching is deferred per the design memo's "
            "open-questions resolution."
        ),
    )
    direction: PortDirection = Field(
        ...,
        description=(
            "Required port direction (Input or Output), matching the "
            "Asset.ports `direction` field byte-for-byte."
        ),
    )
    signal_type: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_PORT_SIGNAL_TYPE_MAX_LENGTH,
        description=(
            "Required port signal_type (TTL, LVDS, Encoder, Network, "
            "Sync, etc.). Free text 1-50 chars, matching AssetPort's "
            "signal_type shape exactly."
        ),
    )

    def to_domain(self) -> PortRequirement:
        return PortRequirement(
            port_name=self.port_name,
            direction=self.direction,
            signal_type=self.signal_type,
        )


class RoleRequirementBody(BaseModel):
    """Wire format for a `RoleRequirement` value object.

    Layer 3 sub-slice 3D widens this body with `role_kind` for the
    federation-portable binding path. Exactly one of `role_kind` /
    `family_id` must be set per the memo Lock 5 XOR invariant; the
    `_xor_role_kind_and_family_id` model_validator catches both-set
    + neither-set at the wire layer (422) before the domain VO
    raises its sister error (400).
    """

    role_name: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_NAME_MAX_LENGTH,
        description=(
            "Method-local positional role label (for example, "
            "'detector', 'sample_monitor', 'axis'). Uniqueness is "
            "scoped to the Method; cross-Method consistency is an "
            "operator convention, not a kernel invariant."
        ),
    )
    role_kind: UUID | None = Field(
        default=None,
        description=(
            "Global Role contract id this slot targets (Layer 3 "
            "sub-slice 3D; federation-portable path). Existence is "
            "verified at the handler edge against the Role projection. "
            "Exactly one of `role_kind` / `family_id` must be set."
        ),
    )
    family_id: UUID | None = Field(
        default=None,
        description=(
            "Anatomical-pinning escape hatch (slice-1 path). When "
            "set, the bound Asset must carry this Family id at Plan "
            "binding time. Eventual-consistency: existence is not "
            "verified at decide time. Exactly one of `role_kind` / "
            "`family_id` must be set."
        ),
    )
    required_ports: list[PortRequirementBody] = Field(
        default_factory=list[PortRequirementBody],
        description=(
            "List of ports the bound Asset must expose for this "
            "role. Empty means the role has no port contract (pure "
            "Asset binding); the Wire-role-endpoint invariant only "
            "applies when this list is non-empty. Wire-side list, "
            "deduplicated to a frozenset at the domain VO."
        ),
    )
    optional: bool = Field(
        default=False,
        description=(
            "If True, Plan binding may omit this role without "
            "triggering PlanRoleNotBoundError. Defaults to required."
        ),
    )

    @model_validator(mode="after")
    def _xor_role_kind_and_family_id(self) -> Self:
        """Wire-layer XOR check (422 before the domain VO raises 400)."""
        has_role_kind = self.role_kind is not None
        has_family_id = self.family_id is not None
        if has_role_kind == has_family_id:
            msg = (
                "RoleRequirement must carry EXACTLY one of role_kind / "
                "family_id (XOR invariant per role-aggregate-design "
                f"Lock 5; got role_kind={self.role_kind!r}, "
                f"family_id={self.family_id!r})"
            )
            raise ValueError(msg)
        return self

    def to_domain(self) -> RoleRequirement:
        return RoleRequirement(
            role_name=RoleName(self.role_name),
            role_kind=self.role_kind,
            family_id=self.family_id,
            required_ports=frozenset(p.to_domain() for p in self.required_ports),
            optional=self.optional,
        )
