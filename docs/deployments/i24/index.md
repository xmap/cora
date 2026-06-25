# I24

*A serial / fixed-target macromolecular-crystallography (MX) beamline at Diamond Light Source. This page walks the beamline as it is being modelled; everything here is reverse-engineered from Diamond's open `dodal` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `I24` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`), the fifth Diamond beamline after [I22](../i22/index.md), [I03](../i03/index.md), [I15-1](../i15-1/index.md), and [I11](../i11/index.md) |
| Status | Design-phase modelling exercise (not a CORA pilot) |
| Technique | serial / fixed-target macromolecular crystallography (raster a chip of thousands of static crystals, one snapshot per window, no goniometer rotation) |
| Beam | undulator source, double-crystal monochromator, focusing mirrors |
| Control stack | Diamond EPICS (driven by GDA and the serial-collection plan suite over the PMAC motion controller and Zebra) |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    I24 is a real, operating beamline, but it is **not** on the CORA pilot roadmap (APS to MAX IV). It is modelled here, like the other Diamond beamlines, to test that the dry, correct device facts in Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library seed CORA's intentional model, and to push the model along an axis the rotation-MX and scattering deployments never touched: a serial, fixed-target acquisition that rasters a chip of static crystals rather than sweeping one. Every value is reverse-engineered from dodal or inferred, carried as `confirm` until Diamond staff verify it. The things CORA still needs the team to confirm are on [Open questions](questions.md).

## What I24 adds over I03 and the other Diamond beamlines

I03 (rotation MX) tests crystallography by sweeping one crystal through a continuous omega rotation. I24 tests the serial, fixed-target shape, and it is the first deployment to exercise an acquisition the others could not.

- **It is CORA's first synchrotron serial / fixed-target crystallography.** Instead of one crystal on a rotating goniometer, I24 holds thousands of static crystals on a fixed-target chip and raster-scans the chip across the beam, taking one diffraction snapshot per addressable window. The motion runs on the PMAC controller and the per-window exposure is Zebra TTL-gated; there is no goniometer rotation. This new acquisition shape, a triggered chip-raster fly-collection over a sample grid, is a new Capability deferred as a question (SSX-1). The fleet carries serial crystallography only as a pending stub at the SLAC LCLS-MFX XFEL, so I24 is the first synchrotron consumer.
- **It coins no new Family.** This is the strongest possible outcome for the families-only descriptor mode: every I24 device reuses an existing catalog or loose Family, and the catalog is unchanged. The vertical pin goniometer reuses the catalog `Goniometer` that I03 graduated; the fixed-target chip stage (dodal's PMAC) reuses `LinearStage`; the Eiger and Jungfrau detectors and the on-axis viewer reuse `Camera`; the Zebra reuses `TimingController`. The serial raster trajectory and the laser / Zebra triggering are the orchestration seam CORA's edge replaces, not a device Family.
- **It has no sample-exchange robot.** Unlike I03, which loads and unloads one crystal at a time through an automated sample-changing robot, I24 mounts a whole chip of crystals at once and addresses them by stage position. There is no robot and no autonomous load / unload loop here. The custody question moves from "which crystal is mounted" to "which chip windows are Subjects in a grid," deferred as CHIP-1.

What I24 keeps the same as its Diamond siblings: the descriptor carries the real dodal EPICS PV handles, and the model reuses existing Families wherever one fits (Monochromator, Mirror, Filter, Aperture, Goniometer, LinearStage, Camera, BeamStop, Shutter, TimingController, plus the loose `Backlight` and `StorageRing`). The attenuator folds into Filter (the I03 / i15-1 precedent), not a new Attenuator kind.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the machine source state, and the energy-selecting and focusing optics (the double-crystal monochromator, the focusing mirrors with a selectable focus mode, the filter-based attenuator, and the beam-defining aperture), rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the experiment hutch, the vertical pin goniometer, the fixed-target chip stage that rasters the addressable chip across the beam, the sample backlight and on-axis-view camera, the beamstop, and the fast Zebra-controlled sample shutter.
- [Detector](equipment/detector.md): the Eiger area detector (production) and the Jungfrau (commissioning) on the detector translation stage.

Cutting across all areas:

- [Controls](equipment/controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the Zebra timing that hardware-sequences the chip-raster collection over the PMAC controller.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the dodal-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i24/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what I24 is designed to do, as design intent. The serial, fixed-target chip-raster collection is a new acquisition Capability over the spine; whether it enters CORA's catalog as a Method is an open question (SSX-1).

## Governance

[Governance](governance.md): who would act at I24 and the trust shape that gates their commands. People and agents are facility principals at the [Diamond Site](../diamond/index.md), carried pending site-level (GOV-1).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I24 content lives, including why this first serial-crystallography deployment coins no new vocabulary and what is deliberately deferred.

## Not yet documented

I24 is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The two scope decisions that are CORA's to make, the fixed-target chip as a Fixture / Subject grid (CHIP-1) and the serial-crystallography Capability (SSX-1), are recorded on the [Model](model.md#deliberately-not-here-yet) page rather than modelled now. The 2-BM deployment shows the shape the operations and live views would take.
