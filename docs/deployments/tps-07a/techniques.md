# Techniques

*What CORA would run at TPS 07A: rotation macromolecular crystallography, each technique a [Catalog](../../catalog/methods.md) Method bound through an [NSRRC Practice](../nsrrc/index.md#the-techniques-adapted-here). TPS 07A reuses the MX Methods Diamond [I03](../i03/techniques.md) introduced, so it coins nothing new.*

TPS 07A's technique, rotation MX, is the macromolecular-crystallography shape CORA already saw at i03 (and at the Australian Synchrotron [MX3](../mx3/techniques.md), and in its serial form at i24 and LCLS-MFX). The Methods render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog, exactly as at i03 and MX3.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the MD3 goniometer + the EIGER2 X 16M, orchestrated through Blu-Ice/DCSS; the i03 Method, pending (TECH-1) |
| Mesh / grid scan | `grid_scan` | mesh scan for crystal location / centring on the MD3, with Dozor spot-scoring (the Meshbest path); the i03 Method (TECH-1) |
| Autonomous sample exchange | `sample_exchange` | the ISARA robot load / centre / collect / unmount loop, a Procedure over the spine (ROBOT-1) |

All three are recorded as pending [Practices](../nsrrc/index.md#the-techniques-adapted-here) on the NSRRC Site, reusing the same Method names Diamond i03 carries.

## Why the Methods are reused, not coined

TPS 07A brings a new Site and a new seam, not a new technique. Rotation MX, mesh-scan centring, and robot sample exchange are the i03 shapes, so TPS 07A binds the same pending Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) rather than coining anything; whether those Methods enter the catalog is the cross-facility owner-scope decision i03 opened (TECH-1), and TPS 07A reinforces the case at a further MX facility (after i03, NSLS-II FMX / AMX, MX3, and Sirius MANACA). The device Roles already exist (the MD3 presents Positioner via the graduated `Goniometer`, the EIGER2 presents Detector via `Camera`), so nothing new is needed in the device model either.

The autonomous sample exchange reuses the i03 / i24 / MX3 autonomous-loop shape: a Procedure over the spine threaded through `Subject` custody, not a new device family (ROBOT-1). The mesh-scan Dozor spot-scoring and CHiMP crystal detection are `ComputePort` work (an Observe / Compute leg), not beamline Methods.

The genuinely new things TPS 07A contributes are below the technique layer: a new Site (NSRRC) and the Blu-Ice/DCSS-over-EPICS orchestration seam at an MX beamline (see [Controls](equipment/controls.md)), which the technique vocabulary rides over unchanged.
