# Notes

## Techniques

*What the modelled part of MOGNO is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../sirius/index.md#the-techniques-adapted-here) is how a facility adapts it. MOGNO runs cone-beam X-ray tomography, which is already in CORA's catalog, so the Method below renders linked and the practice is carried pending until the technique enters scope (`TECH-1`).

### Cone-beam micro and nanotomography

MOGNO illuminates the sample with a quasi-monochromatic divergent (cone) beam and records projections as the sample rotates. Because the geometry is cone-beam, moving the sample along the cone between the secondary source and the detector changes the magnification, so a single instrument spans nanotomography (at the elliptical-mirror nanofocus) and microtomography (large field of view) by sample position. Phase contrast comes from propagation over the sample-to-detector distance, and time-resolved (4D) tomography from fast continuous rotation.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Cone-beam X-ray tomography | `tomography` | projections over a rotation on the [nanotomography](sample.md) and [microtomography](sample.md) stations, hardware-triggered by the [TATU timing unit](controls.md); reuses the graduated `tomography` Method the APS 2-BM pilot and NSLS-II FXI share; practice pending (`TECH-1`) |

Tomography at MOGNO needs the [rotation axis](sample.md) as the master clock, the [TATU trigger](controls.md) to hardware-sync projection acquisition, the [detector chain](detector.md) to record the projections plus flat and dark fields, and the [cone-beam magnification axis](detector.md) to set the resolution-and-field-of-view working point.

### A familiar technique on a third facility

MOGNO is the tomography spine reaching a third facility after the APS 2-BM bending-magnet micro-CT pilot and the NSLS-II FXI transmission microscope. It coins no new Method: the same `tomography` Method covers micro and nano variants, exactly as 2-BM uses it for both. What MOGNO reinforces is not the technique but the surrounding model, the cone-beam magnification as a `PseudoAxis`, the FPGA trigger as a `TimingController`, and the seam against a custom (non-Bluesky) orchestration layer.

The streaming and continuous-rotation tomography variants the catalog already carries (`streaming_tomography`, `continuous_rotation_tomography`) are plausible for MOGNO's 4D time-resolved work, but are not asserted here without a source; they would be added as practices once staff confirm the acquisition modes.

### Not modelled yet

