# Techniques

*What the modelled part of ESM is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. ESM's technique is angle-resolved photoemission, a photoemission method new to CORA's catalog, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Angle-resolved photoemission

ARPES illuminates the sample with monochromatic soft X-rays and measures the kinetic energy and emission angle of the photoelectrons, mapping the electronic band structure. The measurement is the electron distribution recorded by the hemispherical analyzer over a pass-energy and lens-mode window, at a sample orientation set by the cryostat manipulator.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Angle-resolved photoemission | `angle_resolved_photoemission` | electron energy / angle spectra on the Scienta SES analyzer, at low temperature on the UHV manipulator; Method not yet in catalog |

It needs the [grating monochromator](beamline.md) (the incident energy), the [UHV cryostat manipulator](equipment/sample.md), and the [electron analyzer](equipment/detector.md). Polarization is set by the dual EPUs.

## Not modelled yet

The XPEEM/LEEM photoemission-microscopy branch is deferred (a future `ElectronMicroscope` Family; see [Model](model.md#deliberately-not-here-yet)). The concrete acquisition recipes (Fermi-surface maps, energy-distribution curves, the analyzer sweep settings) are not written yet; they join as the deployment approaches the point where CORA drives ESM. See [Open questions](questions.md) for the world-facts to confirm first.
