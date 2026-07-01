# Techniques

*What the modelled part of P03 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P03 runs small- and wide-angle X-ray scattering, which earns no catalog Method today, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

## Small-angle X-ray scattering

P03 focuses the beam (the multilayer monochromator feeding the CRL or the GINIX waveguide) to a micro or nano spot, illuminates the sample, and reads the small-angle scattering on the [Pilatus area detector](equipment/detector.md) at a distance.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Small-angle X-ray scattering (SAXS) | `small_angle_scattering` | the focused beam on the sample read by the Pilatus at a SAXS distance; reuses the `small_angle_scattering` slug, a further consumer (`TECH-1`) |

## Wide-angle X-ray scattering

The microfocus endstation's Pilatus 1M reads the wide-angle scattering simultaneously with the SAXS signal.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Wide-angle X-ray scattering (WAXS) | `wide_angle_scattering` | the Pilatus 1M reading the wide-angle signal; reuses the `wide_angle_scattering` slug, a further consumer (`TECH-1`) |

## A new technique family on familiar vocabulary

P03 is PETRA III's first SAXS / WAXS beamline. Its techniques reuse the `small_angle_scattering` and `wide_angle_scattering` slugs already in the catalog's method vocabulary (the same slugs the NSLS-II SMI / CMS and Diamond i22 scattering beamlines carry), so neither forces a new Method to be coined now. The instrument anatomy reuses existing Families: the monochromator binds `Monochromator`, the mirrors `Mirror`, the CRL and GINIX hexapods `Hexapod`, the slits `Slit`, the detectors `Camera`. The GINIX nanofocus adds a waveguide (modelled as a `Hexapod` carrier plus `LinearStage` waveguide stages) and a sample rotation (`RotaryStage`) that suits scanning / nano-imaging, but no new Family.

## Not modelled yet

The concrete acquisition recipes (the SAXS / WAXS exposure sequences, the GINIX scanning / waveguide alignment, the grazing-incidence variants) are not written yet; they join as the deployment approaches the point where CORA drives P03. Whether the scattering Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
