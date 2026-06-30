# I03

*A macromolecular-crystallography (MX) beamline at Diamond Light Source. This page walks the beamline as it is being modelled; everything here is reverse-engineered from Diamond's open `dodal` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `I03` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`), the second Diamond beamline after [I22](../i22/index.md) |
| Status | Design-phase modelling exercise (not a CORA pilot) |
| Technique | macromolecular crystallography (rotation data collection, grid scan, autonomous sample exchange) |
| Beam | undulator source, double-crystal monochromator, focusing mirror |
| Control stack | Diamond EPICS (driven by GDA and the hyperion / mx-bluesky plan suite) |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    I03 is a real, operating beamline, but it is **not** on the CORA pilot roadmap (APS to MAX IV). It is modelled here, like I22, to test that the dry, correct device facts in Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library seed CORA's intentional model, and to push the model along axes the tomography and scattering pilots never touched: a multi-axis goniometer and autonomous sample handling. Every value is reverse-engineered from dodal or inferred, carried as `confirm` until Diamond staff verify it. The things CORA still needs the team to confirm are on [Open questions](questions.md).

## What I03 adds over I22 and the tomography pilots

I22 (SAXS/WAXS) tested scattering; I03 (MX) tests crystallography, and it is the first deployment to exercise two shapes the others could not.

- **It graduates a catalog Family.** The catalog carried `Goniometer` as a pending, documented-but-undefined kind. I03's `Smargon` is CORA's first canonical six-axis MX goniometer (omega / chi / phi rotation plus x / y / z sample-centring), so I03 is the deployment that **graduates Goniometer from pending to defined**. This is the first new catalog Family any Diamond deployment has earned; I22 earned none.
- **It exercises autonomous sample handling.** I03 carries a sample-changing robot. Following the 19-BM precedent, this is **not** a new Family: it is one Positioner-presenting Asset that loads and unloads a `Subject`, gated by a Clearance, with the vendor robot in a bound Model. An adversarial new-kind review refuted a `SampleChanger` Family (the existing Positioner Role already covers it).
- **It reuses families I22 introduced rather than coining synonyms.** The storage-ring state reuses the loose `StorageRing`; the flux monitors and the cryo / thaw actuators reuse `FluxMonitor` and `TemperatureController` (both since graduated to catalog Families, presenting the Sensor and `Regulator` Roles); the beam-position monitor reuses 2-BM's loose `Diagnostic` family. The flux monitors at a second deployment were part of the rule-of-three that graduated `FluxMonitor` into the catalog.

What I03 keeps the same: the descriptor carries the real dodal EPICS PV handles (as I22 did), and the model reuses existing Families wherever one fits (InsertionDevice, Monochromator, Mirror, Filter, Table, BeamStop, Aperture, Shutter, Camera, LinearStage, TimingController). The attenuator folds into Filter and the aperture-scatterguard into Aperture, both adversarially verified.

## The beamline

The systems in three areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the undulator and storage-ring state, the energy-selecting and focusing optics (the double-crystal monochromator, the focusing mirror with selectable coatings and bimorph bend), the filters and collimation table, the beamstop, aperture-scatterguard, and shutters, and the beam-position and flux diagnostics, rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the experiment hutch, the Smargon goniometer, the sample-centring base, the automated sample-changing robot, and the sample environment (illumination, cryo-cooling, thawing).
- [Detector](equipment/detector.md): the Eiger area detector on its translation, and a retractable fluorescence detector.

Cutting across all three:

- [Controls](equipment/controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the Zebra / PandABox timing and triggering.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the dodal-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i03/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what I03 is designed to do, as design intent. MX data collection, grid scan, and the autonomous sample-exchange loop are new Methods over the spine; which enter scope is an open question (TECH-1).

## Governance

[Governance](governance.md): who would act at I03 and the trust shape that gates their commands, including the Clearance that would gate autonomous robot loading. People and agents are facility principals at the [Diamond Site](../diamond/index.md).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I03 content lives, including the Goniometer graduation.

## Not yet documented

I03 is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The 2-BM deployment shows the shape they would take.
