"""HTTP route for the `define_assembly` slice.

POST /assemblies: define a new composition blueprint.

Re-uses the shared `PlacementBody`, `DrawingBody`, `TemplateSlotBody`,
and `TemplateWireBody` wire shapes; the route handler converts every
nested wire body to its domain VO before constructing the command.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment._drawing_body import DrawingBody
from cora.equipment._template_slot_body import TemplateSlotBody
from cora.equipment._template_wire_body import TemplateWireBody
from cora.equipment.aggregates.assembly import ASSEMBLY_NAME_MAX_LENGTH
from cora.equipment.features.define_assembly.command import DefineAssembly
from cora.equipment.features.define_assembly.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DefineAssemblyRequest(BaseModel):
    """Body for `POST /assemblies`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ASSEMBLY_NAME_MAX_LENGTH,
        description=(
            "Human-readable display name. Non-unique; the UUID is the "
            "storage identity and the content_hash is the structural "
            "fingerprint."
        ),
    )
    presents_as_family_id: UUID = Field(
        ...,
        description=(
            "FamilyId the instantiated Assembly stands in for at the "
            "Method.needed_families satisfaction boundary."
        ),
    )
    required_slots: list[TemplateSlotBody] = Field(
        default_factory=list[TemplateSlotBody],
        description=(
            "Slots that compose this Assembly. Each names a slot "
            "(canonical identity within the blueprint), the FamilyIds "
            "any filling Asset must include, the cardinality, and "
            "optional template defaults. Wire shape is a list; "
            "duplicates collapse when the route handler converts to "
            "the domain frozenset."
        ),
    )
    required_wires: list[TemplateWireBody] = Field(
        default_factory=list[TemplateWireBody],
        description=(
            "Slot-to-slot signal wires inside the Assembly, keyed by "
            "slot_name (NOT Asset UUID). Endpoints must reference "
            "slots declared in required_slots. Wire shape is a list; "
            "duplicates collapse when the route handler converts to "
            "the domain frozenset."
        ),
    )
    parameter_overrides_schema: dict[str, Any] | None = Field(
        None,
        description=(
            "Optional JSON Schema subset declaring the shape of "
            "parameter_overrides accepted at instantiation."
        ),
    )
    drawing: DrawingBody | None = Field(
        None,
        description=(
            "Optional engineering reference for the assembly itself. "
            "Excluded from the content_hash."
        ),
    )
    version: str | None = Field(
        None,
        description=(
            "Operator-curated free-form version label (no SemVer "
            "enforcement). Excluded from the content_hash."
        ),
    )


class DefineAssemblyResponse(BaseModel):
    """Response body for `POST /assemblies`."""

    assembly_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.define_assembly
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assemblies",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineAssemblyResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name or "
                "slot_name, non-enum cardinality, malformed wire spec, "
                "wire references an unknown slot, invalid "
                "parameter_overrides_schema subset, or invalid Placement "
                "/ Drawing nested VO."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "A referenced FamilyId (presents_as_family_id or any "
                "slot's required_families member) does not resolve to "
                "a defined Family."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Stream collision: the generated UUID already has an "
                "AssemblyDefined event (essentially impossible with "
                "UUIDv7 ids; defensive guard)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR "
                "Idempotency-Key was reused with a different request body."
            ),
        },
    },
    summary="Define a new Assembly composition blueprint",
)
async def post_assemblies(
    body: DefineAssemblyRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied key for idempotent retry: "
                "replaying the same key returns the original "
                "assembly_id without creating a new Assembly."
            ),
        ),
    ] = None,
) -> DefineAssemblyResponse:
    assembly_id = await handler(
        DefineAssembly(
            name=body.name,
            presents_as_family_id=body.presents_as_family_id,
            required_slots=frozenset(slot.to_domain() for slot in body.required_slots),
            required_wires=frozenset(wire.to_domain() for wire in body.required_wires),
            parameter_overrides_schema=body.parameter_overrides_schema,
            drawing=body.drawing.to_domain() if body.drawing is not None else None,
            version=body.version,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineAssemblyResponse(assembly_id=assembly_id)
