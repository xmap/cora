"""Pure-function PIDINST v1.0 serializer at the Equipment BC root.

`to_pidinst_record(view)` is the one-call entry point: it consumes a
hydrated `AssetPidinstView` and returns a frozen `PidinstRecord`
intermediate that both slice E's JSON-LD renderer and slice 6's
DataCite renderer consume directly.

The function is pure: no clock, no UUID generator, no Authorize port,
no I/O. Every value it returns is derived from the input view. This
matches CORA's "non-determinism in deciders" principle inverted:
serializers are pure by construction.

## Failure taxonomy (section 6 of the design memo)

Five exception classes, all inheriting from `PidinstSerializationError`,
all defined in `cora.equipment.errors` (the BC-application error
module) per the BC's domain-error placement fitness:

  - Four pre-construction errors raised by the property helpers
    before `PidinstRecord` is constructed, in PIDINST schema order:
      * `LandingPageMissingError` (property 3 source empty)
      * `AssetNameMissingError` (property 4 source empty)
      * `OwnerStateNotAvailableError` (property 5 source empty;
        always raised in slice C until slice D adds owner state)
      * `ManufacturerStateNotAvailableError` (property 6 source empty
        when `view.model is None`)
  - One construction-time invariant error raised from
    `PidinstRecord.__post_init__`: `PidinstRecordInvariantError`
    (raised in `_pidinst_types.py` from the dataclass `__post_init__`;
    re-imported here so callers can `except` once on the serializer
    module surface).

Failure ordering is PIDINST schema order per L9: the FIRST missing
mandatory property in property-number order raises; the serializer
does not collect diagnostics across multiple missing properties.

## Property mapping (section 5 of the design memo)

Each PIDINST v1.0 property has a `_build_<property>` helper. Helpers
run in property order so the first to raise wins.

  1 Identifier         -> `_build_identifier`         (URN fallback)
  2 SchemaVersion      -> constant `SchemaVersion.V1_0`
  3 LandingPage        -> `_build_landing_page`
  4 Name               -> `_build_name`
  5 Owner              -> `_build_owners`              (slice D)
  6 Manufacturer       -> `_build_manufacturers`
  7 Model              -> `_build_model`               (optional)
  8 Description        -> always `None`                (no source yet)
  9 InstrumentType     -> `_build_instrument_types`    (per Family)
 10 MeasuredVariable   -> always `()`                  (no source yet)
 11 Date               -> `_build_dates`               (lifecycle)
 12 RelatedIdentifier  -> always `()`                  (deferred)
 13 AlternateIdentifier -> `_build_alternate_identifiers`
 14 MeasurementTechnique -> always `()`                (no source yet)
"""

from datetime import datetime

from cora.equipment._pidinst_types import (
    AssetPidinstView,
    DateType,
    FixturePidinstView,
    InstrumentType,
    Manufacturer,
    MeasuredVariable,
    MeasurementTechnique,
    Owner,
    PidinstAlternateIdentifier,
    PidinstDate,
    PidinstIdentifier,
    PidinstIdentifierType,
    PidinstModel,
    PidinstRecord,
    PidinstRelationType,
    RelatedIdentifier,
    SchemaVersion,
)
from cora.equipment.errors import (
    AssetNameMissingError,
    FixtureLandingPageMissingError,
    FixtureManufacturerStateNotAvailableError,
    FixtureNameMissingError,
    FixtureOwnerStateNotAvailableError,
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
)
from cora.shared.identifier import PersistentIdentifierScheme

_URN_UUID_PREFIX = "urn:uuid:"
_FAMILY_URN_PREFIX = "urn:cora:family:"


def to_pidinst_record(view: AssetPidinstView) -> PidinstRecord:
    """Transform a hydrated Asset view into a CORA PIDINST v1.0 record.

    Pure synchronous function. Raises `PidinstSerializationError` (one
    of five concrete subclasses) on the first missing mandatory
    property encountered in PIDINST schema order. A successful return
    guarantees the returned `PidinstRecord` satisfies every structural
    invariant in section 6.7 of the design memo (the intermediate's
    `__post_init__` is the backstop, not the primary gate).

    Schema-order failure ordering per L9 + section 6.2: property 3
    LandingPage first, then 4 Name, then 5 Owner, then 6 Manufacturer.
    Property 1 Identifier never raises in slice C because the URN
    fallback always succeeds.

    `PidinstRecordInvariantError` is propagated bare from
    `PidinstRecord.__post_init__`; observability for that bug-class
    path lives in `features/get_asset_pidinst/handler.py` (L22
    forbids I/O here including logging).
    """
    _validate_landing_page(view)
    _validate_name(view)
    _validate_owner_state_available(view)
    _validate_manufacturer_state_available(view)

    return PidinstRecord(
        identifier=_build_identifier(view),
        schema_version=SchemaVersion.V1_0,
        landing_page=_build_landing_page(view),
        name=_build_name(view),
        publisher=_build_publisher(view),
        publication_year=_build_publication_year(view),
        owners=_build_owners(view),
        manufacturers=_build_manufacturers(view),
        model=_build_model(view),
        description=_build_description(view),
        instrument_types=_build_instrument_types(view),
        measured_variables=_build_measured_variables(view),
        dates=_build_dates(view),
        related_identifiers=_build_related_identifiers(view),
        alternate_identifiers=_build_alternate_identifiers(view),
        measurement_techniques=_build_measurement_techniques(view),
    )


