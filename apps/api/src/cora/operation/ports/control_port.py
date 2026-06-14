"""ControlPort: domain-shaped value-IO for the Operation BC executor.

`ControlPort` is the async Protocol that Operation BC slice handlers
(and the future Procedure executor) use to read, write, and subscribe
to control-system values. Substrate details (EPICS CA via aioca,
EPICS PVA via p4p, Tango via PyTango, OPC UA via asyncua) live behind
concrete adapters; the executor never touches substrate-specific
symbols directly.

Per [[project_control_port_generalization_research]] this supersedes
the earlier `PvDriver` design. The supersession was driven by
a three-substrate stress test (EPICS + Tango + OPC UA sanity check)
showing that value-IO genuinely generalises across all three when
the port owns its vocabulary; RPC and typed events do NOT generalise
and stay deferred to future sibling ports (`CommandPort`, `EventPort`)
per adapter-first discipline.

## Domain vocabulary (substrate-neutral)

- **`Reading`** is the typed value-plus-metadata the executor sees.
  Fields are domain-owned: `value`, `kind: ReadingKind`,
  `quality: Quality`, `sampled_at: datetime`, `quality_detail: str`.
- **`ReadingKind`** is a closed 5-value enum (`Scalar | Array | Image
  | Categorical | Tabular`). Maps to EPICS V4 NT kinds + Tango
  `AttrDataFormat` + OPC UA Variant types via adapter-side ACL.
- **`Quality`** is the closed 3-value enum (`Good | Uncertain | Bad`)
  matching OPC UA's spec-defined high-level severity grouping and
  the NAMUR / ISA-95 vocabulary. Adapters translate substrate-native
  quality enums INTO this domain enum; substrate sub-codes (EPICS
  `alarm_status`, Tango string detail, OPC UA's ~240 named sub-codes)
  land in `Reading.quality_detail` as opaque forensic breadcrumbs.

## Address space

`address: str` at v1. Adapters parse substrate-specific syntax: EPICS
PV name (`"2bm:rot:rbv"`), Tango TRL (`"sys/tg_test/1/double_scalar"`),
OPC UA NodeId string (`"ns=2;s=Demo.Static.Scalar.Double"`). At second-
substrate trigger, promote to a typed-sum `ControlAddress`
(`EpicsPvAddress | TangoAttributeAddress | OpcUaNodeAddress`) per
watch item 4; the change is BC-internal and non-breaking outside the
Operation BC.

## Out of scope (deferred sibling ports)

- **RPC** (Tango Commands, OPC UA Methods, EPICS V4 RPC): future
  `CommandPort` Protocol. Triggers at first concrete RPC consumer.
- **Typed events** (Tango `INTERFACE_CHANGE` / `DATA_READY`, OPC UA
  `EventNotificationList`): future `EventPort` Protocol. Triggers at
  first typed-event consumer.

Per [[project_control_port_generalization_research]] anti-hooks:
do NOT widen `ControlPort` with `invoke` (RPC) or
`subscribe_events` (typed events). Add separate ports when triggered;
keep this one value-IO-only.

## Exceptions

Six exception families mirror CORA's standard shape. `ControlPort` is
not REST-accessible; the executor's decider captures these as
event-payload metadata per [[project_non_determinism_principle]].

## Subscribe shape

`subscribe` is a plain `def` returning `AsyncIterator[Reading]` directly
(no surrounding coroutine). Caller iterates with
`async for reading in port.subscribe(address):`. Connect setup may
happen lazily on the first `__anext__`; the adapter still raises
`ControlNotConnectedError` through the iterator if the address is
never reachable. Adapters may coalesce intermediate values on
subscriber lag (p4p Qt keep-last; OPC UA MonitoredItem queue
semantics). Mid-stream disconnect raises `ControlNotConnectedError`
through the iterator so silent stream pause is impossible.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

ReadingKind = Literal["Scalar", "Array", "Image", "Categorical", "Tabular"]
"""Closed 5-value discriminator for `Reading.value` shape.

- `Scalar`: a single typed value (int / float / bool / str).
- `Array`: a 1-D sequence of scalars (tuple at the port boundary).
- `Image`: a 2-D pixel grid (NTNDArray / Tango IMAGE / OPC UA image
  variants); shape and dtype carried inside `value`.
- `Categorical`: a string label from a closed substrate-defined set
  (EPICS NTEnum / Tango DevEnum or DevState / OPC UA enum).
- `Tabular`: column-oriented record (NTTable / OPC UA table / Tango
  multi-attribute bundle).

Adapter ACLs translate substrate-specific type taxonomies INTO this
enum. Extensible by tag addition when a future substrate justifies a
new shape (e.g., OPC UA `LocalizedText` may justify a new tag).
"""


Quality = Literal["Good", "Uncertain", "Bad"]
"""Closed 3-value quality enum matching OPC UA's spec-defined severity
grouping and the NAMUR / ISA-95 vocabulary.

