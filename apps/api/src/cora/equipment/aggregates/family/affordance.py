"""Affordance closed StrEnum: device-level operational primitives a Family supports.

Per [[family-affordance-design-phases-5i-5j-lock]] and the 4-round
research in [[project-capability-research]]:

- An Affordance is a CLAIM about what the device can do, set-membership-
  shaped (a Family `affords` Rotatable iff Rotatable is in
  Family.affordances). Matches type-class membership semantics (Swift
  API Design Guidelines / .NET Framework Design Guidelines / Java
  java.lang / Python collections.abc / W3C SOSA ObservableProperty).
- 29 items in 2 patterns:
    A. Operational affordances (`-able` / `-ible` / `-ing`): "device
       supports doing X" or "device performs X" — 28 items across
       Motion / Imaging / Triggering / Streaming / Optics+Environment /
       Reporting.
    C. Lifecycle affordances (noun): "device has lifecycle property X"
       — 1 item.
- Closed v1 enum. Add-only amendment path (never remove a published
  value). New values land via additive evolution; renames require the
  Marten/Axon dual-match dance and are explicitly out of scope at v1.

## Why two patterns, not one

The dominant computing-vocabulary convention is `-able`/`-ible`/`-ing`
for capability claims (Swift codifies the full triad, .NET endorses it,
Java/Python/Ruby follow informally). All 28 operational affordances
follow this rule, mixing `-able`/`-ible` (action: "device supports
doing X") and `-ing` gerund (role/flow: "device is X-ing"). Examples
of the `-ing` form: `Marking` (device marks positions with output
triggers), `Recording` (device records to durable storage),
`Following` / `Leading` / `Pulsing` (device's role in a signal chain).

`Consumable` is the lone Pattern C noun — a LIFECYCLE property of
passive parts that get swapped (LuAG scintillator screen, filters,
target foils). Forcing `Consumeable` (`-able` form) would violate the
read-aloud test and conceal that this is a part-tracking property,
not an action the device performs. See [[project-capability-research]]
section 5a for the full precedent chain.

## Drops vs the original v1 list

The Round 4 verification pass dropped 5 parameter-shaped candidates
that belong elsewhere:
  - `BitDepthSelectable`, `ROIConfigurable`, `BadPixelMaskable` →
    `Family.settings_schema` (parameter values, not actions).
  - `BraggAddressable`, `EnergySelectable` → operations-layer
    `Capability` (Recipe BC), not Affordance.
The grammatical test: if the candidate reads as "device supports
being configured to set <noun>", it's parameter-shaped, not action-
shaped. Compound `<noun>Selectable` / `<noun>Addressable` is the
foot-gun pattern; banned at code review per
[[project-capability-research]] anti-hook 21.

## Contract per affordance

Each Affordance carries a one-line operational-contract docstring
(Bloch `Cloneable`-trap mitigation per
[[project-capability-research]] anti-hook 23). The contract names
what a device promises when it claims the affordance — not just a
description but a behavior commitment that downstream code can rely
on. Longer-form per-affordance reference docs live in
`docs/reference/affordances.md`.

## Cross-vocabulary mapping

Adapter authors (ros2_control, W3C WoT TD, NeXus, OPC UA LADS,
PandABox, EPICS, areaDetector, SOSA) cross-walk via the mapping
table in `docs/reference/affordances.md`. SOSA's key pattern
inversion is documented there: SOSA puts `-able` on the *property
being acted on* (`ObservableProperty`), CORA puts it on the *device
that acts* (`Rotatable`). Both coherent.
"""

from enum import StrEnum


