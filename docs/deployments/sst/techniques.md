# Techniques

*What CORA would run at SST: soft-scattering, absorption, and photoemission techniques, each a [Catalog](../../catalog/methods.md) Method. SST spans three technique families on two branches, and follows the deferral discipline of the beamlines that brought each to CORA.*

SST's techniques are new-domain science (soft-X-ray scattering, absorption, photoemission), the families Diamond and the earlier NSLS-II soft-X-ray beamlines brought to CORA. The Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Branch / mode | Notes |
| --- | --- | --- |
| Resonant soft X-ray scattering (RSoXS) | soft, monochromatic | scattering pattern on the Greateyes CCD; the i22 / CSX scattering family, new Capability pending (TECH-1) |
| NEXAFS absorption | soft, energy sweep | drain current / partial electron yield / microcalorimeter fluorescence over an energy scan; the BMM energy-scan question (ENERGY-1, TECH-1) |
| HAXPES photoemission | tender, fixed energy | photoelectron spectra on the hemispherical analyzer; the ESM photoemission family, new Capability pending (TECH-1) |

All three need the per-endstation [sample manipulator](equipment/sample.md) and [detector](equipment/detector.md); the fast shutter gates the exposure, and the endstation in control selects the branch.

## Why the Capabilities stay deferred

Each of SST's three technique families sits on a Capability the catalog does not yet carry, and the discipline is the same one the originating beamlines applied: soft-X-ray scattering follows Diamond i22 and NSLS-II CSX (the scattering Capabilities are pending, TECH-1); NEXAFS absorption follows BMM (energy-scan-as-the-measurement, deferred at ENERGY-1); photoemission follows NSLS-II ESM (the `angle_resolved_photoemission` Method ESM coined is pending, and HAXPES is the hard / tender photoemission companion). The device Roles already exist (the CCD presents Detector, the manipulators present Positioner, the analyzer and microcalorimeter are the energy-resolving detectors); what is new is the science Capability, not a device shape. SST reinforces all three at one more, larger instrument without coining any, so it records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

The per-technique reduction (scattering reduction, photoemission spectra, NEXAFS spectra) is `ComputePort` work, not beamline Methods.
