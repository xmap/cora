# Techniques

*What CORA would run at TPS 05A: rotation macromolecular crystallography, each technique a [Catalog](../../catalog/methods.md) Method bound through an [NSRRC Practice](../nsrrc/index.md#the-techniques-adapted-here). TPS 05A reuses the same MX Methods as [TPS 07A](../tps-07a/techniques.md) and Diamond [I03](../i03/techniques.md), so it coins nothing new.*

TPS 05A's technique, rotation MX (in its microcrystallography form), is the macromolecular-crystallography shape CORA already saw at i03, TPS 07A, and MX3. The Methods render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the MD3 goniometer + the EIGER2 X 9M, orchestrated through Blu-Ice/DCSS; the i03 Method, pending (TECH-1) |
| Mesh / grid scan | `grid_scan` | mesh scan for crystal location / centring on the MD3; the i03 Method (TECH-1) |
| Autonomous sample exchange | `sample_exchange` | the ISARA robot load / centre / collect / unmount loop, a Procedure over the spine (ROBOT-1) |

All three are recorded as pending [Practices](../nsrrc/index.md#the-techniques-adapted-here) on the NSRRC Site (the `TPS05A_*` practices), reusing the same Method names TPS 07A and Diamond i03 carry.

## Why the Methods are reused, not coined

TPS 05A brings nothing new at the technique layer: it is the MX-cluster sibling of TPS 07A. Rotation MX, mesh-scan centring, and robot sample exchange are the i03 shapes, so 05A binds the same pending Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) rather than coining anything; whether those Methods enter the catalog is the cross-facility owner-scope decision i03 opened (TECH-1), and 05A reinforces the case at a **further MX deployment** (after i03, NSLS-II FMX / AMX, MX3, Sirius MANACA, and TPS 07A). The device Roles already exist (the MD3 presents Positioner via the graduated `Goniometer`, the EIGER2 presents Detector via `Camera`), so nothing new is needed in the device model either.

The autonomous sample exchange reuses the i03 / i24 / 07A / MX3 autonomous-loop shape: a Procedure over the spine threaded through `Subject` custody, not a new device family (ROBOT-1).

TPS 05A contributes no new vocabulary anywhere; its value is reinforcing that the NSRRC Site, the Blu-Ice/DCSS-over-EPICS seam, and the MX Methods cover the cluster, not just 07A.