Per the OPC UA sanity check in
[[project_control_port_generalization_research]], `StatusCode`'s top
2 bits are exactly this trichotomy:
`Good = 0b00 | Uncertain = 0b01 | Bad = 0b10`. EPICS CA's 4-value
severity collapses (`NONE -> Good`, `MINOR | MAJOR | INVALID -> Bad`).
Tango's 5-value `AttrQuality` collapses (`VALID -> Good`,
`WARNING | CHANGING -> Uncertain`, `ALARM | INVALID -> Bad`).

Substrate-specific forensic detail (EPICS `alarm_status`, Tango
string detail, OPC UA's ~240 named sub-codes such as
`BadCommunicationError` / `UncertainDataSubNormal`) lands in
`Reading.quality_detail` as an opaque string; the closed enum stays
tight.
"""


class ActuationKind(StrEnum):
    """How a conducted episode drove its addresses: real hardware, a
    simulator, or both.

    Derived by the Conductor from the per-route simulated flag the
    registry carries, and snapshotted (as a raw string) onto the
    producing Dataset so simulator-origin data can never be promoted
    to Production. Simulated-ness is a declared property of a route
    (ControlPortRoute.is_simulated), not the transport substrate: a
    soft IOC speaks real Channel Access yet is still a simulator.

    Physical: every address routed to a non-simulated adapter.
    Simulated: every address routed to a simulated adapter.
    Hybrid: a single conduct drove both. The promotion gate treats
    Hybrid exactly as Simulated (any simulator touch disqualifies).
    """

    PHYSICAL = "Physical"
    SIMULATED = "Simulated"
    HYBRID = "Hybrid"


@dataclass(frozen=True)
class Reading:
    """Domain-shaped value-plus-metadata at the executor boundary.

    Domain owns every field. Adapter ACLs translate substrate-native
    value types (EPICS V4 NT structures, Tango `DeviceAttribute`,
    OPC UA `DataValue`) into this shape; substrate vocabulary
    (NTNDArray fields, DevState labels, OPC UA Variant types) stays
    caged in the adapter.

    `value` is `Any` because the runtime shape varies with `kind`:
    `Scalar` is `int | float | bool | str`, `Array` is a tuple,
    `Image` is a 2-D structure (typically `numpy.ndarray` at the
    adapter, normalised to a tuple-of-tuples or wrapped array at the
    port boundary), `Categorical` is a string label, `Tabular` is a
    dict of column names to tuples. Callers narrow per kind at the
    use site.

    Substrate-specific presentation hints (NT `valueAlarm`,
    `displayLimit`, `controlLimit` structures; Tango display formats;
    OPC UA `DisplayName`) are intentionally NOT surfaced here. They
    are operator-UI metadata, not control-plane data; adapters drop
    them at unpacking time.

    `sampled_at` is the time the substrate observed the value
    (EPICS source timestamp, Tango `time`, OPC UA `SourceTimestamp`).
    `quality_detail` is adapter-specific and opaque at the port
    layer; treat it as a forensic breadcrumb, not a value to branch
    on.
    """

    value: Any
    kind: ReadingKind
    quality: Quality
    sampled_at: datetime
    quality_detail: str = ""


class ControlNotConnectedError(Exception):
    """No active channel / session for this address.

    Triggered on pre-connect call OR mid-call / mid-stream
    disconnect. `subscribe` iterators raise this through the iterator
    (not via silent pause) so the caller decides to retry (re-call
    `subscribe`) or close.
    """

    def __init__(self, address: str) -> None:
        super().__init__(f"Control address {address!r} not connected")
        self.address = address


class ControlTimeoutError(Exception):
    """Adapter timeout elapsed before the operation completed.

    Triggered when a `write`'s put-callback / confirmation did not
    fire under `wait=True`, a `read` exceeded its timeout, or
    initial connect timed out. Carries the timeout that was breached
    so logs distinguish "we waited X seconds and gave up" from
    generic latency complaints.
    """

    def __init__(self, address: str, timeout_s: float) -> None:
        super().__init__(f"Control address {address!r} operation exceeded {timeout_s}s")
        self.address = address
        self.timeout_s = timeout_s


class ControlWriteRejectedError(Exception):
    """Substrate rejected the write.

    Triggered on read-only address, invalid value type for the
    address's substrate type, or substrate-level access-security
    denial expressed as a write-callback failure. Distinct from
    `ControlAccessDeniedError` so adapters preserve the substrate's
    failure-mode distinction (e.g., EPICS IOC put-callback failure
    vs Channel Access security denial).
    """

    def __init__(self, address: str, reason: str) -> None:
        super().__init__(f"Control address {address!r} write rejected: {reason}")
        self.address = address
        self.reason = reason


class ControlValueCoercionError(Exception):
    """Adapter cannot unpack the substrate value into a `Reading` shape.

    Triggered when an adapter sees a novel structured type (e.g., a
    new EPICS V4 NT variant) or a substrate primitive that does not
    fit the closed `ReadingKind` set. Carries the substrate's raw
    type label so operators can extend the kind set in a follow-up
    rather than silently dropping data.
    """

    def __init__(self, address: str, raw_type: str, target_kind: str) -> None:
        super().__init__(
            f"Control address {address!r} value of type {raw_type!r} "
            f"cannot coerce to kind {target_kind!r}"
        )
        self.address = address
        self.raw_type = raw_type
        self.target_kind = target_kind


class ControlAccessDeniedError(Exception):
    """Substrate denied access (EPICS CA security policy, Tango
    authorisation, OPC UA `BadUserAccessDenied`, etc.).

    Distinct from `ControlWriteRejectedError` so operators distinguish
    "wrong value, substrate said no" from "you may not touch this
    address at all." Substrate-level ACLs are defense-in-depth; CORA's
    authz primary lives at the executor / Conduit layer per
    [[project_conduit_injection_design]].
    """

    def __init__(self, address: str) -> None:
        super().__init__(f"Control address {address!r} access denied")
        self.address = address


class NoAdapterForAddressError(Exception):
    """No registered adapter route matches this address.

    Triggered when the executor asks the registry for a route and no
    configured prefix matches. Almost always a configuration gap (a
    new IOC / Tango device server / OPC UA server was added without
    extending the registry routes). Lives here, alongside the port,
    so adapters that construct registries can raise it; the registry
    class itself lives in `cora.operation.adapters.control_port_registry`.
    """

    def __init__(self, address: str) -> None:
        super().__init__(f"Control address {address!r} has no matching adapter")
        self.address = address


@runtime_checkable
class ControlPort(Protocol):
    """Domain-shaped value-IO port for control-system addresses.

    Substrate-agnostic. Concrete adapters
    (`InMemoryControlPort`, `CaprotoControlPort`, `EpicsCaControlPort`,
    `EpicsPvaControlPort`, future `TangoControlPort` /
    `OpcUaControlPort`) implement the wire details. Per
    [[project_non_determinism_principle]], port-injected effects are
    captured in the executor's event payloads at decider time.

    Port shape follows the ros2_control "keep port dumb, executor
    pluggable" lesson from [[project_control_port_research]]. Adapter
    internals may use asyncio (aioca, p4p asyncio, asyncua) or
    threading (p4p thread, caproto sync backend); the surface callers
    see is `async def read` / `async def write` / `async def subscribe`.

    The executor that consumes this Protocol stays open at v1:
    `ControlPort` composes with fixed-rate-tick, async event-driven,
    and plain-async executor architectures. The executor arc picks
    an initial shape; `ControlPort` is not coupled to that pick.

    RPC (Tango Commands, OPC UA Methods) and typed events (Tango
    `DATA_READY` / `INTERFACE_CHANGE`, OPC UA `EventNotificationList`)
    are intentionally OUT of scope. Future sibling ports
    (`CommandPort`, `EventPort`) land at first concrete consumer
    trigger per adapter-first discipline.
    """

    async def read(self, address: str) -> Reading:
        """Read the current `Reading` at `address`.

        Raises `ControlNotConnectedError` if there is no active
        channel or `ControlTimeoutError` if the read exceeds the
        adapter timeout.
        """
        ...

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        """Write `value` to `address`.

        `wait=True` (the default) blocks until the substrate confirms
        the write (EPICS caput-callback, Tango synchronous reply,
        OPC UA `WriteResponse`). `wait=False` returns as soon as the
        write is enqueued.

        Raises `ControlNotConnectedError`, `ControlTimeoutError`
        (when `wait=True` and confirmation does not fire in time),
        `ControlWriteRejectedError` (substrate rejected the write),
        or `ControlAccessDeniedError` (substrate denied access).
        """
        ...

    def subscribe(self, address: str) -> AsyncIterator[Reading]:
        """Subscribe to value changes on `address`. Caller iterates the result.

        Plain `def`, no surrounding coroutine: caller pattern is
        `async for reading in port.subscribe(address):`. Adapters may
        defer connect-and-register-as-subscriber to the first
        `__anext__`; a `ControlNotConnectedError` raised through the
        iterator (rather than from `subscribe()` itself) is the
        expected shape when the address never reaches a connected
        state.

        On mid-stream disconnect the iterator raises
        `ControlNotConnectedError` so silent stream pause is
        impossible. The caller decides whether to re-subscribe or
        close.

        Subscriber-responsible back-pressure. Adapters MAY coalesce
        intermediate values on lag (p4p Qt keep-last; OPC UA
        MonitoredItem queue policy); each adapter documents its
        coalescing policy in implementation notes. Cancellation is
        via the iterator's `aclose()`.
        """
        ...


__all__ = [
    "ActuationKind",
    "ControlAccessDeniedError",
    "ControlNotConnectedError",
    "ControlPort",
    "ControlTimeoutError",
    "ControlValueCoercionError",
    "ControlWriteRejectedError",
    "NoAdapterForAddressError",
    "Quality",
    "Reading",
    "ReadingKind",
]
