# TPS 05A

*Protein microcrystallography at the NSRRC Taiwan Photon Source: rotation MX on an Arinax MD3 microdiffractometer reading a DECTRIS EIGER2 X 9M, with an ISARA robot for unattended sample exchange. This page describes how CORA would model and run TPS 05A; the model is reverse-engineered from public configuration, not yet confirmed by NSRRC staff.*

| Property | Value |
| --- | --- |
| Asset | `TPS 05A` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSRRC](../nsrrc/index.md) (bound via `facility_code = "nsrrc"`, `FacilityKind = Site`) |
| Sector | EPICS PV namespace `05a:` (endstation `05a-ES:`), inferred by cluster convention (PV-1) |
| Institution | NSRRC, National Synchrotron Radiation Research Center, Hsinchu, Taiwan (context; not modeled as an Asset) |
| Status | Reverse-engineered from public config (design-phase scaffold, reuse-and-reinforce) |
| Source | TPS undulator, ~5.7-20 keV (front-end PV not in public source, SRC-1) |

!!! note "How CORA would land on TPS 05A"
    These pages describe how CORA would model, govern, and conduct TPS 05A, the second beamline of CORA's NSRRC Site. They are not a survey of the beamline's current software. TPS 05A's public source is **thinner than its sibling [TPS 07A](../tps-07a/index.md)'s**: the [SPXF facility pages](https://nsrrcspxf.github.io/nsrrcspxf/index.html) enumerate its kit (EIGER2 X 9M + ISARA), and a 2025 *J. Synchrotron Rad.* paper covers all three NSRRC MX endstations as one Blu-Ice/DCSS family, but there is **no dedicated 05A control tree** (the public `NSRRC_TPS05A_BeamMonitor` repo is an empty stub). So 05A's device facts come from the SPXF pages plus the shared-cluster paper, and its seam / control model is **inherited from the 07A reading** and confirmed to apply by the cluster paper. Its PV namespace is **inferred, not read from source** (PV-1). Every value is carried `confirm` until staff verify it ([Open questions](questions.md)).

## The defining shape: the MX-cluster sibling of TPS 07A

TPS 05A is a **reuse-and-reinforce deployment**. It is the [TPS 07A](../tps-07a/index.md) shape again, on the same NSRRC Site: the same SPXF group runs the same Blu-Ice/DCSS stack on the same Arinax MD3 + ISARA kit. What differs is small and contained:

- the area detector is a **DECTRIS EIGER2 X 9M** (07A runs the 16M),
- the framing is **protein microcrystallography** rather than 07A's micro-focus MX,
- the public source is thinner (no dedicated control tree), so more values are carried pending.

Everything structural is reused: the **NSRRC Site** (already created by 07A), the **Blu-Ice/DCSS-over-EPICS seam** (the 2-BM TomoScan pattern, [confirmed live over MXCuBE](../tps-07a/equipment/controls.md#why-blu-icedcss-and-not-mxcube) for the whole MX cluster by the 2025 paper), the graduated **`Goniometer`** family for the MD3, and the pending **i03 MX Methods**. TPS 05A coins nothing new in any bounded context.

The value of modelling it is exactly that reuse: it is the demonstration that **one device-library and one seam generalize across the NSRRC MX cluster**, the claim 07A's pages make but cannot prove alone. It is the same move CORA made with NSLS-II FMX → AMX and Diamond i15-1: a sibling that reinforces the vocabulary at a second beamline without adding to it. The third cluster member, TLS 15A1, sits on the older TLS ring with a different detector and robot (a Rayonix CCD + SAM auto-mounter) and is a separate future scaffold.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the storage-ring current monitor and the front-end shutter (the undulator source PV is not in public source, SRC-1), then the optics, the double-crystal monochromator, the master energy axis, the attenuator, and the focusing mirrors.
- [Sample](equipment/sample.md): the Arinax MD3 microdiffractometer goniometer, the cryostream cooling, and the beamstop, plus the ISARA sample-exchange robot.
- [Detector](equipment/detector.md): the DECTRIS EIGER2 X 9M, its translation stage, the on-axis viewing camera, and the beam-position diagnostics.

Cutting across all three:

- [Controls](equipment/controls.md): the shutters, the motion controllers, and the DCSS-over-EPICS orchestration seam inherited from TPS 07A.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the rotation-MX techniques TPS 05A runs (data collection, mesh/grid scan, autonomous sample exchange), each reusing a pending Diamond i03 Method, the same set as TPS 07A.

## Governance

[Governance](governance.md): who may act at TPS 05A and the trust shape CORA applies; identical to TPS 07A, since both share the NSRRC Site's principals, the LDAP-backed staff, and the mandatory training gate.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's TPS 05A content lives.
