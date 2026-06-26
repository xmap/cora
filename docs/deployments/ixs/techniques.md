# Techniques

*What the modelled part of IXS is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. IXS's technique is momentum-resolved hard X-ray inelastic scattering, the fleet's first energy-loss method, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Momentum-resolved inelastic X-ray scattering

IXS sets the momentum transfer Q with the six-circle reciprocal-space arm, then scans the incident energy against a fixed crystal analyzer and counts the energy-analyzed scattered photons, so the measurement is the intensity surface I(Q, energy-loss): how much energy the sample exchanges with the photon at a chosen momentum transfer. The energy loss is read as the difference between the scanned incident energy and the fixed final energy the analyzer passes.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Momentum-resolved inelastic X-ray scattering | `inelastic_scattering` | Q is set on the [six-circle spectrometer arm](equipment/detector.md) via the H/K/L reciprocal-space pseudo-axis; the incident energy is scanned on the [double-crystal and high-resolution monochromators](beamline.md) against the fixed [crystal energy analyzer](equipment/detector.md); the energy-analyzed signal is point-counted on the electrometers; Method not yet in catalog |

It needs the [incident-energy chain](beamline.md) (the DCM for the coarse energy and the high-resolution monochromator for the meV steps), the [sample stage](equipment/sample.md), and the [six-circle arm, crystal energy analyzer, and counting detectors](equipment/detector.md). The arm scattering angle sets the magnitude of the momentum transfer; the analyzer fixes the final energy so the incident-energy scan reads out the energy loss.

## A new operating axis for the fleet

Energy loss is genuinely new for the fleet. The catalog already covers elastic scattering (SAXS/WAXS, XPDF, powder, XPCS, MX), XRF microprobe, hard X-ray absorption (BMM), and soft resonant inelastic scattering (SIX), but no hard inelastic scattering. The new axis is the acquisition shape itself: scan one optic (the incident energy) against a second, fixed energy-selecting optic (the crystal analyzer) while a point detector counts, rather than expose an area detector at one energy. That is a new Capability, deferred as a question (`TECH-1`); it forces no new device families beyond the loose [`EnergyAnalyzer`](model.md#new-loose-families).

## Not modelled yet

The concrete acquisition recipes (the incident-energy maps, the per-Q energy scans, the analyzer alignment, and the counting times) are not written yet; they join as the deployment approaches the point where CORA drives IXS. Whether the technique enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); hard inelastic scattering is a new regime for the fleet (see [Open questions](questions.md) for the world-facts to confirm first).
