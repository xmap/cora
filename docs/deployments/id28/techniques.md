# Techniques

*What the modelled part of ID28 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../esrf/index.md#the-techniques-adapted-here) is how a facility adapts it. ID28 runs momentum-resolved hard X-ray inelastic scattering, a Method not yet in CORA's catalog, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Momentum-resolved inelastic X-ray scattering

ID28 sets a meV-resolution incident energy with the high-resolution backscattering monochromator (scanned by tuning the crystal temperature, not a Bragg angle), places the multi-analyzer spectrometer arm at a scattering angle that selects the momentum transfer, and scans the incident energy against the fixed-angle analyzer crystals, counting the energy-analyzed scattered photons. The measurement is the intensity surface I(Q, energy-loss): how much energy the sample exchanges with the photon at a chosen momentum transfer, the signature of phonons and collective excitations.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Momentum-resolved inelastic X-ray scattering | `inelastic_x_ray_scattering` | the momentum transfer Q is set by the [spectrometer-arm two-theta](detector.md); the meV incident energy is scanned on the [backscattering monochromator](source.md) against the fixed-angle [multi-analyzer crystals](detector.md); the energy-analyzed signal is counted per analyzer; reuses the NSLS-II IXS Method, the second consumer; Method not yet in catalog |

It needs the [incident-energy chain](source.md) (the backscattering mono for the meV resolution), the [sample stage and its temperature environment](sample.md), and the [multi-analyzer spectrometer arm and its detectors](detector.md). The arm scattering angle sets the magnitude of the momentum transfer; the analyzer crystals fix the analyzed energy so the incident-energy scan reads out the energy loss.

## The same inelastic axis, in the hard X-ray regime

ID28 is the fleet's hard X-ray IXS instrument. The catalog already anticipates inelastic scattering (the SIX soft RIXS arm, the NSLS-II IXS beamline, the ID32 soft RIXS / XES arms), and ID28 reuses the `inelastic_x_ray_scattering` Method the NSLS-II IXS beamline left pending as the second consumer, deepening the case for that Capability without coining anything. The device that ties the inelastic beamlines together is the dispersive spectrometer arm: ID28's multi-analyzer crystal arm is a further consumer of the `SpectrometerArm` family, the sighting that reinforced the graduation earned at ID32, now landed as a catalog Family (see [Model](model.md#a-further-spectrometerarm-consumer-held)).

## Not modelled yet

The concrete acquisition recipes (the per-Q energy scans, the analyzer alignment, the counting times, the analyzer-crystal array calibration) are not written yet; they join as the deployment approaches the point where CORA drives ID28. Whether momentum-resolved IXS enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
