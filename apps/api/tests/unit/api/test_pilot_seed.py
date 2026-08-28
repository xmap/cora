"""pilot_seed's pure parts: identity stability, report semantics, CLI.

The database-touching flow lives in the integration tier
(test_pilot_seed_postgres); this tier pins what must never drift
without ceremony: the deterministic Asset key format (a change orphans
every previously seeded instance), the exit-code taxonomy operators
and CI gate on, and the CLI defaults.
"""

from uuid import UUID

import pytest

from cora.api.pilot_seed import (
    ASSET_SEED_NAMESPACE,
    RECIPE_SEED_NAMESPACE,
    _Report,  # pyright: ignore[reportPrivateUsage]
    asset_seed_id,
    build_parser,
    recipe_seed_id,
)

pytestmark = pytest.mark.unit


def test_asset_seed_id_repeated_calls_return_the_same_id() -> None:
    first = asset_seed_id("aps", "2-bm", "Camera")
    second = asset_seed_id("aps", "2-bm", "Camera")
    assert first == second


def test_asset_seed_id_pins_the_key_format() -> None:
    """The exact uuid5 over "facility:beamline:asset:name". Changing the
    namespace or the format orphans every previously seeded instance,
    so this pin must only ever move with a migration story."""
    from uuid import uuid5

    assert asset_seed_id("aps", "2-bm", "Camera") == uuid5(
        ASSET_SEED_NAMESPACE, "aps:2-bm:asset:Camera"
    )


def test_asset_seed_id_distinguishes_beamlines_and_names() -> None:
    ids = {
        asset_seed_id("aps", "2-bm", "Camera"),
        asset_seed_id("aps", "7-bm", "Camera"),
        asset_seed_id("aps", "2-bm", "Mirror"),
        asset_seed_id("maxiv", "2-bm", "Camera"),
    }
    assert len(ids) == 4


def test_report_all_exists_leaves_seeded_and_failed_unset() -> None:
    report = _Report(lines=[])
    report.note("exists", "asset 2-BM")
    report.note("exists", "supply analysis tier")
    assert report.seeded is False
    assert report.failed is False


def test_report_any_seed_marks_seeded() -> None:
    report = _Report(lines=[])
    report.note("exists", "asset 2-BM")
    report.note("seeded", "supply analysis tier")
    assert report.seeded is True
    assert report.failed is False


def test_report_any_error_marks_failed() -> None:
    report = _Report(lines=[])
    report.note("seeded", "asset 2-BM")
    report.note("error", "family Camera", "lacks Capturing")
    assert report.failed is True


def test_parser_defaults_name_the_pilot() -> None:
    args = build_parser().parse_args([])
    assert args.facility_code == "cora"
    assert args.beamline == "2-bm"
    assert args.camera_family_name == "Camera"
    assert args.dry_run is False


def test_parser_accepts_overrides() -> None:
    args = build_parser().parse_args(
        ["--facility-code", "aps", "--camera-name", "Oryx", "--dry-run"]
    )
    assert args.facility_code == "aps"
    assert args.camera_name == "Oryx"
    assert args.dry_run is True


def test_parser_shutter_and_acquisition_camera_defaults_do_not_collide_with_camera_name() -> None:
    """--camera-name and --acquisition-camera-name must never share a
    default: asset_seed_id hashes only on name, so identical defaults
    would derive the SAME id for what are meant to be two distinct
    Device Assets."""
    args = build_parser().parse_args([])
    assert args.shutter_name == "StationShutter"
    assert args.acquisition_camera_name == "AcquisitionCamera"
    assert args.acquisition_camera_name != args.camera_name


def test_parser_accepts_shutter_and_acquisition_camera_overrides() -> None:
    args = build_parser().parse_args(
        ["--shutter-name", "Shutter1", "--acquisition-camera-name", "Camera"]
    )
    assert args.shutter_name == "Shutter1"
    assert args.acquisition_camera_name == "Camera"


