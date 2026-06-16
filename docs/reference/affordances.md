# Affordances

*Closed-enum primitives a [Family](../catalog/families.md) declares it supports. Set-membership over Affordances drives the cross-BC Plan-bind matching engine: `union(family.affordances for family in wired_asset.family_ids) ⊇ method.capability.required_affordances`.*

An **Affordance** is a claim about what a device can do. Affordances are declared on Families (Equipment BC). The contract a Method must satisfy is declared one layer up on its bound **Capability** template (Recipe BC `Capability.required_affordances`). At `define_plan` time, the union of every wired Asset's Families' affordances must cover the bound Method's Capability's required set; otherwise the handler raises `PlanAffordancesNotSatisfiedError` (409).

## Two patterns

The v1 closed enum carries 29 items in two explicit patterns:

- **Pattern A: Operational affordances (`-able` / `-ible` / `-ing`)**: 28 items. The device is the actor.
  - **`-able` / `-ible` form (22 items)**: "device supports doing X": `Rotatable`, `Triggerable`, `Bendable`, …
  - **`-ing` gerund form (6 items)**: "device performs X" / "device is X-ing": `Marking`, `Pulsing`, `Following`, `Leading`, `Recording`, `Capturing`. Used where the device's role in a signal chain or data flow is the primitive being claimed; `-able` would invert the direction.
- **Pattern C: Lifecycle affordances (noun)**: 1 item, `Consumable`. Passive parts whose identity is operationally tracked even though they have no command surface (scintillator screens, filters, sample holders, target foils).

