"""HTTP route for the `add_model_family` slice.

Targeted-mutation endpoint at `POST /models/{model_id}/families`. Body
carries a single `family_id` that is added to the Model's
`declared_families` set. 204 No Content on success. Status (`Defined`
or `Versioned`) is preserved; `Deprecated` rejects the mutation. No
`Idempotency-Key` (update-style, mirrors `version_model`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.add_model_family.command import AddModelFamily
from cora.equipment.features.add_model_family.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddModelFamilyRequest(BaseModel):
    """Body for `POST /models/{model_id}/families`."""

    family_id: UUID = Field(
        ...,
        description="Family id to add to the Model.declared_families set.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_model_family
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/models/{model_id}/families",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No model exists with the given id, OR the supplied "
                "family_id does not resolve to a registered Family."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Model is in `Deprecated` status (mutation requires "
                "`Defined` or `Versioned`), OR the family_id is already "
                "in the Model's declared_families set, OR a concurrent "
                "write to the same model stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Add a Family to an existing Model's declared_families set",
)
async def post_models_add_family(
    model_id: Annotated[UUID, Path(description="Target model's id.")],
    body: AddModelFamilyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddModelFamily(model_id=model_id, family_id=body.family_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
