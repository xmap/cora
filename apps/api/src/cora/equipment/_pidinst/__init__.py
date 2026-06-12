"""PIDINST v1.0 integration subpackage for the Equipment BC.

Carved from the BC root once the private-module count crossed the ~10-file
threshold (see docs/reference/layout.md). Groups the cohesive PIDINST
subsystem: the intermediate type tree (`_types`), the pure serializer
(`_serializer`), and the FastAPI response DTOs (`_response`).

Re-exports the public surface so consumers import from the package
(`from cora.equipment._pidinst import PidinstRecord`) rather than reaching
into the private submodules.
"""

from ._response import PidinstRecordResponse, record_to_response
from ._serializer import (
    AssetNameMissingError,
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
    to_fixture_pidinst_record,
    to_pidinst_record,
)
from ._types import (
    AssetPidinstView,
    DateType,
    FixtureComponentRef,
    FixturePidinstView,
    InstrumentType,
    Manufacturer,
    MeasuredVariable,
    MeasurementTechnique,
    ModelPidinstView,
    Owner,
    PidinstAlternateIdentifier,
    PidinstDate,
    PidinstIdentifier,
    PidinstIdentifierType,
    PidinstModel,
    PidinstRecord,
    PidinstRelationType,
    RelatedIdentifier,
    SchemaVersion,
)

__all__ = [
    "AssetNameMissingError",
    "AssetPidinstView",
    "DateType",
    "FixtureComponentRef",
    "FixturePidinstView",
    "InstrumentType",
    "LandingPageMissingError",
    "Manufacturer",
    "ManufacturerStateNotAvailableError",
    "MeasuredVariable",
    "MeasurementTechnique",
    "ModelPidinstView",
    "Owner",
    "OwnerStateNotAvailableError",
    "PidinstAlternateIdentifier",
    "PidinstDate",
    "PidinstIdentifier",
    "PidinstIdentifierType",
    "PidinstModel",
    "PidinstRecord",
    "PidinstRecordResponse",
    "PidinstRelationType",
    "RelatedIdentifier",
    "SchemaVersion",
    "record_to_response",
    "to_fixture_pidinst_record",
    "to_pidinst_record",
]