def _validate_name(view: AssetPidinstView) -> None:
    if not view.asset_name or not view.asset_name.strip():
        raise AssetNameMissingError(view.asset_id)


def _validate_landing_page(view: AssetPidinstView) -> None:
    if not view.landing_page_url or not view.landing_page_url.strip():
        raise LandingPageMissingError(view.asset_id)


def _validate_owner_state_available(view: AssetPidinstView) -> None:
    # An empty owner tuple is the slice-C sentinel for "upstream
    # owner state not yet populated". Once slice D ships, the view's
    # projection populates owners from the registered AssetOwner VOs;
    # this raise then only fires when an Asset has been registered
    # without an owner.
    if not view.owners:
        raise OwnerStateNotAvailableError(view.asset_id)


def _validate_manufacturer_state_available(view: AssetPidinstView) -> None:
    if view.model is None:
        raise ManufacturerStateNotAvailableError(view.asset_id)


def _build_identifier(view: AssetPidinstView) -> PidinstIdentifier:
    if view.persistent_id is None:
        return PidinstIdentifier(
            value=f"{_URN_UUID_PREFIX}{view.asset_id}",
            scheme=PidinstIdentifierType.URN,
        )
    match view.persistent_id.scheme:
        case PersistentIdentifierScheme.DOI:
            wire_scheme = PidinstIdentifierType.DOI
        case PersistentIdentifierScheme.HANDLE:
            wire_scheme = PidinstIdentifierType.HANDLE
    return PidinstIdentifier(value=view.persistent_id.value, scheme=wire_scheme)


def _build_landing_page(view: AssetPidinstView) -> str:
    return view.landing_page_url


def _build_name(view: AssetPidinstView) -> str:
    return view.asset_name


def _build_publisher(view: AssetPidinstView) -> str:
    return view.publisher


def _build_publication_year(view: AssetPidinstView) -> int | None:
    return view.publication_year


def _build_owners(view: AssetPidinstView) -> tuple[Owner, ...]:
    return view.owners


def _build_manufacturers(view: AssetPidinstView) -> tuple[Manufacturer, ...]:
    model = view.model
    if model is None:
        # Defensive: validation above already raised, but the type
        # system requires this branch for `view.model: ModelPidinstView | None`.
        raise ManufacturerStateNotAvailableError(view.asset_id)
    return (
        Manufacturer(
            name=model.manufacturer_name,
            identifier=model.manufacturer_identifier,
            identifier_type=model.manufacturer_identifier_type,
        ),
    )


def _build_model(view: AssetPidinstView) -> PidinstModel | None:
    model = view.model
    if model is None:
        return None
    return PidinstModel(
        name=model.name,
        identifier=model.part_number,
        identifier_type="PartNumber",
    )


def _build_description(view: AssetPidinstView) -> str | None:
    return None


def _build_instrument_types(view: AssetPidinstView) -> tuple[InstrumentType, ...]:
    return tuple(
        InstrumentType(
            name=name,
            identifier=f"{_FAMILY_URN_PREFIX}{family_id}",
            identifier_type="URN",
        )
        for name, family_id in zip(view.family_names, view.family_ids, strict=True)
    )


def _build_measured_variables(view: AssetPidinstView) -> tuple[MeasuredVariable, ...]:
    return ()


def _build_dates(view: AssetPidinstView) -> tuple[PidinstDate, ...]:
    dates: list[PidinstDate] = []
    if view.commissioned_at is not None:
        dates.append(
            PidinstDate(
                value=_format_iso_date(view.commissioned_at),
                date_type=DateType.COMMISSIONED,
            )
        )
    if view.decommissioned_at is not None:
        dates.append(
            PidinstDate(
                value=_format_iso_date(view.decommissioned_at),
                date_type=DateType.DECOMMISSIONED,
            )
        )
    return tuple(dates)


def _build_related_identifiers(view: AssetPidinstView) -> tuple[RelatedIdentifier, ...]:
    # Slice C emits empty. Future slice picks the closed 20-value
    # `PidinstRelatedIdentifierType` enum and populates from
    # view.parent_id plus any linked-asset relations.
    return ()


def _build_alternate_identifiers(
    view: AssetPidinstView,
) -> tuple[PidinstAlternateIdentifier, ...]:
    sorted_alts = sorted(
        view.alternate_identifiers,
        key=lambda ai: (ai.kind.value, ai.value),
    )
    return tuple(
        PidinstAlternateIdentifier(value=alt.value, kind=alt.kind, name=None) for alt in sorted_alts
    )


def _build_measurement_techniques(
    view: AssetPidinstView,
) -> tuple[MeasurementTechnique, ...]:
    return ()