The convention is grounded in [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/) ("Protocols that describe a _capability_ should be named using the suffixes `able`, `ible`, or `ing`"), [.NET Framework Design Guidelines](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/names-of-classes-structs-and-interfaces) ("DO name interfaces with adjective phrases"), and [W3C SOSA](https://www.w3.org/TR/vocab-ssn/) `ObservableProperty` / `ActuatableProperty`. The pre-rename v1 enum had a third Pattern B for noun-named signal flows (`EncoderInput` / `EncoderOutput` / `PulseGenerator`); those dissolved into Pattern A's `-ing` form (`Following` / `Leading` / `Pulsing`) once the role-based reframing made the device-as-actor reading natural.

## Pattern A: Operational affordances (28)

### Motion (9)

| Affordance | Contract |
|---|---|
| `Rotatable` | Device supports a rotational degree of freedom with a set position command. |
| `Translatable` | Device supports a linear (single-axis) degree of freedom with a set position command. |
| `Homeable` | Device supports a `home` operation that drives to a reference position and zeros the encoder. |
| `Limitable` | Device honors operator-configured software-limit min/max bounds, refusing motion past them. |
| `Capturable` | Device latches encoder or ADC values into a buffer on external trigger edges (PandA `PCAP`). |
| `Posable` | Device accepts a coordinated multi-DOF pose command (typically 6-DOF X/Y/Z/U/V/W) referred to a configurable pivot/tool/work frame; for hexapods + parallel kinematics. |
| `Indexable` | Device has a finite enumerated set of mutually-exclusive named positions with a `go to named position` operation (filter wheel, mirror coating stripe, monochromator crystal pair). |
| `Following` | Device follows an external encoder source as its position feedback (slave role in a master/slave chain). |
| `Leading` | Device emits its position as an encoder signal for downstream followers (master role in a master/slave chain). |

### Imaging (3)

| Affordance | Contract |
|---|---|
| `Imageable` | Device acquires 2D image frames on exposure/trigger; supports basic capture. |
| `Binnable` | Device supports on-sensor pixel binning (N×N combining) to trade resolution for SNR/speed. |
| `Capturing` | Device captures a 2D or 3D data sample on operator command or external trigger; produces a Data BC Acquisition fact on every capture. |

### Triggering and timing (5)

| Affordance | Contract |
|---|---|
| `Triggerable` | Device accepts an external edge trigger to start a single timed operation (exposure, sample, etc.). |
| `Gateable` | Device integrates over the duration of an external level signal (gate high = active, gate low = idle). |
| `Synchronizable` | Device aligns its internal clock to an external master clock or sync signal. |
| `Marking` | Device emits trigger pulses when its encoder crosses configured positions (PandA `PCOMP`). Inverse direction of `Triggerable` (consumer); kept distinct to avoid the direction collision. |
| `Pulsing` | Device generates configurable digital pulse trains (width, period, count) for downstream timing. |

### Streaming and data (4)

| Affordance | Contract |
|---|---|
| `Streamable` | Device pushes data continuously over a transport without per-frame request/response handshake. |
| `Bufferable` | Device exposes an internal buffer with operator-configurable size and behavior (ring vs linear; pre/post-trigger split lives in `parameters_schema`). |
| `Compressible` | Device applies a lossless or lossy codec to outgoing data (JPEG, LZ4, etc.) at runtime. |
| `Recording` | Device records acquired data to durable storage at an operator-configured path (HDF5, TIFF, ADF, etc.). |

### Optics and environment (5)

| Affordance | Contract |
|---|---|
| `Coolable` | Device exposes a setpoint for its thermal control loop (sensor cooling, hexapod thermal management, etc.). |
| `PIDControllable` | Device's control loop exposes P/I/D gains for operator tuning. |
| `Shutterable` | Device has an open/close shutter that the operator can command. |
| `Attenuable` | Device reduces the intensity of an incident beam by an operator-set factor (typically via discrete filters). |
| `Bendable` | Device's optical surface (mirror) has actively-driven curvature/figure (mechanical bender, bimorph piezo array, thermal); see [NXmirror](https://manual.nexusformat.org/classes/base_classes/NXmirror.html) `bend_angle_x/y`. |

### Reporting (2)

| Affordance | Contract |
|---|---|
| `Identifiable` | Device returns a persistent identifier (serial number, MAC, etc.) on query. |
| `Reportable` | Device returns a health/status reading on query (temperature, error count, firmware version, etc.). |

## Pattern C: Lifecycle affordances (1)

| Affordance | Contract |
|---|---|
| `Consumable` | Device is a passive part whose identity, material, thickness, lot, and install/remove history are operationally tracked, even though it has no command surface (scintillator screens, filters, sample holders, target foils). |

## Cross-vocabulary mapping

Affordance ⇄ adjacent-vocabulary cross-walk for adapter authors:

| Affordance | ros2_control | W3C WoT TD | NeXus | OPC UA LADS | PandABox | EPICS |
|---|---|---|---|---|---|---|
| `Rotatable` | `HW_IF_POSITION` (axis=rotary, dir=command) | `PropertyAffordance` (writable) | `NXpositioner` | `AnalogControlFunction` | — | `motorRecord` |
| `Translatable` | `HW_IF_POSITION` (axis=linear, dir=command) | `PropertyAffordance` (writable) | `NXpositioner` | `AnalogControlFunction` | — | `motorRecord` |
| `Homeable` | `HW_IF_HOME` (action) | `ActionAffordance` | — | `MoveControlFunction` | — | `motorRecord HOMR/HOMF` |
| `Marking` | — | — | — | — | `PCOMP` | — |
| `Capturable` | — | — | — | — | `PCAP` | — |
| `Triggerable` | — | `ActionAffordance` | `NXdetector.acquisition_mode=triggered` | — | `PULSE` | — |
| `Gateable` | — | — | `NXdetector.acquisition_mode=gated` | — | `GATE` | — |
| `Imageable` | — | — | `NXdetector` | — | — | `areaDetector` |
| `Capturing` | — | — | `NXdetector` / `NXdata` (W3C SOSA `Observation` cross-walk) | — | — | `areaDetector` |
| `Streamable` | — | `EventAffordance` | — | — | — | `areaDetector NDPluginStream` |
| `Recording` | — | — | — | — | — | `areaDetector NDFileHDF5/TIFF` |
| `Bendable` | — | — | `NXmirror.bend_angle_x/y` | — | — | — |
| `Following` | `HW_IF_POSITION` (state) | `PropertyAffordance` (read) | — | — | `INENC` | — |
| `Leading` | — | — | — | — | `OUTENC` | — |
| `Pulsing` | — | — | — | — | `PGEN` | — |
| `Consumable` | — | — | material+thickness fields on NXmirror / NXattenuator / NXfilter / NXcrystal | — | — | — |

Note on **W3C SOSA inversion**: SOSA puts `-able` on the *property being acted on* (`ObservableProperty`, `ActuatableProperty`), CORA puts it on the *device that acts* (`Rotatable`). Both are coherent. When adapting to SOSA, translate `Rotatable` to `Rotation has type ActuatableProperty on this asset` rather than treating `Rotatable` and `Rotation` as the same noun.

## Catalog governance

- **Closed enum at v1.** Adding a value requires a CORA release; per-deployment extensions are not supported at this layer.
- **Add-only amendment path.** Never remove a published value. If a value becomes obsolete, deprecate it in docs and stop using it in new Family declarations, but the enum member stays for replay safety.
- **Banned pattern: `<noun>Selectable` / `<noun>Addressable`.** Parameter-selection items belong in `Family.settings_schema` or in an operations-layer `Capability`, not in `Affordance`. The grammatical test: "device supports being configured to set X" means settings_schema; "device supports doing X" means Affordance.
- **Contract per Affordance.** Each entry in the enum carries a one-line operational contract docstring inline at `cora.equipment.aggregates.family.affordance` (Bloch `Cloneable`-trap mitigation). The longer-form contract on this page is the authoritative reference for adapter authors.
- **Form discipline.** Pattern A is `-able`/`-ible`/`-ing` (Swift Guidelines triad); Pattern C noun is reserved for the single lifecycle case (`Consumable`). New entries that don't fit one of these forms, particularly compound noun-named signal interfaces, should be reframed as role/flow `-ing` gerunds (precedent: `Following`/`Leading`/`Pulsing` absorbed the pre-rename Pattern B nouns).

## Related

- [Families](../catalog/families.md): registered Families at the deployment level
- [Capabilities](../catalog/capabilities.md): Recipe BC operations-layer templates that consume Affordances as `required_affordances`
