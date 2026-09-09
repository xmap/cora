# Notes

## Techniques

*What CORA would run at IOS: ambient-pressure photoemission and soft X-ray absorption, each a [Catalog](../../catalog/methods.md) Method. IOS follows the deferral discipline of the soft X-ray beamlines that brought each technique family to CORA. First cut.*

IOS's techniques are soft X-ray surface science under working conditions: ambient-pressure photoemission and soft NEXAFS / XAS. The Methods below render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings them into the catalog. Following [SST](../sst/notes.md#techniques), IOS records **no Practice** at the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here) yet, because each technique sits on a pending or deferred Method; each binding lands when its Capability does.

| Technique | Mode | Notes |
| --- | --- | --- |
| Ambient-pressure photoemission (AP-XPS / AP-PES) | fixed energy, gas atmosphere | photoelectron spectra on the SPECS hemispherical analyzer under a working gas pressure; the ESM / SST photoemission family, new Capability pending (`TECH-1`) |
| Soft NEXAFS / XAS | energy sweep | absorption by total / partial electron yield (drain current through the scaler) and partial fluorescence yield (the Vortex / Xspress3), over a PGM energy scan; the BMM energy-scan question (`ENERGY-1`, `TECH-1`) |

Both need the [grating monochromator](source.md) (the incident energy), the [AP-PES manipulator](sample.md) (the sample in the analyzer focus), and the [analyzer and yield chain](detector.md). The detection mode (TEY drain current, PEY kinetic-energy-selected electrons through the analyzer, PFY region-of-interest fluorescence) is a setting, not a separate technique.

### Why the Capabilities stay deferred

Each of IOS's techniques sits on a Capability the catalog does not yet carry, and the discipline is the same one the originating beamlines applied:

- **Ambient-pressure photoemission** follows NSLS-II [ESM](../esm/index.md). The only photoemission Method slug the catalog anticipates is `angle_resolved_photoemission`, coined for ESM's ARPES; IOS's AP-XPS is chemical-state photoemission under a gas atmosphere, not angle-resolved, so reusing that slug would name a shape it was not coined for. The device Role already exists (the analyzer presents Detector); what is new is the science Capability, and the ambient-pressure context on top of it.
- **Soft NEXAFS / XAS** follows [BMM](../bmm/index.md): the measurement is the energy sweep itself, the deferred `energy_scan` Capability (`ENERGY-1`). It is a different shape from the crystal-emission-spectrometer `xas_spectroscopy` that LCLS-MFX and ISS left pending (which disperses emitted photons through an analyzer crystal); IOS's NEXAFS reads absorption by electron and fluorescence yield.

So IOS reinforces both technique families at one more instrument without coining either, and records no Practice; each binding lands when its Capability does (`TECH-1`, `ENERGY-1`).

### The ambient-pressure context

What distinguishes IOS from the fleet's other photoemission and absorption beamlines is that it runs under a working gas atmosphere (in situ / operando), not in vacuum. That context is the heart of the science, but the hardware that delivers it (the reaction cell, the gas dosing and mixing, the pressure control, the sample heating) is not in the profile collection and is carried as the headline open question (`INSITU-1`), not modelled. When a Method for ambient-pressure spectroscopy is eventually authored, the ambient-pressure context would be a Practice-level adaptation (the gas, pressure, and temperature settings) on the photoemission and absorption Methods, not a separate technique.

### Not modelled yet

The concrete acquisition recipes (the energy scans with their coupled EPU edge-table switching, the spectrum acquisitions, the yield reads) are not written yet; they join as the deployment approaches the point where CORA drives IOS. The per-technique reduction (photoemission spectra, NEXAFS spectra) is `ComputePort` work, not beamline Methods. See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at IOS, and the trust shape that will gate it. First cut.*

Governance at IOS follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

IOS is not yet driven by CORA, so this shape is not yet instantiated. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md) (`GOV-1`).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. The PSS search-and-secure permit signals and the photon shutters are absent from the profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and not invented here (`PSS-1`).

IOS carries the hazard classes that come with its instruments, which an experiment Clearance would carry; those land with the instruments that bring them:

- the soft X-ray beam in the optics and endstation enclosures;
- the ultra-high vacuum of the PGM, the KB system, and the analyzer endstation;
- and, distinctively, the **ambient-pressure / operando sample environment**: a working gas atmosphere, the gas dosing and handling, and the sample heating that the reaction cell brings. That hardware is not in the profile collection, so its hazards (gas handling, pressure, temperature) are carried pending with the cell itself, not invented (`INSITU-1`).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives IOS, following the [2-BM governance](../2-bm/governance.md) shape. It re-tests the Site and Federation kernel rather than introducing a new trust model.

## Model

