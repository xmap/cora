# Controls

*The control stack and the orchestration seam. First cut; ALS BCS / LabVIEW, no public per-beamline handles, carried confirm.*

8.3.2 runs on the ALS BCS (Beamline Control System), a LabVIEW control house-style and the fleet's **first** BCS plane (every prior Site is EPICS, Tango / Sardana, or BLISS). The ALS originated BCS, so this is the house-style's home facility. CORA observes that floor and, where it replaces BCS scan orchestration, conducts over it; it does not replace BCS.

## Device handles

ALS publishes no per-beamline BCS channel manifest, and BCS is LabVIEW, not EPICS, so unlike the NSLS-II FXI profile collection (real EPICS PVs) or the ESRF BLISS Beacon database there is no public source of 8.3.2's real addresses. What is public is the **data record**: BCS scan files (Time Scan, Single Motor Scan, Trajectory Scan) carry a structured DXchange / DXfile HDF5 metadata header that names the device hierarchy and its axes ([`als-computing/als.bcs`](https://github.com/als-computing/als.bcs)). CORA reads that data record for the device **structure**, but the live control handles are not bound; the descriptor carries the device tree with handles pending (`CTRL-1`). The transport shapes the handle forms the stack uses:

| Handle form | What it addresses | Where it would appear |
| --- | --- | --- |
| BCS channel name | the LabVIEW-surfaced motors and detectors | the monochromator, slits, sample stack, and camera |
| BCS scan (Trajectory / Single Motor) | the scan-level acquisition | the tomography sweep and the alignment moves |
| DXfile metadata path | the device-state data record | the per-device state the HDF5 header captures |

CORA would model each device as an opaque control handle set at the edge, the way the MX3 and ID32 heterogeneous-control precedents do: the transport (BCS over LabVIEW) is a `ControlPort` adapter concern, not a difference in the Asset. The handles remain confirm-pending until 8.3.2 staff supply them (`CTRL-1`). The full source / optics walk and the per-device list live on the generated [Source](../beamline.md) page; this page covers the control seam.

## The orchestration seam

The 8.3.2 acquisition (the energy selection over the monochromator, the continuous-rotation tomography trajectory, the camera triggering off the rotary master clock, the flat / dark sequencing) runs as a BCS Trajectory Scan. An emerging integration layer wraps BCS scans as bluesky ophyd `fly` devices through the LabVIEW BCS API ([`als-computing/bcs-api`](https://github.com/als-computing/bcs-api)), so a run can be driven from the bluesky Run Engine over BCS. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through BCS rather than replacing it. The live BCS scan engine that computes the trajectories stays the floor; CORA names the rotation, energy, and detector axes and records the moves, the controller owns the kinematics (`TRIG-1`).

## Data movement and reconstruction

8.3.2 has a well-developed downstream data layer that CORA observes and subsumes at the debrief layer, not data it owns. [`als-computing/splash_flows`](https://github.com/als-computing/splash_flows) moves raw data with Prefect + Globus from the beamline (the `spot832` / `data832` endpoints) to NERSC and ALCF, catalogues it in SciCat, and triggers tomography reconstruction (TomoPy / ASTRA / SVMBIR) via [`als-computing/microct`](https://github.com/als-computing/microct), with viewers like `view_tomography_recon_app`. CORA keeps its own data-of-record (the PG event store); the SciCat catalogue is a source-of-truth contest named only at the seam, and the Globus / Prefect movement and HPC reconstruction are a port roundtrip CORA governs but does not own (see [Model](../model.md)).

## Equipment protection

The ALS personnel-safety permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are not published per beamline and are not invented here (`PSS-1`). The Enclosure permit shape and the hazard tier are carried pending at the ALS Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../als/index.md#the-safety-envelope)).
