"""Shared `AssetPidinstView` builders for the Equipment BC's PIDINST tests.

Per L21 / section 7.1 of the design memo. Four builders cover the
golden-file matrix (minimal, with-model, with-alt-ids, 2BM rotary
stage) and are reused across the serializer positive tests and the
byte-equal golden tests.

File name `_helpers.py` is the per-BC unit-test helper convention
enforced by `tests/architecture/test_helper_naming_convention.py`
(the BC-level analogue of `tests/unit/_helpers.py`); the per-aggregate
`_fixtures.py` precedent under `tests/unit/trust/visit/` lives one
directory deeper and falls outside that fitness.

A fifth golden case lands by adding a fifth builder here, not by
copy-pasting view construction into the test file.
"""

from datetime import UTC, datetime
from uuid import UUID

from cora.equipment._pidinst_types import (
    AssetPidinstView,
    ModelPidinstView,
    Owner,
)
from cora.equipment.aggregates.asset import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    AssetLifecycle,
)
from cora.equipment.aggregates.model import ManufacturerIdentifierType

_ASSET_ID = UUID("01900000-0000-7000-8000-00000000b001")
_MODEL_ID = UUID("01900000-0000-7000-8000-00000000b002")
_FAMILY_ID_ROTARY = UUID("01900000-0000-7000-8000-00000000b010")
_FAMILY_ID_PRECISION = UUID("01900000-0000-7000-8000-00000000b011")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000b020")

_COMMISSIONED_AT = datetime(2024, 5, 15, 9, 30, 0, tzinfo=UTC)
_DECOMMISSIONED_AT = datetime(2026, 4, 1, 14, 0, 0, tzinfo=UTC)

_PUBLISHER = "Argonne National Laboratory"
_LANDING_PAGE = f"https://cora.example/assets/{_ASSET_ID}"

_DEFAULT_OWNER = Owner(
    name="Advanced Photon Source",
    contact="aps-ops@anl.gov",
    identifier="https://ror.org/05gvnxz63",
    identifier_type="ROR",
)


def build_minimal_view() -> AssetPidinstView:
    """Asset with the smallest possible view that still serializes.

    Carries the four mandatory PIDINST properties (Identifier via URN
    fallback, SchemaVersion via constant, LandingPage, Name) plus the
    minimum-viable Owner and Model (Manufacturer source). No
    families, no alternate identifiers, no lifecycle dates.
    """
    return AssetPidinstView(
        asset_id=_ASSET_ID,
        asset_name="Rotary Stage A",
        landing_page_url=_LANDING_PAGE,
        lifecycle=AssetLifecycle.COMMISSIONED,
        alternate_identifiers=frozenset(),
        parent_id=None,
        family_names=(),
        family_ids=(),
        model=ModelPidinstView(
            name="ANT130-L",
            part_number="ANT130-L-RM",
            manufacturer_name="Aerotech",
            manufacturer_identifier=None,
            manufacturer_identifier_type=None,
        ),
        commissioned_at=None,
        decommissioned_at=None,
        publisher=_PUBLISHER,
        publication_year=None,
        owners=(_DEFAULT_OWNER,),
    )


def build_view_with_model() -> AssetPidinstView:
    """Asset with a single Family and a fully populated Model.

    Adds one Family (InstrumentType property) and a manufacturer
    identifier (ROR), plus a commissioned date. No alternate
    identifiers; no parent.
    """
    return AssetPidinstView(
        asset_id=_ASSET_ID,
        asset_name="Rotary Stage A",
        landing_page_url=_LANDING_PAGE,
        lifecycle=AssetLifecycle.ACTIVE,
        alternate_identifiers=frozenset(),
        parent_id=_PARENT_ID,
        family_names=("RotaryStage",),
        family_ids=(_FAMILY_ID_ROTARY,),
        model=ModelPidinstView(
            name="ANT130-L",
            part_number="ANT130-L-RM",
            manufacturer_name="Aerotech",
            manufacturer_identifier="https://ror.org/04bw7nh07",
            manufacturer_identifier_type=ManufacturerIdentifierType.ROR,
        ),
        commissioned_at=_COMMISSIONED_AT,
        decommissioned_at=None,
        publisher=_PUBLISHER,
        publication_year=_COMMISSIONED_AT.year,
        owners=(_DEFAULT_OWNER,),
    )


