# Sample

*The I11 sample stage. Design-phase; values are reverse-engineered from dodal or inferred.*

The sample stage is the experiment hutch: the powder diffractometer, the capillary spinner, the thermal sample environment (the earn), and the sample-changing robot.

## The diffractometer and spinner

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Diffractometer` | `RotaryStage` | `BL11I-MO-DIFF-01:` | theta (sample rotation) + two_theta / delta (detector-arm angles) + spos |
| `DiffractometerBase` | `LinearStage` | `BL11I-MO-DIFF-01:BASE:` | diffractometer base translation |
| `Spinner` | `RotaryStage` | `BL11I-EA-ENV-01:` | capillary spinner (enable + speed) for powder averaging |

The diffractometer is modelled as **per-axis `RotaryStage` Assets under a `DiffractometerStage` Assembly**, **not** the `Goniometer` Family that I03 graduated. The distinction is load-bearing: I03's Goniometer is a multi-axis sample-orientation cradle (omega/chi/phi converging on one sample point for MX centring); I11's two_theta/delta are detector-arm angles and theta is a single sample rotation, so reusing Goniometer would conflate detector-arm motion with sample orientation (GONIO-1). The axis PVs are to confirm (the dodal class was not read axis-by-axis) (DIFF-1). The spinner is a sample-rotation device (RotaryStage) for powder averaging (SPIN-1).

## The thermal sample environment (the earn)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `CyberstarBlower1` | `TemperatureController` (loose) | `BL11I-EA-BLOW-01:` | Cyberstar hot-air blower; Eurotherm controller, updating PID |
| `CyberstarBlower2` | `TemperatureController` (loose) | `BL11I-EA-BLOW-02:LOOP1:` | Cyberstar blower; autotuneable Eurotherm |
| `Cryostream1` | `TemperatureController` (loose) | `BL11I-CG-CSTRM-01:` | Oxford Cryostream 700 plus |
| `Cryostream2` | `TemperatureController` (loose) | `BL11I-CG-CSTRM-02:` | Oxford Cryostream 700 standard |

This is what makes I11 generative. The four actuators are **continuous-setpoint** devices: the Eurotherm controllers expose `set(value)`, `setpoint`, `ramprate`, PID, and autotune. After the loose `TemperatureController` family was carried at I22 (the Linkam) and I03 (cryostream/thawer), I11 is the **rule-of-three** that genuinely earns:

1. graduating the `TemperatureController` catalog Family, and
2. a **new settable-continuous-setpoint actuator Role** (CORA has none: Positioner is spatial, Controller supervises, GenericProbe is read-only).

Because the Role is a code change (`SEED_ROLES`, drift-guarded) and core vocabulary, the earn is routed to a **separate, gate-reviewed change**, not this scaffold; the actuators are carried loose here, as I22/I03 did, and TEMP-1 tracks it.

## The sample-changing robot

| Device | Presents | Control handle | Notes |
| --- | --- | --- | --- |
| `Robot` | Positioner Role | `BL11I-EA-ROBOT-01:` | NX100 arm + carousel that loads / unloads samples on the spinner |

The robot reuses the settled I03 / 19-BM position: **one Positioner-presenting Asset** that loads and unloads a `Subject` (a sample from the carousel), gated by a Clearance, with the vendor robot in a bound Model. Not a new `SampleChanger` Family. The custody lifecycle and exchange Procedure are deferred (ROBOT-1).

See [Open questions](../questions.md) and [Inventory](../inventory.md).
