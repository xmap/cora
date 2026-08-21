"""Settings-loadable shape for `CaptureScanIngestor`'s per-capture-code bindings.

Mirrors the layering used for `ControlPortRoute` and
`IdentityProviderConfig`: the typed config models live here in
`cora.infrastructure` so `Settings` can validate the env var at
startup, while the code that consumes the validated shape
(`cora.api._capture_scan_ingestor`) lives in the composition root.

A capture code binds one producing Asset plus one or more locations
(vault rows) the finished file may land on, each naming the Supply and
access protocol CORA should record for `IngestScan`. See
`run.aggregates.run.capture_path`'s module docstring for why a Run may
hold more than one vault row (one per storage location it was observed
under) and `CapturePathStore.upsert`'s own docstring for why that store
is "idempotent per LOCATION, not per Run".

## Env var shape

`Settings.capture_scan_ingestor_bindings` reads from
CAPTURE_SCAN_INGESTOR_BINDINGS as JSON, keyed by capture code:

    CAPTURE_SCAN_INGESTOR_BINDINGS='{
      "2bmb-tomoscan": {
        "producing_asset_id": "0c5e...-camera-asset-uuid",
        "locations": {
          "/local1/2BM": {
            "supply_id": "b2a1...-storage-supply-uuid",
            "access_protocol": "POSIX"
          },
          "/gdata/dm/2BM": {
            "supply_id": "77f0...-storage-supply-uuid",
            "access_protocol": "NFS"
          }
        }
      }
    }'

A code absent from this map is never auto-ingested, mirroring every
other per-code table's optionality.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cora.shared.storage_root import normalize_storage_root, require_nonempty_absolute_root

# Local mirror of `cora.data.aggregates.distribution.state.AccessProtocol`.
# Not imported directly: `cora.infrastructure` may not depend on
# `cora.data` (`tach check`), and the Data BC's own `IngestScan` decider
# already validates the value it receives, so this mirror only needs to
# keep an operator's typo from surfacing at the first sweep tick instead
# of at boot. `tests/architecture/test_capture_scan_ingestor_access_protocol_sync.py`
# pins the value set against the real enum so the two cannot silently drift.
_AccessProtocolLiteral = Literal["HTTPS", "Globus", "S3", "POSIX", "NFS", "OAI_PMH"]


class CaptureScanIngestorLocation(BaseModel):
    """One location a capture code's file may reach: which Supply holds it, over what protocol."""

    model_config = ConfigDict(extra="forbid")

    supply_id: UUID = Field(
        description="The Distribution Supply `IngestScan` should record as reading this location."
    )
    access_protocol: _AccessProtocolLiteral = Field(
        description=(
            "The transport family `IngestScan` should record for a "
            "Dataset minted from this location."
        )
    )


class CaptureScanIngestorBinding(BaseModel):
    """What `IngestScan` needs for one capture code: the producing Asset, plus its locations."""

    model_config = ConfigDict(extra="forbid")

    producing_asset_id: UUID = Field(
        description="The Asset that produced files under this capture code."
    )
    locations: dict[str, CaptureScanIngestorLocation] = Field(
        description=(
            "One location per storage root the finished file may land on, "
            "keyed by the root itself (normalized at validation time)."
        )
    )

    @field_validator("locations")
    @classmethod
    def _validate_locations(
        cls, value: dict[str, CaptureScanIngestorLocation]
    ) -> dict[str, CaptureScanIngestorLocation]:
        """Refuse an empty map, and normalize + dedupe root keys.

        A relative or root-collapsing key is meaningless to
        `cora.api._capture_scan_ingestor`'s join against the vault's own
        `root` column. Keys are stored NORMALIZED so a deployment
        writing a trailing slash still matches the vault's normalized
        column; see `cora.shared.storage_root`'s module docstring for
        why one un-normalized caller makes every lookup miss. Two keys
        that normalize to the same root raise rather than silently
        collapsing to whichever one iteration visited last, since that
        would drop a Supply/protocol pairing an operator wrote on
        purpose with no signal that it happened.
        """
        if not value:
            msg = "locations is empty. A binding with no location can never ingest anything."
            raise ValueError(msg)
        normalized: dict[str, CaptureScanIngestorLocation] = {}
        original_spelling: dict[str, str] = {}
        for root, location in value.items():
            require_nonempty_absolute_root(root, label="locations key")
            key = normalize_storage_root(root)
            if key in normalized:
                msg = (
                    f"locations keys {original_spelling[key]!r} and {root!r} "
                    f"both normalize to {key!r}. Each location must name a "
                    "distinct storage root."
                )
                raise ValueError(msg)
            normalized[key] = location
            original_spelling[key] = root
        return normalized


__all__ = ["CaptureScanIngestorBinding", "CaptureScanIngestorLocation"]