class Affordance(StrEnum):
    """Device-level operational primitive. Closed v1 enum (29 items, 2 patterns).

    Values are PascalCase strings so they serialize naturally as JSON
    discriminators without translation.

    Pattern A, Operational affordances (`-able` / `-ible` / `-ing`):
        "device supports doing X" (action) or "device performs X"
        (role/flow). Set-membership claim. 28 items.

    Pattern C, Lifecycle affordances (noun):
        "device has lifecycle property X". 1 item.
    """

    # ---------- Pattern A: Operational affordances ----------
    # Motion (9)
    ROTATABLE = "Rotatable"
    """Device supports a rotational degree of freedom with a set position command."""
    TRANSLATABLE = "Translatable"
    """Device supports a linear (single-axis) degree of freedom with a set position command."""
    HOMEABLE = "Homeable"
    """`home` operation drives to a reference position and zeros the encoder."""
    LIMITABLE = "Limitable"
    """Honors operator-configured software-limit min/max bounds; refuses motion past them."""
    CAPTURABLE = "Capturable"
    """Latches encoder/ADC values into a buffer on external trigger edges (PandA `PCAP`)."""
    POSABLE = "Posable"
    """Accepts a coordinated multi-DOF pose command (6-DOF X/Y/Z/U/V/W) referred
    to a configurable pivot/tool/work frame; for hexapods + parallel kinematics."""
    INDEXABLE = "Indexable"
    """Finite enumerated set of mutually-exclusive named positions with a `go to
    named position` operation (filter wheel, mirror coating stripe, monochromator)."""
    FOLLOWING = "Following"
    """Follows an external encoder source as its position feedback (slave role in
    master/slave chain). Replaces the EncoderInput signal noun."""
    LEADING = "Leading"
    """Emits its position as an encoder signal for downstream followers (master role
    in master/slave chain). Replaces the EncoderOutput signal noun."""

    # Imaging (3)
    IMAGEABLE = "Imageable"
    """Acquires 2D image frames on exposure/trigger; supports basic capture."""
    BINNABLE = "Binnable"
    """Supports on-sensor pixel binning (NxN combining) to trade resolution for SNR/speed."""
    CAPTURING = "Capturing"
    """Captures a 2D or 3D data sample on operator command or external trigger;
    produces a Data BC Acquisition fact on every capture."""

    # Triggering and timing (5)
    TRIGGERABLE = "Triggerable"
    """Accepts an external edge trigger to start a single timed operation."""
    GATEABLE = "Gateable"
    """Integrates over the duration of an external level signal (gate high = active)."""
    SYNCHRONIZABLE = "Synchronizable"
    """Aligns its internal clock to an external master clock or sync signal."""
    MARKING = "Marking"
    """Emits trigger pulses when its encoder crosses configured positions (PandA `PCOMP`)."""
    PULSING = "Pulsing"
    """Generates configurable digital pulse trains (width, period, count) for downstream
    timing. Replaces the PulseGenerator signal noun."""

    # Streaming and data (4)
    STREAMABLE = "Streamable"
    """Pushes data continuously over a transport without per-frame request/response."""
    BUFFERABLE = "Bufferable"
    """Exposes an internal buffer with operator-configurable size and behavior
    (ring vs linear; pre/post-trigger split lives in parameters_schema)."""
    COMPRESSIBLE = "Compressible"
    """Applies a lossless or lossy codec to outgoing data (JPEG, LZ4, etc.) at runtime."""
    RECORDING = "Recording"
    """Records acquired data to durable storage at an operator-configured path
    (HDF5, TIFF, ADF, etc.)."""

    # Optics and environment (5)
    COOLABLE = "Coolable"
    """Exposes a setpoint for its thermal control loop (sensor cooling, etc.)."""
    PID_CONTROLLABLE = "PIDControllable"
    """Control loop exposes P/I/D gains for operator tuning."""
    SHUTTERABLE = "Shutterable"
    """Has an open/close shutter that the operator can command."""
    ATTENUABLE = "Attenuable"
    """Reduces the intensity of an incident beam by an operator-set factor."""
    BENDABLE = "Bendable"
    """Optical surface (mirror) has actively-driven curvature/figure (mechanical
    bender, bimorph piezo array, thermal); see NXmirror `bend_angle_x/y`."""

    # Reporting (2)
    IDENTIFIABLE = "Identifiable"
    """Returns a persistent identifier (serial number, MAC, etc.) on query."""
    REPORTABLE = "Reportable"
    """Returns a health/status reading on query (temperature, error count, etc.)."""

    # ---------- Pattern C: Lifecycle affordances (noun) ----------
    CONSUMABLE = "Consumable"
    """Passive part whose identity, material, thickness, lot, and install/remove
    history are operationally tracked, even though it has no command surface
    (scintillator screens, filters, sample holders, target foils)."""


class InvalidAffordanceError(ValueError):
    """The supplied affordance value is not a member of the closed `Affordance` enum.

    Defensive guard for direct in-process callers (sagas, tests,
    fixtures). REST + MCP boundaries catch this via Pydantic
    enum validation first, returning HTTP 422 / MCP error before
    this exception fires.
    """

    def __init__(self, value: object) -> None:
        super().__init__(
            f"Invalid Affordance value: {value!r}; must be one of the 29 "
            f"closed-enum members (see cora.equipment.aggregates.family.affordance)"
        )
        self.value = value


__all__ = ["Affordance", "InvalidAffordanceError"]
