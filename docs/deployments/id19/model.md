# Model

*The developer's index into where ID19 content lives, why this first non-EPICS deployment coins no new family, and the record of what is deliberately deferred.*

ID19 is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's own public BLISS Beacon device database: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/id19/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id19/beamline.yaml) | the device walk with real BLISS / Tango handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/esrf/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/esrf/site.yaml) | the ESRF facility surface, CORA's seventh Site; carries the microtomography Practice |
| Upstream source | [`gitlab.esrf.fr/id19/beamline_configuration`](https://gitlab.esrf.fr/id19/beamline_configuration) | the beamline's own public BLISS Beacon device database the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog Family |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; ID19 reuses the existing `tomography` Method (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers ID19 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes ID19 new

ID19 is CORA's first beamline on a **non-EPICS control floor**. The fleet to date is an EPICS monoculture (APS, Diamond, NSLS-II, SLAC, all ophyd / bluesky / dodal / pcdshub), and the one prior non-EPICS model, MAX IV TomoWise (Tango / Sardana), is design-phase only. ESRF runs BLISS, a Tango-based control system, so ID19 is the fleet's first *live* non-EPICS floor. That is the novelty, and it is a **control-plane** concern, not a device or technique concern.

The seam model that today reads "EPICS is the floor" generalizes at ID19 to "BLISS / Tango is the floor". CORA's edge conducts the tomographic scan over its `ControlPort` against BLISS scan procedures and Lima detector servers, rather than EPICS IOCs. The test ID19 poses is that the `ControlPort` and the conduct-versus-drive-through seam are genuinely control-system-agnostic, not secretly EPICS-shaped (see [Controls](equipment/controls.md), CTRL-1).

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

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
