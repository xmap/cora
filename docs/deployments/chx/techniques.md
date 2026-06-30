# Techniques

*What CORA would run at CHX: coherent-scattering techniques, each a [Catalog](../../catalog/methods.md) Method. CHX is the second coherent beamline CORA models, after APS [8-ID](../8-id/techniques.md), and it follows 8-ID's deferral exactly.*

CHX's techniques are coherent-scattering, new to CORA's imaging- and spectroscopy-heritage catalog. As at 8-ID, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| XPCS | `xpcs` | coherent-speckle intensity time series on the Eiger, gated by the Zebra / fast shutter (TIMING-1); Method not yet in catalog |
| Small-angle scattering | `small_angle_scattering` | static SAXS/WAXS on the same detectors; a Plan setting over the same chain |
| Grazing-incidence scattering | `small_angle_scattering` | GISAXS: the same scattering Method with the beam steered onto a surface by the `GrazingIncidenceMirror` (GI-1) |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, mirror, transfocator, and slit tuning; reuses the existing Method |

All three scattering techniques need the [sample stack](equipment/sample.md) and the [coherent detectors](equipment/detector.md); the fast shutter and Zebra (TIMING-1) gate the exposure.

## Why the Methods stay deferred

8-ID opened the question of whether the XPCS and small-angle-scattering Methods enter CORA's catalog (TECH-1), and `main` deliberately left them pending: the concrete acquisition recipes (correlation time series, frame rates, exposures) join as the deployment approaches the point where CORA drives the beamline. CHX reinforces the case for both Methods at a second facility without coining either, the same earn-the-abstraction discipline the deferred `scanning` (HXN) and `energy_scan` (BMM) Capabilities follow. Because the defining Methods are not in the catalog, CHX records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here), exactly as 8-ID records none at APS; the binding lands when the Method does.

The correlation analysis itself (the g2 / multi-tau computation that turns the frame series into dynamics) is `ComputePort` work, not a beamline Method.
