# Techniques

*What the modelled part of P09 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P09's resonant-scattering, magnetic-scattering, and dichroism techniques earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## Resonant elastic X-ray scattering

P09 tunes the incident energy onto an absorption edge (the DCM) and measures the elastically scattered intensity on the six-circle [goniometer](equipment/sample.md), with the [phase retarder](equipment/sample.md) setting incident polarization and the [analyzer](equipment/sample.md) resolving the scattered polarization.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant elastic X-ray scattering | `resonant_scattering` | edge-tuned elastic scattering on the six-circle diffractometer + PerkinElmer / Pilatus, with polarization analysis; reuses the `resonant_scattering` slug 4-ID / i06 / i10 share, a further consumer (`TECH-1`) |

## Magnetic scattering and dichroism

P09's MAG endstation applies a 14 T field to the sample and measures the magnetic scattering / dichroism, with the phase retarder switching incident polarization for XMCD.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Magnetic scattering | `magnetic_scattering` | scattering in the 14 T high-field magnet; reuses the `magnetic_scattering` slug, a further consumer (`TECH-1`) |
| X-ray magnetic circular / linear dichroism | `xmcd` | dichroism in the 14 T magnet with the phase retarder setting polarization; reuses the `xmcd` slug 4-ID / i06 / i10 share, a further consumer (`TECH-1`) |

## A polarization / magnetism beamline on the 4-ID POLAR vocabulary

P09 is the fleet's resonant-scattering and high-field-magnetism beamline. Its techniques are new to CORA's catalog (no resonant / magnetic Method is earned yet), but they reuse the slugs the APS 4-ID POLAR deployment and the Diamond i06 / i10 beamlines already carry pending, so none forces a new Method now. Crucially, the instrument anatomy reuses the polarization / magnetism Families 4-ID POLAR introduced: the phase retarder binds the allowlisted-loose `PhaseRetarder`, the analyzer `PolarizationAnalyzer`, and the 14 T magnet `Magnet`. P09 is the second consumer of each, the rule-of-three signal toward eventual graduation, recorded on [Model](model.md).

## Not modelled yet

The concrete acquisition recipes (the energy / diffractometer / field scan sequences, the polarization-switching dichroism loops) are not written yet; they join as the deployment approaches the point where CORA drives P09. Whether the resonant / magnetic Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
