# 7-BM

*A multi-technique flow and combustion imaging beamline at APS. This page walks the beamline as it is being designed; everything here is taken from the 7-BM operations docs or inferred, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `7-BM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`), Sector 7 |
| Status | In design (recommissioning for APS-U) |
| Techniques | high-speed imaging, radiography, tomography, energy-dispersive diffraction, fluorescence |
| Beam modes | white, monochromatic (DMM, 6 to 18 keV), focused (KB mirrors) |
| Control stack | APS EPICS, the same stack 2-BM uses |

!!! warning "Design phase"
    7-BM is being recommissioned and its operations documentation is partial (empty technique stubs, "to be completed once APS-U operation starts"). Every value on these pages is taken from the docs or inferred, carried as `confirm` until 7-BM staff verify it. The things CORA still needs the team to confirm are collected on [Open questions](questions.md); they are long on purpose.

## What makes 7-BM a different shape from the 2-BM pilot

2-BM is a single-technique micro-CT beamline. 7-BM is the opposite: one beamline hosting several techniques over partly-shared apparatus, with a sample environment 2-BM has nothing like.

- **Multiple techniques, multiple beam modes.** High-speed imaging and energy-dispersive diffraction run white beam; radiography runs a focused beam; tomography runs monochromatic. The beam mode is a per-technique choice, not a fixed source property.
- **Detector modalities beyond the 2D camera.** A germanium energy-dispersive detector records a per-photon spectrum; a PIN photodiode reads point intensity for time-resolved radiography; a high-speed camera captures chopper-gated movie bursts. All three present shapes the 2-BM camera path never needed.
- **A flow and combustion sample environment.** A compressed-air plant, a vacuum system, and metered process gases serve flow and combustion experiments, with a heavier hazard surface (flammable gas, fuel vapor, oxygen deficiency).
- **A heterogeneous floor.** Several technique-specific orchestrators (tomoScan, DataGrabber, the digitizer Python scripts, the EPICS scan record) coexist, where 2-BM has one.

What 7-BM does **not** change: the tomography path reuses the 2-BM model unchanged (the same tomoScan engine and the same Methods), and the APS Site envelope is reused rather than created.

## The beamline

The systems in three areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the source, the front-end and beam-conditioning optics (filters, the rotary chopper, white-beam slits), the energy-selecting and focusing optics (the double multilayer monochromator, the multilayer mirror, the KB pair), and the safety shutters, rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the experiment hutch, the tomography rotation and sample positioning, the energy-dispersive gauge slits, and the flow and combustion sample environment.
- [Detector](equipment/detector.md): the several detector modalities, an imaging camera, a high-speed camera, a point photodiode, and the energy-dispersive detector.

Cutting across all three:

- [Controls](equipment/controls.md): the EPICS control stack and the DG645 timing and triggering scheme.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/7-bm/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what 7-BM is designed to do, as design intent. Each is a portable [Catalog](../../catalog/methods.md) Method that an APS [Practice](../aps/index.md#the-techniques-adapted-here) would adapt once the technique is in the pilot scope.

## Governance

[Governance](governance.md): who will act at 7-BM and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's 7-BM content lives.

## Not yet documented

7-BM is pre-build for CORA, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written yet: a runbook for an unmodelled beamline would be invention, not record. They join these pages as the techniques enter the pilot scope. The 2-BM deployment shows the shape they will take.
