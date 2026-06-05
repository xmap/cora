"""Pydantic mirror of the PIDINST v1.0 record + conversion helper.

The aggregate kernel owns the slice-C `PidinstRecord` frozen dataclass
(in `_pidinst_types.py`). FastAPI's OpenAPI schema generator requires a
Pydantic-typed mirror to render `response_model`, so this module hosts
that mirror plus the `_record_to_response` helper that walks the
slice-C tree into Pydantic.

Lives at BC root rather than inside any one feature slice because both
the Asset-tier (`get_asset_pidinst`) and Fixture-tier
(`get_fixture_pidinst`) read routes return the same record shape. Per
the BC-flat-root layout convention private to this BC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from cora.equipment._pidinst_types import PidinstRecord


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


def record_to_response(record: PidinstRecord) -> PidinstRecordResponse:
    """Walk the slice-C `PidinstRecord` tree into the Pydantic mirror."""
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
