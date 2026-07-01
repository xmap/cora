# Techniques

*What the modelled part of P22 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P22's HAXPES technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Hard X-ray photoelectron spectroscopy

P22 illuminates the sample with a monochromatic hard X-ray beam (the shared P09 optics, with the phase retarder setting polarization) and measures the kinetic-energy spectrum of the emitted photoelectrons on the [electron analyzer](equipment/detector.md), probing bulk / buried electronic structure (the hard X-ray depth advantage over soft X-ray photoemission).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Hard X-ray photoelectron spectroscopy (HAXPES) | `angle_resolved_photoemission` | photoemission on the HAXPS electron analyzer over the shared P09 optics; reuses the `angle_resolved_photoemission` slug P04 shares, a further consumer (`TECH-1`) |

## A photoemission beamline on familiar vocabulary

P22 is the fleet's hard X-ray photoemission beamline. Its technique reuses the `angle_resolved_photoemission` slug already carried pending (P04, NSLS-II ESM), so it forces no new Method. The instrument anatomy reuses existing Families: the shared optics bind `Monochromator` / `Mirror` / the catalog `PhaseRetarder`, the sample stage `Manipulator`, and the electron analyzer the catalog `ElectronAnalyzer` (graduated at NSLS-II ESM, carried pending here since not exposed in the registry). The HAXPES depth sensitivity is a physics consequence of the hard X-ray energy, not a new device.

## Not modelled yet

The concrete acquisition recipes (the analyzer energy sweeps, the depth-profiling / standing-wave HAXPES, the polarization-dependent measurements) are not written yet; they join as the deployment approaches the point where CORA drives P22. Whether `angle_resolved_photoemission` enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