*The developer's by-kind index: where each CORA aggregate's IOS content lives, how the ambient-pressure environment is carried as a deferral, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at IOS |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes IOS new

The honest answer is: little on the hardware, one real thing on the science. IOS measures surface and interface chemistry under working conditions by ambient-pressure X-ray photoemission (AP-XPS / AP-PES) and soft NEXAFS / XAS. Every device it carries is a fleet shape ported once more:

- the SPECS hemispherical analyzer binds the catalog `ElectronAnalyzer`, the third sighting after ESM and SST;
- the VLS-PGM binds `GratingMonochromator`, a further consumer after SIX / CSX / ESM / SST;
- the Vortex and Xspress3 silicon-drift detectors bind `EnergyDispersiveSpectrometer`;
- the AP-PES four-axis stage binds `Manipulator`;
- the two canted EPUs are the same `SR:C23-ID` twin-EPU straight CSX reads, with IOS on the 23-ID-2 branch.

IOS's one genuinely distinct contribution is **in-situ / operando ambient-pressure spectroscopy**: measuring chemistry under a working gas atmosphere rather than in vacuum. That is the heart of the beamline, but the hardware that makes it (the reaction cell, the gas dosing and mixing manifold, the pressure control, the sample heating) is not in the profile collection, so CORA carries it as the headline open question (`INSITU-1`) and does not invent it. IOS also re-tests the NSLS-II Site and Federation kernel once more; the value there is confidence that the kernel holds, not a new abstraction.

### No new families

IOS coins no new Family and changes nothing in the catalog.

- **The SPECS analyzer binds `ElectronAnalyzer`** (a photon-in / electron-out hemispherical analyzer, the ESM / SST precedent), the third sighting and the first non-Scienta and first ambient-pressure one; the analyzer make, the lens-mode set, and the pass-energy range are a per-Asset settings or bound-Model difference, not a Family split (`DET-1`).
- **The VLS-PGM binds `GratingMonochromator`** (the soft X-ray plane-grating optic, the SIX / CSX precedent); the energy is its master axis with the EPU edge-table switching coupled in (`MONO-1`).
- **The fluorescence detectors all reuse:** the Vortex (silicon-drift detector + MCA) and the Xspress3 (four-channel silicon-drift) bind `EnergyDispersiveSpectrometer`; the AP-PES stage binds `Manipulator`; the XAS-endstation translation binds `LinearStage`; the front-end and branch mirrors and the KB pair bind `Mirror`; the branch slits bind `Slit`; the front-end and branch shutters bind `Shutter`; the scaler and the Au-mesh I0 reference bind `FluxMonitor`; the surface-prep ion gun binds `GenericProbe`; the exit-slit diagnostic camera binds `Camera`; the two EPUs bind `InsertionDevice`.

### How the ambient-pressure environment is carried (no device)

The ambient-pressure / operando sample environment is what makes IOS IOS, and it is carried as a deferral, not a device:

- the sample positioning that **is** in the profile (the APPES four-axis manipulator) is modelled as `Manipulator`;
- the gas dosing and mixing, the pressure control, and the sample heating that the reaction cell needs are **not** in the profile collection (no gas, pressure, or temperature PVs), so they are carried as the headline open question (`INSITU-1`), not modelled.

This is the same discipline the fleet's other in-situ accessories follow (SMI defers its humidity cell and blade coater, SST defers its ADR cryostat and syringe pump, ISS defers its broader sample environment): the device Roles that exist are modelled, and the sample-environment hardware that is not in the public source is deferred to an open question rather than invented. Whether a `ReactionCell` or near-ambient-pressure-cell Family is ever earned is a future owner decision, pending a second ambient-pressure deployment and the real PVs (`INSITU-1`).

### Why no Practice is recorded

