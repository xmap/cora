"""Unit tests for `CaptureScanIngestorDurableLocationLookup` and
`CaptureScanIngestorBinding`'s own validators.

`CaptureScanIngestorLocation` carries `supply_id` / `access_protocol` /
`durable` / `subdirectory` but not `root` -- root is the dict key of
`CaptureScanIngestorBinding.locations`. `CaptureScanIngestorDurableLocationLookup`
is the small adapter that reassembles the four `DurableLocationBinding`
properties from the validated config, structurally satisfying
`cora.api._durable_distribution_driver.DurableLocationLookup` without
`cora.infrastructure` importing `cora.api`.

The `_validate_camera_expectation` tests below cover the OTHER thing this
module validates: the both-or-neither pairing of `camera_channel_name` and
`expected_camera_label`, the producing-Asset cross-check's config surface
(see `cora.api._capture_scan_ingestor`'s module docstring).
"""

from uuid import uuid4

import pydantic
import pytest

from cora.infrastructure.capture_scan_ingestor_binding import (
    CaptureScanIngestorBinding,
    CaptureScanIngestorDurableLocationLookup,
    CaptureScanIngestorLocation,
    DurableLocationBinding,
)

pytestmark = pytest.mark.unit

_ACQUISITION_SUPPLY_ID = uuid4()
_DURABLE_SUPPLY_ID = uuid4()


def _binding_with_durable_location() -> CaptureScanIngestorBinding:
    return CaptureScanIngestorBinding(
        producing_asset_id=uuid4(),
        locations={
            "/local1/2BM": CaptureScanIngestorLocation(
                supply_id=_ACQUISITION_SUPPLY_ID, access_protocol="POSIX"
            ),
            "/gdata/dm/2BM": CaptureScanIngestorLocation(
                supply_id=_DURABLE_SUPPLY_ID,
                access_protocol="NFS",
                durable=True,
                subdirectory="data",
            ),
        },
    )


def test_durable_location_for_returns_the_durable_root_and_its_four_properties() -> None:
    lookup = CaptureScanIngestorDurableLocationLookup(
        {"2bmb-tomoscan": _binding_with_durable_location()}
    )

    location = lookup.durable_location_for("2bmb-tomoscan")

    assert location == DurableLocationBinding(
        root="/gdata/dm/2BM",
        supply_id=_DURABLE_SUPPLY_ID,
        access_protocol="NFS",
        subdirectory="data",
    )


def test_durable_location_for_an_unbound_capture_code_returns_none() -> None:
    lookup = CaptureScanIngestorDurableLocationLookup(
        {"2bmb-tomoscan": _binding_with_durable_location()}
    )

    assert lookup.durable_location_for("some-other-code") is None


def test_durable_location_for_a_binding_with_no_durable_location_returns_none() -> None:
    """A capture code may be bound (so `CaptureScanIngestor` can ingest
    the acquisition-tier copy) without any location marked durable yet;
    the durable sweep simply has nothing to find for it."""
    binding = CaptureScanIngestorBinding(
        producing_asset_id=uuid4(),
        locations={
            "/local1/2BM": CaptureScanIngestorLocation(
                supply_id=_ACQUISITION_SUPPLY_ID, access_protocol="POSIX"
            )
        },
    )
    lookup = CaptureScanIngestorDurableLocationLookup({"2bmb-tomoscan": binding})

    assert lookup.durable_location_for("2bmb-tomoscan") is None


def test_durable_location_for_reads_a_binding_with_no_subdirectory() -> None:
    """`subdirectory` is optional on the location; the reassembled
    `DurableLocationBinding` must carry `None` through rather than a
    fabricated default."""
    binding = CaptureScanIngestorBinding(
        producing_asset_id=uuid4(),
        locations={
            "/gdata/dm/2BM": CaptureScanIngestorLocation(
                supply_id=_DURABLE_SUPPLY_ID, access_protocol="NFS", durable=True
            )
        },
    )
    lookup = CaptureScanIngestorDurableLocationLookup({"2bmb-tomoscan": binding})

    location = lookup.durable_location_for("2bmb-tomoscan")

    assert location is not None
    assert location.subdirectory is None


def test_durable_location_for_against_an_empty_binding_map_returns_none() -> None:
    lookup = CaptureScanIngestorDurableLocationLookup({})

    assert lookup.durable_location_for("2bmb-tomoscan") is None


def _minimal_locations() -> dict[str, CaptureScanIngestorLocation]:
    return {
        "/local1/2BM": CaptureScanIngestorLocation(
            supply_id=_ACQUISITION_SUPPLY_ID, access_protocol="POSIX"
        )
    }


def test_camera_expectation_defaults_to_unset_and_is_valid() -> None:
    """Neither field set (today's shape, every already-deployed binding)
    is a full opt-out, not a config error."""
    binding = CaptureScanIngestorBinding(producing_asset_id=uuid4(), locations=_minimal_locations())

    assert binding.camera_channel_name is None
    assert binding.expected_camera_label is None


def test_camera_expectation_accepts_both_fields_set() -> None:
    binding = CaptureScanIngestorBinding(
        producing_asset_id=uuid4(),
        locations=_minimal_locations(),
        camera_channel_name="camera_selected",
        expected_camera_label="Camera Selected 0",
    )

    assert binding.camera_channel_name == "camera_selected"
    assert binding.expected_camera_label == "Camera Selected 0"


def test_camera_expectation_rejects_channel_name_without_label() -> None:
    with pytest.raises(pydantic.ValidationError):
        CaptureScanIngestorBinding(
            producing_asset_id=uuid4(),
            locations=_minimal_locations(),
            camera_channel_name="camera_selected",
        )


def test_camera_expectation_rejects_label_without_channel_name() -> None:
    with pytest.raises(pydantic.ValidationError):
        CaptureScanIngestorBinding(
            producing_asset_id=uuid4(),
            locations=_minimal_locations(),
            expected_camera_label="Camera Selected 0",
        )


def test_camera_expectation_rejects_an_empty_label() -> None:
    """Both-set-but-empty is not a valid opt-in: an empty label can never
    match a real recorded observation, so it would silently SKIP every
    candidate forever rather than confirm anything."""
    with pytest.raises(pydantic.ValidationError):
        CaptureScanIngestorBinding(
            producing_asset_id=uuid4(),
            locations=_minimal_locations(),
            camera_channel_name="camera_selected",
            expected_camera_label="",
        )
