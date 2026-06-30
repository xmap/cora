# Techniques

*What the modelled part of P02 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P02's diffraction techniques reuse Methods the fleet already carries pending, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

## Powder diffraction (P02.1)

P02.1 illuminates a powder / polycrystalline sample with a high-energy (~60 keV) monochromatic beam and reads the Debye-Scherrer rings on the [Pilatus 1M area detector](equipment/detector.md), with in-situ temperature control for parametric studies.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-energy powder diffraction | `powder_diffraction` | the powder sample read by the Pilatus 1M; reuses the `powder_diffraction` slug i11 / XPD share, a further consumer (`TECH-1`) |

## Total scattering / PDF (P02.1)

P02.1 also collects total scattering to high momentum transfer (the high-energy beam plus the [PerkinElmer flat-panel](equipment/detector.md)) for pair-distribution-function analysis of local / disordered structure.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Total scattering / pair-distribution-function | `total_scattering` | high-Q total scattering on the PerkinElmer flat-panel; reuses the `total_scattering` slug i15-1 / XPD share, a further consumer (`TECH-1`) |

## High-pressure diffraction (P02.2)

P02.2 puts the sample in a [diamond-anvil cell](equipment/sample.md) and collects diffraction under high pressure (and variable temperature), for extreme-conditions studies.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Diamond-anvil-cell high-pressure diffraction | `powder_diffraction` | high-pressure diffraction in the DAC; reuses the `powder_diffraction` slug, a further consumer (`TECH-1`, `PRESSURE-1`) |

## A high-energy diffraction beamline on familiar vocabulary

P02 is the fleet's high-energy powder / total-scattering beamline and its first diamond-anvil-cell extreme-conditions endstation. Its techniques reuse the `powder_diffraction` and `total_scattering` slugs already carried pending across the fleet (Diamond i11 / i15-1, NSLS-II XPD), so none forces a new Method now. The instrument anatomy reuses existing Families end to end: the monochromator binds `Monochromator`, the bendable mirrors `Mirror`, the detectors `Camera`, the sample environment `TemperatureController`, and the high-pressure cell the allowlisted-loose `PressureCell` (the 13-id-d precedent, now at its second consumer).

## Not modelled yet

The concrete acquisition recipes (the powder-ring integration sequences, the high-Q PDF collection, the pressure-ramp diffraction loops) are not written yet; they join as the deployment approaches the point where CORA drives P02. Whether the diffraction Methods or the PressureCell Family enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
