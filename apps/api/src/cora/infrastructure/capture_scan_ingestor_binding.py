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
            "access_protocol": "NFS",
            "durable": true,
            "subdirectory": "data"
          }
        }
      }
    }'

A code absent from this map is never auto-ingested, mirroring every
other per-code table's optionality.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cora.shared.path_segment import is_safe_path_segment
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
    """One location a capture code's file may reach: which Supply holds it, over what protocol.

    `durable` lives here, on the location, rather than in a separate
    top-level setting listing durable roots. A separate list would be a
    second place to keep in sync with this one, and the two would
    drift; the fact that a tier is the durable one belongs with the
    tier it describes.
    """

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
    durable: bool = Field(
        default=False,
        description=(
            "Whether this is the durable copy: the one the sweep should "
            "find and register as a second Distribution on the same "
            "Dataset once the acquisition-tier copy risks being purged. "
            "At most one location per capture code may set this."
        ),
    )
    subdirectory: str | None = Field(
        default=None,
        description=(
            "The path segment below the experiment folder where files "
            "at this location live, such as APS Data Management's "
            "`data` directory under DMagic's layout. None when files "
            "sit directly in the experiment folder, which is the "
            "acquisition tier's shape and most locations'."
        ),
    )

    @field_validator("subdirectory")
    @classmethod
    def _validate_subdirectory(cls, value: str | None) -> str | None:
        """Refuse anything that is not one safe path segment.

        Uses the same `is_safe_path_segment` rule both ends of the scan
        probe already apply to `subdirectory`, rather than a second
        rule that could disagree with it.
        """
        if value is not None and not is_safe_path_segment(value):
            msg = f"subdirectory {value!r} is not one safe path segment."
            raise ValueError(msg)
        return value


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

        At most one location may be marked `durable`: two would leave
        the sweep no way to choose between them, and failing here beats
        discovering the ambiguity on the first sweep tick. Zero is
        fine; it means this code has no durable tier configured yet and
        the sweep simply skips it.
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
        durable_keys = [key for key, location in normalized.items() if location.durable]
        if len(durable_keys) > 1:
            msg = (
                f"locations marks {len(durable_keys)} roots durable: "
                f"{sorted(durable_keys)!r}. At most one location per capture "
                "code may be durable, or the sweep has no way to choose."
            )
            raise ValueError(msg)
        return normalized


def durable_roots(bindings: Mapping[str, CaptureScanIngestorBinding]) -> frozenset[str]:
    """The normalized storage roots marked durable, across every capture code.

    Derived from `bindings` rather than read from a separate Settings
    field, since deriving it is what keeps it from drifting out of sync
    with the per-location flag it is computed from. Empty when nothing
    is marked durable, which the caller treats as the sweep being off.
    """
    return frozenset(
        root
        for binding in bindings.values()
        for root, location in binding.locations.items()
        if location.durable
    )


def durable_supply_ids(bindings: Mapping[str, CaptureScanIngestorBinding]) -> frozenset[UUID]:
    """The Supply ids of the locations marked durable, across every capture code.

    Empty under the same condition as `durable_roots`, and derived the
    same way: from `bindings` directly, never from a Settings field
    that could fall out of step with it.
    """
    return frozenset(
        location.supply_id
        for binding in bindings.values()
        for location in binding.locations.values()
        if location.durable
    )


@dataclass(frozen=True)
class DurableLocationBinding:
    """The one durable location configured for a capture code.

    Structurally satisfies
    `cora.api._durable_distribution_driver.DurableLocationBinding` (same
    four properties, by name) without importing it: `cora.infrastructure`
    may not depend on `cora.api` per `tach.toml`, and duck typing is
    exactly what that Protocol asks a caller to provide.
    """

    root: str
    supply_id: UUID
    access_protocol: str
    subdirectory: str | None


class CaptureScanIngestorDurableLocationLookup:
    """`DurableLocationLookup` read directly off the validated binding
    config; no derived index kept alongside it to fall out of sync.

    `CaptureScanIngestorBinding._validate_locations` already enforces at
    most one durable location per capture code, so the scan below always
    finds zero or one match.
    """

    def __init__(self, bindings: Mapping[str, CaptureScanIngestorBinding]) -> None:
        self._bindings = bindings

    def durable_location_for(self, capture_code: str) -> DurableLocationBinding | None:
        binding = self._bindings.get(capture_code)
        if binding is None:
            return None
        for root, location in binding.locations.items():
            if location.durable:
                return DurableLocationBinding(
                    root=root,
                    supply_id=location.supply_id,
                    access_protocol=location.access_protocol,
                    subdirectory=location.subdirectory,
                )
        return None


__all__ = [
    "CaptureScanIngestorBinding",
    "CaptureScanIngestorDurableLocationLookup",
    "CaptureScanIngestorLocation",
    "DurableLocationBinding",
    "durable_roots",
    "durable_supply_ids",
]
