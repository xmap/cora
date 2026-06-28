# I22

*A small- and wide-angle X-ray scattering (SAXS/WAXS) beamline at Diamond Light Source. This page walks the beamline as it is being modelled; everything here is reverse-engineered from Diamond's open `dodal` controls library or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `I22` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`) |
| Status | Design-phase modelling exercise (not a CORA pilot) |
| Techniques | small-angle scattering (SAXS), wide-angle scattering (WAXS), routinely simultaneous |
| Beam | undulator source, double-crystal monochromator, KB focusing mirrors |
| Control stack | Diamond EPICS (driven by GDA and bluesky/blueapi) |

!!! warning "Design phase, and a deliberate off-roadmap exercise"
    I22 is a real, operating beamline, but it is **not** on the CORA pilot roadmap (APS to MAX IV). It is modelled here to test two things: that the dry, correct device facts in Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library can seed CORA's intentional model, and that the model generalizes beyond the tomography pilots. Every value is reverse-engineered from dodal or inferred, carried as `confirm` until Diamond staff verify it. The things CORA still needs the team to confirm are collected on [Open questions](questions.md).

## What makes I22 a different shape from the tomography pilots

The CORA pilots (2-BM, and the design-phase 7-BM / 19-BM / 32-ID / TomoWISE) are imaging and tomography beamlines. I22 is a scattering beamline, which stresses the model along an axis the pilots never touched, while sharing most of the equipment.

- **A scattering technique, not imaging.** SAXS and WAXS record diffraction patterns on area detectors, not projection images of a rotating sample. There is no rotation stage and no tomographic reconstruction. The science Capabilities (small-angle, wide-angle) are new vocabulary the catalog does not yet carry (TECH-1).
- **Two detectors, run simultaneously.** The routine I22 mode runs a SAXS detector at long camera length and a WAXS detector at short camera length at the same time. They are the same camera model, one Family, two Asset instances separated by distance and role, not a Family split.
- **Quantitative flux, not just position.** Incident and transmitted ion chambers (I0 / It) read beam current for transmission and dose, presenting the Sensor Role the imaging camera path never needed.
- **It carries real EPICS handles.** Unlike the TomoWISE scaffold (MAX IV Tango, PVs unknown), dodal records I22's real EPICS PV prefixes. So this scaffold carries `pv` on every device: the dry, correct controls fact is the whole point of the exercise.

What I22 does **not** force into the model: it earns no new catalog Family. dodal's device set maps onto existing Families (Camera, Mirror, Monochromator, InsertionDevice, Slit, BeamStop, LinearStage, TimingController, plus the now-graduated TemperatureController, FluxMonitor, Transfocator, and FlowController), plus the loose `StorageRing` design-intent family an adversarial new-kind review deferred (see [Inventory](inventory.md)).

## The beamline

The systems in three areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the undulator and the machine-level storage-ring state, the focusing and monochromating optics (the double-crystal monochromator, the KB mirror pair, the adaptive bimorphs, the transfocator), and the beam-defining slits, rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the experiment hutch, the sample base and on-axis-view camera, the incident and transmitted flux monitors, and the sample-environment actuators.
- [Detector](equipment/detector.md): the SAXS and WAXS area detectors that record simultaneously, and the beamstops that protect them.

Cutting across all three:

- [Controls](equipment/controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the PandABox timing and triggering.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families, the dodal-derived PV handles, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i22/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what I22 is designed to do, as design intent. SAXS and WAXS are scattering Capabilities the cross-facility [Catalog](../../catalog/capabilities.md) does not yet define; which enter scope is an open question (TECH-1).

## Governance

[Governance](governance.md): who would act at I22 and the trust shape that gates their commands. People and agents are facility principals at the [Diamond Site](../diamond/index.md).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I22 content lives.

## Not yet documented

I22 is a modelling exercise for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written: a runbook for an unmodelled, off-roadmap beamline would be invention, not record. The 2-BM deployment shows the shape they would take.
