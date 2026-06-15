"""HTTP route for the `version_assembly` slice.

POST /assemblies/{assembly_id}/versions: publish a new revision
snapshot of an existing Assembly.

Replace-on-version per the design memo: the body carries the FULL
canonical structural subset (slots, wires, schema, drawing, version
label, presents_as), NOT a diff. The route reuses the
shared TemplateSlotBody / TemplateWireBody / DrawingBody wire
shapes and the same list-to-frozenset conversion as define_assembly.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment._bodies import (
    DrawingBody,
    SubAssemblyLinkBody,
    TemplateSlotBody,
    TemplateWireBody,
)
from cora.equipment.aggregates.assembly import ASSEMBLY_NAME_MAX_LENGTH
from cora.equipment.features.version_assembly.command import VersionAssembly
from cora.equipment.features.version_assembly.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class VersionAssemblyRequest(BaseModel):
    """Body for `POST /assemblies/{assembly_id}/versions`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ASSEMBLY_NAME_MAX_LENGTH,
        description=(
            "Display name for this revision snapshot. May change across revisions; non-unique."
        ),
    )
    presents_as: list[UUID] = Field(
        default_factory=list[UUID],
        description=(
            "Global Role contract ids this revision advertises; replaced "
            "wholesale on version. What a Method role binding targets."
        ),
    )
    required_slots: list[TemplateSlotBody] = Field(
        default_factory=list[TemplateSlotBody],
        description=(
            "Full slot set for this revision (replace-on-version). "
            "Wire shape is a list; duplicates collapse when the "
            "route handler converts to the domain frozenset."
        ),
    )
    required_wires: list[TemplateWireBody] = Field(
        default_factory=list[TemplateWireBody],
        description=(
            "Full wire set for this revision (replace-on-version). "
            "Endpoints must reference slots declared in required_slots."
        ),
    )
    required_sub_assemblies: list[SubAssemblyLinkBody] = Field(
        default_factory=list[SubAssemblyLinkBody],
        description=(
            "Full sub-assembly-link set for this revision "
            "(replace-on-version). Each pins a child Assembly's "
            "content_hash at a named position; a stale pin is rejected "
            "so re-adopting a child revision is deliberate."
        ),
    )
    parameter_overrides_schema: dict[str, Any] | None = Field(
        None,
        description=(
            "Optional JSON Schema subset declaring the shape of "
            "parameter_overrides accepted at instantiation. Excluded "
            "if the revision keeps the previous schema unchanged."
        ),
    )
    drawing: DrawingBody | None = Field(
        None,
        description=(
            "Optional engineering reference for this revision. Excluded from the content_hash."
        ),
    )
    version: str | None = Field(
        None,
        description=(
            "Operator-curated free-form version label (no SemVer "
            "enforcement). Excluded from the content_hash."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.version_assembly
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assemblies/{assembly_id}/versions",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name or "
                "slot_name, non-enum cardinality, malformed wire spec, "
                "wire references an unknown slot, or invalid "
                "parameter_overrides_schema subset."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Assembly with the given assembly_id does not exist, "
                "OR a referenced RoleId in presents_as does not resolve "
                "to a defined Role, OR a slot's required_family_ids "
                "member does not resolve to a defined Family."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Assembly is in a status that cannot be versioned "
                "(Deprecated is terminal; new revisions must fork "
                "via POST /assemblies with a fresh id)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Publish a new revision snapshot of an existing Assembly",
)
async def post_assembly_version(
    assembly_id: Annotated[
        UUID,
        Path(description="The target Assembly's UUID."),
    ],
    body: VersionAssemblyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VersionAssembly(
            assembly_id=assembly_id,
            name=body.name,
            presents_as=frozenset(body.presents_as),
            required_slots=frozenset(slot.to_domain() for slot in body.required_slots),
            required_wires=frozenset(wire.to_domain() for wire in body.required_wires),
            required_sub_assemblies=frozenset(
                ref.to_domain() for ref in body.required_sub_assemblies
            ),
            parameter_overrides_schema=body.parameter_overrides_schema,
            drawing=body.drawing.to_domain() if body.drawing is not None else None,
            version=body.version,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
