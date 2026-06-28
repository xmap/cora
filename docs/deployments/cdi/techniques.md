# Techniques

*What CORA would run at CDI: coherent-imaging techniques, each a [Catalog](../../catalog/methods.md) Method. CDI follows the deferral the coherent and scanning beamlines set, after Diamond [i13-1](../i13-1/techniques.md), which opened the pending `ptychography` Method, and APS [8-ID](../8-id/techniques.md), [CHX](../chx/techniques.md), and [HXN](../hxn/techniques.md).*

CDI's techniques are coherent diffractive imaging: focus a coherent beam, record the far-field diffraction pattern, and recover the real-space image offline by phase retrieval. These Methods are new to CORA's imaging- and spectroscopy-heritage catalog, so the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Ptychography | `ptychography` | a scan of overlapping coherent-diffraction frames across the sample; reuses the pending `ptychography` Method Diamond i13-1 opened; the reconstruction is a `ComputePort` leg, not a beamline Method (the HXN framing) |
| Forward CDI | `coherent_diffraction_imaging` | a single far-field coherent-diffraction frame on the Eiger2 / Merlin from an isolated object; the single-shot variant of the same deferred coherent-imaging cohort, not separately coined |
| Bragg CDI | `coherent_diffraction_imaging` | a rocking series around a Bragg peak for strain imaging of a crystalline grain, with the [goniometer](equipment/sample.md) setting the orientation; the same deferred coherent-imaging cohort |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, KB, mirror, and slit tuning; reuses the existing Method |

All three imaging techniques need the [KB nanofocus and sample stack](equipment/sample.md) and the [coherent detectors](equipment/detector.md); how the exposure is gated on the floor is the open timing question (TIMING-1).

## Why the Methods stay deferred

Diamond i13-1 opened the coherent-imaging Method as the pending `ptychography` Method (the fleet's first coherent diffractive imaging), carried pending until a conduct-path earns it (TECH-1). CDI reinforces that Method at a second facility and adds the single-shot forward and Bragg CDI variants, which are not separately coined; the concrete acquisition recipes (frame counts, scan grids, rocking ranges, exposures) join as the deployment approaches the point where CORA drives the beamline. This is the same earn-the-abstraction discipline the deferred `small_angle_scattering` (8-ID, CHX) techniques follow. Because the full coherent-imaging Method scope is not in the catalog, CDI records **no Practice** in the [NSLS-II Site](../nsls2/index.md), as CHX records none for its coherent-scattering Methods; the binding lands when the Method does.

The phase retrieval itself (the iterative reconstruction that turns the diffraction frames into a real-space image, and the ptychographic engine that solves for object and probe together) is `ComputePort` work, not a beamline Method. This is the imaging analogue of CHX's correlation analysis: the beamline takes the frames, CORA's compute leg turns them into the result.
