# Techniques

*What CORA would run at MX3: rotation macromolecular crystallography, each technique a [Catalog](../../catalog/methods.md) Method bound through an [Australian Synchrotron Practice](../as/index.md#the-techniques-adapted-here). MX3 reuses the MX Methods Diamond [I03](../i03/techniques.md) introduced, so it coins nothing new.*

MX3's technique, rotation MX, is the macromolecular-crystallography shape CORA already saw at i03 (and, in its serial form, at i24 and LCLS-MFX). The Methods render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog, exactly as at i03.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the MD3 goniometer + the Eiger; the i03 Method, pending (TECH-1) |
| Grid scan | `grid_scan` | fast grid scan for sample location / centring on the MD3 (TECH-1) |
| Autonomous sample exchange | `sample_exchange` | the ISARA robot load / centre / collect / unmount loop, a Procedure over the spine (ROBOT-1) |

All three are recorded as pending [Practices](../as/index.md#the-techniques-adapted-here) on the Australian Synchrotron Site, reusing the same Method names Diamond i03 carries.

## Why the Methods are reused, not coined

MX3 brings a new Site, not a new technique. Rotation MX, grid-scan centring, and robot sample exchange are the i03 shapes, so MX3 binds the same pending Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) rather than coining anything; whether those Methods enter the catalog is the cross-facility owner-scope decision i03 opened (TECH-1), and MX3 reinforces the case at a second facility. The device Roles already exist (the MD3 presents Positioner via the graduated `Goniometer`, the Eiger presents Detector via `Camera`), so nothing new is needed in the device model either.

The autonomous sample exchange reuses the i03 / i24 autonomous-loop shape: a Procedure over the spine threaded through `Subject` custody, not a new device family (ROBOT-1). Indexing and integration of the diffraction frames are `ComputePort` work, not beamline Methods.

The genuinely new thing MX3 contributes is below the technique layer: a sixth Site and a heterogeneous control plane (see [Controls](equipment/controls.md)), which the technique vocabulary rides over unchanged.
