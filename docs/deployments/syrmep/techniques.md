# Techniques

*What the modelled part of SYRMEP is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../elettra/index.md) is how a facility adapts it. SYRMEP is a hard X-ray microtomography beamline, so its core imaging techniques reuse the catalog Methods the fleet's imaging beamlines already share; the helical, white-beam, and phase-retrieval Methods are new to CORA's catalog and render unlinked, carried pending until a technique enters scope (`TECH-1`).

## Microtomography: absorption and phase contrast

SYRMEP sets the X-ray energy with the Si(111) monochromator (or passes white / pink beam), then rotates the specimen while the detector records projections. It does absorption tomography, propagation-based phase-contrast tomography (the long sample-to-detector rail), and diffraction-enhanced imaging.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Microtomography | [`tomography`](../../catalog/methods.md) | the canonical imaging routine on the [rotation stage](sample.md) and [camera](detector.md); reuses the 2-BM tomography Method directly |
| Continuous (fly) tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | trigger-driven continuous rotation under DonkiOrchestra; reuses the catalog Method |
| Wide / laminar-beam tomography | [`mosaic_tomography`](../../catalog/methods.md) | tiled tomography for samples beyond the field of view; reuses the catalog Method |
| Dark / flat field | [`dark_field`](../../catalog/methods.md), [`flat_field`](../../catalog/methods.md) | the reconstruction baseline frames; reuse the catalog acquisition Methods |
| Rotation-axis centring | [`center_alignment`](../../catalog/methods.md) | the alignment step; reuses the catalog Method |
| Helical CT | `helical_tomography` | the large-specimen continuous-pitch mode (the XC Hydra photon-counting setup); Method not yet in the catalog, renders unlinked |
| White / pink-beam tomography | `white_beam_tomography` | fast tomography with the DCM bypassed; Method not yet in the catalog |
| Phase retrieval | `phase_retrieval` | single-distance TIE-HOM / Paganin retrieval (the SYRMEP Tomo Project pipeline); a compute Method not yet in the catalog (`COMPUTE-1`) |

## A clean re-test of the imaging spine

SYRMEP's significance for the catalog is that it forces nothing new at the Family level: every device binds an existing imaging Family (`RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Slit`, `Filter`, `Monochromator`), and the core tomography Practices bind real catalog Methods. It is the cleanest re-test the fleet has of whether the imaging spine ports to a brand-new Site and control house-style. The clinical breast-CT programme (SYRMA-3D) and the large-specimen helical work are extensions that would earn new Methods if the deployment enters pilot scope.

## Not modelled yet

The concrete acquisition recipes (the exposure, projection counts, angle ranges, propagation distances, and the phase-retrieval and ring-removal parameters) are not written yet; they join as the deployment approaches the point where CORA drives SYRMEP. Whether helical CT, white-beam tomography, and phase retrieval enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
