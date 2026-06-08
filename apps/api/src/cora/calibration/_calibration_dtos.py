"""Shared Pydantic discriminated-union DTOs for the Calibration wire shape.

BC-level scaffolding consumed by the `append_calibration_revision` slice (the only
slice today that takes a polymorphic `CalibrationSource` as input).
Hoisted to the BC level so future slices that also take a source
(for example, 12g `promote_revision` if it carries a refinement source) can
reuse the same wire shape without reaching across sibling slices (the
cross-slice-independence architecture fitness function would otherwise
reject the import).

Naming: leading underscore on the filename marks this as BC-private
(not part of the public API surface); the contained class + function
names are public-within-the-BC so importing slices reference them
without the underscore (`SourceDTO`, `source_from_dto`, etc.).

Mirrors `cora.caution._caution_dtos` shape for the discriminated
target. Day-1 lock: three variants (Measured / Computed / Asserted)
matching the `CalibrationSource` discriminated union.

## Wire shape (REST + MCP)

```json
{"kind": "Measured", "procedure_id": "<uuid>"}
{"kind": "Computed", "dataset_id": "<uuid>"}
{"kind": "Asserted", "asserted_by": "<uuid>"}
```

The wire uses a tagged `{kind, ...}` envelope (Caution / Safety
precedent) rather than the exclusive-arc layout the event payload
uses. Each layer's wire shape is optimised for that layer:

  - Wire (REST/MCP): nested `{kind, id-field}` — readable for clients,
    matches Caution / Safety conventions.
  - Aggregate (in-memory): typed `MeasuredSource | ComputedSource |
    AssertedSource` discriminated union — type-safe pattern-matching.
  - Event payload + projection columns: three nullable id fields with
    exactly-one-non-null (exclusive-arc per Q5 lock, Postgres-
    community consensus).

`source_from_dto` and `dto_from_source` bridge wire <-> typed VO.
"""

from typing import Annotated, Literal, assert_never
from uuid import UUID

from pydantic import BaseModel, Field

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    CalibrationSource,
    ComputedSource,
    MeasuredSource,
)
from cora.shared.identity import ActorId


class SourceMeasuredDTO(BaseModel):
    """Wire shape for a Measured source (alignment Procedure)."""

    kind: Literal["Measured"]
    procedure_id: UUID = Field(
        ...,
        description="Alignment Procedure id whose run measured this value.",
    )


class SourceComputedDTO(BaseModel):
    """Wire shape for a Computed source (numerical analysis of a Dataset)."""

    kind: Literal["Computed"]
    dataset_id: UUID = Field(
        ...,
        description=(
            "Dataset id whose data this revision was computed from "
            "(for example, `tomopy.find_center_vo` on the projections)."
        ),
    )


class SourceAssertedDTO(BaseModel):
    """Wire shape for an Asserted source (operator-typed value)."""

    kind: Literal["Asserted"]
    asserted_by: UUID = Field(
        ...,
        description=(
            "Actor id who asserted the value. Usually equals the request "
            "envelope's principal_id but may differ when an operator "
            "asserts a value on behalf of another."
        ),
    )


SourceDTO = Annotated[
    SourceMeasuredDTO | SourceComputedDTO | SourceAssertedDTO,
    Field(discriminator="kind"),
]


def source_from_dto(
    dto: SourceMeasuredDTO | SourceComputedDTO | SourceAssertedDTO,
) -> CalibrationSource:
    """Decode a wire-shape SourceDTO into a typed CalibrationSource union arm."""
    match dto:
        case SourceMeasuredDTO(procedure_id=procedure_id):
            return MeasuredSource(procedure_id=procedure_id)
        case SourceComputedDTO(dataset_id=dataset_id):
            return ComputedSource(dataset_id=dataset_id)
        case SourceAssertedDTO(asserted_by=asserted_by):
            return AssertedSource(asserted_by=ActorId(asserted_by))
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(dto)


def dto_from_source(
    source: CalibrationSource,
) -> SourceMeasuredDTO | SourceComputedDTO | SourceAssertedDTO:
    """Encode a typed CalibrationSource into the wire-shape SourceDTO."""
    match source:
        case MeasuredSource(procedure_id=procedure_id):
            return SourceMeasuredDTO(kind="Measured", procedure_id=procedure_id)
        case ComputedSource(dataset_id=dataset_id):
            return SourceComputedDTO(kind="Computed", dataset_id=dataset_id)
        case AssertedSource(asserted_by=asserted_by):
            return SourceAssertedDTO(kind="Asserted", asserted_by=asserted_by)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(source)


__all__ = [
    "SourceAssertedDTO",
    "SourceComputedDTO",
    "SourceDTO",
    "SourceMeasuredDTO",
    "dto_from_source",
    "source_from_dto",
]
