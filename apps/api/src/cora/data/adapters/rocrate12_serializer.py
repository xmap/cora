"""`RoCrate12Adapter`: first `EditionSerializer` implementation.

Produces JSON-LD per the RO-Crate 1.2 + Workflow Run Crate profiles
(per the Edition design memo L10). The serializer is deterministic:
given the same logical inputs, the output bytes (and therefore the
sha256 `content_hash`) are byte-identical. All set-semantic fields
sort their entries on the wire; ordered fields (`creators`) preserve
input order; numeric keys serialize as canonical JSON via
`cora.shared.canonical_json`.

The resulting bytes are returned via a `data:` URL inline today; a
production deployment that writes to object storage swaps the adapter
or extends this one with an upload step.

## What ships

  - Top-level JSON-LD with `@context` = the RO-Crate 1.2-DRAFT context
    plus the Workflow Run Crate profile.
  - Root `Dataset` entity for the Edition itself (`@id="./"`) with:
      - `name`: the Edition title
      - `datePublished`: the publication year (RFC-3339 year)
      - `license`: the SPDX identifier when present
      - `publisher`: the Facility code as an `Organization`
      - `creator`: ordered list of `Person` entities (one per Creator)
      - `hasPart`: opaque list of `@id` references, one per DatasetRef
      - `identifier`: the `external_pid` value when published
      - `conformsTo`: list of profile URIs
  - One `Dataset` entry per `DatasetRef`, carrying:
      - `@id`: `urn:uuid:<dataset_id>` (stable; cross-system safe)
      - `contentUrl`: the canonical Distribution URI
      - `sha256`: from the Distribution checksum (algorithm pinned to
        sha256 in the Dataset BC today)
      - `contentSize`: byte size as integer
      - `encodingFormat`: media type
      - `conformsTo`: encoding's `conforms_to` profile URIs (sorted)

External-pid awareness: when `external_pid is None` the artifact omits
`identifier` (pre-DOI bytes). When `external_pid` is supplied, the
root entity gains `identifier` carrying the scheme-prefixed value
(e.g. `doi:10.5281/zenodo.1234567`). The sha256 of the two byte
streams differs by design (this is the two-content-hash model).
"""

import base64
import hashlib
from uuid import UUID

from cora.data.aggregates.edition.state import (
    Creator,
    EditionKind,
    SpdxIdentifier,
)
from cora.data.ports.edition_serializer import (
    DatasetRef,
    SerializedEdition,
)
from cora.shared.canonical_json import canonical_json_bytes
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier

_ROCRATE_12_CONTEXT = "https://w3id.org/ro/crate/1.2-DRAFT/context"
_WORKFLOW_RUN_CRATE_PROFILE = "https://w3id.org/ro/wfrun/workflow/0.5"
_PROCESS_RUN_CRATE_PROFILE = "https://w3id.org/ro/wfrun/process/0.5"
_CONTENT_TYPE = "application/ld+json"


def _dataset_id_uri(dataset_id: UUID) -> str:
    return f"urn:uuid:{dataset_id}"


def _external_pid_uri(external_pid: PersistentIdentifier) -> str:
    return f"{external_pid.scheme.value}:{external_pid.value}"


def _dataset_part(ref: DatasetRef) -> dict[str, object]:
    return {
        "@id": _dataset_id_uri(ref.dataset_id),
        "@type": "Dataset",
        "contentUrl": ref.uri.value,
        "sha256": ref.checksum.value,
        "contentSize": ref.byte_size,
        "encodingFormat": ref.encoding.media_type,
        "conformsTo": sorted(ref.encoding.conforms_to),
    }


def _creator_entity(creator: Creator, index: int) -> dict[str, object]:
    person_id = f"_:creator-{index}"
    entity: dict[str, object] = {
        "@id": person_id,
        "@type": "Person",
        "identifier": str(creator.actor_id),
    }
    if creator.affiliation is not None:
        entity["affiliation"] = creator.affiliation
    return entity


def _publisher_entity(publisher_facility_code: FacilityCode) -> dict[str, object]:
    return {
        "@id": f"_:facility-{publisher_facility_code.value}",
        "@type": "Organization",
        "identifier": publisher_facility_code.value,
    }


class RoCrate12Adapter:
    """`EditionSerializer` implementation for `EditionKind.ROCRATE`.

    Pure in-process serializer; no IO. `serialize` returns a
    `SerializedEdition` carrying the sha256 hash + an inline
    `data:application/ld+json;base64,...` URI + the IANA content type.
    """

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
        _ = kind  # routed by caller; verified by precondition
        sorted_dataset_refs = sorted(dataset_refs, key=lambda r: r.dataset_id)

        creator_entities = [
            _creator_entity(creator, index) for index, creator in enumerate(creators)
        ]
        publisher_entity = _publisher_entity(publisher_facility_code)

        root_entity: dict[str, object] = {
            "@id": "./",
            "@type": "Dataset",
            "name": title,
            "datePublished": str(publication_year),
            "publisher": {"@id": publisher_entity["@id"]},
            "creator": [{"@id": entity["@id"]} for entity in creator_entities],
            "hasPart": [{"@id": _dataset_id_uri(ref.dataset_id)} for ref in sorted_dataset_refs],
            "conformsTo": [
                {"@id": _PROCESS_RUN_CRATE_PROFILE},
                {"@id": _WORKFLOW_RUN_CRATE_PROFILE},
            ],
            "identifier": f"edition:{edition_id}",
        }
        if license is not None:
            root_entity["license"] = license.value
        if external_pid is not None:
            root_entity["identifier"] = _external_pid_uri(external_pid)

        graph: list[dict[str, object]] = [root_entity]
        graph.append(publisher_entity)
        graph.extend(creator_entities)
        graph.extend(_dataset_part(ref) for ref in sorted_dataset_refs)

        document: dict[str, object] = {
            "@context": _ROCRATE_12_CONTEXT,
            "@graph": graph,
        }

        canonical_bytes = canonical_json_bytes(document)
        content_hash = hashlib.sha256(canonical_bytes).hexdigest()
        bytes_uri = f"data:{_CONTENT_TYPE};base64," + base64.b64encode(canonical_bytes).decode(
            "ascii"
        )
        return SerializedEdition(
            content_hash=content_hash,
            bytes_uri=bytes_uri,
            content_type=_CONTENT_TYPE,
        )


__all__ = ["RoCrate12Adapter"]
