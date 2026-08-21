"""`RoCrate12Adapter`: first `EditionSerializer` implementation.

Produces RO-Crate-flavored JSON-LD, modeled on the RO-Crate 1.2 +
Workflow Run Crate profiles (per the Edition design memo L10). It is
not yet a conformant RO-Crate; see "Known gaps blocking first
publication" below. The serializer is deterministic:
given the same logical inputs, the output bytes (and therefore the
sha256 `content_hash`) are byte-identical. All set-semantic fields
sort their entries on the wire; ordered fields (`creators`) preserve
input order; numeric keys serialize as canonical JSON via
`cora.shared.canonical_json`.

The resulting bytes are returned via a `data:` URL inline today; a
production deployment that writes to object storage swaps the adapter
or extends this one with an upload step.

## Publish-once discipline

This artifact gets registered under a DOI once sealed, and a DOI-bearing
document is unretractable. Every field it carries must therefore be a
HISTORICAL STATEMENT ("this was so when published"), never a LIVE
PROMISE ("follow this and it will work"). A live promise rots the
moment the world moves, and CORA has no mechanism to revise bytes that
already carry a checksum a third party may have copied. Fields that
would only ever be a live promise (a fetch location, an access
procedure, an internal identifier the outside world cannot resolve)
are omitted outright rather than published in a form that will go
stale.

## What ships

  - Top-level JSON-LD with `@context` = the RO-Crate 1.2 context (the
    released Recommendation, not the superseded 1.2-DRAFT constant
    this adapter shipped with before RO-Crate 1.2 was finalized) plus
    the Workflow Run Crate profile.
  - Root `Dataset` entity for the Edition itself (`@id="./"`) with:
      - `name`: the Edition title
      - `datePublished`: the publication year (ISO 8601 reduced
        precision, year only; RFC 3339 has no year-only production)
      - `license`: the SPDX identifier when present
      - `publisher`: a reference to the Organization entity below
      - `creator`: list of `Person` entities (one per Creator, in
        input order in the JSON array; RO-Crate does not treat this
        as semantically ordered and may render the entries content-
        free, see "Known gaps" below)
      - `hasPart`: opaque list of `@id` references, one per DatasetRef
      - `identifier`: the `external_pid` value when published, absent
        entirely otherwise (no pre-DOI fallback value is emitted)
      - `conformsTo`: list of profile URIs
  - One `Organization` entity for the publisher, carrying:
      - `@id`: a document-local blank node
      - `identifier`: the Facility code, an internal code under no
        registered scheme (same class of gap as the creator id; ROR
        is the eventual fix, not built here)
  - One `Dataset` entry per `DatasetRef`, carrying:
      - `@id`: `urn:uuid:<dataset_id>` (stable; cross-system safe)
      - `sha256`: from the Distribution checksum (algorithm pinned to
        sha256 in the Dataset BC today)
      - `contentSize`: byte size as integer
      - `encodingFormat`: media type
      - `conformsTo`: encoding's `conforms_to` profile URIs (sorted)

    `contentUrl` is deliberately NOT emitted. The Distribution URI is
    either an internal `cora-capture-path://` locator that resolves
    for nobody outside CORA, or a real filesystem path that embeds
    operator-identifying detail (a lead scientist's surname has shown
    up in these paths). No value this field could hold is safe to
    publish permanently, and omitting it only for some rows would be
    worse than omitting it always: a reader could not tell "restricted"
    from "forgotten". The `@id` (`urn:uuid`) plus `sha256` already let
    anyone who obtains a candidate file prove it is this dataset; that
    is the stronger of the two links anyway; a path only says where to
    look and proves nothing about what you find. Do not add
    `conditionsOfAccess` or any other field describing how to obtain
    the bytes: an access mechanism is exactly the same live-promise
    shape and rots the same way (this project has already watched one
    storage tier carry three different names in a few months).

Creators are published without an `identifier`. `Creator.actor_id`
(see `cora.data.aggregates.edition.state.Creator`) is CORA's internal-
opaque Actor id, useless for external attribution since no outside
reader can resolve it, and dangerous to publish anyway: it is a stable
pseudonymous person-identifier that would let anyone correlate every
Edition credited to the same individual forever without ever learning
who that is. Pseudonymous is not anonymous, and nobody consented to
that linkage. Keeping it out is still correct; that harm outweighs the
one below, and no Edition has ever been published.

But the honest accounting stops there, and BLOCKS the first real
publication. The pinned RO-Crate 1.2 context declares no `@container`
for `creator`, so it maps to plain `schema:creator`: the JSON array is
an unordered RDF `@set`, not an ordered `@list`. Order is not carried.
The Person entity's `@id` is a document-scoped blank node
(`_:creator-0`), which is not an identifier a consumer may rely on for
anything, including position. And `affiliation` is optional on
`Creator`, so a Person with none serializes to exactly `{"@id":
"_:creator-0", "@type": "Person"}`: a content-free node indistinguishable
from any other creator with no affiliation. Four co-authors at one
institution are four identical, unordered, contentless nodes. The
artifact cannot credit anyone. The intended resolution is to resolve
`actor_id` to a name / ORCID via an `ActorLookup` port before
serializing (`Creator`'s own docstring already says so); that port has
not been built, and building it is a separate slice with its own
design. Until it ships, this adapter has no attribution to offer, and
that is a publication blocker, not a nicety.

External-pid awareness: when `external_pid is None` the artifact omits
`identifier` entirely (pre-DOI bytes). When `external_pid` is
supplied, the root entity gains `identifier` carrying the
scheme-prefixed value (e.g. `doi:10.5281/zenodo.1234567`). The sha256
of the two byte streams differs by design (this is the two-content-hash
model). The root `identifier` no longer falls back to `edition:<uuid>`
when no DOI is present: that value was an internal id under an
unregistered scheme, unresolvable outside CORA, the exact shape this
module's rule at the top says to omit rather than publish.

## Known gaps blocking first publication

Two things must ship before this adapter's output should back a real
DOI:

  1. Attribution (above): no name/ORCID resolution exists yet, so
     `creator` carries no information a reader can use.
  2. Validity: this module emits an RO-Crate `@graph` with a root
     `Dataset`, a publisher `Organization`, per-creator `Person`
     entities, and per-part `Dataset` entities, but RO-Crate requires
     a self-describing metadata descriptor entity (`@id` =
     `ro-crate-metadata.json`) carrying an `about` reference to the
     root entity, and it is the ROOT ENTITY's `conformsTo` (not
     `@context`) that a consumer reads to learn which profile version
     applies. Neither exists here. The output is RO-Crate-flavored
     JSON-LD, not a conformant RO-Crate. Adding the descriptor is its
     own slice; this module docstring recorded the gap, not a fix.
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

_ROCRATE_12_CONTEXT = "https://w3id.org/ro/crate/1.2/context"
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
        _ = edition_id  # no internal-id fallback published; see module docstring
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