The concrete acquisition recipes (the rotation ranges and speeds, the projection counts, the flat and dark field cadence, the per-energy and per-station alignment routines, and the reconstruction parameters) are not written yet; they join as the deployment approaches the point where CORA drives MOGNO. The reconstruction step (`ssc-raft` on the HPC cluster) is named on [Model](#the-compute-axis-reconstruction-named-not-built) as the compute axis, not modelled here. See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at MOGNO, and the trust shape that will gate it. First cut.*

Governance at MOGNO follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [Sirius Site](../sirius/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

MOGNO is CORA's first Sirius deployment, so Sirius is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [Sirius Site](../sirius/index.md#safety-and-governance), shared across the facility's beamlines, until LNLS staff confirm them (`GOV-1`). MOGNO is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives MOGNO, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The Sirius personnel-safety permit signals and the photon and front-end shutters are not in any public source, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [Sirius Site](../sirius/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

MOGNO carries the hazard classes that come with a tomography beamline: an intense X-ray beam (a quasi-monochromatic dipole source running up to ~68 keV), and the radiation-enclosure interlocks of the two experiment stations. Those land at the Site safety envelope; an experiment Clearance would carry the per-experiment authorization.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives MOGNO, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's MOGNO content lives, the new Sirius Site and the compute axis named for reconstruction, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at MOGNO |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the cone-beam magnification `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes MOGNO new

MOGNO is CORA's **eighth Site** (Sirius, the Brazilian Synchrotron Light Laboratory at CNPEM) and the fleet's **first South American facility**, the biggest re-test of the Site and Federation kernel a single deployment can be. Its science is cone-beam X-ray micro and nanotomography across two endstations, fed by a quasi-monochromatic dipole source at three working energies.

It is also the thinnest reverse-engineered scaffold to date, by necessity. The NSLS-II and Diamond beamlines were built from public open-source controls libraries (bluesky profile collections, `dodal`), so their descriptors carry real EPICS PVs or device handles. MOGNO has no public controls configuration: its facts come from two papers and a facility page. So every device binds a catalog Family but carries no handle and no vendor Model; the handles are open questions, not read-from-config evidence.

### No new families, no new method (reuse and reinforce)

MOGNO coins nothing. It is the tomography spine landing on a third facility after the APS 2-BM pilot and NSLS-II FXI, and it reuses their vocabulary wholesale:

- the rotation axes bind `RotaryStage` (the master clock for triggered acquisition);
- the sample positioners (including the fine piezo "tripod") bind `LinearStage`, the axis set a per-Asset setting;
- the focusing optics bind `Mirror`, the beam-defining slits bind `Slit`;
- the detectors bind `Camera` and `Scintillator` (the indirect chain);
- the cone-beam magnification binds `PseudoAxis` (the FXI Magnification precedent);
- the TATU FPGA trigger binds `TimingController` (the 2-BM softGlueZynq / FXI Zebra precedent);
- the machine state binds the loose `StorageRing`;
- the `tomography` Method is reused, the practice carried pending (`TECH-1`).

### The control seam: a custom EPICS application layer

MOGNO is the fleet's first orchestration layer that is neither Bluesky nor BLISS nor Sardana. Its floor is EPICS IOCs plus a TATU FPGA trigger/timer (shared Sirius infrastructure, exposing EPICS PVs via the LNLS Nheengatu layer). Above that floor sits a beamline-owned custom PyEpics application stack: `mgn-devices` (device abstraction over PyEpics), `mgn-routines` (the alignment and tomogram acquisition routines), and `mgn-control-guis` (the PyQt/PyDM launchers). A tomogram is launched from a GUI dialog that runs the relevant `mgn-routines` script as a subprocess, driving the rotation stage, detector, and TATU trigger over EPICS.

That custom routine layer is the orchestration CORA's edge would conduct over the EPICS floor, exactly as the 2-BM seam designates: CORA's EdgeConductor replaces the scan/alignment orchestration the `mgn-routines` perform today, conducting over the EPICS + TATU floor rather than replacing it. The beamline has named Bluesky/sophys (Ophyd devices, Bluesky plans) as a future migration target; whether it has migrated is an open question (`ORCH-1`). Modelling the seam against a custom stack, not Bluesky, is the point: it confirms the seam model does not assume a particular orchestration framework.

### The compute axis: reconstruction named, not built

MOGNO reconstructs on an HPC cluster. The beamline's reconstruction library is `ssc-raft` (CUDA, from the Sirius Scientific Computing group), submitted to the cluster over SSH from a FastAPI reconstruction service with a PyQt job-queue GUI; it has been the production reconstruction path since early 2024. This is a clean instance of CORA's compute axis (a `ComputePort` over a Method, no new BC): named here as reinforcement of the compute-modelling synthesis, not modelled as Assets in this cut. The cluster name, scheduler, and storage path are not confirmed from public sources (`COMPUTE-1`).

### Deliberately not here yet

- **The exact device handles and vendor models (`CTRL-1`, `STAGE-1`, `STAGE-2`, `STAGE-3`, `CAM-1`, `CAM-2`, `OPT-1`, `OPT-2`).** No public controls config exists; the PVs, controller boxes, and part numbers must come from staff. They carry no value here rather than a guessed one.
- **The reconstruction Assets and the compute leg (`COMPUTE-1`).** The `ssc-raft` HPC path is named above, not modelled.
- **The orchestration migration status (`ORCH-1`).** Whether MOGNO still runs the custom `mgn-*` stack or has moved to Bluesky/sophys is an open question.
- **The PSS permit signals and shutters (`PSS-1`).** Absent from public sources, carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_mogno_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the MOGNO team to confirm before the model can be trusted.*

MOGNO was reverse-engineered from two published papers (Campoi et al. 2025, the software architecture; Archilha et al. 2022, the beamline) and the public [Sirius MOGNO facility page](https://lnls.cnpem.br/facilities/mogno/). Unlike the NSLS-II and Diamond scaffolds, there is no public controls configuration to read, so MOGNO carries no real control handles at all: the device families are inferred from the papers, and every handle, model, and PV namespace is an open question. This is CORA's first Sirius Site and first South American facility. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The source type (permanent-magnet dipole vs superbend), field, and the energy-selection mechanism. | A 3.2 T dipole / superbend bound to `InsertionDevice`, recorded as a Supply (PhotonBeam) at the Site. | The source Asset detail. |
| SRC-2 | Nice-to-have | The working energy set: the hardware paper gives 21.5 / 39.0 / 67.7 keV, the facility page 22 / 39 / 67.5 keV. | The three quasi-monochromatic working energies; exact values pending. | The energy working points. |
| MACHINE-1 | Nice-to-have | The Sirius storage-ring state MOGNO reads. | Observe-only machine state, a loose `StorageRing`; exact read pending. | The machine-state observation. |
| OPT-1 | Blocks-go-live | The focusing-mirror count, geometry (elliptical set vs KB pair), coatings, and handles. | Elliptical / KB-style focusing mirrors bound to `Mirror`, demagnifying to ~100-120 nm. | The mirror Assets. |
| OPT-2 | Nice-to-have | The beam-defining slit blade-axis map and handles. | Slits bound to `Slit`. | The slit Asset detail. |

### Sample stations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The nanotomography rotation stage (model, encoder, max speed, handle). | A `RotaryStage`, the master clock for hardware-triggered acquisition. | The nano rotation Asset. |
| STAGE-2 | Blocks-go-live | The nanotomography fine sample positioner (the piezo "tripod" axes and model). | A `LinearStage`; axis set a per-Asset setting. | The nano sample-positioner Asset. |
| STAGE-3 | Blocks-go-live | The microtomography station stages (rotation and positioner models, axes, handles). | A `RotaryStage` and a `LinearStage`, mirroring the nano station at coarser resolution. | The micro-station Assets. |

### Detector and data

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CAM-1 | Blocks-go-live | The detector roster and per-station pairing: which of Pimega (Si photon-counting), the sCMOS indirect chain, and the CdTe Medipix/Mobipix are installed and active at each station. | One detector position bound to `Camera` until staff confirm; the FXI multi-camera precedent. | The detector Assets. |
| CAM-2 | Nice-to-have | The scintillator material and thickness and the Optique Peter microscope objective set for the indirect chain. | A `Scintillator` (e.g. LuAG:Ce) coupled via a microscope. | The indirect-chain detail. |
| MAG-1 | Nice-to-have | The cone-beam magnification rule (how sample-along-cone position maps to magnification). | A `PseudoAxis` over the sample and detector distances; rule deferred. The FXI Magnification precedent. | The magnification Asset. |
| DATA-1 | Blocks-go-live | The acquisition file format and layout: HDF5 / NeXus / DXchange `exchange/data` + flat + dark, and the metadata schema injected into the file. | A single main data file carrying projections, flat, dark, and metadata; format pending. | The data-of-record interface. |

### Control, compute, and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | The EPICS PV namespaces, the TATU trigger handles, and the motion-controller boxes. None are in public sources. | EPICS IOCs + a TATU FPGA trigger as the floor, with the handles carried confirm. | Verifying each Asset's control handle. |
| ORCH-1 | Blocks-go-live | Does MOGNO still run the custom `mgn-*` PyEpics stack, or has it migrated to Bluesky/sophys? | The custom `mgn-devices` / `mgn-routines` / `mgn-control-guis` stack today, with Bluesky a future target. | The orchestration seam CORA conducts over. |
| COMPUTE-1 | Nice-to-have | The reconstruction HPC cluster name, scheduler (SLURM?), GPU resources, and shared storage path. | `ssc-raft` (CUDA) submitted to an HPC cluster over SSH; cluster specifics pending. | The compute leg. |
| PSS-1 | Blocks-go-live | The Sirius personnel-safety permit signals and the photon / front-end shutters. | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| GOV-1 | Nice-to-have | The Sirius operator pool and safety-review structure (site-level). | Carried pending on the Sirius Site, not instantiated per beamline. | The governance principals. |
