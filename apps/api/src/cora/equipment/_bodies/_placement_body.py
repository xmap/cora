"""Shared Pydantic wire-format mirror of the `Placement` value object.

Hoisted at the third importer (`register_frame.route`,
`register_frame.tool`, `update_frame_placement.route`, `update_frame_placement.tool`),
satisfying the rule-of-three precedent that landed
`make_asset_update_handler` and `validate_bounded_text`.

`Placement` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates._placement`); this body is purely the
wire shape that Pydantic parses, with one `to_domain()` method that
constructs the domain VO (and may raise `InvalidPlacementError` on
domain-rule violations like negative tolerance, mapped to 400 by
the BC's exception handler).

Pydantic enforces `ge=0` on every tolerance field so REST clients
hit a 422 before the request even reaches the handler. MCP clients
parse through the same `PlacementBody`, so the validation runs
identically on the MCP path; the only asymmetry is that the MCP
tool's surface doesn't carry an explicit `responses={422: ...}`
schema annotation (FastMCP has no equivalent declaration today).

When a future `Mount.placement` field is added (alongside the Mount
aggregate), the Mount slices import this same wire body.
Mirrors the `PortBody` pattern
that landed once Subject + Equipment both needed a Pydantic mirror
for `AssetPort`.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)


class PlacementBody(BaseModel):
    """Wire format for a Placement value object.

    Mirrors the domain `Placement` dataclass field-for-field. Field
    semantics, units, and tolerance rules live with the dataclass
    in `cora.equipment.aggregates._placement`; this body is purely
    the wire shape that Pydantic parses.

    Domain validation (negative tolerance rejection) happens during
    the dataclass construction in `to_domain`, not here, so the
    route surfaces `InvalidPlacementError` -> 400 through the BC's
    exception handler.
    """

    x: float = Field(..., description="Translation along world x (mm in SI_mm_rad).")
    y: float = Field(..., description="Translation along world y.")
    z: float = Field(..., description="Translation along beam direction z.")
    rx: float = Field(..., description="Rotation around x (rad in SI_mm_rad).")
    ry: float = Field(..., description="Rotation around y.")
    rz: float = Field(..., description="Rotation around z.")
    parent_frame_id: UUID = Field(
        ...,
        description=(
            "The Frame whose origin these coordinates are measured "
            "against. For a child Frame's placement, "
            "this MUST equal the owning Frame's parent_id."
        ),
    )
    reference_surface: ReferenceSurface = Field(
        ...,
        description=(
            "Which physical feature of the part the position values "
            "are measured FROM. One of: ThermalFace, OpticCenter, "
            "ShieldingFace, MountingFace."
        ),
    )
    tol_x: float = Field(..., ge=0, description="Bilateral plus-or-minus tolerance on x.")
    tol_y: float = Field(..., ge=0, description="Bilateral plus-or-minus tolerance on y.")
    tol_z: float = Field(..., ge=0, description="Bilateral plus-or-minus tolerance on z.")
    tol_rx: float = Field(..., ge=0, description="Bilateral plus-or-minus tolerance on rx.")
    tol_ry: float = Field(..., ge=0, description="Bilateral plus-or-minus tolerance on ry.")
    tol_rz: float = Field(..., ge=0, description="Bilateral plus-or-minus tolerance on rz.")
    units: UnitSystem = Field(
        UnitSystem.SI_MM_RAD,
        description=(
            "Unit system. v1 ships one value (SI_mm_rad): mm for translation, rad for rotation."
        ),
    )

    def to_domain(self) -> Placement:
        """Convert this wire body to the domain Placement dataclass."""
        return Placement(
            x=self.x,
            y=self.y,
            z=self.z,
            rx=self.rx,
            ry=self.ry,
            rz=self.rz,
            parent_frame_id=self.parent_frame_id,
            reference_surface=self.reference_surface,
            tol_x=self.tol_x,
            tol_y=self.tol_y,
            tol_z=self.tol_z,
            tol_rx=self.tol_rx,
            tol_ry=self.tol_ry,
            tol_rz=self.tol_rz,
            units=self.units,
        )


__all__ = ["PlacementBody"]