IOS records **no Practice** at the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here), following [SST](../sst/notes.md#techniques), the closest sibling (the soft / tender NSLS-II photoemission-and-absorption beamline that also recorded none):

- IOS's ambient-pressure photoemission is photoemission, but the only photoemission Method slug the catalog anticipates is `angle_resolved_photoemission`, coined for ESM's ARPES; AP-XPS is chemical-state, not angle-resolved, so reusing that slug would name a shape it was not coined for;
- IOS's soft NEXAFS / XAS is absorption by electron and fluorescence yield over an energy sweep, which leans on the deferred `energy_scan` Capability (the BMM question, `ENERGY-1`) and is a different shape from the crystal-emission-spectrometer `xas_spectroscopy` that MFX and ISS left pending.

So no Practice is bound until a Method lands; IOS is bound to the Site through the beamline list, and each binding lands when its Capability does (`TECH-1`, `ENERGY-1`).

### Deliberately not here yet

- **The ambient-pressure reaction cell (`INSITU-1`).** The gas dosing / mixing manifold, the pressure control, and the sample heating are absent from the profile collection (no gas / pressure / temperature PVs) and are not invented; the sample positioning that is in the profile is modelled as `Manipulator`. A second ambient-pressure deployment and the real PVs would earn the abstraction.
- **The sample transfer / load-lock.** A load-lock gate valve (`IOXAS-GV:4`) is in the profile but no sample-transfer motor PVs are, so the transfer mechanism is deferred (`SAMPLE-1`).
- **The gate valves and the storage-ring readback.** The vacuum gate valves (`XF:23ID2-VA`) and the storage-ring current (`XF:23ID-SR`) are vacuum plumbing and facility observation, carried as notes, not Assets.
- **The photoemission and NEXAFS Methods.** Whether ambient-pressure photoemission and soft NEXAFS enter CORA's catalog as Capabilities / Methods is an owner decision; the techniques render unlinked, and no Practice is recorded (`TECH-1`, `ENERGY-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_ios_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the IOS team to confirm before the model can be trusted.*

IOS was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/ios-profile-collection](https://github.com/NSLS2/ios-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | The 23-ID canted straight: do the two EPUs feed both CSX (23-ID-1) and IOS (23-ID-2), and is IOS one root Unit? | One root Unit `IOS` fed by the canted twin-EPU straight (the 32-ID / CSX precedent). | The source topology in the [descriptor](index.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:23IDA` / `XF:23ID2-OP` / `XF:23ID2-ES` separate shielded hutches or beam zones within fewer? | Two enclosures (front-end optics + the 23-ID-2 branch). | The Enclosure grouping. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the ios-profile-collection current and correct, and is a queue server in use? | The handles in the descriptor are taken from the profile collection and carried confirm; queue-server use unknown. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the front-end shutter is `XF:23ID-PPS{Sh:FE}` and the branch shutter `XF:23ID2-PPS{PSh}`. | The Enclosure permit signals. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (`EPU:1`, `EPU:2`): type, period, the polarization (phase) model, and the energy-edge lookup tables. | Two `InsertionDevice` Assets; the phase axis and the edge table carried as settings. | The insertion-device specs. |
| MONO-1 | Blocks-go-live | The VLS-PGM: the grating line densities, the c-value model, and the 200-2200 eV range. | A `GratingMonochromator` Asset with energy / mirror-pitch / mirror-x / grating-pitch / grating-x axes and an energy fly-scan. | The monochromator model. |
| OPT-1 | Nice-to-have | The mirrors (M1A front-end, M1B1 / M1B2 deflecting, M3B branch, DM1, the KB pair): coatings and axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The branch slits (`Slt:1` gap-center, `Slt:2` vertical): the internal axis maps. | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |

### Sample and ambient-pressure environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-build | The APPES manipulator (x / y / z / rotation) and the IOXAS stage: the axis roles, and the sample-transfer / load-lock mechanism (the `IOXAS-GV:4` valve is present, no transfer-motor PVs are). | A `Manipulator` and a `LinearStage`; the transfer mechanism deferred. | The sample-positioning model. |
| SAMPLE-2 | Nice-to-have | The SPECS surface-prep sputter / ion gun: control and role. | A `GenericProbe` auxiliary, not the analyzer. | The surface-prep model. |
| INSITU-1 | Blocks-build | The ambient-pressure reaction cell, the gas dosing / mixing manifold, the pressure control, and the sample heating: there are no gas / pressure / temperature PVs in the profile collection. | The ambient-pressure sample environment is out of the profile collection and not modelled until the hardware and PVs are provided. | The operando sample environment, IOS's defining feature. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The SPECS hemispherical analyzer: model (Phoibos NAP?), pass-energy range, lens-mode set, and angular acceptance. | An `ElectronAnalyzer` Asset; analyzer make and ranges are settings. | The analyzer model. |
| DET-2 | Blocks-go-live | The Vortex and Xspress3 silicon-drift detectors: models, channels, and the ROI map (and why one of four Xspress3 channels is active). | `EnergyDispersiveSpectrometer` Assets; ROI / channel maps partial. | The fluorescence-detector models. |
| DET-3 | Nice-to-have | The scaler, the `CurrAmp:1/2/3` current amplifiers, and the Au mesh: the electron-yield (TEY / PEY) channel wiring and the I0 reference. | `FluxMonitor` Assets; the yield-chain wiring partial. | The yield-chain map. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENERGY-1 | Nice-to-have | Is the NEXAFS / XAS measurement a continuous PGM energy fly-scan (with coupled EPU edge-table switching) or a stepped scan? | The PGM energy fly-scan is available; the sweep-as-measurement is carried as intent. | The energy-scan mode. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and cooling supplies the UHV optics, the KB system, and the analyzer endstation draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
