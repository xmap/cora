# Model

*The developer's by-kind index: where each CORA aggregate's ID19 content lives, why this BLISS-floor imaging deployment coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID19 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes ID19 new

ID19 is CORA's first imaging beamline on a **non-EPICS control floor**. Most of the fleet is EPICS (APS, Diamond, NSLS-II, SLAC, all ophyd / bluesky / dodal / pcdshub). ESRF runs BLISS, a Tango-based control system; its soft X-ray sibling ID32 opened the BLISS floor for CORA, and ID19 is the first to bring it to tomographic imaging. That is the novelty, and it is a **control-plane** concern, not a device or technique concern.

The seam model that today reads "EPICS is the floor" generalizes at ID19 to "BLISS / Tango is the floor". CORA's edge conducts the tomographic scan over its `ControlPort` against BLISS scan procedures and Lima detector servers, rather than EPICS IOCs. The test ID19 poses is that the `ControlPort` and the conduct-versus-drive-through seam are genuinely control-system-agnostic, not secretly EPICS-shaped (see [Controls](controls.md), CTRL-1).

## No new families, no new methods

ID19 is a microtomography beamline, and CORA already models microtomography. So holding the device families and the technique constant is deliberate: it isolates the control-plane axis as the only new thing.

- **The rotation stages bind the catalog `RotaryStage`.** `mrsrot` (MR) and `hrsrot` (HR) are the tomographic spins, the master motions of each scan, expected to clock the detector triggering (SAMPLE-1).
- **The sample and detector positioning stages bind the catalog `LinearStage`.** Sample centring (with the `XYOnRotation` pseudo-axis keeping the sample on the rotation axis) and the detector propagation distance are plain linear motion (SAMPLE-1, DET-1).
- **The detectors bind the catalog `Camera`, which presents the Detector Role.** ID19's indirect-detection area detectors (interchangeable Frelon CCD, PCO 4k, PCO Dimax high-speed, and Basler Lima cameras) are thin `Camera` instances (DET-1).
- **The optics bind existing Families.** `Monochromator` (the TripleMono), `Slit` (primary / secondary), `Transfocator` (the white-beam Be-lens transfocator), `Filter` (the attenuator banks, folding in per the i03 precedent rather than a new `Attenuator` Family), `Shutter` (front-end and beam shutters), and `InsertionDevice` (the undulator / wiggler set).
- **The technique is the existing `tomography` Method.** ID19 is a further consumer of the Method the 2-BM pilot and TomoWise carry; the Practice `ID19_microtomography_practice` is carried pending only because ID19 is not yet driven by CORA (TECH-1).

ID19 coins no new Family, nothing graduates, and the catalog is unchanged.

## Two endstations

MR (micro-resolution) and HR (high-resolution) are distinct BLISS sessions (`MRTOMO`, `HRTOMO`) sharing the source and optics. CORA models each as its own sample and detection group under the shared experiment hutch: same Families, same `tomography` Method, different stage stack and magnification optic. This is a Practice-and-settings difference, not new vocabulary.

## Deliberately not here yet

- **The further endstations (`ENDSTATION-1`).** The config carries MH, MED, laminography (LATOMO, a MicosAnka-over-TCP controller with a tilt-transformation pusher), RADIO, PCOTOMO, the SmarAct multi-tower stack, and the FalconX / Mercury fluorescence MCAs. This cut models MR and HR, the two main tomography stations; the rest are noted, not modelled.
- **The PSS permit signals (`PSS-1`).** The TangoShutter handles (`frontend`, `id19/bsh/1`, `id19/bsh/2`) are known, but the personnel-safety permit signals behind them are not in the config; carried pending, not invented.
- **Vendor models, serials, and physical positions.** Not in the config; carried confirm.
- **The simulated devices and full asset-tree scenarios.** No `test_id19_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
