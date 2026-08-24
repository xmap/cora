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
  `quality: Quality`, `produced_at: datetime | None`,
  `quality_detail: str`, plus the substrate-neutral `name` and
  `units` annotations.
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
  It is DEFINED in `cora.shared.quality` and re-exported here, because
  consumers outside this BC read it and `cora.shared` is the one place
  they can all reach. That module also owns the two named floors
  (`believable` / `actionable`) a consumer picks between, and the
  account of why picking by hand went wrong three times.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from cora.shared.quality import Quality

MeasurementKind = Literal["Scalar", "Array", "Image", "Categorical", "Tabular"]
"""Closed 5-value discriminator for `Measurement.value` shape.

- `Scalar`: a single typed value (int / float / bool / str).
- `Array`: a 1-D sequence of scalars (tuple at the port boundary).
- `Image`: a 2-D pixel grid (NTNDArray / Tango IMAGE / OPC UA image
  variants); shape and dtype carried inside `value`.
- `Categorical`: a string label from a closed substrate-defined set
  (EPICS NTEnum / Tango DevEnum or DevState / OPC UA enum). The set is
  substrate-DEFINED, so the label is only as portable as the facility
  that authored it; `Measurement.ordinal` carries the index behind it
  for consumers that need a portable answer rather than a readable one.
- `Tabular`: column-oriented record (NTTable / OPC UA table / Tango
  multi-attribute bundle).

Adapter ACLs translate substrate-specific type taxonomies INTO this
enum. Extensible by tag addition when a future substrate justifies a
new shape (e.g., OPC UA `LocalizedText` may justify a new tag).
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
    observation time). It is `None` when the substrate supplied no
    usable time, which is a normal condition rather than an error:
    plenty of real equipment reports a value without ever stamping
    it. Consumers must decide what an absent source time means for
    them; a consumer that needs SOME time should use its own
    ingest-time rather than inventing one here.

    Absence is decided by each adapter, never at this port, because
    every substrate spells "no timestamp" differently. What adapters
    MUST NOT do is substitute a wall-clock reading, which would make
    an ingest time indistinguishable from a substrate time, or pass
    through the substrate's zero, which parses as a real date and so
    lies more convincingly than a gap. See
    [[project-source-timestamp-design]].

    `quality_detail` is adapter-specific and opaque at the port
    layer; treat it as a forensic breadcrumb, not a value to branch
    on.

    `name` is an optional substrate-neutral key naming the output or
    quantity the value carries (the channel / output / quantity label);
    it is empty when the consumer identifies the value by position or
    address instead. `units` is the optional unit string for the value,
    `None` when the value is dimensionless or units are unknown.

    `ordinal` is the substrate's own numeric code for a `Categorical`
    reading, carried BESIDE the label rather than instead of it, and
    `None` for every other kind. The split matters because the two
    halves have different owners: an EPICS `bi` record's ZNAM / ONAM, a
    Tango `DevEnum`'s config labels and an NTEnum's `choices` are all
    free text one engineer chose at one facility, while the index behind
    them is fixed by the record's own definition. So a consumer
    resolving a two-state signal reads `ordinal`, and a consumer
    recording what an operator saw reads `value`. This is the same
    division `quality` (domain-owned meaning) already makes with
    `quality_detail` (substrate breadcrumb), applied to the one axis
    that had been resolving facility vocabulary in shared code instead.

    STATE THE PRECONDITION, because the field is easy to over-trust: the
    ordinal is portable for a record that is genuinely two-state with
    the conventional bit sense, which is what a `bi` is by construction
    (0 is the false / clear / de-asserted state). It is NOT a universal
    truth about enums. For a multi-state record, WHICH index means
    tripped is exactly as facility-authored as the label, and for a
    vocabulary indexed on some other axis the number answers a different
    question entirely (Tango `DevState`, below). So `ordinal` says "here
    is the substrate's code", never "here is a flag". Deciding whether a
    given record is a flag at all remains the caller's problem, and
    `binary_code` refusing an out-of-range ordinal catches only the
    subset of wrong records that happen to be resting outside 0 / 1.

    An adapter populates `ordinal` ONLY where the number sits on the
    same axis as the label. Tango `DevState` is the standing exception:
    its ordinal is a Tango-global state code (`ON = 0`, `OFF = 1`,
    `OPEN = 3`, ...), so a flag consumer reading it would resolve `ON`
    to false, exactly backwards. That adapter leaves `ordinal` unset
    rather than offer a number that answers a different question, and
    the label path still serves it correctly.
    """

    value: Any
    kind: MeasurementKind
    quality: Quality
    produced_at: datetime | None
    quality_detail: str = ""
    name: str = ""
    units: str | None = None
    ordinal: int | None = None


__all__ = [
    "Measurement",
    "MeasurementKind",
    "Quality",
]
