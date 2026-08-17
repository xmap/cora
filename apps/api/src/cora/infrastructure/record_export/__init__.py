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

from cora.infrastructure.record_export._bundle import (
    LOGBOOKS_DIR,
    MANIFEST_NAME,
    STREAMS_NAME,
    BundleDestinationNotEmptyError,
    MalformedBundleError,
    ManifestRecordMismatchError,
    read_bundle_body,
    write_bundle,
)
from cora.infrastructure.record_export._export import (
    EmptyExportError,
    ExportedRecord,
    capture_watermark,
    export_record,
)
from cora.infrastructure.record_export._hashing import (
    LOGBOOKS_PAYLOAD_TYPE,
    PUBLISHED_RECORD_PAYLOAD_TYPE,
    RECORD_PAYLOAD_TYPE,
    REDACTION_PROFILE_PAYLOAD_TYPE,
    STREAMS_PAYLOAD_TYPE,
    TwoTierRecord,
    hash_logbooks,
    hash_record,
    hash_redacted_record,
    hash_redaction_profile,
    hash_streams,
)
from cora.infrastructure.record_export._manifest import Manifest, build_manifest, capture_git_commit
from cora.infrastructure.record_export._redact_tier1 import (
    FIXED_DROP_COLUMNS,
    FIXED_KEEP_COLUMNS,
    FIXED_TOKEN_COLUMNS,
    Tier1Redactor,
    UnknownEventTypeError,
    redact_tier1_payload,
)
from cora.infrastructure.record_export._redact_tier2 import (
    TIER2_DISPOSITIONS,
    TIER2_JSONB_CLEARED_POINTERS,
    TIER2_JSONB_DROPPED_COLUMNS,
    redact_tier2_row,
    unfired_clearances,
)
from cora.infrastructure.record_export._redaction import (
    RedactedRecord,
    RedactionProfileMismatchError,
    RedactionResult,
    redact_record,
)
from cora.infrastructure.record_export._registry import (
    EntriesReader,
    EntriesTableSpec,
    UnknownLogbookKindError,
    all_specs,
    registered_envelope_classes,
    resolve,
)
from cora.infrastructure.record_export._render import (
    UndecodedJsonColumnError,
    render_row,
    render_value,
)
from cora.infrastructure.record_export._shell import export_bundle
from cora.infrastructure.record_export._stream_types import (
    KNOWN_STREAM_TYPES,
    UnknownStreamTypeError,
    ensure_stream_type_known,
)
from cora.infrastructure.record_export._tokens import TokenMap

__all__ = [
    "FIXED_DROP_COLUMNS",
    "FIXED_KEEP_COLUMNS",
    "FIXED_TOKEN_COLUMNS",
    "KNOWN_STREAM_TYPES",
    "LOGBOOKS_DIR",
    "LOGBOOKS_PAYLOAD_TYPE",
    "MANIFEST_NAME",
    "PUBLISHED_RECORD_PAYLOAD_TYPE",
    "RECORD_PAYLOAD_TYPE",
    "REDACTION_PROFILE_PAYLOAD_TYPE",
    "STREAMS_NAME",
    "STREAMS_PAYLOAD_TYPE",
    "TIER2_DISPOSITIONS",
    "TIER2_JSONB_CLEARED_POINTERS",
    "TIER2_JSONB_DROPPED_COLUMNS",
    "BundleDestinationNotEmptyError",
    "EmptyExportError",
    "EntriesReader",
    "EntriesTableSpec",
    "ExportedRecord",
    "MalformedBundleError",
    "Manifest",
    "ManifestRecordMismatchError",
    "RedactedRecord",
    "RedactionProfileMismatchError",
    "RedactionResult",
    "Tier1Redactor",
    "TokenMap",
    "TwoTierRecord",
    "UndecodedJsonColumnError",
    "UnknownEventTypeError",
    "UnknownLogbookKindError",
    "UnknownStreamTypeError",
    "all_specs",
    "build_manifest",
    "capture_git_commit",
    "capture_watermark",
    "ensure_stream_type_known",
    "export_bundle",
    "export_record",
    "hash_logbooks",
    "hash_record",
    "hash_redacted_record",
    "hash_redaction_profile",
    "hash_streams",
    "read_bundle_body",
    "redact_record",
    "redact_tier1_payload",
    "redact_tier2_row",
    "registered_envelope_classes",
    "render_row",
    "render_value",
    "resolve",
    "unfired_clearances",
    "write_bundle",
]