def build_view_with_alt_ids() -> AssetPidinstView:
    """Asset with two alternate identifiers (serial + inventory).

    Exercises the AlternateIdentifier property and the sort-by-
    `(kind, value)` rule in `_build_alternate_identifiers`. Same
    Model as `build_view_with_model`; adds two distinct alt-ids.
    """
    return AssetPidinstView(
        asset_id=_ASSET_ID,
        asset_name="Rotary Stage A",
        landing_page_url=_LANDING_PAGE,
        lifecycle=AssetLifecycle.ACTIVE,
        alternate_identifiers=frozenset(
            {
                AlternateIdentifier(
                    kind=AlternateIdentifierKind.SERIAL_NUMBER,
                    value="ANT130-12345",
                ),
                AlternateIdentifier(
                    kind=AlternateIdentifierKind.INVENTORY_NUMBER,
                    value="APS-2BM-RS-001",
                ),
            }
        ),
        parent_id=_PARENT_ID,
        family_names=("RotaryStage",),
        family_ids=(_FAMILY_ID_ROTARY,),
        model=ModelPidinstView(
            name="ANT130-L",
            part_number="ANT130-L-RM",
            manufacturer_name="Aerotech",
            manufacturer_identifier="https://ror.org/04bw7nh07",
            manufacturer_identifier_type=ManufacturerIdentifierType.ROR,
        ),
        commissioned_at=_COMMISSIONED_AT,
        decommissioned_at=None,
        publisher=_PUBLISHER,
        publication_year=_COMMISSIONED_AT.year,
        owners=(_DEFAULT_OWNER,),
    )


def build_view_2bm_rotary_stage() -> AssetPidinstView:
    """Realistic 2-BM rotary stage view.

    Two Families (RotaryStage + PrecisionStage), three alternate
    identifiers covering all three `AlternateIdentifierKind` values
    (SerialNumber, InventoryNumber, Other), both commissioned and
    decommissioned dates, full Manufacturer ROR.
    """
    return AssetPidinstView(
        asset_id=_ASSET_ID,
        asset_name="2-BM Sample Rotary Stage",
        landing_page_url=_LANDING_PAGE,
        lifecycle=AssetLifecycle.DECOMMISSIONED,
        alternate_identifiers=frozenset(
            {
                AlternateIdentifier(
                    kind=AlternateIdentifierKind.SERIAL_NUMBER,
                    value="ANT130-12345",
                ),
                AlternateIdentifier(
                    kind=AlternateIdentifierKind.INVENTORY_NUMBER,
                    value="APS-2BM-RS-001",
                ),
                AlternateIdentifier(
                    kind=AlternateIdentifierKind.OTHER,
                    value="LEGACY-RS-99",
                ),
            }
        ),
        parent_id=_PARENT_ID,
        family_names=("PrecisionStage", "RotaryStage"),
        family_ids=(_FAMILY_ID_PRECISION, _FAMILY_ID_ROTARY),
        model=ModelPidinstView(
            name="ANT130-L",
            part_number="ANT130-L-RM",
            manufacturer_name="Aerotech",
            manufacturer_identifier="https://ror.org/04bw7nh07",
            manufacturer_identifier_type=ManufacturerIdentifierType.ROR,
        ),
        commissioned_at=_COMMISSIONED_AT,
        decommissioned_at=_DECOMMISSIONED_AT,
        publisher=_PUBLISHER,
        publication_year=_COMMISSIONED_AT.year,
        owners=(_DEFAULT_OWNER,),
    )
