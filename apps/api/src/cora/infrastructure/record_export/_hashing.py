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

from collections.abc import Iterable
from typing import Protocol

from cora.infrastructure.record_export._dispositions import DISPOSITIONS
from cora.infrastructure.record_export._redact_tier1 import (
    FIXED_DROP_COLUMNS,
    FIXED_KEEP_COLUMNS,
    FIXED_TOKEN_COLUMNS,
)
from cora.infrastructure.record_export._redact_tier2 import (
    TIER2_DISPOSITIONS,
    TIER2_JSONB_CLEARED_POINTERS,
    TIER2_JSONB_DROPPED_COLUMNS,
)
from cora.shared.content_hash import compute_content_hash

RECORD_PAYLOAD_TYPE = "application/vnd.cora.record+json"
STREAMS_PAYLOAD_TYPE = "application/vnd.cora.record-streams+json"
LOGBOOKS_PAYLOAD_TYPE = "application/vnd.cora.record-logbooks+json"
REDACTION_PROFILE_PAYLOAD_TYPE = "application/vnd.cora.record-redaction-profile+json"
PUBLISHED_RECORD_PAYLOAD_TYPE = "application/vnd.cora.record-published+json"
REGISTERED_KINDS_PAYLOAD_TYPE = "application/vnd.cora.record-registered-kinds+json"


class TwoTierRecord(Protocol):
    """The shape both `ExportedRecord` and `RedactedRecord` share.

    Structural, not a base class, so `_hashing` can hash a redacted
    record without importing `_redaction` (which imports this module:
    the dependency runs one way only).
    """

    @property
    def streams(self) -> tuple[dict[str, object], ...]: ...

    @property
    def logbooks(self) -> dict[str, tuple[dict[str, object], ...]]: ...


def _two_tier_body(record: TwoTierRecord) -> dict[str, object]:
    """The hashed body shape shared by H1 and H3, so the two can never
    disagree about what "the whole bundle" means."""
    return {
        "streams": list(record.streams),
        "logbooks": {kind: list(rows) for kind, rows in record.logbooks.items()},
    }


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


def hash_record(record: TwoTierRecord) -> str:
    """SHA-256 content hash over the whole bundle, both tiers, no exclusions.

    This is THE record hash (H1): per F2, it covers everything
    `export_record` produced. Re-running the export against an unchanged
    database reproduces this value exactly; any single differing byte
    anywhere in either tier changes it.

    Takes the structural `TwoTierRecord`, not `ExportedRecord` by name,
    so `_bundle.write_bundle`'s binding check can call this on whatever
    it was actually handed and compare against what a manifest claims,
    without needing to know which concrete type that is.
    """
    return compute_content_hash(RECORD_PAYLOAD_TYPE, _two_tier_body(record))


def hash_redacted_record(record: TwoTierRecord) -> str:
    """SHA-256 content hash over the PUBLISHED record: H3.

    The third of `project_record_export_v3.md` F5's three hashes (full
    record H1, redaction profile H2, published record H3), and the one
    the paper actually prints beside its locator, because it is the only
    one covering the bytes a reader can hold.

    The payload type is deliberately distinct from
    `RECORD_PAYLOAD_TYPE`. `compute_content_hash` binds the payload type
    into the DSSE-PAE preamble, so an unredacted and a redacted record
    that happened to reduce to identical bodies still hash differently.
    That matters: without it, an export whose redaction dropped nothing
    (every field already publishable) would produce H1 == H3, and a
    reader could not tell a published record from a full one by its hash
    alone. They must never collide.

    Takes the structural `TwoTierRecord` rather than `RedactedRecord`
    only because importing `_redaction` here would invert this module's
    dependency; callers pass `RedactionResult.redacted_record`. Passing
    an unredacted `ExportedRecord` alongside a manifest whose
    `published_record_hash` was computed from the real redacted record
    is a caller error this function's signature cannot catch by itself
    -- `write_bundle` is what catches it, by recomputing this same hash
    over whatever record it was actually handed and refusing on
    disagreement (`ManifestRecordMismatchError`) before writing a single
    byte.
    """
    return compute_content_hash(PUBLISHED_RECORD_PAYLOAD_TYPE, _two_tier_body(record))


