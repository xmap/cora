"""HTTP route for the `version_model` slice.

Action endpoint at `POST /models/{model_id}/versions`. Body carries
the full replacement declaration (name, manufacturer, part_number,
declared_families, version_tag). 204 No Content on success. A new
version IS a new declaration, so the supplied fields REPLACE the
prior values wholesale.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
    MODEL_VERSION_TAG_MAX_LENGTH,
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features.version_model.command import VersionModel
from cora.equipment.features.version_model.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ManufacturerBody(BaseModel):
    """Pydantic mirror of the Manufacturer VO for the request body.

    `identifier` and `identifier_type` are both optional but must be
    supplied together or both omitted (the pairing invariant is
    enforced at the VO constructor; a bare identifier with no scheme
    cannot be resolved).
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=MANUFACTURER_NAME_MAX_LENGTH,
        description="Display name of the manufacturer.",
    )
    identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=MANUFACTURER_IDENTIFIER_MAX_LENGTH,
        description=(
            "Optional opaque identifier value. If supplied, `identifier_type` "
            "is required (and vice versa)."
        ),
    )
    identifier_type: ManufacturerIdentifierType | None = Field(
        default=None,
        description="Closed scheme for the optional manufacturer identifier.",
    )

    def to_vo(self) -> Manufacturer:
        identifier = (
            ManufacturerIdentifier(self.identifier) if self.identifier is not None else None
        )
        return Manufacturer(
            name=ManufacturerName(self.name),
            identifier=identifier,
            identifier_type=self.identifier_type,
        )


class VersionModelRequest(BaseModel):
    """Body for `POST /models/{model_id}/versions`.

    A new version IS a new declaration: every field REPLACES the prior
    value wholesale (no diff/merge semantics). `version_tag` is
    REQUIRED here, unlike `define_model` where it is optional.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_NAME_MAX_LENGTH,
        description="Replacement display name for the Model at this version.",
    )
    manufacturer: ManufacturerBody = Field(
        ...,
        description="Replacement vendor identity (name plus optional ROR/GRID/ISNI identifier).",
    )
    part_number: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_PART_NUMBER_MAX_LENGTH,
        description=(
            "Replacement vendor SKU; case-sensitive (RV120CCHL and rv120cchl "
            "are different Newport entries)."
        ),
    )
    declared_families: list[UUID] = Field(
        ...,
        min_length=1,
        description=(
            "Replacement Family ids the catalog entry satisfies at this "
            "version. At least one required; deduplicated server-side."
        ),
    )
    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'rev-B', '2026-Q3'). Free text; institution-specific."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.version_model
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/models/{model_id}/versions",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (for example whitespace-only "
                "name, whitespace-only part_number, whitespace-only "
                "version_tag, or empty declared_families)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No model exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Model is in `Deprecated` status (version requires "
                "`Defined` or `Versioned`), OR a concurrent write to the "
                "same model stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Issue a new version declaration for an existing Model",
)
async def post_models_versions(
    model_id: Annotated[UUID, Path(description="Target model's id.")],
    body: VersionModelRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VersionModel(
            model_id=model_id,
            name=body.name,
            manufacturer=body.manufacturer.to_vo(),
            part_number=body.part_number,
            declared_families=frozenset(body.declared_families),
            version_tag=body.version_tag,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
