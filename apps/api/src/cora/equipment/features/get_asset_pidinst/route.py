"""HTTP route for the `get_asset_pidinst` query slice.

`GET /assets/{asset_id}/pidinst` returns 200 + `PidinstRecordResponse`
on hit. Errors propagate to the BC's exception-handler tuples in
`equipment/routes.py` per L8 + L9:

  - `AssetNotFoundError`                  -> 404
  - `OwnerStateNotAvailableError`         -> 409
  - `ManufacturerStateNotAvailableError`  -> 409
  - `LandingPageMissingError`             -> 422
  - `AssetNameMissingError`               -> 422
  - `PidinstRecordInvariantError`         -> 500 (intentional per L11 of
    project_asset_persistent_id_design: server-bug backstop;
    FastAPI default 500 is the locked policy. The query handler
    logs the violation at error level before re-raising so the
    bare 500 path still leaves a structured trail.)

The Pydantic mirror `PidinstRecordResponse` plus its `record_to_response`
walker live at the BC root in `_pidinst_response.py` so both
Asset-tier and Fixture-tier read routes can share the same wire shape
without crossing slice boundaries.

Slice E.1 of project_asset_persistent_id_design.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment._pidinst_response import PidinstRecordResponse, record_to_response
from cora.equipment.features.get_asset_pidinst.handler import Handler
from cora.equipment.features.get_asset_pidinst.query import GetAssetPidinst
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_asset_pidinst
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/assets/{asset_id}/pidinst",
    status_code=status.HTTP_200_OK,
    response_model=PidinstRecordResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset state is missing a mandatory PIDINST source: at least one Owner "
                "(PIDINST Property 5) or a bound Model carrying the Manufacturer (Property 6)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "View preparation produced an empty landing page URL or asset name; "
                "or the path parameter failed schema validation."
            ),
        },
    },
    summary="Get the PIDINST v1.0 record for an asset",
)
async def get_asset_pidinst(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> PidinstRecordResponse:
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return record_to_response(record)
