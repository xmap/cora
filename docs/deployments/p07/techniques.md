# Techniques

*What the modelled part of P07 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P07's diffraction and high-field techniques earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## High-energy materials-science diffraction

P07 uses a high-energy monochromatic beam to study engineering materials (bulk diffraction, residual stress, texture, in-situ deformation), reading the diffraction on the [four-circle diffractometer](equipment/sample.md) and the [Pilatus / PerkinElmer detectors](equipment/detector.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-energy diffraction | `diffraction` | bulk / engineering diffraction on the four-circle diffractometer + area detectors; reuses the `diffraction` slug, a further consumer (`TECH-1`) |

## High-field materials science

P07's EH2 endstation carries a 17 T high-field magnet for studies under applied magnetic field.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-field magnetic scattering | `magnetic_scattering` | scattering / diffraction in the 17 T magnet; reuses the `magnetic_scattering` slug P09 / 4-ID share, a further consumer (`TECH-1`) |

## A high-energy materials beamline on familiar vocabulary

P07 is the fleet's high-energy materials-science beamline. Its techniques reuse the `diffraction` and `magnetic_scattering` slugs already carried across the fleet, so none forces a new Method now. The instrument anatomy reuses existing Families: the multi-bounce mono binds `Monochromator`, the four-circle diffractometer `Goniometer`, the 17 T magnet the graduated catalog `Magnet` Family, the Linkam stage `TemperatureController`, the detectors `Camera`. The in-situ sample environment (the Linkam heating / cooling, the magnet) suits operando materials studies but coins no new Family.

## Not modelled yet

The concrete acquisition recipes (the diffraction / stress-mapping scans, the in-situ deformation / temperature ramps, the high-field scans) are not written yet; they join as the deployment approaches the point where CORA drives P07. Whether the diffraction Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
