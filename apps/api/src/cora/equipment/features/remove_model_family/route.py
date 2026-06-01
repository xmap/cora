"""HTTP route for the `remove_model_family` slice.

Targeted-mutation endpoint at `DELETE /models/{model_id}/families/{family_id}`.
Both ids travel as path parameters; there is no request body. 204 No
Content on success. Status (`Defined` or `Versioned`) is preserved;
`Deprecated` rejects the mutation. No `Idempotency-Key` (update-style,
mirrors `add_model_family`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment.features.remove_model_family.command import RemoveModelFamily
from cora.equipment.features.remove_model_family.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.remove_model_family
    return handler


router = APIRouter(tags=["equipment"])


@router.delete(
    "/models/{model_id}/families/{family_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
                "Model is in `Deprecated` status (mutation requires "
                "`Defined` or `Versioned`), OR the family_id is not in "
                "the Model's declared_families set, OR a concurrent "
                "write to the same model stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Remove a Family from an existing Model's declared_families set",
)
async def delete_models_family(
    model_id: Annotated[UUID, Path(description="Target model's id.")],
    family_id: Annotated[
        UUID, Path(description="Family id to remove from the Model.declared_families set.")
    ],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveModelFamily(model_id=model_id, family_id=family_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
