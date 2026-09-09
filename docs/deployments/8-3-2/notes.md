# Notes

## Techniques

*What the modelled part of 8.3.2 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../als/index.md#the-techniques-adapted-here) is how a facility adapts it. 8.3.2 is a hard X-ray micro-tomography beamline: its techniques reuse Methods CORA's catalog already carries.

### Hard X-ray micro-tomography

8.3.2 sets the X-ray energy with the monochromator (6,000-43,000 eV from the Superbend source), then rotates the sample on the tomographic rotary stage while the scintillator, objective, and camera record projections. It images non-destructively in 3D at ~1 micron resolution, with absorption and propagation-phase contrast (the detector stack's `camera_distance` sets the propagation distance).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Tomography | [`tomography`](../../catalog/methods.md) | absorption and propagation-phase micro-CT, the [rotary stage](sample.md) stepped against the [scintillator + camera](detector.md); reuses the catalog tomography Method (the 2-BM pilot) |
| Continuous-rotation tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | fast fly-scan tomography, the [rotary stage](sample.md) in continuous rotation as the trigger master (`TRIG-1`); reuses the catalog continuous-rotation Method |

Tomography needs the [incident energy](source.md) set by the [monochromator](source.md), the [rotary stage and sample positioning](sample.md), and the [scintillator + objective + camera](detector.md), with the [detector stack](detector.md) setting the sample-to-detector propagation distance.

### A new Site on familiar vocabulary

8.3.2 is the ALS's hard X-ray micro-CT beamline, and it ties into the tomography lineage CORA already models: the same imaging device anatomy as the 2-BM pilot, the NSLS-II FXI design, and the ALBA FAXTOR design (a bending-magnet or insertion-device source, an energy-setting optic, a rotary-stage endstation, and an indirect scintillator + camera detector). It reuses the `tomography` and `continuous_rotation_tomography` Methods directly; none forces a new device family.

### Not modelled yet

The concrete acquisition recipes (the fly-scan tomography sequences and their counting times, the flat / dark sequencing, the propagation-phase setups) are not written yet; they join as the deployment approaches the point where CORA drives 8.3.2. See [Open questions](#open-questions) for the world-facts to confirm first, in particular which sample-stack axis is the tomographic rotation (`ROT-1`) and the triggering scheme (`TRIG-1`).

## Governance

*Who will act at 8.3.2, and the trust shape that will gate it. First cut.*

Governance at 8.3.2 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ALS Site](../als/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

8.3.2 is CORA's first ALS deployment, so ALS is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [ALS Site](../als/index.md#safety-and-governance), shared across the facility's beamlines, until ALS staff confirm them (`GOV-1`). 8.3.2 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives 8.3.2, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. ALS publishes no per-beamline personnel-safety permit signals or photon / front-end shutters, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ALS Site](../als/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 8.3.2, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 8.3.2 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 8.3.2 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes 8.3.2 new

8.3.2 is two things at the Site level and nothing new at the vocabulary level. It is CORA's **first ALS Site** (the Advanced Light Source at LBNL), a re-test of the Site and Federation kernel, and the **first BCS / LabVIEW** control plane CORA models. The ALS originated BCS (the Beamline Control System), so this is the controls house-style's home facility; every prior Site is EPICS (the APS and NSLS-II beamlines), Tango / Sardana (MAX IV, ALBA), or BLISS (the ESRF). Its science is hard X-ray micro-tomography on a Superbend source.

It also introduces the **data-record descriptor mode**: the device structure is read from the DXchange / DXfile HDF5 metadata schema (verified against the `als-computing/scicat_beamline` ingester and the `als-computing/microct` reconstruction backend), while the live BCS control handles, which are not public, are carried pending. This sits between the FXI mode (real EPICS PVs read from a public profile collection) and the FAXTOR mode (no device manifest at all).

### No new families (the imaging spine reuses the 2-BM / FXI / FAXTOR precedent)

8.3.2 coins no new Family. The Superbend binds the catalog `InsertionDevice` (recorded as a Supply, the 2-BM bending-magnet precedent); the energy optic binds `Monochromator`; the slits bind `Slit` and the attenuator binds `Filter`; the sample stack binds `RotaryStage` and `LinearStage`; the detector binds `Scintillator`, `Objective`, and `Camera`, with the detector motion binding `LinearStage`; the machine state binds the loose `StorageRing`. Nothing in the catalog changes.

### The BCS control plane and the data orchestration

8.3.2 is the fleet's first BCS / LabVIEW controls house-style. Device IO is BCS, the ALS Beamline Control System, surfaced as scan files (Time Scan, Single Motor Scan, Trajectory Scan) whose headers carry the device-state data record ([`als-computing/als.bcs`](https://github.com/als-computing/als.bcs)). An emerging acquisition layer wraps BCS scans as bluesky ophyd `fly` devices through the LabVIEW BCS API ([`als-computing/bcs-api`](https://github.com/als-computing/bcs-api)). ALS publishes no per-beamline BCS channel manifest, so CORA does not bind the BCS handles here; when bound they would be modelled as opaque edge handles over the `ControlPort`, the way the MX3 and ID32 heterogeneous-control precedents do (`CTRL-1`). The continuous-rotation tomography acquisition runs as a BCS Trajectory Scan; that orchestration is the seam CORA's edge replaces, conducting over BCS rather than replacing it.

The downstream data movement and reconstruction is a separate, well-developed layer that CORA observes and subsumes at the debrief layer, not data it owns: [`als-computing/splash_flows`](https://github.com/als-computing/splash_flows) moves data with Prefect + Globus to NERSC and ALCF, catalogues it in SciCat, and runs tomography reconstruction (TomoPy / ASTRA / SVMBIR) via [`als-computing/microct`](https://github.com/als-computing/microct). CORA keeps its own data-of-record (the PG event store); the SciCat catalogue is a source-of-truth contest named only at the seam, not a dependency.

### Deliberately not here yet

- **The BCS control handles (`CTRL-1`).** No public per-beamline BCS / LabVIEW channel manifest exists; the handles are carried pending, not invented.
- **The detector model (`DET-1`).** The camera, scintillator, and objective are bound to `Camera`, `Scintillator`, and `Objective` but their models are unpublished (detector specs are per-dataset values in the data record), carried fully pending.
- **The rotation-axis identity (`ROT-1`).** The data record's `sample_motor_stack` exposes `axis1pos` / `axis2pos` / `axis5pos`; which is the tomographic rotation is pending.
- **The monochromator detail (`MONO-1`).** The mechanism (multilayer vs crystal), d-spacing, and the energy-axis wiring are carried confirm-pending.
- **The slit and filter detail (`OPT-2`, `FILT-1`).** The full slit blade-axis map and the filter materials / thicknesses are carried confirm-pending.
- **The detector-stack detail (`DET-2`).** The camera-distance / elevation / tilt axis models are named; their travels and the propagation-distance wiring are pending.
- **The hutch grouping (`ENC-1`).** Modelled as a single experiment hutch pending the optics / experiment grouping.
- **The simulated devices and full asset-tree scenarios.** No `test_8_3_2_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
- **The ALS-U upgrade fate (`ALSU-1`).** Whether 8.3.2 goes dark, is rebuilt, or relocates in the ALS-U dark time (no sooner than October 2027) is a staff question, not modelled here.

## Open questions

*What CORA needs the 8.3.2 team to confirm before the model can be trusted.*

8.3.2 was reverse-engineered from ALS's public facility pages ([als.lbl.gov/beamlines/8-3-2](https://als.lbl.gov/beamlines/8-3-2/), [microct.lbl.gov](https://microct.lbl.gov/)) and the public [als-computing](https://github.com/als-computing) GitHub org, not from a live connection. The device structure is read from the DXchange / DXfile HDF5 data record that the ALS tooling reads, but ALS runs BCS (a LabVIEW Beamline Control System, not EPICS) and publishes no per-beamline channel manifest, so the [device pages](index.md) carry a planned shape with control handles unbound. This is CORA's first ALS Site and its first BCS / LabVIEW controls house-style. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a single experiment hutch, or a separate optics hutch feeding it? | A single `8-3-2-hutch`. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The Superbend field and critical energy. | A superconducting bending-magnet source, 6-43 keV; field pending. | The source Asset detail. |
| ALSU-1 | Nice-to-have | The ALS-U upgrade fate of 8.3.2: does it go dark, get rebuilt, or relocate, and on what schedule? | Dark time no sooner than October 2027; 8.3.2's fate carried pending. | The deployment roadmap. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ALS storage-ring state 8.3.2 reads (the `source_name` / `current` handles). | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The energy optic: the mechanism (multilayer vs crystal), d-spacing, and how the `energy`, `Z2`, `turret1` / `turret2`, and `TC2` / `TC3` channels relate. | An energy-setting `Monochromator`, 6-43 keV; `energy` the master axis. | The monochromator and energy modelling. |
| OPT-2 | Nice-to-have | The slit blade-axis map (the `hslits_*` and `vslits_*` channels) and handles. | Horizontal + vertical slits bound to `Slit`. | The slit Asset detail. |
| FILT-1 | Nice-to-have | The attenuating-filter materials and thicknesses on the `filter_y` axis. | A filter bound to `Filter`. | The filter Asset detail. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The sample-motor stack: the rotary, the sample-centring axes (`sample_x` / `sample_y`), and the role of `axis1pos` / `axis2pos` / `axis5pos`. | A `RotaryStage` plus a `LinearStage`; axis sets and models pending. | The sample-stage modelling. |
| ROT-1 | Blocks-go-live | Which sample-stack axis is the tomographic rotation. | One of the `axisNpos` channels is the rotation; identity pending. | The rotation Asset binding. |
| TRIG-1 | Nice-to-have | The triggering / synchronization scheme for continuous-rotation tomography. | The rotary stage is the master clock feeding the camera trigger. | The trigger wiring. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector chain: the camera sensor / frame rate / model, the `scintillator_type`, and the `camera_objective` set. | A `Scintillator` + `Objective` + `Camera`; specs are per-dataset values, model carried pending. | The detector modelling. |
| DET-2 | Nice-to-have | The detector-stack axes (`camera_distance`, `camera_elevation`, `tilt_motor`): models, travels, and which is the propagation distance. | A `LinearStage` detector stack; `camera_distance` the propagation distance. | The detector-stack modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | The BCS / LabVIEW control handles per 8.3.2 device (absent from any public manifest). | The handles are unbound, carried pending; the control plane is ALS BCS. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ALS personnel-safety permit signals and the photon / front-end shutters (not published per beamline). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling-water / beam / power supplies. | Photon beam, cooling water, vacuum, and power. | The Supply observations. |
| GOV-1 | Nice-to-have | The ALS operator pool and safety-review structure (site-level). | Carried pending on the ALS Site, not instantiated per beamline. | The governance principals. |
