# Techniques

*What CORA would run at PDF: high-energy total-scattering and powder-diffraction techniques, each a [Catalog](../../catalog/methods.md) Method. PDF is the twin of [XPD](../xpd/techniques.md) and follows its deferral exactly, after Diamond [i11](../i11/techniques.md) and [i15-1](../i15-1/techniques.md).*

PDF's techniques are high-energy total scattering and powder diffraction: a high-energy beam through a powder or capillary sample onto a large area detector, with the sample-to-detector distance setting the accessible Q. These Methods are new to CORA's imaging- and spectroscopy-heritage catalog. As at XPD, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Total scattering / PDF | `total_scattering` | rapid-acquisition pair distribution function: a near and a far detector distance merged to high Q (DIST-1); Method not yet in catalog, shared with i15-1 and XPD |
| Powder diffraction | `powder_diffraction` | the same high-energy beam and detector for Rietveld-quality powder patterns; Method not yet in catalog, shared with i11 and XPD |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, monochromator, mirror, and slit tuning; reuses the existing Method |

Both techniques need the [sample spinner and environment](equipment/sample.md) and the [area detectors](equipment/detector.md); the exposure is gated by the fast shutter, with the two-distance merge sequenced in software (DIST-1).

## Why the Methods stay deferred

Diamond i11 (powder diffraction) and i15-1 (total scattering / PDF) opened the question of whether these Methods enter CORA's catalog (TECH-1), and `main` deliberately left them pending: the concrete acquisition recipes (energies, distances, exposures, the near / far merge) join as the deployment approaches the point where CORA drives the beamline. PDF reinforces both Methods at a second NSLS-II endstation without coining either, the same earn-the-abstraction discipline XPD follows. Because the defining Methods are not in the catalog, PDF records **no Practice** in the [NSLS-II Site](../nsls2/index.md), exactly as XPD records none; the binding lands when the Method does.

The PDF reduction itself (the azimuthal integration of the detector frames and the Fourier transform of the structure function into the pair distribution function G(r)) is `ComputePort` work, not a beamline Method: the beamline takes the frames, CORA's compute leg turns them into the result.
