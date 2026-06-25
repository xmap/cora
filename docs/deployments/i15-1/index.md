# I15-1

*An X-ray pair-distribution-function / total-scattering (XPDF) beamline at Diamond Light Source. This page walks the beamline as it is being modelled; everything here is reverse-engineered from Diamond's open `dodal` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `I15-1` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`), the third Diamond beamline after [I22](../i22/index.md) and [I03](../i03/index.md) |
| Status | Design-phase modelling exercise (not a CORA pilot) |
| Technique | total scattering / pair distribution function (PDF) |
| Beam | bent-Laue monochromator (fixed-energy selection), multilayer mirror |
| Control stack | Diamond EPICS (driven by GDA and bluesky) |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    I15-1 is a real, operating beamline, but it is **not** on the CORA pilot roadmap. It is modelled here, like I22 and I03, to test the dodal-seed pipeline against another technique. Every value is reverse-engineered from [`dodal`](https://github.com/DiamondLightSource/dodal) or inferred, carried as `confirm` until Diamond staff verify it. See [Open questions](questions.md).

## What I15-1 earns: nothing new (and that is the point)

I15-1 was chosen partly on the expectation that it would graduate the open settable-actuator affordance. **A close read of the dodal source refuted that.** Like I22, I15-1 earns **zero new catalog Families and zero new affordances**: every device maps onto an existing Family or a reused loose one. Its value is consolidation plus three intentional-modelling decisions, each of which resists a mirror-the-controls trap:

- **`SafeOrBeamPositioner` is a Positioner, not a new affordance.** The blower / cobra / cryostream sample-environment devices are each a `Movable` that drives a motor to two named positions, `SAFE` and `BEAM`. That is the existing **Positioner Role with Indexable named positions**, not a settable-actuator affordance, and **not a `TemperatureController`**: the dodal classes are *named* for temperature controllers but model only the in/out-of-beam move, so modelling them as `TemperatureController` would mirror the class name, not the behaviour (SAFEBEAM-1).
- **The rail is a `Table`, not a new `Rail` Family.** The shared support on which the cobra and cryostream are interchanged is the existing `Table` Family (the TomoWISE DetectorGantry precedent), not a coined kind (RAIL-1).
- **The interlocks are not devices.** The PSS and goniometer interlocks dodal exposes are the data behind the **Enclosure `permit_signal`** (the shipped Enclosure aggregate), so they are carried on the enclosures, not as equipment Assets (INTERLOCK-1).

It also reuses `FluxMonitor` for the incident-flux monitor (the JBPM TetrAMM `i0`), the deployment that completed its rule-of-three graduation into the catalog, and adds a third robot-as-Positioner instance (after I03 and 19-BM).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the storage-ring state, the bent-Laue monochromator (fixed-energy, a y-to-energy lookup readback, not a scanning DCM), the multilayer mirror, the attenuators, the beam-defining slits and shutters, rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the sample positioning and hexapod, the two-theta detector arm, and the interchangeable sample-environment devices on a shared rail, plus the powder/capillary sample-changing robot.
- [Detector](equipment/detector.md): the Eiger area detector capturing wide-Q total-scattering frames, a second detector translation, and the incident-flux monitor.

Cutting across all three:

- [Controls](equipment/controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the Zebra timing.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i15-1/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): total scattering / PDF as design intent. The total-scattering Capability is new vocabulary the catalog does not yet carry; the energy-scan Capability is explicitly **not** earnable here (the bent-Laue mono is a fixed selection, not a scan) (TECH-1, ENERGY-1).

## Governance

[Governance](governance.md): who would act at I15-1 and the trust shape, including the Clearance that would gate autonomous robot loading. Principals are facility-wide at the [Diamond Site](../diamond/index.md).

## Model

[Model](model.md): the developer's by-kind index, and why I15-1 adds no catalog kinds.

## Not yet documented

I15-1 is a modelling exercise, so the operations runbook and the live experiment view are deliberately not written. The 2-BM deployment shows the shape they would take.
