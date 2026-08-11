"""Record export: CORA's record as a hashed, offline-verifiable artifact.

The design is `project_record_export_v3.md`, locked for the no-beam
commissioning scope. This package holds the exporter and the generated
redaction disposition table it reads.

It lives at `cora.infrastructure`, whose `tach.toml` entry allows
`cora.shared` and nothing else, and that constraint is the guarantee
rather than the obstacle: the exporter composes nothing (column-driven
over raw rows, a registry of `str -> str` pairs, and a table read as
data), so the layering rule ENFORCES the zero-bounded-context-import
property that makes the standalone-verifiability claim honest. If a
change here wants to import an aggregate, the design has drifted.

Two things this package must never do, both learned from review rather
than from first principles:

- Drive extraction, redaction or parity from `LogbookSchema`.
  `LogbookFieldType` is closed over six scalars, so no schema can name a
  jsonb column, and jsonb is where the doing lives. The schema travels
  with the export as documentation.
- Describe the published record as anonymous. It is pseudonymous:
  timestamps plus a facility's own published beamtime schedule
  re-identify without the token map.
"""

from cora.infrastructure.record_export._export import (
    EmptyExportError,
    ExportedRecord,
    capture_watermark,
    export_record,
)
from cora.infrastructure.record_export._hashing import (
    LOGBOOKS_PAYLOAD_TYPE,
    RECORD_PAYLOAD_TYPE,
    STREAMS_PAYLOAD_TYPE,
    hash_logbooks,
    hash_record,
    hash_streams,
)
from cora.infrastructure.record_export._registry import (
    EntriesReader,
    EntriesTableSpec,
    UnknownLogbookKindError,
    all_specs,
    registered_envelope_classes,
    resolve,
)
from cora.infrastructure.record_export._render import render_row, render_value
from cora.infrastructure.record_export._stream_types import (
    KNOWN_STREAM_TYPES,
    UnknownStreamTypeError,
    ensure_stream_type_known,
)

__all__ = [
    "KNOWN_STREAM_TYPES",
    "LOGBOOKS_PAYLOAD_TYPE",
    "RECORD_PAYLOAD_TYPE",
    "STREAMS_PAYLOAD_TYPE",
    "EmptyExportError",
    "EntriesReader",
    "EntriesTableSpec",
    "ExportedRecord",
    "UnknownLogbookKindError",
    "UnknownStreamTypeError",
    "all_specs",
    "capture_watermark",
    "ensure_stream_type_known",
    "export_record",
    "hash_logbooks",
    "hash_record",
    "hash_streams",
    "registered_envelope_classes",
    "render_row",
    "render_value",
    "resolve",
]
