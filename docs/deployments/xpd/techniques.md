# Techniques

*What CORA would run at XPD: powder-diffraction and total-scattering techniques, each a [Catalog](../../catalog/methods.md) Method. XPD is the NSLS-II twin of the Diamond [I11](../i11/techniques.md) (powder diffraction) and [I15-1](../i15-1/techniques.md) (total scattering / PDF) beamlines, and it follows their deferral exactly.*

XPD's techniques are powder diffraction and total scattering, a science domain Diamond's i11 and i15-1 brought to CORA as new Capabilities. As there, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Mode | Notes |
| --- | --- | --- |
| Powder diffraction | monochromatic, flat panel | Debye-Scherrer rings on the flat panel at a chosen energy; the i11 Capability, new Capability pending (TECH-1) |
| Total scattering / PDF | fixed high energy, close detector | wide-Q on the flat panel at a close detector distance; the i15-1 Capability, new Capability pending (TECH-1) |
| Variable-temperature diffraction | over a temperature ramp | the same, over a ramp on the sample-environment stages (TEMP-1) |
| Autonomous sample exchange | n/a | a Procedure over the spine, threaded through `Subject` custody and gated by a Clearance (ROBOT-1) |

All the scattering techniques need the [diffractometer and sample stages](equipment/sample.md), the [flat-panel detectors](equipment/detector.md), and the detector distance; the exposure shutter gates the frames.

## Why the Capabilities stay deferred

Diamond i11 and i15-1 opened the question of whether the powder-diffraction and total-scattering Capabilities enter CORA's catalog (TECH-1), and `main` deliberately left them pending: a powder or PDF measurement is a new science Capability binding device Roles that already exist (the flat panel presents Detector, the diffractometer and mono present Positioner), so what is new is the Capability, not a device shape. XPD reinforces the case for both at a second facility without coining either, the same earn-the-abstraction discipline the deferred `xpcs` (CHX), `scanning` (HXN), and `energy_scan` (BMM) Capabilities follow. Because the defining Capabilities are not in the catalog, XPD records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); the binding lands when the Capability does.

The azimuthal integration and pair-distribution-function reduction (the Fourier transform of the total-scattering structure function into a real-space PDF) are `ComputePort` work, not beamline Methods. The autonomous sample exchange reuses the i03 / i15-1 autonomous-loop shape: a Procedure over the spine, not a new device family (ROBOT-1).
