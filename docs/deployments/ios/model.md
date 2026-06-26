# Model

*The developer's index into where IOS content lives, why this deployment coins no new family, how the ambient-pressure environment is carried as a deferral, and the record of what is deliberately deferred. First cut.*

IOS is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/ios/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/ios/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `IOS` added to its beamline list, with no Practice recorded yet (below) |
| Extraction provenance | [NSLS2/ios-profile-collection](https://github.com/NSLS2/ios-profile-collection) | the `startup/*.py` device classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the photoemission and NEXAFS Methods are pending / deferred (`TECH-1`, `ENERGY-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers IOS Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes IOS new

The honest answer is: little on the hardware, one real thing on the science. IOS measures surface and interface chemistry under working conditions by ambient-pressure X-ray photoemission (AP-XPS / AP-PES) and soft NEXAFS / XAS. Every device it carries is a fleet shape ported once more:

- the SPECS hemispherical analyzer binds the catalog `ElectronAnalyzer`, the third sighting after ESM and SST;
- the VLS-PGM binds `GratingMonochromator`, a further consumer after SIX / CSX / ESM / SST;
- the Vortex and Xspress3 silicon-drift detectors bind `EnergyDispersiveSpectrometer`;
- the AP-PES four-axis stage binds `Manipulator`;
- the two canted EPUs are the same `SR:C23-ID` twin-EPU straight CSX reads, with IOS on the 23-ID-2 branch.

IOS's one genuinely distinct contribution is **in-situ / operando ambient-pressure spectroscopy**: measuring chemistry under a working gas atmosphere rather than in vacuum. That is the heart of the beamline, but the hardware that makes it (the reaction cell, the gas dosing and mixing manifold, the pressure control, the sample heating) is not in the profile collection, so CORA carries it as the headline open question (`INSITU-1`) and does not invent it. IOS also re-tests the NSLS-II Site and Federation kernel once more; the value there is confidence that the kernel holds, not a new abstraction.

## No new families

IOS coins no new Family and changes nothing in the catalog.

- **The SPECS analyzer binds `ElectronAnalyzer`** (a photon-in / electron-out hemispherical analyzer, the ESM / SST precedent), the third sighting and the first non-Scienta and first ambient-pressure one; the analyzer make, the lens-mode set, and the pass-energy range are a per-Asset settings or bound-Model difference, not a Family split (`DET-1`).
- **The VLS-PGM binds `GratingMonochromator`** (the soft X-ray plane-grating optic, the SIX / CSX precedent); the energy is its master axis with the EPU edge-table switching coupled in (`MONO-1`).
- **The fluorescence detectors all reuse:** the Vortex (silicon-drift detector + MCA) and the Xspress3 (four-channel silicon-drift) bind `EnergyDispersiveSpectrometer`; the AP-PES stage binds `Manipulator`; the XAS-endstation translation binds `LinearStage`; the front-end and branch mirrors and the KB pair bind `Mirror`; the branch slits bind `Slit`; the front-end and branch shutters bind `Shutter`; the scaler and the Au-mesh I0 reference bind `FluxMonitor`; the surface-prep ion gun binds `GenericProbe`; the exit-slit diagnostic camera binds `Camera`; the two EPUs bind `InsertionDevice`.

## How the ambient-pressure environment is carried (no device)

The ambient-pressure / operando sample environment is what makes IOS IOS, and it is carried as a deferral, not a device:

- the sample positioning that **is** in the profile (the APPES four-axis manipulator) is modelled as `Manipulator`;
- the gas dosing and mixing, the pressure control, and the sample heating that the reaction cell needs are **not** in the profile collection (no gas, pressure, or temperature PVs), so they are carried as the headline open question (`INSITU-1`), not modelled.

This is the same discipline the fleet's other in-situ accessories follow (SMI defers its humidity cell and blade coater, SST defers its ADR cryostat and syringe pump, ISS defers its broader sample environment): the device Roles that exist are modelled, and the sample-environment hardware that is not in the public source is deferred to an open question rather than invented. Whether a `ReactionCell` or near-ambient-pressure-cell Family is ever earned is a future owner decision, pending a second ambient-pressure deployment and the real PVs (`INSITU-1`).

## Why no Practice is recorded

IOS records **no Practice** at the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here), following [SST](../sst/techniques.md), the closest sibling (the soft / tender NSLS-II photoemission-and-absorption beamline that also recorded none):

- IOS's ambient-pressure photoemission is photoemission, but the only photoemission Method slug the catalog anticipates is `angle_resolved_photoemission`, coined for ESM's ARPES; AP-XPS is chemical-state, not angle-resolved, so reusing that slug would name a shape it was not coined for;
- IOS's soft NEXAFS / XAS is absorption by electron and fluorescence yield over an energy sweep, which leans on the deferred `energy_scan` Capability (the BMM question, `ENERGY-1`) and is a different shape from the crystal-emission-spectrometer `xas_spectroscopy` that MFX and ISS left pending.

So no Practice is bound until a Method lands; IOS is bound to the Site through the beamline list, and each binding lands when its Capability does (`TECH-1`, `ENERGY-1`).

## Deliberately not here yet

- **The ambient-pressure reaction cell (`INSITU-1`).** The gas dosing / mixing manifold, the pressure control, and the sample heating are absent from the profile collection (no gas / pressure / temperature PVs) and are not invented; the sample positioning that is in the profile is modelled as `Manipulator`. A second ambient-pressure deployment and the real PVs would earn the abstraction.
- **The sample transfer / load-lock.** A load-lock gate valve (`IOXAS-GV:4`) is in the profile but no sample-transfer motor PVs are, so the transfer mechanism is deferred (`SAMPLE-1`).
- **The gate valves and the storage-ring readback.** The vacuum gate valves (`XF:23ID2-VA`) and the storage-ring current (`XF:23ID-SR`) are vacuum plumbing and facility observation, carried as notes, not Assets.
- **The photoemission and NEXAFS Methods.** Whether ambient-pressure photoemission and soft NEXAFS enter CORA's catalog as Capabilities / Methods is an owner decision; the techniques render unlinked, and no Practice is recorded (`TECH-1`, `ENERGY-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_ios_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
