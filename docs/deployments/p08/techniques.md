# Techniques

*What the modelled part of P08 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P08's diffraction technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## High-resolution diffraction

P08 uses a high-resolution monochromatic beam on a six-circle [diffractometer](sample.md) to measure surface / interface diffraction, reflectivity (XRR), and high-resolution powder / single-crystal diffraction, reading the [Eiger / Pilatus / Mythen detectors](detector.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-resolution diffraction / reflectivity | `diffraction` | surface / interface diffraction and reflectivity on the six-circle Kohzu diffractometer + area / strip detectors; reuses the `diffraction` slug P07 share, a further consumer (`TECH-1`) |

## A diffraction beamline on familiar vocabulary

P08 is the fleet's high-resolution diffraction beamline. Its technique reuses the `diffraction` slug already carried pending across the fleet, so it forces no new Method now. The instrument anatomy reuses existing Families: the monochromators bind `Monochromator`, the six-circle diffractometer `Goniometer`, the CRL `Transfocator`, the hexapod `Hexapod`, the detectors `Camera` / `EnergyDispersiveSpectrometer`. The rich detector set (Eiger / Pilatus / Mythen / PerkinElmer / Vortex) suits the breadth of diffraction modes but coins no new Family.

## Not modelled yet

The concrete acquisition recipes (the reflectivity / rocking-curve scans, the reciprocal-space mapping, the high-resolution powder collection) are not written yet; they join as the deployment approaches the point where CORA drives P08. Whether the diffraction Method enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
