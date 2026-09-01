"""Preflight read: check a beamline descriptor's declared channels against
the live control system.

`python -m cora.api.descriptor_preflight deployments/2-bm/beamline.yaml` walks a
descriptor for every control address it declares, anywhere in the tree (a
device, one of its constituents, or an enclosure), reads each one exactly
once, and reports whether it connects and what shape `ControlPort` sees it
as. `ADDRESS_FIELDS` below is the list of fields that carry one, and
`NOT_ADDRESS_FIELDS` the address-shaped ones deliberately left alone.

## Why this exists, and what makes it a real check

A descriptor is hand-authored prose plus addresses, reverse-engineered from a
controls config or a design document. The control system is a separate,
independently-maintained thing. When the descriptor says `2bma:m14` and the
IOC has no such record, the two genuinely disagree, and neither derives from
the other: that is the property [[project_independent_check_principle]] asks
for, and it is why this command is worth more than re-reading the YAML.

The drift it catches is the one that has already shipped three times on the
capture-watch PV set (see `cora.api.capture_watch_preflight`, "Why this
exists"): an address that moved, got renamed by an IOC rebuild, or reads as a
different wire shape than the descriptor's author assumed.

## What a green row does NOT mean

A connected channel proves a record answers to that name. It says nothing
about the claim the descriptor actually makes, which is that the record
drives the named device, on the named axis, in the named Family. A renumbered
motor crate answers on every one of its old names while every one of them now
points at different hardware, and this command reports a clean sweep.

So: a red row is evidence of drift, a green row is the absence of one narrow
kind of evidence. Confirming device identity stays an operator conversation,
which is what a descriptor's `confirm:` markers are for.

## Read-only by construction, and more strictly than the deployment

`build_control_port` is called with `writes_enabled=False` as a literal, NOT
with `Settings.control_writes_enabled`. `capture_watch_preflight` inherits the
deployment's write posture because it is a rehearsal for a path that runs
under it; this command has no write path at any setting, so inheriting a
writable posture would widen its blast radius for no gain.

## Footprint on the wire, which is not zero

Channel Access search is broadcast, and an unresolvable address is the noisy
case: it never answers, so the client keeps searching until the read times
out. A descriptor whose addresses are unconfirmed is exactly the input that
generates the most search traffic, and pointing this command at a beamline
whose staff have not agreed to it puts that traffic on their subnet and CORA's
host in their IOC client logs.

For a descriptor outside the deployment's own beamline, pin
`EPICS_CA_AUTO_ADDR_LIST=NO` and name a specific gateway in
`EPICS_CA_ADDR_LIST` at process start (per `EpicsCaControlPort`'s connection
model, those are read once and never revisited). Every search is then a
unicast to a named target and nothing reaches a subnet you were not invited
onto.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import yaml

from cora.infrastructure.config import Settings
from cora.operation.adapters.control_port_config import build_control_port
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    NoAdapterForAddressError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.ports.control_port import ControlPort

_EXIT_CLEAN = 0
_EXIT_MISMATCH = 1

# The descriptor fields that carry a readable control-system address.
# `Device.pv` and `Enclosure.permit_signal` are declared in the schema
# (scripts/beamline_descriptor.py); the rest are open key-specs living in
# `model_extra`, so the schema cannot enumerate them and this set is the only
# place they are written down. Guarded by
# `test_address_fields_cover_the_descriptor_corpus`, which fails when a
# descriptor introduces an address-shaped key that is in neither this set nor
# `NOT_ADDRESS_FIELDS`.
ADDRESS_FIELDS: frozenset[str] = frozenset(
    {
        "pv",
        "virtual_pv",
        "axis_channels",
        "permit_signal",
        "readback_pv",
        "slot_labels_pv",
        "camera_rotation_pv",
        "per_lens_focus_pv",
        "temperature_pv",
    }
)

# Address-SHAPED descriptor keys that are deliberately never read, each for its
# own reason. Listed rather than omitted so the corpus guard can tell a
# considered exclusion from a field nobody has looked at yet.
#
#   epics_handle   provenance, not an address: the controls section uses it to
#                  say which crate or IOC serves a device, so its values are
#                  ranges (`2bmb:m100-m102`), globs (`2bmb:m*`) and hostnames
#                  (`JenaNV200D`). Several would pass `_shape_of` as addresses
#                  and fail at read, reporting drift that is not there.
#   ip_addresses   network endpoints for a device's own controller, not
#                  Channel Access addresses. Nothing here can read them, and
#                  reaching for them would be a port scan.
#   channels       an integer count of a bimorph mirror's electrodes.
NOT_ADDRESS_FIELDS: frozenset[str] = frozenset({"epics_handle", "ip_addresses", "channels"})

# A descriptor's address-shaped dict uses this key to say "none yet, ask
# an operator". It carries prose, never an address.
_CONFIRM_KEY = "confirm"

ChannelShape = Literal["address", "prefix", "unresolved", "opaque"]


@dataclass(frozen=True)
class DescriptorChannel:
    """One address the descriptor declares, classified before any read.

    `shape` decides whether this entry is readable at all, and the three
    non-readable shapes are reported rather than dropped: a silently skipped
    entry makes a partial sweep look like a complete one.

      - `address`: an address-shaped token, the only shape that gets read.
      - `prefix`: a trailing-colon device prefix (`usxLAX:`). Names a family
        of records, is not itself one, so there is nothing to `read`.
      - `unresolved`: a `confirm:` marker standing in for an address nobody has
        supplied yet.
      - `opaque`: a token in an address field that does not look like one
        (2-BM's `gate_valves: [GV1, GV2, GV3]` names valves, not records).
        Reported so a genuine typo cannot hide behind the same shape.
    """

    location: str
    field_name: str
    key: str | None
    token: str | None
    shape: ChannelShape

    @property
    def label(self) -> str:
        """`field[key]` when the address is one entry in a named-axis map,
        bare `field` otherwise."""
        return f"{self.field_name}[{self.key}]" if self.key is not None else self.field_name


@dataclass(frozen=True)
class ChannelReading:
    """One channel's read outcome. `detail` carries the adapter's own
    message on a failure and stays empty on success."""

    channel: DescriptorChannel
    ok: bool
    connected: bool
    kind: str | None = None
    value: object = None
    units: str | None = None
    element_count: int | None = None
    detail: str = ""

    def render(self) -> str:
        head = f"{self.channel.token} ({self.channel.location}, {self.channel.label})"
        if not self.connected:
            return f"BAD  {head}: {self.detail}"
        shape = self.kind or "?"
        if self.element_count is not None:
            shape = f"{shape}[{self.element_count}]"
        units = f" {self.units}" if self.units else ""
        return f"OK   {head}: {shape} = {self.value!r}{units}"


@dataclass
class PreflightReport:
    """A descriptor's full sweep: what was read, and what was not readable.

    `skipped` is carried beside `readings` rather than folded into it because
    the two answer different questions. A skipped entry is a fact about the
    DESCRIPTOR (it declares no address here), a reading is a fact about the
    CONTROL SYSTEM. Counting them together would let a descriptor full of
    `confirm:` markers report a high pass rate having contacted almost
    nothing, which is the specific way this command could mislead.
    """

    readings: list[ChannelReading] = field(default_factory=list[ChannelReading])
    skipped: list[DescriptorChannel] = field(default_factory=list[DescriptorChannel])

    @property
    def problem(self) -> bool:
        return any(not reading.ok for reading in self.readings)


def _walk(node: object, location: str, out: list[DescriptorChannel]) -> None:
    """Collect address fields from anywhere in the descriptor tree.

    Recursive over the raw YAML rather than over the Pydantic model: the
    schema lives in `scripts/`, which is deliberately free of `cora.*`
    imports, and the address fields nest (a device's `constituents` are
    devices). Structure-blind recursion needs to know only the field names,
    which `ADDRESS_FIELDS` pins and a fitness test holds to the schema.

    The two `cast`s carry parsed-YAML shape, which the loader cannot type:
    `safe_load` returns `Any`, and narrowing it by `isinstance` alone leaves
    the element types unknown. Keys in a descriptor are always strings;
    values stay `object` and every use site narrows before touching them.
    """
    if isinstance(node, dict):
        mapping = cast("dict[str, object]", node)
        here = mapping.get("name")
        current = here if isinstance(here, str) and here else location
        for key, value in mapping.items():
            if key in ADDRESS_FIELDS:
                _classify(value, current, key, out)
            else:
                _walk(value, current, out)
    elif isinstance(node, list):
        for item in cast("list[object]", node):
            _walk(item, location, out)


def _classify(value: object, location: str, field_name: str, out: list[DescriptorChannel]) -> None:
    """Turn one address field's value into zero or more classified entries.

    Three value shapes occur, and all three must be reached: a bare string
    (`pv: "2bma:m44"`), a named-axis map (`pv: {x_in: ..., y_top: ...}`), and
    a bare list (`slot_labels_pv: [...]`). The list case is easy to miss
    because it is rare, and missing it drops addresses silently, which is the
    one failure this command must not have.
    """
    if isinstance(value, str):
        out.append(_entry(location, field_name, None, value))
        return
    if isinstance(value, list):
        for item in cast("list[object]", value):
            if isinstance(item, str):
                out.append(_entry(location, field_name, None, item))
        return
    if isinstance(value, dict):
        for key, inner in cast("dict[str, object]", value).items():
            if key == _CONFIRM_KEY:
                out.append(
                    DescriptorChannel(
                        location=location,
                        field_name=field_name,
                        key=None,
                        token=None,
                        shape="unresolved",
                    )
                )
            elif isinstance(inner, str):
                out.append(_entry(location, field_name, key, inner))
            elif isinstance(inner, list):
                for item in cast("list[object]", inner):
                    if isinstance(item, str):
                        out.append(_entry(location, field_name, key, item))


def _entry(location: str, field_name: str, key: str | None, token: str) -> DescriptorChannel:
    return DescriptorChannel(
        location=location,
        field_name=field_name,
        key=key,
        token=token,
        shape=_shape_of(token),
    )


def _shape_of(token: str) -> ChannelShape:
    """Classify an address token by its own text.

    A colon is the discriminator: every EPICS address in the fleet's
    descriptors carries at least one, and the tokens that carry none are
    device labels sharing an address field (`GV1`), not addresses. This is a
    TEXT test, not a reachability one; a well-formed address for a record
    that does not exist still classifies `address` and fails at read, which
    is the outcome that carries information.
    """
    stripped = token.strip()
    if not stripped:
        return "opaque"
    if stripped.endswith(":"):
        return "prefix"
    return "address" if ":" in stripped else "opaque"


def descriptor_channels(raw: Mapping[str, object]) -> list[DescriptorChannel]:
    """Every address a parsed descriptor declares, in document order."""
    out: list[DescriptorChannel] = []
    _walk(raw, location="(descriptor)", out=out)
    return out


def load_descriptor(path: Path) -> dict[str, object]:
    """Read a descriptor's raw YAML mapping.

    Deliberately does NOT go through `scripts/beamline_descriptor.load`: this
    command reads addresses, and a descriptor whose schema has drifted is
    exactly one worth probing rather than refusing.
    """
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return cast("dict[str, object]", raw)


async def preflight_read_channels(
    *,
    control_port: ControlPort,
    channels: list[DescriptorChannel],
) -> PreflightReport:
    """Read every `address`-shaped token once, reporting the rest as skipped.

    Deduplicated by token: a descriptor names the same prefix or record from
    several devices, and re-reading it would multiply this command's wire
    footprint for no extra information. Every occurrence still gets its own
    reported row, so a shared address's failure is visible at each site that
    depends on it.
    """
    report = PreflightReport()
    seen: dict[str, ChannelReading] = {}
    for channel in channels:
        if channel.shape != "address" or channel.token is None:
            report.skipped.append(channel)
            continue
        cached = seen.get(channel.token)
        reading = (
            _rebind(cached, channel)
            if cached is not None
            else await _read_one(control_port, channel)
        )
        seen.setdefault(channel.token, reading)
        report.readings.append(reading)
    return report


def _rebind(reading: ChannelReading, channel: DescriptorChannel) -> ChannelReading:
    """Re-attach a cached reading to a second declaration site."""
    return ChannelReading(
        channel=channel,
        ok=reading.ok,
        connected=reading.connected,
        kind=reading.kind,
        value=reading.value,
        units=reading.units,
        element_count=reading.element_count,
        detail=reading.detail,
    )


async def _read_one(control_port: ControlPort, channel: DescriptorChannel) -> ChannelReading:
    assert channel.token is not None
    try:
        measurement = await control_port.read(channel.token)
    except NoAdapterForAddressError:
        return ChannelReading(
            channel=channel,
            ok=False,
            connected=False,
            detail="no CONTROL_PORT_ROUTES prefix covers this address",
        )
    except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
        return ChannelReading(channel=channel, ok=False, connected=False, detail=str(exc))
    except ControlValueCoercionError as exc:
        return ChannelReading(
            channel=channel,
            ok=False,
            connected=True,
            detail=f"adapter could not decode the reading: {exc}",
        )
    element_count = (
        len(measurement.value)
        if measurement.kind == "Array" and hasattr(measurement.value, "__len__")
        else None
    )
    return ChannelReading(
        channel=channel,
        ok=True,
        connected=True,
        kind=measurement.kind,
        value=measurement.value,
        units=measurement.units,
        element_count=element_count,
    )


def render_report(report: PreflightReport, *, path: Path) -> list[str]:
    """The printed report, as lines, so a test can assert on it without
    capturing stdout."""
    lines = [f"descriptor preflight: {path}"]
    if not report.readings and not report.skipped:
        lines.append("  (descriptor declares no control-system addresses)")
        return lines
    for reading in report.readings:
        lines.append(f"  {reading.render()}")
    for shape in ("prefix", "unresolved", "opaque"):
        group = [entry for entry in report.skipped if entry.shape == shape]
        if not group:
            continue
        lines.append(f"  {len(group)} skipped ({shape}):")
        for entry in group:
            token = entry.token if entry.token is not None else "(no address declared)"
            lines.append(f"    {token} ({entry.location}, {entry.label})")
    ok_count = sum(1 for reading in report.readings if reading.ok)
    lines.append(
        f"{ok_count}/{len(report.readings)} channels read, {len(report.skipped)} not readable"
    )
    return lines


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from `main` so tests can invoke it without
    building a real `ControlPort`."""
    parser = argparse.ArgumentParser(
        prog="python -m cora.api.descriptor_preflight",
        description=(
            "Read every control-system address a beamline descriptor declares, "
            "once, and report whether it connects and what shape CORA's "
            "ControlPort sees it as. Read-only; changes nothing, at any "
            "CONTROL_WRITES_ENABLED setting. A failed row is evidence the "
            "descriptor has drifted from the control system; a clean row "
            "proves only that a record answers to that name, never that it "
            "drives the device the descriptor names."
        ),
    )
    parser.add_argument("descriptor", type=Path, help="path to a deployments/<id>/beamline.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path: Path = args.descriptor
    channels = descriptor_channels(load_descriptor(path))
    # writes_enabled=False as a literal, not Settings.control_writes_enabled:
    # this command has no write path to enable. See the module docstring.
    control_port = build_control_port(Settings().control_port_routes, writes_enabled=False)

    async def _run() -> int:
        try:
            report = await preflight_read_channels(control_port=control_port, channels=channels)
            for line in render_report(report, path=path):
                print(line)
            return _EXIT_MISMATCH if report.problem else _EXIT_CLEAN
        finally:
            # ControlPort Protocol does not declare aclose (it's
            # adapter-optional); getattr + suppress mirrors
            # capture_watch_preflight's own teardown for the same port.
            aclose = getattr(control_port, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
