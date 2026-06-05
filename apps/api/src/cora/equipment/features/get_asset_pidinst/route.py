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

FastAPI cannot generate `response_model` from the frozen slice-C
`PidinstRecord` dataclass directly: the OpenAPI schema generator
requires a Pydantic-typed mirror. The mirror lives here per the
`AssetIntegrationViewResponse` precedent at
`features/get_asset_integration_view/route.py:63-87`. `_record_to_response`
walks the slice-C tree into the Pydantic shape; tuple-of-dataclass
fields serialize as lists per the OpenAPI norm.

Slice E.1 of project_asset_persistent_id_design.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel

from cora.equipment._pidinst_types import PidinstRecord
from cora.equipment.features.get_asset_pidinst.handler import Handler
from cora.equipment.features.get_asset_pidinst.query import GetAssetPidinst
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class PidinstIdentifierDTO(BaseModel):
    """PIDINST v1.0 Property 1: persistent identifier of the instrument."""

    value: str
    scheme: str


class OwnerDTO(BaseModel):
    """PIDINST v1.0 Property 5: a body owning or curating the instrument."""

    name: str
    contact: str | None = None
    identifier: str | None = None
    identifier_type: str | None = None


class ManufacturerDTO(BaseModel):
    """PIDINST v1.0 Property 6: the body manufacturing the instrument."""

    name: str
    identifier: str | None = None
    identifier_type: str | None = None


class PidinstModelDTO(BaseModel):
    """PIDINST v1.0 Property 7: the model identification of the instrument."""

    name: str
    identifier: str
    identifier_type: str


class InstrumentTypeDTO(BaseModel):
    """PIDINST v1.0 Property 9: a typology category for the instrument."""

    name: str
    identifier: str | None = None
    identifier_type: str


class MeasuredVariableDTO(BaseModel):
    """PIDINST v1.0 Property 10: a physical quantity the instrument measures."""

    name: str


class PidinstDateDTO(BaseModel):
    """PIDINST v1.0 Property 11: a date marker on the instrument lifecycle."""

    value: str
    date_type: str


class RelatedIdentifierDTO(BaseModel):
    """PIDINST v1.0 Property 12: a related identifier (parent asset, etc.)."""

    value: str
    identifier_type: str
    relation_type: str


class PidinstAlternateIdentifierDTO(BaseModel):
    """PIDINST v1.0 Property 13: an alternate identifier under a known scheme."""

    value: str
    kind: str
    name: str | None = None


class MeasurementTechniqueDTO(BaseModel):
    """PIDINST v1.0 Property 14: a measurement technique applied by the instrument."""

    name: str


class PidinstRecordResponse(BaseModel):
    """Read-side DTO mirroring the slice-C `PidinstRecord` dataclass.

    Pydantic mirror so FastAPI can generate an OpenAPI schema. Decouples
    the wire format from the slice-C `PidinstRecord` so the two can
    evolve independently. Field shapes verbatim from the slice-C tree.
    """

    identifier: PidinstIdentifierDTO
    schema_version: str
    landing_page: str
    name: str
    publisher: str
    publication_year: int | None
    owners: list[OwnerDTO]
    manufacturers: list[ManufacturerDTO]
    model: PidinstModelDTO | None
    description: str | None
    instrument_types: list[InstrumentTypeDTO]
    measured_variables: list[MeasuredVariableDTO]
    dates: list[PidinstDateDTO]
    related_identifiers: list[RelatedIdentifierDTO]
    alternate_identifiers: list[PidinstAlternateIdentifierDTO]
    measurement_techniques: list[MeasurementTechniqueDTO]


def _record_to_response(record: PidinstRecord) -> PidinstRecordResponse:
    return PidinstRecordResponse(
        identifier=PidinstIdentifierDTO(
            value=record.identifier.value,
            scheme=record.identifier.scheme.value,
        ),
        schema_version=record.schema_version.value,
        landing_page=record.landing_page,
        name=record.name,
        publisher=record.publisher,
        publication_year=record.publication_year,
        owners=[
            OwnerDTO(
                name=owner.name,
                contact=owner.contact,
                identifier=owner.identifier,
                identifier_type=owner.identifier_type,
            )
            for owner in record.owners
        ],
        manufacturers=[
            ManufacturerDTO(
                name=manufacturer.name,
                identifier=manufacturer.identifier,
                identifier_type=(
                    manufacturer.identifier_type.value
                    if manufacturer.identifier_type is not None
                    else None
                ),
            )
            for manufacturer in record.manufacturers
        ],
        model=(
            PidinstModelDTO(
                name=record.model.name,
                identifier=record.model.identifier,
                identifier_type=record.model.identifier_type,
            )
            if record.model is not None
            else None
        ),
        description=record.description,
        instrument_types=[
            InstrumentTypeDTO(
                name=instrument_type.name,
                identifier=instrument_type.identifier,
                identifier_type=instrument_type.identifier_type,
            )
            for instrument_type in record.instrument_types
        ],
        measured_variables=[
            MeasuredVariableDTO(name=variable.name) for variable in record.measured_variables
        ],
        dates=[
            PidinstDateDTO(value=pidinst_date.value, date_type=pidinst_date.date_type.value)
            for pidinst_date in record.dates
        ],
        related_identifiers=[
            RelatedIdentifierDTO(
                value=related_identifier.value,
                identifier_type=related_identifier.identifier_type,
                relation_type=related_identifier.relation_type.value,
            )
            for related_identifier in record.related_identifiers
        ],
        alternate_identifiers=[
            PidinstAlternateIdentifierDTO(
                value=alternate_identifier.value,
                kind=alternate_identifier.kind.value,
                name=alternate_identifier.name,
            )
            for alternate_identifier in record.alternate_identifiers
        ],
        measurement_techniques=[
            MeasurementTechniqueDTO(name=technique.name)
            for technique in record.measurement_techniques
        ],
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
    return _record_to_response(record)
