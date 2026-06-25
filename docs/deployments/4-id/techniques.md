# Techniques

*What the modelled part of 4-ID POLAR is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. POLAR's techniques are diffraction, magnetism, and polarization, none of which exist in CORA's imaging-heritage catalog yet, so the Methods below render unlinked and are carried pending until one enters the pilot scope (`TECH-1`). The function view survives the eventual hardware and catalog choices, which is why it can be written before the Methods are coined.

## Single-crystal diffraction

The Huber diffractometers at 4-ID-G orient a single crystal and scan reciprocal space, measuring scattered intensity as a function of momentum transfer.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray diffraction | `diffraction` | reciprocal-space scans on the Eulerian or high-pressure diffractometer; Method not yet in catalog |
| High-pressure diffraction | `diffraction` | the high-pressure diffractometer with a pressure cell; a Plan setting over the same Method |

Both need the [diffractometers](equipment/sample.md) and the [detectors](equipment/detector.md). Whether the reciprocal-space coordination (hklpy2) is modelled as a `PseudoAxis` inside an `Assembly(Diffractometer)` is the design recorded on [Model](model.md#deliberately-not-here-yet); the world-fact half (the circle geometry) is `DIFF-1`.

## Magnetic and resonant scattering

POLAR's signature: resonant scattering across an absorption edge, in an applied magnetic field and at low temperature, to probe magnetic and electronic order.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant magnetic scattering | `magnetic_scattering` | scattering in field (2 T or high-field magnet) at low temperature; Method not yet in catalog |
| Resonant elastic scattering | `resonant_scattering` | energy-resonant scattering across an edge; Method not yet in catalog |

These need the [sample environment](equipment/sample.md) (magnet plus temperature controller) and the monochromator's energy control.

## Polarization analysis

The phase retarders set the incident X-ray polarization, and the polarization analyzer resolves the scattered-beam polarization; together they enable dichroism and polarization-dependent scattering.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray magnetic circular dichroism | `xmcd` | circular polarization set by the phase retarders; Method not yet in catalog |
| Polarization-analyzed scattering | `magnetic_scattering` | the analyzer crystal resolves the scattered polarization; a Plan setting over the scattering Method |

These need the [phase retarders and polarization analyzer](equipment/sample.md).

## Not modelled yet

The Raman station's techniques are out of this cut (`TOPO-2`). The concrete acquisition recipes (scan sequences, energies, fields, exposures) are not written yet; they join as the deployment approaches the point where CORA drives 4-ID. Whether diffraction and the polarization / magnetism Methods enter CORA's catalog at all is an owner-scope decision recorded on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
