"""Hash an exported record with `cora.shared.content_hash`, no exclusions.

Per `project_record_export_v3.md` F6: one canonicalization, `content_hash`'s
profile, for both serialization and hashing. `canonical_json` (used
elsewhere in the codebase) is a DIFFERENT recipe; mixing the two means the
committed file is not the bytes the hash covers. `cora.shared` is exactly
what `tach.toml` allows `cora.infrastructure` to depend on, so this import
is the dependency the layering rule exists to permit.

No exclusions: every rendered stream row and every rendered logbook row
goes into the hashed body. Re-exporting the same database twice is
measured stable (`test_hashing.py`'s integration test); a regenerated
record hashing differently across genuinely different content is content
addressing working, not a defect, and cross-record comparison is the
shape layer's job, not this module's.

Payload types follow the scheme
`application/vnd.cora.<event-type>+json` (`content_hash.py`'s own
convention) and the three names `project_record_export_v3.md`'s "Naming"
section already picked: `record`, `record-streams`, `record-logbooks`.
That section calls `record+json` the manifest's type; nothing writes a
manifest yet (step 4), so there is no live collision today. Used here for
the whole-bundle hash because `{streams, logbooks}` together *is* the
record the manifest will describe -- if step 4 wants manifest.json to
carry its own distinct wrapping type when it starts writing bytes to
disk, that is a decision for whoever builds it, made with an actual
manifest body in hand rather than guessed at here.
"""

from cora.infrastructure.record_export._dispositions import DISPOSITIONS
from cora.infrastructure.record_export._export import ExportedRecord
from cora.shared.content_hash import compute_content_hash

RECORD_PAYLOAD_TYPE = "application/vnd.cora.record+json"
STREAMS_PAYLOAD_TYPE = "application/vnd.cora.record-streams+json"
LOGBOOKS_PAYLOAD_TYPE = "application/vnd.cora.record-logbooks+json"
REDACTION_PROFILE_PAYLOAD_TYPE = "application/vnd.cora.record-redaction-profile+json"


def hash_streams(streams: tuple[dict[str, object], ...]) -> str:
    """SHA-256 content hash over the streams tier alone, in its own order."""
    return compute_content_hash(STREAMS_PAYLOAD_TYPE, list(streams))


def hash_logbooks(logbooks: dict[str, tuple[dict[str, object], ...]]) -> str:
    """SHA-256 content hash over the logbooks tier alone.

    Kind keys are NFC-normalized and sort themselves via
    `json.dumps(sort_keys=True)`; each kind's row order is preserved
    (the registry's own order-by), never re-sorted.
    """
    body = {kind: list(rows) for kind, rows in logbooks.items()}
    return compute_content_hash(LOGBOOKS_PAYLOAD_TYPE, body)


def hash_record(record: ExportedRecord) -> str:
    """SHA-256 content hash over the whole bundle, both tiers, no exclusions.

    This is THE record hash: per F2, it covers everything `export_record`
    produced. Re-running the export against an unchanged database
    reproduces this value exactly; any single differing byte anywhere in
    either tier changes it.
    """
    body = {
        "streams": list(record.streams),
        "logbooks": {kind: list(rows) for kind, rows in record.logbooks.items()},
    }
    return compute_content_hash(RECORD_PAYLOAD_TYPE, body)


def hash_redaction_profile() -> str:
    """SHA-256 content hash over Step 0's generated disposition table.

    This IS the redaction profile hash (H2): the disposition table
    decides what a published record discloses, so its hash is what
    step 6's fail-closed switch checks and what the manifest names
    alongside `record_hash` (H1). Regenerating the table via
    `make record-dispositions` after a real event-model change is
    expected to change this value; `test_record_dispositions_drift.py`
    is the guard against an UNREVIEWED change slipping through instead.
    """
    return compute_content_hash(REDACTION_PROFILE_PAYLOAD_TYPE, DISPOSITIONS)


__all__ = [
    "LOGBOOKS_PAYLOAD_TYPE",
    "RECORD_PAYLOAD_TYPE",
    "REDACTION_PROFILE_PAYLOAD_TYPE",
    "STREAMS_PAYLOAD_TYPE",
    "hash_logbooks",
    "hash_record",
    "hash_redaction_profile",
    "hash_streams",
]
