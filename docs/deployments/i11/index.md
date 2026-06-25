# I11

*A high-resolution powder-diffraction beamline at Diamond Light Source. This page walks the beamline as it is being modelled; everything here is reverse-engineered from Diamond's open `dodal` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `I11` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md), the fourth Diamond beamline after [I22](../i22/index.md), [I03](../i03/index.md), and [I15-1](../i15-1/index.md) |
| Status | Design-phase modelling exercise (not a CORA pilot) |
| Technique | high-resolution powder diffraction (often with a temperature ramp) |
| Beam | double-crystal monochromator |
| Control stack | Diamond EPICS (driven by GDA and bluesky) |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    I11 is a real, operating beamline, but it is **not** on the CORA pilot roadmap. It is modelled here, like the other Diamond beamlines, to test the dodal-seed pipeline against another technique. Every value is reverse-engineered from [`dodal`](https://github.com/DiamondLightSource/dodal) or inferred, carried as `confirm` until Diamond staff verify it. See [Open questions](questions.md).

## What I11 earns: a deferred abstraction, banked properly

I11 is the deployment that **genuinely earns** the abstraction the earlier Diamond beamlines only flirted with. It carries **four continuous-setpoint thermal actuators** (two Cyberstar hot-air blowers wrapping Eurotherm controllers with `set(value)`/`setpoint`/`ramprate`/PID, and two Oxford cryostreams). After the loose `TemperatureController` family was carried at I22 and I03, I11 is the **rule-of-three** that earns:

1. graduating the `TemperatureController` catalog Family, and
2. a **new settable-continuous-setpoint actuator Role** (CORA had none at the time: Positioner is spatial, Controller supervises, GenericProbe is read-only).

But a new Role is a **code change** (to `cora.equipment.aggregates.role.SEED_ROLES`, drift-guarded by an exact-match test) and core cross-facility vocabulary, so it belonged in a **separate, gate-reviewed change**, not this families-only scaffold. This scaffold carried the four actuators as loose `TemperatureController` (as I22/I03 did) and **TEMP-1** recorded the earn; that gate-reviewed change has since landed, graduating `TemperatureController` to a catalog Family presenting the new `Regulator` Role. This is the earn-the-abstraction discipline working: the trigger fires in a deployment, the abstraction is banked deliberately, then graduated under gate-review.

Three other intentional decisions the eval settled, each resisting a mirror-the-controls trap:

- **The diffractometer is per-axis `RotaryStage`, not the `Goniometer` Family** I03 graduated. `theta` is a single sample rotation and `two_theta`/`delta` are detector-arm angles, not an MX sample-orientation cradle (GONIO-1).
- **The `Mythen3` (a 1D position-sensitive strip detector) reuses `Camera`** (Detector Role), with the strip-vs-2D nuance noted; it is skip-flagged in dodal (MYTHEN-1).
- **The sample robot is one `Positioner` Asset + Clearance + Subject** (the locked 19-BM/I03 posture), not a new `SampleChanger` Family (ROBOT-1).

## The beamline

- [Source](beamline.md): the storage-ring state, the double-crystal monochromator, and the beam-defining slits, rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the powder diffractometer (sample rotation + detector-arm angles), the capillary spinner, the thermal sample environment, and the sample-changing robot.
- [Detector](equipment/detector.md): the Mythen3 position-sensitive strip detector.

Cutting across:

- [Controls](equipment/controls.md): the Diamond EPICS control stack (with the real dodal PV handles).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i11/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): powder diffraction as design intent, often with a temperature ramp over the thermal actuators. A new Capability the catalog does not yet carry (TECH-1).

## Governance

[Governance](governance.md): who would act at I11 and the trust shape, including the Clearance that would gate autonomous robot loading. Principals are facility-wide at the [Diamond Site](../diamond/index.md).

## Model

[Model](model.md): the developer's by-kind index, and the TemperatureController earn that landed via gate-review.

## Not yet documented

I11 is a modelling exercise, so the operations runbook and the live experiment view are deliberately not written. The 2-BM deployment shows the shape they would take.
