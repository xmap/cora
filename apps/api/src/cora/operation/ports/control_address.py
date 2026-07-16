"""ControlAddress: the typed-sum control-system address space.

`ControlPort` (the caller-facing Protocol) stays `str`-surfaced because the
Conductor receives raw address strings from recipe steps and cannot know a
substrate: whether `2bma:rot` is EPICS Channel Access, `2bma:cam1:image` is
EPICS pvAccess, or `id19/bsh/1/state` is a Tango attribute is a property of the
deployment ROUTE table (`ControlPortRoute.substrate` + prefix), never of the
string itself. Substrate identity therefore lives in the
`ControlPortRegistry`, and the registry is the one place that can turn a raw
string into a substrate-typed `ControlAddress` (at route-match time).

This module is that typed address space: the sum
`EpicsPvAddress | TangoAttributeAddress | InMemoryAddress` plus the single
`parse_control_address(raw, substrate)` dispatch the registry calls. The
substrate adapters (`SubstrateControlPort` implementations) consume the typed
variants so they never re-parse a raw string per call: the Tango adapter reads
`address.device` / `address.attribute` instead of splitting a TRL on every read.

Per [[project_control_port_generalization_research]] the sum discriminates
substrate FAMILY (EPICS vs Tango vs in-memory), not transport within a family:
both EPICS Channel Access and pvAccess use `EpicsPvAddress` because a PV name is
the same shape on either transport; CA-vs-PVA stays a route decision. OPC UA is
deferred (no `OpcUaNodeAddress` variant until a real OPC UA adapter lands); the
sum extends by adding a variant plus a `parse_control_address` arm.

Every variant round-trips to its original string via `str(...)` so structured
logging + `Measurement.name` breadcrumbs stay stable across the typed boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cora.infrastructure.control_port_route import Substrate


class MalformedControlAddressError(Exception):
    """A raw address string does not satisfy its substrate's address syntax.

    Raised by a variant's `parse` (e.g. a Tango TRL with no attribute
    segment). The registry lets it propagate the same way it propagates
    `NoAdapterForAddressError`: a configuration / recipe gap surfaced at the
    routing boundary rather than deep in an adapter's wire call. Carries the
    raw address so operators can spot the offending value from logs alone.
    """

    def __init__(self, raw: str, substrate: str, reason: str) -> None:
        super().__init__(
            f"Control address {raw!r} is malformed for substrate {substrate!r}: {reason}"
        )
        self.raw = raw
        self.substrate = substrate
        self.reason = reason


@dataclass(frozen=True)
class EpicsPvAddress:
    """An EPICS process-variable name, used by both Channel Access and pvAccess.

    A PV name is atomic (no CORA-side sub-structure); the adapter hands it to
    aioca / p4p verbatim. The CA-vs-PVA choice is a route decision, not an
    address-syntax one, so both EPICS adapters accept this same variant.
    """

    pv: str

    def __str__(self) -> str:
        return self.pv

    @staticmethod
    def parse(raw: str, substrate: str) -> EpicsPvAddress:
        if not raw:
            raise MalformedControlAddressError(raw, substrate, "empty PV name")
        return EpicsPvAddress(raw)


@dataclass(frozen=True)
class TangoAttributeAddress:
    """A Tango attribute TRL split into its device name and attribute.

    `id19/bsh/1/state` -> `device="id19/bsh/1"`, `attribute="state"`. Splitting
    happens once here (at the registry boundary) instead of on every adapter
    call, so a malformed TRL fails as a `MalformedControlAddressError` before
    any proxy work.
    """

    device: str
    attribute: str

    def __str__(self) -> str:
        return f"{self.device}/{self.attribute}"

    @staticmethod
    def parse(raw: str, substrate: str) -> TangoAttributeAddress:
        device, sep, attribute = raw.rpartition("/")
        if not sep or not device or not attribute:
            raise MalformedControlAddressError(
                raw, substrate, "expected 'device/family/member/attribute'"
            )
        return TangoAttributeAddress(device, attribute)


@dataclass(frozen=True)
class InMemoryAddress:
    """An opaque address for the in-memory adapter (tests + opt-out routes).

    No substrate syntax to validate beyond non-emptiness; the in-memory
    adapter keys its dict store by the raw string.
    """

    address: str

    def __str__(self) -> str:
        return self.address

    @staticmethod
    def parse(raw: str, substrate: str) -> InMemoryAddress:
        if not raw:
            raise MalformedControlAddressError(raw, substrate, "empty address")
        return InMemoryAddress(raw)


ControlAddress = EpicsPvAddress | TangoAttributeAddress | InMemoryAddress
"""The typed control-system address space consumed by `SubstrateControlPort`.

Extends by adding a variant (e.g. a future `OpcUaNodeAddress`) plus a matching
arm in `parse_control_address`.
"""


def parse_control_address(raw: str, substrate: Substrate) -> ControlAddress:
    """Parse a raw address string into the `ControlAddress` for `substrate`.

    The single str->typed dispatch the `ControlPortRegistry` calls once it has
    matched a route (whose `substrate` names the family). Raises
    `MalformedControlAddressError` when `raw` does not satisfy the substrate's
    syntax.
    """
    if substrate in ("epics_ca", "epics_pva"):
        return EpicsPvAddress.parse(raw, substrate)
    if substrate == "tango":
        return TangoAttributeAddress.parse(raw, substrate)
    return InMemoryAddress.parse(raw, substrate)


__all__ = [
    "ControlAddress",
    "EpicsPvAddress",
    "InMemoryAddress",
    "MalformedControlAddressError",
    "TangoAttributeAddress",
    "parse_control_address",
]
