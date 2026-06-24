"""Measurement: the substrate-neutral value-plus-metadata produced by a conducted act.

A `Measurement` is the typed value a conducted act yields, whatever edge
runtime produced it: a control read (ControlPort), a compute job output
(ComputePort), or a transfer observation (TransferPort). The value-types
here are domain-owned and shared across all three ports; concrete
adapters serve as ACLs translating substrate-native shapes (EPICS V4 NT
structures, Tango `DeviceAttribute`, OPC UA `DataValue`, a compute job's
result record, a transfer manifest) into this CORA-owned vocabulary.

## Domain vocabulary (substrate-neutral)

- **`Measurement`** is the typed value-plus-metadata a consumer sees.
  Fields are domain-owned: `value`, `kind: MeasurementKind`,
  `quality: Quality`, `produced_at: datetime`, `quality_detail: str`,
  plus the substrate-neutral `name` and `units` annotations.
- **`MeasurementKind`** is a closed 5-value enum (`Scalar | Array |
  Image | Categorical | Tabular`). Maps to EPICS V4 NT kinds + Tango
  `AttrDataFormat` + OPC UA Variant types via adapter-side ACL, and
  describes compute / transfer outputs by the same shape vocabulary.
- **`Quality`** is the closed 3-value enum (`Good | Uncertain | Bad`)
  matching OPC UA's spec-defined high-level severity grouping and the
  NAMUR / ISA-95 vocabulary. Adapters translate substrate-native
  quality enums INTO this domain enum; substrate sub-codes (EPICS
  `alarm_status`, Tango string detail, OPC UA's ~240 named sub-codes)
  land in `Measurement.quality_detail` as opaque forensic breadcrumbs.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

MeasurementKind = Literal["Scalar", "Array", "Image", "Categorical", "Tabular"]
"""Closed 5-value discriminator for `Measurement.value` shape.

- `Scalar`: a single typed value (int / float / bool / str).
- `Array`: a 1-D sequence of scalars (tuple at the port boundary).
- `Image`: a 2-D pixel grid (NTNDArray / Tango IMAGE / OPC UA image
  variants); shape and dtype carried inside `value`.
- `Categorical`: a string label from a closed substrate-defined set
  (EPICS NTEnum / Tango DevEnum or DevState / OPC UA enum).
- `Tabular`: column-oriented record (NTTable / OPC UA table / Tango
  multi-attribute bundle).

Adapter ACLs translate substrate-specific type taxonomies INTO this
enum. Extensible by tag addition when a future substrate justifies a
new shape (e.g., OPC UA `LocalizedText` may justify a new tag).
"""


Quality = Literal["Good", "Uncertain", "Bad"]
"""Closed 3-value quality enum matching OPC UA's spec-defined severity
grouping and the NAMUR / ISA-95 vocabulary.

Per the OPC UA sanity check in
[[project_control_port_generalization_research]], `StatusCode`'s top
2 bits are exactly this trichotomy:
`Good = 0b00 | Uncertain = 0b01 | Bad = 0b10`. EPICS CA's 4-value
severity collapses (`NONE -> Good`, `MINOR | MAJOR | INVALID -> Bad`).
Tango's 5-value `AttrQuality` collapses (`VALID -> Good`,
`WARNING | CHANGING -> Uncertain`, `ALARM | INVALID -> Bad`).

Substrate-specific forensic detail (EPICS `alarm_status`, Tango
string detail, OPC UA's ~240 named sub-codes such as
`BadCommunicationError` / `UncertainDataSubNormal`) lands in
`Measurement.quality_detail` as an opaque string; the closed enum stays
tight.
"""


@dataclass(frozen=True)
class Measurement:
    """Domain-shaped value-plus-metadata a conducted act produces or observes.

    Substrate-neutral: a `Measurement` is what a consumer sees from any
    edge runtime, whether the value was read off a control address,
    produced by a compute job, or observed during a transfer. Domain
    owns every field. Adapter ACLs translate substrate-native value
    types (EPICS V4 NT structures, Tango `DeviceAttribute`, OPC UA
    `DataValue`, a compute result record, a transfer manifest) into this
    shape; substrate vocabulary (NTNDArray fields, DevState labels,
    OPC UA Variant types) stays caged in the adapter.

    `value` is `Any` because the runtime shape varies with `kind`:
    `Scalar` is `int | float | bool | str`, `Array` is a tuple,
    `Image` is a 2-D structure (typically `numpy.ndarray` at the
    adapter, normalised to a tuple-of-tuples or wrapped array at the
    port boundary), `Categorical` is a string label, `Tabular` is a
    dict of column names to tuples. Callers narrow per kind at the
    use site.

    Substrate-specific presentation hints (NT `valueAlarm`,
    `displayLimit`, `controlLimit` structures; Tango display formats;
    OPC UA `DisplayName`) are intentionally NOT surfaced here. They
    are operator-UI metadata, not data-plane data; adapters drop
    them at unpacking time.

    `produced_at` is the time the substrate produced or observed the
    value (EPICS source timestamp, Tango `time`, OPC UA
    `SourceTimestamp`, a compute job's completion time, a transfer's
    observation time). `quality_detail` is adapter-specific and opaque
    at the port layer; treat it as a forensic breadcrumb, not a value
    to branch on.

    `name` is an optional substrate-neutral key naming the output or
    quantity the value carries (the channel / output / quantity label);
    it is empty when the consumer identifies the value by position or
    address instead. `units` is the optional unit string for the value,
    `None` when the value is dimensionless or units are unknown.
    """

    value: Any
    kind: MeasurementKind
    quality: Quality
    produced_at: datetime
    quality_detail: str = ""
    name: str = ""
    units: str | None = None


__all__ = [
    "Measurement",
    "MeasurementKind",
    "Quality",
]
