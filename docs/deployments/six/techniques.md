# Techniques

*What the modelled part of SIX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. SIX's technique is resonant inelastic X-ray scattering, a soft X-ray scattering method new to CORA's imaging-heritage catalog, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Resonant inelastic X-ray scattering

RIXS tunes the incident soft X-ray energy to an absorption edge and measures the energy and momentum the sample exchanges with the scattered photon, so the measurement is a spectrum of the emitted light dispersed by the spectrometer arm onto the photon-counting camera.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant inelastic X-ray scattering | `resonant_inelastic_scattering` | the incident energy is set on the [grating monochromator](beamline.md); the emitted spectrum is dispersed by the [spectrometer arm](equipment/detector.md) and recorded on the photon-counting camera; Method not yet in catalog |

It needs the [grating monochromator](beamline.md) (the incident-energy and resolution chain, exit slit included), the [UHV cryostat sample](equipment/sample.md), and the [RIXS spectrometer arm and camera](equipment/detector.md). The arm scattering angle selects the momentum transfer.

## Not modelled yet

The concrete acquisition recipes (energy maps, emission-spectrum exposures, the arm-angle and resolution settings) are not written yet; they join as the deployment approaches the point where CORA drives SIX. Whether RIXS enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); soft X-ray is a new regime for the fleet (see [Open questions](questions.md) for the world-facts to confirm first).