def test_parser_shutter_command_and_status_addresses_are_distinct_records() -> None:
    """The close COMMAND and the status READBACK must never be the same
    PV. `BeamBlockingM` is a status leaf every other reader in this
    codebase treats as read-only (the permit observer, the beam
    availability lookup, the Run safety envelope); TomoScan's own
    deployed autosave writes `CloseEPICSC` and reads `BeamBlockingM`
    back. Collapsing the two would point the setpoint at a record that
    does not command the shutter, and the check would then confirm a
    write that never actuated."""
    args = build_parser().parse_args([])
    assert args.shutter_close_address == "S02BM-PSS:SBS:CloseEPICSC"
    assert args.shutter_status_address == "S02BM-PSS:SBS:BeamBlockingM"
    assert args.shutter_close_address != args.shutter_status_address


def test_parser_dark_field_capture_defaults_are_bounded() -> None:
    args = build_parser().parse_args([])
    assert args.detector_address == "2bmSP1:cam1"
    assert args.dark_field_frames == 10
    assert args.dark_field_dwell_s == 0.05


def test_parser_accepts_dark_field_address_overrides() -> None:
    args = build_parser().parse_args(
        [
            "--shutter-close-address",
            "SIM:SBS:CloseEPICSC",
            "--shutter-status-address",
            "SIM:SBS:BeamBlockingM",
            "--detector-address",
            "SIM:cam1",
            "--dark-field-frames",
            "3",
        ]
    )
    assert args.shutter_close_address == "SIM:SBS:CloseEPICSC"
    assert args.shutter_status_address == "SIM:SBS:BeamBlockingM"
    assert args.detector_address == "SIM:cam1"
    assert args.dark_field_frames == 3


def test_asset_seed_namespace_is_the_locked_constant() -> None:
    assert UUID("6c1f4a52-8f2e-4bb0-9d59-1a4c9be1a23d") == ASSET_SEED_NAMESPACE


def test_recipe_seed_id_repeated_calls_return_the_same_id() -> None:
    first = recipe_seed_id("aps", "2-bm", "method", "dark_field")
    second = recipe_seed_id("aps", "2-bm", "method", "dark_field")
    assert first == second


def test_recipe_seed_id_pins_the_key_format() -> None:
    """The exact uuid5 over "facility:beamline:kind:name". Changing the
    namespace or the format orphans every previously seeded ladder
    instance, so this pin must only ever move with a migration story."""
    from uuid import uuid5

    assert recipe_seed_id("aps", "2-bm", "method", "dark_field") == uuid5(
        RECIPE_SEED_NAMESPACE, "aps:2-bm:method:dark_field"
    )


def test_recipe_seed_id_distinguishes_kind_and_name() -> None:
    ids = {
        recipe_seed_id("aps", "2-bm", "method", "dark_field"),
        recipe_seed_id("aps", "2-bm", "method", "flat_field"),
        recipe_seed_id("aps", "2-bm", "practice", "dark_field"),
        recipe_seed_id("maxiv", "2-bm", "method", "dark_field"),
    }
    assert len(ids) == 4


def test_recipe_seed_namespace_is_distinct_from_asset_seed_namespace() -> None:
    assert RECIPE_SEED_NAMESPACE != ASSET_SEED_NAMESPACE


def test_recipe_seed_namespace_is_the_locked_constant() -> None:
    assert UUID("48eb0d48-8fc2-482c-9e9e-d3547b1ff37b") == RECIPE_SEED_NAMESPACE


def test_main_parses_argv_and_returns_the_ceremony_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cora.api import pilot_seed

    received: dict[str, object] = {}

    async def fake_ceremony(**kwargs: object) -> int:
        received.update(kwargs)
        return 2

    monkeypatch.setattr(pilot_seed, "seed_pilot_beamline", fake_ceremony)

    exit_code = pilot_seed.main(["--camera-name", "Oryx", "--dry-run"])

    assert exit_code == 2
    assert received["camera_name"] == "Oryx"
    assert received["dry_run"] is True


def test_main_forwards_shutter_and_acquisition_camera_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cora.api import pilot_seed

    received: dict[str, object] = {}

    async def fake_ceremony(**kwargs: object) -> int:
        received.update(kwargs)
        return 0

    monkeypatch.setattr(pilot_seed, "seed_pilot_beamline", fake_ceremony)

    pilot_seed.main(["--shutter-name", "Shutter1", "--acquisition-camera-name", "Camera"])

    assert received["shutter_name"] == "Shutter1"
    assert received["acquisition_camera_name"] == "Camera"