def _format_iso_date(value: datetime) -> str:
    return value.date().isoformat()


def to_fixture_pidinst_record(
    view: FixturePidinstView,
    *,
    landing_page_url: str,
    publisher: str,
) -> PidinstRecord:
    """Transform a hydrated Fixture view into a CORA PIDINST v1.0 record.

    Pure synchronous function. Sibling to `to_pidinst_record`; shares
    the kernel (PidinstRecord, all closed StrEnums, PidinstRecord
    invariants) but has its own error class taxonomy. Raises
    `FixturePidinstSerializationError` (one of four concrete subclasses)
    on the first missing mandatory property in PIDINST schema order.

    Schema-order failure ordering: LandingPage first, then Name, then
    Owner, then Manufacturer. Identifier never raises on the read path
    because the URN fallback always succeeds; the swap to DOI / Handle
    when `view.persistent_id` is set is structurally typed and cannot
    raise.

    `landing_page_url` and `publisher` are injected by the caller (the
    read-side view assembler) from per-deployment facility configuration;
    they are not aggregate state. `publication_year` is carried on the
    view because Fixture's `registered_at` IS aggregate state.

    The HasComponent `related_identifiers` list is populated from
    `view.components`: only components whose (scheme, value) are both
    non-None become `RelatedIdentifier` entries with
    `relation_type=HAS_COMPONENT` (PIDINST-faithful; the slice-6
    renderer substitutes to HasPart at the DataCite wire boundary per
    L3). Unminted components are OMITTED from `related_identifiers` per
    L27 and surface in the Description block instead.

    `PidinstRecordInvariantError` propagates unwrapped from
    `PidinstRecord.__post_init__`, mirroring the Asset side.
    """
    _validate_fixture_landing_page(view, landing_page_url)
    _validate_fixture_name(view)
    _validate_fixture_owner_state_available(view)
    _validate_fixture_manufacturer_state_available(view)

    return PidinstRecord(
        identifier=_build_fixture_identifier(view),
        schema_version=SchemaVersion.V1_0,
        landing_page=landing_page_url,
        name=view.name,
        publisher=publisher,
        publication_year=view.publication_year,
        owners=_build_fixture_owners(view),
        manufacturers=view.manufacturers,
        model=None,
        description=_build_fixture_description(view),
        instrument_types=(),
        measured_variables=(),
        dates=(),
        related_identifiers=_build_fixture_components(view),
        alternate_identifiers=(),
        measurement_techniques=(),
    )


def _validate_fixture_landing_page(view: FixturePidinstView, landing_page_url: str) -> None:
    if not landing_page_url or not landing_page_url.strip():
        raise FixtureLandingPageMissingError(view.fixture_id)


def _validate_fixture_name(view: FixturePidinstView) -> None:
    if not view.name or not view.name.strip():
        raise FixtureNameMissingError(view.fixture_id)


def _validate_fixture_owner_state_available(view: FixturePidinstView) -> None:
    if not view.owners:
        raise FixtureOwnerStateNotAvailableError(view.fixture_id)


def _validate_fixture_manufacturer_state_available(view: FixturePidinstView) -> None:
    if not view.manufacturers:
        raise FixtureManufacturerStateNotAvailableError(view.fixture_id)


def _build_fixture_identifier(view: FixturePidinstView) -> PidinstIdentifier:
    if view.persistent_id is None:
        return PidinstIdentifier(
            value=f"{_URN_UUID_PREFIX}{view.fixture_id}",
            scheme=PidinstIdentifierType.URN,
        )
    match view.persistent_id.scheme:
        case PersistentIdentifierScheme.DOI:
            wire_scheme = PidinstIdentifierType.DOI
        case PersistentIdentifierScheme.HANDLE:
            wire_scheme = PidinstIdentifierType.HANDLE
    return PidinstIdentifier(value=view.persistent_id.value, scheme=wire_scheme)


def _build_fixture_owners(view: FixturePidinstView) -> tuple[Owner, ...]:
    return tuple(
        Owner(
            name=raw.name.value,
            contact=raw.contact.value if raw.contact is not None else None,
            identifier=raw.identifier.value if raw.identifier is not None else None,
            identifier_type=(
                raw.identifier_type.value if raw.identifier_type is not None else None
            ),
        )
        for raw in view.owners
    )


def _build_fixture_components(view: FixturePidinstView) -> tuple[RelatedIdentifier, ...]:
    return tuple(
        RelatedIdentifier(
            value=component.value,
            identifier_type=component.scheme.value,
            relation_type=PidinstRelationType.HAS_COMPONENT,
        )
        for component in view.components
        if component.scheme is not None and component.value is not None
    )


def _build_fixture_description(view: FixturePidinstView) -> str | None:
    if not view.components:
        return None
    lines: list[str] = []
    for component in view.components:
        suffix = ""
        if component.scheme is None or component.value is None:
            suffix = " (no persistent identifier)"
        lines.append(f"- {component.name}{suffix}")
    return "\n".join(lines)
