# Sample

*The I15-1 sample stage. Design-phase; values are reverse-engineered from dodal or inferred.*

The sample stage is the experiment hutch: the sample positioning and hexapod, the two-theta detector arm, the interchangeable sample-environment devices on a shared rail, and the powder/capillary sample-changing robot. It is where I15-1's three intentional-modelling decisions live.

## Positioning and the detector arm

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `SampleTrans` | `LinearStage` | `BL15I-MO-TABLE-01:TRANS:` | sample x / y / phi |
| `Hexapod` | `Hexapod` | `BL15I-MO-HEX-01:` | six-axis sample hexapod (linear + virtual rotation axes) |
| `BaseY` | `LinearStage` | `BL15I-MO-TABLE-01:Y` | sample table base height |
| `TwoTheta` | `RotaryStage` | `BL15I-MO-TABLE-01:TTH` | the two-theta detector arm angle |

## The sample environment (the SafeOrBeam decision)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Rail` | `Table` | `BL15I-MO-RAIL-01:` | the shared support the environment devices ride |
| `EnvX` | `LinearStage` | `BL15I-MO-TABLE-01:ENV:X` | the shared rail X the cobra / cryostream interchange on |
| `Blower` | `LinearStage` | `BL15I-EA-BLOWR-01:TLATE` | gas blower |
| `Cobra` | `LinearStage` | `BL15I-MO-TABLE-01:ENV:X` | Oxford Cobra, interchangeable with the cryostream |
| `Cryostream` | `LinearStage` | `BL15I-MO-TABLE-01:ENV:X` | Oxford Cryostream, interchangeable with the cobra |

This is the decision an adversarial eval settled. In dodal the blower, cobra, and cryostream are each a `SafeOrBeamPositioner`: a `Movable` whose `set()` drives an underlying motor to a configured **SAFE** or **BEAM** position from a lookup table. That is the existing **Positioner Role with two Indexable named positions**, so they are modelled as `LinearStage` Assets, **not** as a new settable-actuator affordance, and **not** as a `TemperatureController`. The dodal classes are *named* for temperature controllers, but the device models only the in/out-of-beam move, not the temperature setpoint; modelling them as `TemperatureController` would mirror the class name rather than the behaviour (intentional-modelling-not-mirroring). The cobra and cryostream share the rail X motor (`ENV:X`) because they are physically interchanged on the rail; whether that exchange is a Fixture-style swap or an Assembly is the open question (SAFEBEAM-1). The rail itself is the existing `Table` Family (the TomoWISE DetectorGantry precedent), not a coined `Rail` kind (RAIL-1).

## The sample-changing robot

| Device | Presents | Control handle | Notes |
| --- | --- | --- | --- |
| `Robot` | Positioner Role | `BL15I-MO-ROBOT-01:` | powder/capillary changer (current sample at `BL15I-EA-LOC-01:`) |

The robot reuses the settled I03 / 19-BM position: **one Positioner-presenting Asset** that loads and unloads a `Subject` (a capillary/puck from a queue), gated by a Clearance that must be Active, with the vendor robot in a bound Model. It is not a new `SampleChanger` Family. The puck custody lifecycle and the autonomous exchange Procedure are deferred (ROBOT-1). The dodal `puck_detect` (an image-processing web service, not a device) is not modelled.

See [Open questions](../questions.md) and [Inventory](../inventory.md).
