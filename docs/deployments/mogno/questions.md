# Open questions

*What CORA needs the MOGNO team to confirm before the model can be trusted.*

MOGNO was reverse-engineered from two published papers (Campoi et al. 2025, the software architecture; Archilha et al. 2022, the beamline) and the public [Sirius MOGNO facility page](https://lnls.cnpem.br/facilities/mogno/). Unlike the NSLS-II and Diamond scaffolds, there is no public controls configuration to read, so MOGNO carries no real control handles at all: the device families are inferred from the papers, and every handle, model, and PV namespace is an open question. This is CORA's first Sirius Site and first South American facility. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The source type (permanent-magnet dipole vs superbend), field, and the energy-selection mechanism. | A 3.2 T dipole / superbend bound to `InsertionDevice`, recorded as a Supply (PhotonBeam) at the Site. | The source Asset detail. |
| SRC-2 | Nice-to-have | The working energy set: the hardware paper gives 21.5 / 39.0 / 67.7 keV, the facility page 22 / 39 / 67.5 keV. | The three quasi-monochromatic working energies; exact values pending. | The energy working points. |
| MACHINE-1 | Nice-to-have | The Sirius storage-ring state MOGNO reads. | Observe-only machine state, a loose `StorageRing`; exact read pending. | The machine-state observation. |
| OPT-1 | Blocks-go-live | The focusing-mirror count, geometry (elliptical set vs KB pair), coatings, and handles. | Elliptical / KB-style focusing mirrors bound to `Mirror`, demagnifying to ~100-120 nm. | The mirror Assets. |
| OPT-2 | Nice-to-have | The beam-defining slit blade-axis map and handles. | Slits bound to `Slit`. | The slit Asset detail. |

## Sample stations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The nanotomography rotation stage (model, encoder, max speed, handle). | A `RotaryStage`, the master clock for hardware-triggered acquisition. | The nano rotation Asset. |
| STAGE-2 | Blocks-go-live | The nanotomography fine sample positioner (the piezo "tripod" axes and model). | A `LinearStage`; axis set a per-Asset setting. | The nano sample-positioner Asset. |
| STAGE-3 | Blocks-go-live | The microtomography station stages (rotation and positioner models, axes, handles). | A `RotaryStage` and a `LinearStage`, mirroring the nano station at coarser resolution. | The micro-station Assets. |

## Detector and data

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CAM-1 | Blocks-go-live | The detector roster and per-station pairing: which of Pimega (Si photon-counting), the sCMOS indirect chain, and the CdTe Medipix/Mobipix are installed and active at each station. | One detector position bound to `Camera` until staff confirm; the FXI multi-camera precedent. | The detector Assets. |
| CAM-2 | Nice-to-have | The scintillator material and thickness and the Optique Peter microscope objective set for the indirect chain. | A `Scintillator` (e.g. LuAG:Ce) coupled via a microscope. | The indirect-chain detail. |
| MAG-1 | Nice-to-have | The cone-beam magnification rule (how sample-along-cone position maps to magnification). | A `PseudoAxis` over the sample and detector distances; rule deferred. The FXI Magnification precedent. | The magnification Asset. |
| DATA-1 | Blocks-go-live | The acquisition file format and layout: HDF5 / NeXus / DXchange `exchange/data` + flat + dark, and the metadata schema injected into the file. | A single main data file carrying projections, flat, dark, and metadata; format pending. | The data-of-record interface. |

## Control, compute, and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | The EPICS PV namespaces, the TATU trigger handles, and the motion-controller boxes. None are in public sources. | EPICS IOCs + a TATU FPGA trigger as the floor, with the handles carried confirm. | Verifying each Asset's control handle. |
| ORCH-1 | Blocks-go-live | Does MOGNO still run the custom `mgn-*` PyEpics stack, or has it migrated to Bluesky/sophys? | The custom `mgn-devices` / `mgn-routines` / `mgn-control-guis` stack today, with Bluesky a future target. | The orchestration seam CORA conducts over. |
| COMPUTE-1 | Nice-to-have | The reconstruction HPC cluster name, scheduler (SLURM?), GPU resources, and shared storage path. | `ssc-raft` (CUDA) submitted to an HPC cluster over SSH; cluster specifics pending. | The compute leg. |
| PSS-1 | Blocks-go-live | The Sirius personnel-safety permit signals and the photon / front-end shutters. | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| GOV-1 | Nice-to-have | The Sirius operator pool and safety-review structure (site-level). | Carried pending on the Sirius Site, not instantiated per beamline. | The governance principals. |
