# Techniques

*What CORA would run at CDI: coherent-imaging techniques, each a [Catalog](../../catalog/methods.md) Method. CDI follows the deferral the coherent and scanning beamlines already set, after APS [8-ID](../8-id/techniques.md), [CHX](../chx/techniques.md), and [HXN](../hxn/techniques.md).*

CDI's techniques are coherent diffractive imaging: focus a coherent beam, record the far-field diffraction pattern, and recover the real-space image offline by phase retrieval. These Methods are new to CORA's imaging- and spectroscopy-heritage catalog, so the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Forward CDI | `coherent_diffraction_imaging` | a single far-field coherent-diffraction frame on the Eiger2 / Merlin from an isolated object; Method not yet in catalog |
| Ptychography | `ptychography` | a scan of overlapping coherent-diffraction frames across the sample; the reconstruction is a `ComputePort` leg, not a beamline Method (the HXN framing) |
| Bragg CDI | `coherent_diffraction_imaging` | a rocking series around a Bragg peak for strain imaging of a crystalline grain; the same imaging Method with the [goniometer](equipment/sample.md) setting the orientation |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, KB, mirror, and slit tuning; reuses the existing Method |

All three imaging techniques need the [KB nanofocus and sample stack](equipment/sample.md) and the [coherent detectors](equipment/detector.md); how the exposure is gated on the floor is the open timing question (TIMING-1).

## Why the Methods stay deferred

8-ID opened the question of which coherent Methods enter CORA's catalog (TECH-1): its XPCS has since graduated to a catalog `xpcs` Method, but its small-angle scattering and diffraction stayed pending, and CDI's coherent-imaging Methods are not coined at all. The concrete acquisition recipes (frame counts, scan grids, rocking ranges, exposures) join as the deployment approaches the point where CORA drives the beamline. CDI reinforces the case for a coherent-imaging Method without coining it, the same earn-the-abstraction discipline the deferred `small_angle_scattering` (8-ID, CHX) and ptychography (HXN) techniques follow. Because the defining Methods are not in the catalog, CDI records **no Practice** in the [NSLS-II Site](../nsls2/index.md), as CHX records none for its coherent-scattering Methods; the binding lands when the Method does.

The phase retrieval itself (the iterative reconstruction that turns the diffraction frames into a real-space image, and the ptychographic engine that solves for object and probe together) is `ComputePort` work, not a beamline Method. This is the imaging analogue of CHX's correlation analysis: the beamline takes the frames, CORA's compute leg turns them into the result.