def hash_registered_kinds(kinds: Iterable[str]) -> str:
    """SHA-256 content hash over the sorted registered logbook kind set.

    Takes the kind strings directly rather than importing
    `_registry.all_specs` here: `_hashing` stays a leaf module hashing
    whatever body a caller hands it, the same posture every other
    `hash_*` function in this file takes. `_manifest.py` is the caller
    that actually reads the registry.

    Per `project_record_completeness_design.md`'s "Two authorities, two
    times": this is the build-time half. A reader comparing a bundle's
    `registered_kinds_hash` against a hash it computes from ITS OWN
    checkout's registry can tell whether the universe of kinds this
    export was measured against has since grown a tenth member, without
    needing to trust the manifest's `extent_by_logbook_kind` keys alone.
    """
    return compute_content_hash(REGISTERED_KINDS_PAYLOAD_TYPE, sorted(kinds))


def hash_redaction_profile() -> str:
    """SHA-256 content hash over every table that decides what a
    published record discloses: tier 1's generated per-field
    `DISPOSITIONS` AND its hand-authored fixed-column dispositions
    (`FIXED_KEEP_COLUMNS` / `FIXED_TOKEN_COLUMNS` / `FIXED_DROP_COLUMNS`
    in `_redact_tier1.py`, which govern `stream_id`, `principal_id`,
    `signature`, and every other `events` column outside `payload`), AND
    tier 2's hand-authored `TIER2_DISPOSITIONS` /
    `TIER2_JSONB_CLEARED_POINTERS` / `TIER2_JSONB_DROPPED_COLUMNS`.

    This IS the redaction profile hash (H2). Step 7's security re-review
    found the tier-2 tables missing from this hash and fixed that; this
    fixes the same class of gap one seam over. `_redact_tier1.py`'s three
    fixed-column tuples decide, unconditionally for every event, whether
    `principal_id` tokens or `signature` drops -- editing either was
    invisible to `redact_record`'s `expected_redaction_profile_hash`
    check, so moving `principal_id` from TOKEN to KEEP, or `signature`
    from DROP to KEEP (republishing a signature beside a redacted payload,
    the exact confirmation oracle F5's anti-hooks forbid), would not have
    moved H2 at all. Every table that decides a disposition must be in
    H2, or "the hash matches" does not mean what
    `RedactionProfileMismatchError`'s docstring claims it means.

    Tuple-keyed dicts (`TIER2_JSONB_CLEARED_POINTERS` /
    `TIER2_JSONB_DROPPED_COLUMNS`) are flattened to `"kind/column"`
    string keys before hashing rather than relying on
    `compute_content_hash`'s `str(key)` fallback for non-string Mapping
    keys, which would hash a Python tuple's `repr()` instead of a
    reviewable string.

    Regenerating tier 1's table via `make record-dispositions` after a
    real event-model change, or hand-editing either tier's fixed tables,
    is expected to change this value; `test_record_dispositions_drift.py`
    guards tier 1's generator output specifically, and
    `test_redact_tier2.py`'s live-schema drift test guards tier 2's
    column coverage, but only THIS hash is what a caller's
    `expected_redaction_profile_hash` actually pins.
    """
    body = {
        "tier1": DISPOSITIONS,
        "tier1_fixed_keep_columns": sorted(FIXED_KEEP_COLUMNS),
        "tier1_fixed_token_columns": sorted(FIXED_TOKEN_COLUMNS),
        "tier1_fixed_drop_columns": sorted(FIXED_DROP_COLUMNS),
        "tier2_dispositions": TIER2_DISPOSITIONS,
        "tier2_jsonb_cleared_pointers": {
            f"{kind}/{column}": sorted(pointers)
            for (kind, column), pointers in TIER2_JSONB_CLEARED_POINTERS.items()
        },
        "tier2_jsonb_dropped_columns": sorted(
            f"{kind}/{column}" for kind, column in TIER2_JSONB_DROPPED_COLUMNS
        ),
    }
    return compute_content_hash(REDACTION_PROFILE_PAYLOAD_TYPE, body)


__all__ = [
    "LOGBOOKS_PAYLOAD_TYPE",
    "PUBLISHED_RECORD_PAYLOAD_TYPE",
    "RECORD_PAYLOAD_TYPE",
    "REDACTION_PROFILE_PAYLOAD_TYPE",
    "REGISTERED_KINDS_PAYLOAD_TYPE",
    "STREAMS_PAYLOAD_TYPE",
    "TwoTierRecord",
    "hash_logbooks",
    "hash_record",
    "hash_redacted_record",
    "hash_redaction_profile",
    "hash_registered_kinds",
    "hash_streams",
]
