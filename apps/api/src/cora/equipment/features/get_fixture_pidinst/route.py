"""HTTP route for the `get_fixture_pidinst` query slice.

`GET /fixtures/{fixture_id}/pidinst` returns 200 + `PidinstRecordResponse`
on hit. Errors propagate to the BC's exception-handler tuples in
`equipment/routes.py` per L19:

  - handler returned `None`                       -> 404 (route raises)
  - `FixtureOwnerStateNotAvailableError`          -> 409
  - `FixtureManufacturerStateNotAvailableError`   -> 409
  - `FixtureLandingPageMissingError`              -> 422
  - `FixtureNameMissingError`                     -> 422
  - `PidinstRecordInvariantError`                 -> 500 (kernel backstop)

FastAPI cannot generate `response_model` from the frozen slice-C
`PidinstRecord` dataclass directly: the OpenAPI schema generator
requires a Pydantic-typed mirror. The mirror reuses the slice-E.1
`PidinstRecordResponse` shape; the Fixture-tier serializer produces
the same `PidinstRecord` shape, so the DTO is reused unchanged.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment._pidinst import (
    PidinstRecordResponse,
    record_to_response,
    to_fixture_pidinst_record,
)
from cora.equipment.aggregates.fixture import FixtureNotFoundError
from cora.equipment.features.get_fixture_pidinst.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_fixture_pidinst
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/fixtures/{fixture_id}/pidinst",
    status_code=status.HTTP_200_OK,
    response_model=PidinstRecordResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No fixture exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Fixture state is missing a mandatory PIDINST source: "
                "no bound Asset carries any owners "
                "(FixtureOwnerStateNotAvailableError), or no bound Asset "
                "carries any manufacturer "
                "(FixtureManufacturerStateNotAvailableError)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "View preparation produced an empty landing page URL "
                "or fixture name; or the path parameter failed schema "
                "validation."
            ),
        },
    },
    summary="Get the PIDINST v1.0 record for a fixture",
)
async def get_fixture_pidinst(
    request: Request,
    fixture_id: Annotated[UUID, Path(description="Target fixture's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> PidinstRecordResponse:
    view = await handler(
        fixture_id,
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise FixtureNotFoundError(fixture_id)
    settings = request.app.state.settings
    landing_page_url = _fixture_landing_page_url(settings.landing_page_template, fixture_id)
    record = to_fixture_pidinst_record(
        view,
        landing_page_url=landing_page_url,
        publisher=settings.facility_publisher,
    )
    return record_to_response(record)


def _fixture_landing_page_url(asset_template: str, fixture_id: UUID) -> str:
    """Derive a Fixture-tier landing-page URL from the Asset-tier template.

    Reuses the Asset BC's `landing_page_template` Setting and swaps
    the `/assets/` segment + `{asset_id}` placeholder for their
    Fixture-tier equivalents. A future
    `fixture_pidinst_landing_page_template` Setting is deferred behind
    D-FIX-LANDING-PAGE so this slice ships without a Settings extension.
    """
    return asset_template.replace("{asset_id}", str(fixture_id)).replace("/assets/", "/fixtures/")
