"""Unit tests for the descriptor preflight command.

Two halves, and they fail for different reasons. The extraction half is pure
and runs against inline descriptor fragments plus the real
`deployments/*/beamline.yaml` corpus: it fails when an address the descriptor
declares is not reached. The read half drives `preflight_read_channels` against a
scripted fake `ControlPort` (read-only; this command never calls `.write()`
or `.subscribe()`, so the fake implements `.read()` only): it fails when a
substrate outcome is reported as something other than what it was.

The corpus guard (`test_address_fields_cover_the_descriptor_corpus`) is the
one that earns its place over time. Both of the extraction defects found
while writing this command -- five address fields the walk never reached, and
a bare-list value shape it dropped silently -- were found by ranging over the
real corpus rather than over an example, per
[[project_aggregate_coverage_blindness]].
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
import yaml

from cora.api.descriptor_preflight import (
    _EXIT_CLEAN,  # pyright: ignore[reportPrivateUsage]
    _EXIT_MISMATCH,  # pyright: ignore[reportPrivateUsage]
    ADDRESS_FIELDS,
    NOT_ADDRESS_FIELDS,
    DescriptorChannel,
    PreflightReport,
    build_parser,
    descriptor_channels,
    load_descriptor,
    preflight_read_channels,
    render_report,
)
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    Measurement,
    NoAdapterForAddressError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_T = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEPLOYMENTS = _REPO_ROOT / "deployments"

# Keys whose name looks like it could carry a control address. Intentionally
# broad: the guard's job is to make a new address-bearing field impossible to
# add without a human classifying it, so over-matching costs one line in
# NOT_ADDRESS_FIELDS and under-matching costs a silently unprobed channel.
_ADDRESS_SHAPED = ("pv", "channel", "signal", "address", "attr", "handle", "tango", "epics")


def _reading(value: object, kind: str = "Scalar", units: str | None = None) -> Measurement:
    return Measurement(
        value=value,
        kind=kind,  # type: ignore[arg-type]
        quality="Good",
        produced_at=_T,
        units=units,
    )


class _FakeControlPort:
    """Scripted `read()`-only fake. The probe never writes or subscribes."""

    def __init__(self, script: dict[str, Measurement | Exception]) -> None:
        self._script = script
        self.reads: list[str] = []

    async def read(self, address: str) -> Measurement:
        self.reads.append(address)
        outcome = self._script[address]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _channels(raw: Mapping[str, object]) -> list[DescriptorChannel]:
    return descriptor_channels(raw)


def _descriptors() -> list[Path]:
    return sorted(_DEPLOYMENTS.glob("*/beamline.yaml"))


def _corpus_keys(paths: list[Path]) -> set[str]:
    """Every mapping key appearing anywhere in the given descriptors."""
    keys: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in cast("dict[str, object]", node).items():
                keys.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in cast("list[object]", node):
                walk(item)

    for path in paths:
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return keys


# --- extraction -------------------------------------------------------


def test_descriptor_channels_reads_a_bare_string_address() -> None:
    found = _channels({"optics": {"devices": [{"name": "Flag", "pv": "2bma:m44"}]}})
    assert [(c.token, c.shape, c.location) for c in found] == [("2bma:m44", "address", "Flag")]


def test_descriptor_channels_reads_each_axis_of_a_named_axis_map() -> None:
    found = _channels(
        {"optics": {"devices": [{"name": "Slit", "pv": {"x_in": "2bma:m14", "y_top": "2bma:m15"}}]}}
    )
    assert [(c.key, c.token) for c in found] == [("x_in", "2bma:m14"), ("y_top", "2bma:m15")]


def test_descriptor_channels_reads_a_bare_list_address() -> None:
    """The shape that was silently dropped: an address field whose value is a
    list, with no axis map around it."""
    found = _channels(
        {"det": {"devices": [{"name": "Sel", "slot_labels_pv": ["2bm:X:L0", "2bm:X:L1"]}]}}
    )
    assert [c.token for c in found] == ["2bm:X:L0", "2bm:X:L1"]


def test_descriptor_channels_reads_a_list_nested_in_an_axis_map() -> None:
    found = _channels({"g": {"devices": [{"name": "Slit", "pv": {"x": ["2bma:m11", "2bma:m12"]}}]}})
    assert [(c.key, c.token) for c in found] == [("x", "2bma:m11"), ("x", "2bma:m12")]


def test_descriptor_channels_descends_into_constituents() -> None:
    found = _channels(
        {
            "g": {
                "devices": [
                    {
                        "name": "Tower",
                        "pv": "2bmb:m24",
                        "constituents": [{"name": "Hexapod", "pv": "2bmHXP:m1"}],
                    }
                ]
            }
        }
    )
    assert [(c.location, c.token) for c in found] == [
        ("Tower", "2bmb:m24"),
        ("Hexapod", "2bmHXP:m1"),
    ]


def test_descriptor_channels_reads_an_enclosure_permit_signal() -> None:
    found = _channels({"enclosures": [{"name": "2-BM-A", "permit_signal": "S02BM-PSS:StaA:Sec"}]})
    assert [(c.location, c.field_name, c.shape) for c in found] == [
        ("2-BM-A", "permit_signal", "address")
    ]


@pytest.mark.parametrize(
    ("token", "shape"),
    [
        ("2bma:m14", "address"),
        ("2bmb:table3.X", "address"),
        ("usxLAX:", "prefix"),
        ("2bm:MCTOptics:", "prefix"),
        ("GV1", "opaque"),
        ("", "opaque"),
        ("   ", "opaque"),
    ],
)
def test_descriptor_channels_classifies_an_address_by_its_own_text(token: str, shape: str) -> None:
    found = _channels({"g": {"devices": [{"name": "D", "pv": token}]}})
    assert found[0].shape == shape


def test_descriptor_channels_marks_a_confirm_marker_unresolved_carrying_no_address() -> None:
    found = _channels({"g": {"devices": [{"name": "Mono", "pv": {"confirm": "MONO-1"}}]}})
    assert [(c.shape, c.token) for c in found] == [("unresolved", None)]


def test_descriptor_channels_ignores_a_field_that_is_not_an_address_field() -> None:
    found = _channels({"g": {"devices": [{"name": "D", "epics_handle": "2bmb:m*", "note": "x"}]}})
    assert found == []


def test_descriptor_channels_attributes_an_address_to_the_nearest_named_ancestor() -> None:
    found = _channels({"grp": {"stage": "sample", "devices": [{"name": "Stage", "pv": "2bmb:m1"}]}})
    assert found[0].location == "Stage"


# --- the corpus guard -------------------------------------------------


def test_address_fields_cover_the_descriptor_corpus() -> None:
    """Every address-shaped key in every descriptor is classified.

    Ranges over the whole corpus, not one descriptor: a field used only by
    i22 is exactly the one a 2-BM-shaped example would miss. A new key here
    is not a failure to fix by widening the pattern; it is a question --
    is this a readable channel or not -- answered by putting the key in
    ADDRESS_FIELDS or in NOT_ADDRESS_FIELDS with its reason.
    """
    descriptors = _descriptors()
    assert descriptors, "no descriptors found; the guard would pass vacuously"
    keys = _corpus_keys(descriptors)

    address_shaped = {key for key in keys if any(tok in key.lower() for tok in _ADDRESS_SHAPED)}
    unclassified = address_shaped - ADDRESS_FIELDS - NOT_ADDRESS_FIELDS
    assert not unclassified, (
        f"descriptor key(s) {sorted(unclassified)} look like control addresses but are in neither "
        "ADDRESS_FIELDS nor NOT_ADDRESS_FIELDS. Decide which, in cora.api.descriptor_preflight."
    )


def test_address_fields_and_not_address_fields_are_disjoint() -> None:
    assert not (ADDRESS_FIELDS & NOT_ADDRESS_FIELDS)


def test_every_declared_address_field_is_used_by_some_descriptor() -> None:
    """An address field nobody declares any more is dead weight in the walk."""
    keys = _corpus_keys(_descriptors())
    assert not (ADDRESS_FIELDS - keys), f"unused address field(s): {sorted(ADDRESS_FIELDS - keys)}"


def test_the_pilot_descriptor_yields_readable_channels() -> None:
    """2-BM is the live pilot: if the walk reaches nothing there, every green
    report this command prints is green because it probed nothing."""
    found = descriptor_channels(load_descriptor(_DEPLOYMENTS / "2-bm" / "beamline.yaml"))
    readable = [c for c in found if c.shape == "address"]
    assert len(readable) > 50
    assert all(c.token for c in readable)


# --- reading ----------------------------------------------------------


async def test_preflight_read_channels_reports_a_healthy_channel_ok() -> None:
    channel = _channels({"g": {"devices": [{"name": "D", "pv": "2bma:m1"}]}})
    port = _FakeControlPort({"2bma:m1": _reading(1.5, units="mm")})
    report = await preflight_read_channels(control_port=port, channels=channel)  # type: ignore[arg-type]
    assert [(r.ok, r.kind, r.value, r.units) for r in report.readings] == [
        (True, "Scalar", 1.5, "mm")
    ]
    assert not report.problem


@pytest.mark.parametrize(
    "error",
    [
        ControlNotConnectedError("2bma:m1"),
        ControlTimeoutError("2bma:m1", 5.0),
        ControlAccessDeniedError("2bma:m1"),
    ],
)
async def test_preflight_read_channels_reports_an_unreachable_channel_as_disconnected(
    error: Exception,
) -> None:
    channel = _channels({"g": {"devices": [{"name": "D", "pv": "2bma:m1"}]}})
    port = _FakeControlPort({"2bma:m1": error})
    report = await preflight_read_channels(control_port=port, channels=channel)  # type: ignore[arg-type]
    reading = report.readings[0]
    assert (reading.ok, reading.connected) == (False, False)
    assert str(error) in reading.detail
    assert report.problem


async def test_preflight_read_channels_reports_a_coercion_failure_as_connected_but_bad() -> None:
    """The distinction matters: the record exists and answered, so this is a
    wire-shape problem, not the descriptor naming something absent."""
    channel = _channels({"g": {"devices": [{"name": "D", "pv": "2bma:m1"}]}})
    port = _FakeControlPort({"2bma:m1": ControlValueCoercionError("2bma:m1", "bytes", "Scalar")})
    report = await preflight_read_channels(control_port=port, channels=channel)  # type: ignore[arg-type]
    reading = report.readings[0]
    assert (reading.ok, reading.connected) == (False, True)
    assert "could not decode" in reading.detail


async def test_preflight_read_channels_names_a_missing_route_rather_than_a_dead_pv() -> None:
    channel = _channels({"g": {"devices": [{"name": "D", "pv": "other:m1"}]}})
    port = _FakeControlPort({"other:m1": NoAdapterForAddressError("other:m1")})
    report = await preflight_read_channels(control_port=port, channels=channel)  # type: ignore[arg-type]
    assert "CONTROL_PORT_ROUTES" in report.readings[0].detail


async def test_preflight_read_channels_carries_an_arrays_element_count() -> None:
    channel = _channels({"g": {"devices": [{"name": "D", "pv": "2bma:m1"}]}})
    port = _FakeControlPort({"2bma:m1": _reading((1, 2, 3), kind="Array")})
    report = await preflight_read_channels(control_port=port, channels=channel)  # type: ignore[arg-type]
    assert report.readings[0].element_count == 3


async def test_preflight_read_channels_skips_every_non_channel_shape_without_reading() -> None:
    raw = {
        "g": {
            "devices": [
                {"name": "A", "pv": "2bma:m1"},
                {"name": "B", "pv": "2bmSP1:"},
                {"name": "C", "pv": {"confirm": "OPT-1"}},
                {"name": "D", "pv": {"gate_valves": ["GV1"]}},
            ]
        }
    }
    port = _FakeControlPort({"2bma:m1": _reading(1.0)})
    report = await preflight_read_channels(control_port=port, channels=_channels(raw))  # type: ignore[arg-type]
    assert port.reads == ["2bma:m1"]
    assert sorted(c.shape for c in report.skipped) == ["opaque", "prefix", "unresolved"]


async def test_preflight_reads_a_repeated_address_once_but_reports_each_site() -> None:
    raw = {
        "g": {
            "devices": [
                {"name": "A", "pv": "2bma:m1"},
                {"name": "B", "pv": "2bma:m1"},
            ]
        }
    }
    port = _FakeControlPort({"2bma:m1": _reading(7.0)})
    report = await preflight_read_channels(control_port=port, channels=_channels(raw))  # type: ignore[arg-type]
    assert port.reads == ["2bma:m1"]
    assert [r.channel.location for r in report.readings] == ["A", "B"]
    assert all(r.ok and r.value == 7.0 for r in report.readings)


async def test_preflight_read_channels_propagates_a_cached_failure_to_each_site() -> None:
    raw = {"g": {"devices": [{"name": "A", "pv": "x:1"}, {"name": "B", "pv": "x:1"}]}}
    port = _FakeControlPort({"x:1": ControlNotConnectedError("down")})
    report = await preflight_read_channels(control_port=port, channels=_channels(raw))  # type: ignore[arg-type]
    assert [r.ok for r in report.readings] == [False, False]
    assert port.reads == ["x:1"]


# --- reporting --------------------------------------------------------


async def test_render_counts_readings_and_skips_separately() -> None:
    """A descriptor of pure `confirm:` markers must not report a clean sweep:
    the pass rate is over what was READ, and the skips are stated beside it."""
    raw = {"g": {"devices": [{"name": "A", "pv": {"confirm": "Q-1"}}, {"name": "B", "pv": "s:"}]}}
    port = _FakeControlPort({})
    report = await preflight_read_channels(control_port=port, channels=_channels(raw))  # type: ignore[arg-type]
    lines = render_report(report, path=Path("d.yaml"))
    assert "0/0 channels read, 2 not readable" in lines[-1]
    assert not report.problem


def test_render_report_states_a_descriptor_declared_no_addresses() -> None:
    lines = render_report(PreflightReport(), path=Path("d.yaml"))
    assert "declares no control-system addresses" in lines[1]


async def test_render_groups_skips_by_shape() -> None:
    raw = {"g": {"devices": [{"name": "A", "pv": "s:"}, {"name": "B", "pv": {"gv": ["GV1"]}}]}}
    port = _FakeControlPort({})
    report = await preflight_read_channels(control_port=port, channels=_channels(raw))  # type: ignore[arg-type]
    text = "\n".join(render_report(report, path=Path("d.yaml")))
    assert "1 skipped (prefix):" in text
    assert "1 skipped (opaque):" in text


async def test_render_labels_a_named_axis_address_with_its_axis() -> None:
    raw = {"g": {"devices": [{"name": "Slit", "pv": {"x_in": "2bma:m14"}}]}}
    port = _FakeControlPort({"2bma:m14": _reading(1.0)})
    report = await preflight_read_channels(control_port=port, channels=_channels(raw))  # type: ignore[arg-type]
    assert "pv[x_in]" in report.readings[0].render()


# --- CLI --------------------------------------------------------------


def test_build_parser_requires_a_descriptor_path() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_build_parser_accepts_a_descriptor_path() -> None:
    assert build_parser().parse_args(["deployments/2-bm/beamline.yaml"]).descriptor == Path(
        "deployments/2-bm/beamline.yaml"
    )


def test_load_descriptor_rejects_a_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "d.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top level must be a mapping"):
        load_descriptor(path)


def test_exit_codes_are_distinct() -> None:
    assert _EXIT_CLEAN != _EXIT_MISMATCH
