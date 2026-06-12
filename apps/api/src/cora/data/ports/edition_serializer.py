"""EditionSerializer: per-kind serializer for citable Edition records.

Invoked twice across the Edition lifecycle:

  1. At `seal_edition` time with `external_pid=None`: the serializer
     produces the canonical pre-DOI bytes; their sha256 becomes
     `Edition.content_hash` (set ONCE, immutable thereafter per the
     two-content-hash model).
  2. At `publish_edition` time with `external_pid=<minted_pid>`: the
     serializer re-renders the SAME logical content with the DOI baked
     in; the resulting sha256 is the event-payload-only
     `published_content_hash` (NOT stored on Edition aggregate state).

Per-kind dispatch is inline in the consuming handlers today (only
`RoCrate12Adapter` ships); the registry hoist trigger is the 4th kind
adapter (ROCrate + DataCite + Croissant = rule-of-three).

## DatasetRef boundary shape

`DatasetRef` is a slim DTO carrying just the fields a serializer needs.
The handler pre-loads the Dataset stream (for intent + status) plus
the canonical Distribution row (for the authoritative `uri` / `checksum`
/ `byte_size` / `encoding`) and constructs `DatasetRef` at the port
boundary. Anti-hook: do NOT pass raw `Dataset` aggregates into the
serializer; the port boundary is intentionally narrow.

## SerializedEdition return shape

`SerializedEdition.content_hash` is the sha256 of the canonical serialized
bytes (lowercase hex, 64 chars). `bytes_uri` is an opaque URI pointing
at the bytes (today an in-memory `data:` URL produced by the RoCrate
adapter; future DataCite / Croissant adapters may write to object storage
and return an `s3://` URL). `content_type` is the IANA media type
(`application/ld+json` for RO-Crate; future adapters set their own).
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset.state import (
    DatasetChecksum,
    DatasetEncoding,
    Intent,
)
from cora.data.aggregates.distribution.state import DistributionUri
from cora.data.aggregates.edition.state import (
    Creator,
    EditionKind,
    SpdxIdentifier,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier


@dataclass(frozen=True)
class DatasetRef:
    """Boundary DTO: one Dataset's serialization-relevant fields.

    `uri`, `checksum`, `byte_size`, and `encoding` come from the
    canonical Distribution (NOT the Dataset's denormalized convenience
    fields per data-territory L5). `intent` is the Dataset's trust
    level (Production-only at seal-time per the Edition decider guard).
    """

    dataset_id: UUID
    uri: DistributionUri
    checksum: DatasetChecksum
    byte_size: int
    encoding: DatasetEncoding
    intent: Intent


@dataclass(frozen=True)
class SerializedEdition:
    """Result of `EditionSerializer.serialize`.

    `content_hash` is the sha256 of the canonical serialized bytes;
    `bytes_uri` points at where those bytes live (in-memory data URL
    today; object-storage URI when adapters mature); `content_type` is
    the IANA media type of the serialized form.
    """

    content_hash: str
    bytes_uri: str
    content_type: str


class EditionSerializer(Protocol):
    """Per-kind serializer for citation-grade Edition artifacts."""

    async def serialize(
        self,
        *,
        edition_id: UUID,
        kind: EditionKind,
        title: str,
        dataset_refs: tuple[DatasetRef, ...],
        publisher_facility_code: FacilityCode,
        creators: tuple[Creator, ...],
        publication_year: int,
        license: SpdxIdentifier | None,
        external_pid: PersistentIdentifier | None,
    ) -> SerializedEdition:
        """Render an Edition as bytes + sha256 hash + content_type.

        Called twice in the lifecycle (seal + publish); the second call
        passes the minted DOI via `external_pid` so the post-mint bytes
        bake the citation into the artifact.
        """
        ...


__all__ = [
    "DatasetRef",
    "EditionSerializer",
    "SerializedEdition",
]
