# Controls

*The control stack and the orchestration seam. First cut; MOGNO has no public controls config, so all handles are carried confirm.*

MOGNO runs on EPICS, like the APS and NSLS-II beamlines, but its application layer is distinctive: a beamline-owned custom PyEpics stack, not Bluesky/sophys, not BLISS, not Sardana. CORA observes the EPICS floor and, where it replaces the custom orchestration, conducts over it; it does not replace EPICS or the TATU trigger.

## The layered stack

The MOGNO software paper (Campoi et al. 2025) describes a layered architecture:

| Layer | What it is | CORA's relation |
| --- | --- | --- |
| Driver / device | Motion controllers and detectors, some with embedded triggered-acquisition code | The floor; CORA never replaces it |
| Service | EPICS IOCs + TATU (an FPGA trigger/timer on CompactRIO, exposing EPICS PVs via the LNLS Nheengatu layer) | The floor; CORA actuates and triggers through it |
| Application | The beamline-owned custom Python: `mgn-devices` (PyEpics device abstraction), `mgn-routines` (alignment + tomogram acquisition), `mgn-control-guis` (PyQt/PyDM launchers) | The orchestration CORA's edge conducts over (ORCH-1) |
| Metadata | Soft IOCs + PV-name config building a metadata dict injected into the data file | A source CORA observes; CORA keeps its own data of record |

## Device handles

MOGNO has no public controls configuration: there is no open-source profile collection, IOC repository, or device database to read. So unlike the NSLS-II and Diamond scaffolds, the descriptor carries **no** PVs or controller-box identities; the device families are inferred from the published papers, and every handle is an open question (`CTRL-1`). The production deployment configuration lives on the internal CNPEM GitLab, not public. The motion-controller boxes (model, protocol, axis count) and the EPICS PV namespaces must come from staff.

## The orchestration seam

A MOGNO tomogram is launched today from a `mgn-control-guis` dialog that runs the relevant `mgn-routines` script as a subprocess; the script drives the rotation stage, the detector, and the TATU trigger over EPICS to collect projections plus flat and dark fields, with metadata injected into the output file. That custom routine layer is the seam CORA's edge replaces: CORA's EdgeConductor conducts the run over the `ControlPort`, driving the EPICS + TATU floor rather than replacing it. The TATU FPGA trigger stays the floor (it hardware-synchronises the projection exposures to the rotation); CORA arms and configures it over the ControlPort, the 2-BM Aerotech PSO / FXI Zebra precedent.

The beamline has named Bluesky/sophys (Ophyd devices, Bluesky plans, eventually React web apps) as a future migration target. Whether MOGNO still runs the custom `mgn-*` stack or has migrated is an open question (`ORCH-1`); the seam is the same either way, since both the custom routines and Bluesky plans sit at the orchestration layer above the EPICS floor.

## Reconstruction

Reconstruction runs off the control path, on an HPC cluster: the `ssc-raft` CUDA library, submitted over SSH from a FastAPI service with a PyQt job-queue GUI, in production since early 2024. CORA models this as the compute axis (a `ComputePort` over the tomography Method), named on [Model](../model.md#the-compute-axis-reconstruction-named-not-built) but not built in this cut. The cluster name, scheduler, and storage path are not confirmed from public sources (`COMPUTE-1`).

## Equipment protection

The Sirius personnel-safety permit signals, the photon and front-end shutters, and any equipment-protection interlock tier are not in any public source and are not invented here (`PSS-1`). MOGNO carries the hazard classes of a hard X-ray tomography beamline (an intense beam up to ~68 keV and the radiation-enclosure interlocks of the two stations); the Enclosure permit shape and the hazard tier are carried pending at the Sirius Site, and the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../sirius/index.md#the-safety-envelope)).
