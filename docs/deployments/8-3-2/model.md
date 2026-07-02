# Model

*The developer's by-kind index: where each CORA aggregate's 8.3.2 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 8.3.2 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes 8.3.2 new

8.3.2 is two things at the Site level and nothing new at the vocabulary level. It is CORA's **first ALS Site** (the Advanced Light Source at LBNL), a re-test of the Site and Federation kernel, and the **first BCS / LabVIEW** control plane CORA models. The ALS originated BCS (the Beamline Control System), so this is the controls house-style's home facility; every prior Site is EPICS (the APS and NSLS-II beamlines), Tango / Sardana (MAX IV, ALBA), or BLISS (the ESRF). Its science is hard X-ray micro-tomography on a Superbend source.

It also introduces the **data-record descriptor mode**: the device structure is read from the DXchange / DXfile HDF5 metadata schema (verified against the `als-computing/scicat_beamline` ingester and the `als-computing/microct` reconstruction backend), while the live BCS control handles, which are not public, are carried pending. This sits between the FXI mode (real EPICS PVs read from a public profile collection) and the FAXTOR mode (no device manifest at all).

## No new families (the imaging spine reuses the 2-BM / FXI / FAXTOR precedent)

8.3.2 coins no new Family. The Superbend binds the catalog `InsertionDevice` (recorded as a Supply, the 2-BM bending-magnet precedent); the energy optic binds `Monochromator`; the slits bind `Slit` and the attenuator binds `Filter`; the sample stack binds `RotaryStage` and `LinearStage`; the detector binds `Scintillator`, `Objective`, and `Camera`, with the detector motion binding `LinearStage`; the machine state binds the loose `StorageRing`. Nothing in the catalog changes.

## The BCS control plane and the data orchestration

8.3.2 is the fleet's first BCS / LabVIEW controls house-style. Device IO is BCS, the ALS Beamline Control System, surfaced as scan files (Time Scan, Single Motor Scan, Trajectory Scan) whose headers carry the device-state data record ([`als-computing/als.bcs`](https://github.com/als-computing/als.bcs)). An emerging acquisition layer wraps BCS scans as bluesky ophyd `fly` devices through the LabVIEW BCS API ([`als-computing/bcs-api`](https://github.com/als-computing/bcs-api)). ALS publishes no per-beamline BCS channel manifest, so CORA does not bind the BCS handles here; when bound they would be modelled as opaque edge handles over the `ControlPort`, the way the MX3 and ID32 heterogeneous-control precedents do (`CTRL-1`). The continuous-rotation tomography acquisition runs as a BCS Trajectory Scan; that orchestration is the seam CORA's edge replaces, conducting over BCS rather than replacing it.

The downstream data movement and reconstruction is a separate, well-developed layer that CORA observes and subsumes at the debrief layer, not data it owns: [`als-computing/splash_flows`](https://github.com/als-computing/splash_flows) moves data with Prefect + Globus to NERSC and ALCF, catalogues it in SciCat, and runs tomography reconstruction (TomoPy / ASTRA / SVMBIR) via [`als-computing/microct`](https://github.com/als-computing/microct). CORA keeps its own data-of-record (the PG event store); the SciCat catalogue is a source-of-truth contest named only at the seam, not a dependency.

## Deliberately not here yet

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
