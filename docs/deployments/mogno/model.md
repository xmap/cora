# Model

*The developer's by-kind index: where each CORA aggregate's MOGNO content lives, the new Sirius Site and the compute axis named for reconstruction, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at MOGNO |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the cone-beam magnification `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes MOGNO new

MOGNO is CORA's **eighth Site** (Sirius, the Brazilian Synchrotron Light Laboratory at CNPEM) and the fleet's **first South American facility**, the biggest re-test of the Site and Federation kernel a single deployment can be. Its science is cone-beam X-ray micro and nanotomography across two endstations, fed by a quasi-monochromatic dipole source at three working energies.

It is also the thinnest reverse-engineered scaffold to date, by necessity. The NSLS-II and Diamond beamlines were built from public open-source controls libraries (bluesky profile collections, `dodal`), so their descriptors carry real EPICS PVs or device handles. MOGNO has no public controls configuration: its facts come from two papers and a facility page. So every device binds a catalog Family but carries no handle and no vendor Model; the handles are open questions, not read-from-config evidence.

## No new families, no new method (reuse and reinforce)

MOGNO coins nothing. It is the tomography spine landing on a third facility after the APS 2-BM pilot and NSLS-II FXI, and it reuses their vocabulary wholesale:

- the rotation axes bind `RotaryStage` (the master clock for triggered acquisition);
- the sample positioners (including the fine piezo "tripod") bind `LinearStage`, the axis set a per-Asset setting;
- the focusing optics bind `Mirror`, the beam-defining slits bind `Slit`;
- the detectors bind `Camera` and `Scintillator` (the indirect chain);
- the cone-beam magnification binds `PseudoAxis` (the FXI Magnification precedent);
- the TATU FPGA trigger binds `TimingController` (the 2-BM softGlueZynq / FXI Zebra precedent);
- the machine state binds the loose `StorageRing`;
- the `tomography` Method is reused, the practice carried pending (`TECH-1`).

## The control seam: a custom EPICS application layer

MOGNO is the fleet's first orchestration layer that is neither Bluesky nor BLISS nor Sardana. Its floor is EPICS IOCs plus a TATU FPGA trigger/timer (shared Sirius infrastructure, exposing EPICS PVs via the LNLS Nheengatu layer). Above that floor sits a beamline-owned custom PyEpics application stack: `mgn-devices` (device abstraction over PyEpics), `mgn-routines` (the alignment and tomogram acquisition routines), and `mgn-control-guis` (the PyQt/PyDM launchers). A tomogram is launched from a GUI dialog that runs the relevant `mgn-routines` script as a subprocess, driving the rotation stage, detector, and TATU trigger over EPICS.

That custom routine layer is the orchestration CORA's edge would conduct over the EPICS floor, exactly as the 2-BM seam designates: CORA's EdgeConductor replaces the scan/alignment orchestration the `mgn-routines` perform today, conducting over the EPICS + TATU floor rather than replacing it. The beamline has named Bluesky/sophys (Ophyd devices, Bluesky plans) as a future migration target; whether it has migrated is an open question (`ORCH-1`). Modelling the seam against a custom stack, not Bluesky, is the point: it confirms the seam model does not assume a particular orchestration framework.

## The compute axis: reconstruction named, not built

MOGNO reconstructs on an HPC cluster. The beamline's reconstruction library is `ssc-raft` (CUDA, from the Sirius Scientific Computing group), submitted to the cluster over SSH from a FastAPI reconstruction service with a PyQt job-queue GUI; it has been the production reconstruction path since early 2024. This is a clean instance of CORA's compute axis (a `ComputePort` over a Method, no new BC): named here as reinforcement of the compute-modelling synthesis, not modelled as Assets in this cut. The cluster name, scheduler, and storage path are not confirmed from public sources (`COMPUTE-1`).

## Deliberately not here yet

- **The exact device handles and vendor models (`CTRL-1`, `STAGE-1`, `STAGE-2`, `STAGE-3`, `CAM-1`, `CAM-2`, `OPT-1`, `OPT-2`).** No public controls config exists; the PVs, controller boxes, and part numbers must come from staff. They carry no value here rather than a guessed one.
- **The reconstruction Assets and the compute leg (`COMPUTE-1`).** The `ssc-raft` HPC path is named above, not modelled.
- **The orchestration migration status (`ORCH-1`).** Whether MOGNO still runs the custom `mgn-*` stack or has moved to Bluesky/sophys is an open question.
- **The PSS permit signals and shutters (`PSS-1`).** Absent from public sources, carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_mogno_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
