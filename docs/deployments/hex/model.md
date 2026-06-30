# Model

*The developer's index into where HEX content lives, why this deployment coins no new family, how it models the multi-technique endstation and the heavy sample tower, and the record of what is deliberately deferred. First cut.*

HEX is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's public sources: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/hex/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/hex/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `HEX` added to its beamline list, with the tomography / radiography / EDXD / powder-diffraction Practices |
| Extraction provenance | [NSLS2/hex-profile-collection](https://github.com/NSLS2/hex-profile-collection), [NSLS2/hextools](https://github.com/NSLS2/hextools) | the `startup/*.py` device definitions and the detector helpers the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; tomography is graduated, the diffraction Methods are pending (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers HEX Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes HEX new

The honest answer is: not much on any single technique, and three real things on structure. HEX measures engineering-materials and energy-storage samples by high-energy imaging / tomography, energy-dispersive diffraction (EDXD), and angle-dispersive / powder diffraction (ADXD). The imaging overlaps the fleet heavily (the 2-BM pilot, the NSLS-II FXI), and the diffraction reuses the pending energy-dispersive (7-BM) and powder (i11) Methods. That side reuses the existing `Camera` / `Scintillator` / `RotaryStage` / `LinearStage` / `EnergyDispersiveSpectrometer` / `InsertionDevice` / `Monochromator` / `Filter` vocabulary and contributes reinforcement, not novelty.

HEX's three genuinely distinct contributions are:

- **Multi-technique in one experiment.** All three techniques run in the single F-hutch endstation during one experiment, with detectors and optics moved into the beam remotely. CORA models this as multiple Methods over one endstation, the technique switch a positioning leg over the `ControlPort`, not a new Capability (`TECH-1`).
- **Very large and heavy engineering samples.** The 500 kg removable sample tower is a heavy reconfigurable fixture, not a precision goniometer. It reuses `Table` + `RotaryStage` + `LinearStage` with capacity and the configuration set as settings (`STAGE-1`).
- **A high-energy hard X-ray source.** The superconducting wiggler (4.3 T, 70 mm period) reaching 200 keV monochromatic is a first for the fleet. It binds the existing `InsertionDevice` Family, with the field and energy reach as source specs (`SCW-1`).

## No new families

HEX coins no new Family and changes nothing in the catalog.

- **The superconducting wiggler binds `InsertionDevice`** (the undulator precedent at the NSLS-II siblings). The beam mode (white 30 to 250 keV versus monochromatic 30 to 200 keV) is selected by inserting or retracting the monochromator first crystal, so it is a setting on the optic, not a second source (`MONO-2`).
- **The optics reuse:** the low-energy filters bind `Filter`; the bent-Laue monochromator binds `Monochromator` (a Bragg optic, not the soft X-ray `GratingMonochromator`); the incident energy is a `PseudoAxis` over it; the front-end slits bind `Slit`.
- **The sample side reuses:** the tomographic rotation binds `RotaryStage`; the sample translations bind `LinearStage`; the 500 kg removable tower binds `Table`.
- **The detection side reuses:** the Kinetix sCMOS and Phantom Veo cameras and the PerkinElmer flat panel bind `Camera`; the imaging scintillator-lens table binds `Scintillator`; the detector / optics positioning binds `LinearStage`; the GeRM germanium strip detector binds the existing `EnergyDispersiveSpectrometer` Family (below).

## The GeRM strip detector reuses an earned family

The one place HEX looks like it might force a new abstraction is its energy-dispersive detector, the GeRM germanium strip detector that produces a per-channel energy spectrum rather than a 2D frame. That shape is already in the catalog: the `EnergyDispersiveSpectrometer` Family was earned by the APS 2-ID fluorescence detector and the 7-BM germanium energy-dispersive-diffraction detector, and its definition presents the `Sensor` Role (a scalar or short-vector Reading per point) and explicitly spans the silicon-drift and germanium variants. HEX's GeRM detector is the **third consumer** of that Family, with channel count and energy resolution per-Asset settings. So EDXD on HEX is a reuse, not a graduation, and no catalog or loose-family change is forced (`DET-2`).

## How the multi-technique switch is modelled (no new capability)

The F-hutch offers imaging / tomography, EDXD, and ADXD in one experiment. CORA models the switch between them as a **positioning action over existing devices**, not a new Capability or device:

- each technique has its detector already on the [detection](equipment/detector.md) side (the Kinetix cameras, the PerkinElmer flat panel, the GeRM strip detector);
- a `LinearStage` (`DetectorStage`) moves the chosen detector or optic into the beam;
- CORA conducts that positioning over the `ControlPort`, then runs the technique's Method.

So the "multi-technique endstation" is a Practice-level sequence, not a fused mega-instrument. The stress it puts on the model, that a single endstation hosts several one-technique acquisitions selected by positioning, is resolved by treating technique selection as a conducted positioning leg ahead of acquisition (`TECH-1`). No new family is coined for the switch.

## Deliberately not here yet

- **The B / C / D / E hutch contents (`ENC-1`, `LAYOUT-1`).** HEX is designed for six enclosures (A = FOE, B, C, D, E, F). All six are declared in the descriptor, forward-looking, but only the operational FOE (`hex-foe`) and F-hutch (`hex-endstation`) carry devices; B (not erected) and C / D / E (future-upgrade shells) are declared as device-free enclosures and carry no Assets in this cut. The descriptor validates that every device's enclosure ref is declared but allows an unreferenced enclosure, so the shells are honest forward-looking placeholders, not invented contents. The satellite-building identity and the per-hutch positions are carried as world-facts (`SAT-1`, `LAYOUT-1`).
- **The monochromatic focusing optic (`FOCUS-1`).** The beamline page lists focusing for the monochromatic beam as "being commissioned." It is not yet modelled as a device; what optic it is and its target spot are carried as a world-fact.
- **In-situ sample environments (`INSITU-1`).** HEX's science is operando battery and engineering-materials work, but no specific rig (load frame, furnace, cryostat, battery cycler) is source-confirmed as installed; the endstation is "capable of housing" user-brought environments. Per earn-the-abstraction, no in-situ rig is modelled as an Asset in this cut. If a specific rig is confirmed installed and a second fleet beamline brings one, that is the trigger to consider a sample-environment Family.
- **The heavy-sample stage as a distinct family (`STAGE-1`).** The 500 kg removable tower stresses the assumption that a sample-orientation Asset is small and goniometer-like. CORA holds the line: capacity and the configuration set (configs A to D) are settings on a reused `Table` + `RotaryStage` + `LinearStage`, not a new `HeavyStage` Family. A second fleet beamline with a heavy removable tower would be the rule-of-three trigger.
- **The diffraction Methods.** Whether energy-dispersive diffraction, radiography, and powder diffraction enter CORA's catalog as Capabilities / Methods is an owner decision; the Practices render unlinked, pending. EDXD and radiography are shared with 7-BM and powder diffraction with i11 (`TECH-1`).
- **Pair-distribution-function and 3DXRD.** Public sources do not list PDF (that is NSLS-II 28-ID / [XPD](../xpd/index.md)) or three-dimensional X-ray diffraction for HEX, so neither is modelled or assumed (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_hex_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
