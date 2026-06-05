"""Frozen-dataclass intermediate, input view, and closed enums for PIDINST v1.0.

The PIDINST integration carves the asset-to-DataCite path into two
modules at the Equipment BC root plus one in `errors.py`:

  - `_pidinst_types.py` (this file): the intermediate `PidinstRecord`
    tree, the `AssetPidinstView` input view, and the four closed
    StrEnums (`SchemaVersion`, `DateType`, `PidinstIdentifierType`,
    `PidinstRelationType`).
  - `_pidinst_serializer.py`: the `to_pidinst_record(view)` pure
    function plus its property helpers.
  - `cora.equipment.errors`: the five `PidinstSerializationError`
    subclasses (four pre-construction errors plus
    `PidinstRecordInvariantError`). Co-located with `UnauthorizedError`
    per the BC's domain-error placement fitness; the architecture
    test `test_no_domain_errors_outside_aggregate_or_errors_module`
    forbids error class definitions inside private slice modules.

Splitting keeps the slice-6 mint adapter importable against the
intermediate types alone without dragging in serializer logic.

The `_types` suffix avoids collision with the `_*_body.py` Pydantic
wire-mirror convention used by `_alternate_identifier_body`,
`_drawing_body`, `_placement_body`. The intermediate here is a
frozen-dataclass tree, not a Pydantic wire model.

Forward-complete per L7 of the design memo: every recommended PIDINST
v1.0 property is represented on `PidinstRecord` even when slice C
cannot populate it. Slices D and E populate fields on the unchanged
type; only the serializer function is feature-additive.

L27 cross-BC import boundary: this module MAY import from
`cora.equipment.aggregates.*` and MUST NOT import from any other BC.
Enforced by `test_pidinst_serializer_imports_no_other_bc`.

L28 typing rigor: NO `Any` and NO `dict[str, Any]` anywhere in this
file. Every dataclass field carries a concrete type. Enforced by
`test_pidinst_record_has_no_any_or_dict_str_any_annotations`.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    AssetLifecycle,
    AssetOwner,
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.equipment.aggregates.model import ManufacturerIdentifierType
from cora.equipment.errors import PidinstRecordInvariantError


class SchemaVersion(StrEnum):
    """The PIDINST schema version emitted by the serializer.

    Pinned to v1.0 per L2 of the design memo. A v1.1 serializer ships
    as a sibling function with its own constant; this enum never gains
    new members.
    """

    V1_0 = "1.0"


class DateType(StrEnum):
    """PIDINST date-type controlled vocabulary.

    Spec literal is `DeCommissioned` (intercap), not `Decommissioned`;
    see PIDINST v1.0 schema.rst line 106. Mapping this verbatim avoids
    a translation step at the DataCite-renderer boundary in slice 6.
    """

    COMMISSIONED = "Commissioned"
    DECOMMISSIONED = "DeCommissioned"


class PidinstIdentifierType(StrEnum):
    """The four spec-allowed PIDINST identifier types.

    Forward-complete per L7. Slice C emits only `URN` (the asset
    URN fallback per L16); slice E adds `DOI` once `Asset.persistent_id`
    lands. `HANDLE` and `URL` are reserved for D-PERSISTID-2: PIDINST
    v1.1 identifierType is free text per spec note [#identtype], but
    CORA constrains its emitters to this closed four-value set as a
    policy decision.
    """

    HANDLE = "Handle"
    DOI = "DOI"
    URN = "URN"
    URL = "URL"


class PidinstRelationType(StrEnum):
    """The 10-value PIDINST v1.0 property 12.2 `relationType` closed CV.

    Forward-complete per L7 / L19. Slice C emits an empty
    `related_identifiers` tuple, but the enum ships now so the deferred
    slice has nothing to add at the kernel. The DataCite renderer
    (slice 6) remaps `IsComponentOf` to DataCite `IsPartOf` and
    `HasComponent` to DataCite `HasPart` per [#reltype].
    """

    IS_DESCRIBED_BY = "IsDescribedBy"
    IS_NEW_VERSION_OF = "IsNewVersionOf"
    IS_PREVIOUS_VERSION_OF = "IsPreviousVersionOf"
    HAS_COMPONENT = "HasComponent"
    IS_COMPONENT_OF = "IsComponentOf"
    REFERENCES = "References"
    HAS_METADATA = "HasMetadata"
    WAS_USED_IN = "WasUsedIn"
    IS_IDENTICAL_TO = "IsIdenticalTo"
    IS_ATTACHED_TO = "IsAttachedTo"


@dataclass(frozen=True)
class ModelPidinstView:
    """Subset of `Model` aggregate state needed for PIDINST serialization.

    Constructed by slice E's projection from a hydrated `Model`
    snapshot. `manufacturer_identifier_type` mirrors the source field
    name on `Manufacturer` and reuses the closed
    `ManufacturerIdentifierType` enum directly from
    `cora.equipment.aggregates.model.state`.
    """

    name: str
    part_number: str
    manufacturer_name: str
    manufacturer_identifier: str | None
    manufacturer_identifier_type: ManufacturerIdentifierType | None


@dataclass(frozen=True)
class PidinstIdentifier:
    """PIDINST v1.0 property 1: the persistent identifier of the instrument.

    Slice C wraps `view.asset_id` as `urn:uuid:<asset_id>` with
    `scheme=PidinstIdentifierType.URN` per L16. Slice E swaps to the
    DOI once `view.persistent_id` is set. Slice 6 ignores property 1
    entirely because DataCite reads the DOI from the URL path of the
    PUT request.
    """

    value: str
    scheme: PidinstIdentifierType


@dataclass(frozen=True)
class Owner:
    """PIDINST v1.0 property 5: a body owning or curating the instrument.

    Owner-pairing invariant: `identifier` and `identifier_type` are
    both set or both `None`. Mirrors `Model.Manufacturer`'s own pairing
    enforcement (see `cora.equipment.aggregates.model.state.Manufacturer`
    lines 378-399). Enforced in `__post_init__` here so the invariant
    holds on the intermediate even before `PidinstRecord.__post_init__`
    runs.

    `identifier_type` is intentionally `str | None`, NOT a closed enum
    (per F6.3 of `project-pidinst-operational-patterns-research`):
    PIDINST `ownerIdentifierType` is free text in the spec, unlike its
    sibling field on `Manufacturer` which is constrained to ROR / GRID
    / ISNI. ROR is the de facto operator choice but the spec leaves
    the door open. Slice 6's DataCite renderer maps each owner to a
    `contributors[i]` entry with `contributorType: HostingInstitution`.
    """

    name: str
    contact: str | None = None
    identifier: str | None = None
    identifier_type: str | None = None

    def __post_init__(self) -> None:
        has_id = self.identifier is not None
        has_type = self.identifier_type is not None
        if has_id != has_type:
            raise PidinstRecordInvariantError(
                f"Owner.identifier and Owner.identifier_type must be both set or "
                f"both None (got identifier={self.identifier!r}, "
                f"identifier_type={self.identifier_type!r})"
            )


@dataclass(frozen=True)
class AssetPidinstView:
    """Hydrated read-model view consumed by `to_pidinst_record`.

    Carries Asset state plus its joined neighbors (Model, Family
    display names, lifecycle dates, Owner tuple, publisher). Constructed
    by slice E's projection from Asset + Model + Family streams (and
    upstream owner state once slice D lands) plus per-deployment
    configuration. For slice C tests, builders in
    `_pidinst_view_fixtures.py` construct it directly.

    `family_names` and `family_ids` are PRE-SORTED by the projection
    using `(display_name, id)`; the serializer honors the view's
    tuple order without re-sorting (asserted by
    `test_to_pidinst_record_with_unsorted_family_tuple_preserves_view_order`).

    `commissioned_at` and `decommissioned_at` are derived by slice E's
    projection from lifecycle events; the serializer does not read
    event streams. Asset is a lifecycle aggregate, not a template
    aggregate, but follows the broader projection-denormalization
    pattern visible on `AssetSummaryProjection` and the `get_method`
    handler Path C docstring.

    `owners` is `tuple[Owner, ...]`; an empty tuple is the slice-C
    sentinel for "upstream owner state not yet populated by slice D".
    The serializer raises `OwnerStateNotAvailableError` on empty so
    slice C never silently emits a PIDINST-invalid record. Slice D
    ships `Asset.owner` and slice E's projection populates this field;
    the raise then only fires when an Asset has been registered without
    an owner.

    `publisher` and `publication_year` are supplied by per-deployment
    configuration via slice E. DataCite makes both mandatory at mint
    time. `publication_year` is the year the asset was first
    commissioned (or `None` if not commissioned yet); the projection
    derives it and supplies it on the view, the serializer never
    derives it from `commissioned_at`. See L5 / L7 forward-complete
    principle.
    """

    asset_id: UUID
    asset_name: str
    landing_page_url: str
    lifecycle: AssetLifecycle
    alternate_identifiers: frozenset[AlternateIdentifier]
    parent_id: UUID | None
    family_names: tuple[str, ...]
    family_ids: tuple[UUID, ...]
    model: ModelPidinstView | None
    commissioned_at: datetime | None
    decommissioned_at: datetime | None
    publisher: str
    publication_year: int | None
    owners: tuple[Owner, ...]
    persistent_id: PersistentIdentifier | None = None


@dataclass(frozen=True)
class FixtureComponentRef:
    """One bound Asset under a Fixture, with PID-or-fallback resolution.

    `component_id` is the bound Asset's id (the Fixture's
    `SlotAssetBinding.asset_id`). `scheme` and `value` carry the
    bound Asset's `PersistentIdentifier` decomposed into primitives;
    both are None when the Asset has not been minted yet. The
    serializer skips unminted components from the HAS_COMPONENT
    related_identifiers tuple per L27 (HasComponent requires a
    PID-bearing target); unminted components still appear in this
    tuple so the Description block can surface the full composition.

    `name` is the bound Asset's display name; used by the Description
    builder to surface unminted and decommissioned components.

    Skip-unminted semantics live in the assembler / serializer, NOT
    in this dataclass. The dataclass is a plain data substrate.
    """

    component_id: UUID
    scheme: PersistentIdentifierScheme | None
    value: str | None
    name: str


@dataclass(frozen=True)
class FixturePidinstView:
    """Hydrated read-model view consumed by `to_fixture_pidinst_record`.

    Separate dataclass from `AssetPidinstView` per Lock 1. Carries the
    Fixture-tier rollup of bound Assets' PIDINST-relevant facets,
    populated by the read-side view assembler from Fixture + Asset +
    Model streams.

    `owners` is the UNION of bound Assets' owners deduplicated by
    (name, identifier) and sorted by name per L7. An empty tuple is
    the sentinel for "no bound Asset carries any owners"; the
    serializer raises `FixtureOwnerStateNotAvailableError` so the
    Fixture-tier record never silently emits PIDINST-invalid output.

    `manufacturers` is the UNION of bound Assets' Models' manufacturers
    deduplicated by (name, identifier) and sorted by name per L9
    (revised). The cascade is model-mediated: Asset does NOT carry a
    manufacturers field, the Model catalog tier is the source of truth.
    An empty tuple triggers `FixtureManufacturerStateNotAvailableError`
    at the serializer.

    `components` is one entry per bound Asset, ordered deterministically
    by the assembler. The serializer emits HasComponent
    `RelatedIdentifier` entries ONLY for components with non-None
    (scheme, value) per L27.

    `publication_year` is typed `int` (non-optional) because Fixture is
    single-event-genesis; the assembler narrows
    `fixture.registered_at.year` to int via the FixtureRegistered fold
    invariant. Diverges from `AssetPidinstView` (where commissioned_at
    may be None pre-commissioning) as a Fixture-specific simplification.

    `persistent_id` is None until a future `assign_fixture_persistent_id`
    write slice lands; the read route surfaces None as the absent
    optional field per the PIDINST v1.0 schema.
    """

    fixture_id: UUID
    name: str
    persistent_id: PersistentIdentifier | None
    owners: tuple[AssetOwner, ...]
    manufacturers: tuple["Manufacturer", ...]
    components: tuple[FixtureComponentRef, ...]
    publication_year: int


@dataclass(frozen=True)
class Manufacturer:
    """PIDINST v1.0 property 6: the body manufacturing the instrument.

    Reuses `ManufacturerIdentifierType` from
    `cora.equipment.aggregates.model.state` unchanged: the closed
    enum is the same scheme set (ROR / GRID / ISNI) on the catalog
    tier. `identifier` and `identifier_type` are independently optional
    on this VO; the source-aggregate `Manufacturer` already enforces
    the pairing invariant on `Model.manufacturer` (see
    `InvalidManufacturerIdentifierPairingError`), and the
    `_build_manufacturers` helper only constructs this VO from
    `view.model.manufacturer_*` fields which already came through
    that gate.
    """

    name: str
    identifier: str | None = None
    identifier_type: ManufacturerIdentifierType | None = None


@dataclass(frozen=True)
class PidinstModel:
    """PIDINST v1.0 property 7: the model / type identification of the instrument.

    Per L17: `name` mirrors `Model.name`, `identifier` mirrors
    `Model.part_number`, and `identifier_type` is the literal string
    `"PartNumber"`. No composition or joining; each PIDINST
    subproperty has exactly one CORA source field.
    """

    name: str
    identifier: str
    identifier_type: str = "PartNumber"


@dataclass(frozen=True)
class InstrumentType:
    """PIDINST v1.0 property 9: a typology category for the instrument.

    Slice C emits one entry per Family in the view, using
    `urn:cora:family:<uuid>` as the identifier. A future slice may
    resolve to an external taxonomy (NCIT, EDAM-bioimaging, ...)
    once a mapping is curated.
    """

    name: str
    identifier: str | None = None
    identifier_type: str = "URN"


@dataclass(frozen=True)
class MeasuredVariable:
    """PIDINST v1.0 property 10: a physical quantity the instrument measures.

    Slice C emits an empty tuple. The source field is not yet on Asset
    / Capability / Family and inventing one here would create churn.
    """

    name: str


@dataclass(frozen=True)
class PidinstDate:
    """PIDINST v1.0 property 11: a date marker on the instrument lifecycle.

    `value` is an ISO 8601 date string. Slice E's projection owns the
    lifecycle-event-to-timestamp derivation; the serializer reads
    `view.commissioned_at` and `view.decommissioned_at` and formats
    them.
    """

    value: str
    date_type: DateType


@dataclass(frozen=True)
class RelatedIdentifier:
    """PIDINST v1.0 property 12: a related identifier (parent asset, etc.).

    Slice C emits an empty tuple. A future slice picks the closed
    20-value `PidinstRelatedIdentifierType` enum and populates this
    from `view.parent_id` plus any other linked-asset relations.
    `relation_type` uses the forward-complete `PidinstRelationType`
    enum already in this module.
    """

    value: str
    identifier_type: str
    relation_type: PidinstRelationType


@dataclass(frozen=True)
class PidinstAlternateIdentifier:
    """PIDINST v1.0 property 13: an alternate identifier under a known scheme.

    Reuses `AlternateIdentifierKind` from
    `cora.equipment.aggregates.asset.state` (values `SerialNumber`,
    `InventoryNumber`, `Other`, verbatim from PIDINST v1.0 Table 1)
    rather than introducing a parallel
    `PidinstAlternateIdentifierType` enum, per L13. The architecture
    fitness test
    `test_pidinst_alternate_identifier_kind_reuses_existing_enum`
    enforces this.

    `name` is PIDINST 13.2 `alternateIdentifierName`, optional free
    text per the spec ("mostly useful if alternateIdentifierType is
    Other"). The upstream `AlternateIdentifier` VO does not yet carry
    a label; slice C always emits `None`. Forward-complete per L7.

    The kind-isinstance invariant is enforced in `__post_init__` so
    that callers passing a stray string (a likely slice-6 mistake)
    fail loudly at construction.
    """

    value: str
    kind: AlternateIdentifierKind
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AlternateIdentifierKind):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise PidinstRecordInvariantError(
                f"PidinstAlternateIdentifier.kind must be AlternateIdentifierKind, "
                f"got {type(self.kind).__name__}: {self.kind!r}"
            )


@dataclass(frozen=True)
class MeasurementTechnique:
    """PIDINST v1.0 property 14: a measurement technique applied by the instrument.

    Slice C emits an empty tuple. The source field is not yet on
    Asset / Capability / Family.
    """

    name: str


@dataclass(frozen=True)
class PidinstRecord:
    """The CORA intermediate representation of a PIDINST v1.0 record.

    Frozen-dataclass tree returned by `to_pidinst_record`. Slice E's
    JSON-LD renderer and slice 6's DataCite renderer consume this
    record directly; neither parses JSON.

    Forward-complete per L7: every PIDINST v1.0 property has a field
    here even when slice C cannot populate it. `owners` is mandatory
    by PIDINST cardinality but slice C raises `OwnerStateNotAvailableError`
    before reaching construction until slice D ships; the field stays
    typed `tuple[Owner, ...]` so slice D plugs in without touching the
    intermediate type.

    `publisher` and `publication_year` are carried on the intermediate
    because DataCite makes both mandatory at mint time, while PIDINST
    only flags them as unresolved per [#publisher] and [#pubyear]. They
    are sourced by the view from facility configuration: slice E
    supplies `publisher` from per-deployment config and
    `publication_year` from the year the asset was first commissioned
    (or `None` if not commissioned yet).

    `__post_init__` enforces the nine structural invariants listed in
    section 6.7 of the design memo. Each violation raises
    `PidinstRecordInvariantError` explicitly; bare `assert` is
    intentionally not used because it is stripped under `python -O`.
    """

    identifier: PidinstIdentifier
    schema_version: SchemaVersion
    landing_page: str
    name: str
    publisher: str
    publication_year: int | None
    owners: tuple[Owner, ...]
    manufacturers: tuple[Manufacturer, ...]
    model: PidinstModel | None
    description: str | None
    instrument_types: tuple[InstrumentType, ...]
    measured_variables: tuple[MeasuredVariable, ...]
    dates: tuple[PidinstDate, ...]
    related_identifiers: tuple[RelatedIdentifier, ...]
    alternate_identifiers: tuple[PidinstAlternateIdentifier, ...]
    measurement_techniques: tuple[MeasurementTechnique, ...]

    def __post_init__(self) -> None:
        if not self.identifier.value:
            raise PidinstRecordInvariantError("identifier.value must be non-empty")
        if self.schema_version is not SchemaVersion.V1_0:
            raise PidinstRecordInvariantError(
                f"schema_version must be SchemaVersion.V1_0, got {self.schema_version!r}"
            )
        if not self.landing_page:
            raise PidinstRecordInvariantError("landing_page must be non-empty")
        if not self.name:
            raise PidinstRecordInvariantError("name must be non-empty")
        if len(self.owners) < 1:
            raise PidinstRecordInvariantError(
                "owners must contain at least one Owner (PIDINST property 5 cardinality 1-n)"
            )
        if len(self.manufacturers) < 1:
            raise PidinstRecordInvariantError(
                "manufacturers must contain at least one Manufacturer "
                "(PIDINST property 6 cardinality 1-n)"
            )
        for date in self.dates:
            if date.date_type not in {DateType.COMMISSIONED, DateType.DECOMMISSIONED}:
                raise PidinstRecordInvariantError(
                    f"PidinstDate.date_type must be in {{Commissioned, DeCommissioned}}, "
                    f"got {date.date_type!r}"
                )
        for alt in self.alternate_identifiers:
            if not isinstance(alt.kind, AlternateIdentifierKind):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise PidinstRecordInvariantError(
                    f"PidinstAlternateIdentifier.kind must be AlternateIdentifierKind, "
                    f"got {type(alt.kind).__name__}"
                )
        # Owner.identifier / identifier_type pairing is enforced in
        # Owner.__post_init__ (section 6.7 invariant #9); the record-level
        # backstop would only fire on a deliberately bypassed VO (object.__setattr__).
