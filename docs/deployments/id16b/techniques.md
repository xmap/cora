# Techniques

*What CORA would run at ID16B: KB-focused hard X-ray nano-tomography and nano-XRF (fluorescence) mapping, two [Catalog](../../catalog/methods.md) Methods bound through [ESRF Practices](../esrf/index.md#the-techniques-adapted-here). Both are reused, not new; ID16B's novelty is the nanoprobe-on-BLISS combination, not the techniques.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| KB-focused nano-tomography | `tomography` | the sample is spun through the nanofocused beam while an area detector records a projection stack; a real-space volume is reconstructed downstream. The existing Method ID19 / 2-BM / TomoWise carry; ID16B is a further consumer (TECH-1) |
| Nano-XRF mapping (incl. fluorescence-tomography) | `scanning_fluorescence_microscopy` | the sample is rastered through the nanoprobe on a piezo scanner while an energy-dispersive detector reads a fluorescence spectrum per point, building an element map; fluorescence-tomography adds a rotation axis. The pending Method 2-ID / XFM / LIX carry; ID16B is a further consumer (METHOD-1) |

The techniques are recorded as pending [Practices](../esrf/index.md#the-techniques-adapted-here) on the ESRF Site: `ID16B_nanotomography_practice` and `ID16B_scanning_fluorescence_microscopy_practice` (TECH-1, METHOD-1).

## The two acquisition shapes

Both are acquisition shapes CORA already models; ID16B runs them through one KB nanofocus.

- **Nano-tomography.** The [rotation stage](sample.md) spins the sample through the nanofocused beam; the [area detector](detector.md) records a projection at each angle; the projection stack reconstructs to a volume. Same shape as ID19, at nanoscale resolution.
- **Nano-XRF mapping.** The [piezo raster scanner](sample.md) steps the sample through the nanoprobe point by point; at each point the [fluorescence detector](detector.md) reads an energy-dispersive spectrum, and the element maps are fit downstream. Adding the rotation axis turns this into fluorescence-tomography (a 3D element map).

The parts are a `RotaryStage` (the tomo spin / fluo-tomo rotation), `LinearStage`s (coarse positioning and the PI piezo raster scanner), `Mirror`s (the KB nanofocus), an `EnergyDispersiveSpectrometer` (the FalconX XRF detector), and a `Camera` (the area detector). None is new. The reconstructions, both the tomographic volume and the XRF map fitting, are `ComputePort` work, not beamline devices.

## Why the techniques are not the novelty

CORA already models tomography (ID19, 2-BM) and scanning fluorescence microscopy (2-ID, XFM, LIX). ID16B is a further consumer of both, so the Practices are carried pending only because ID16B is not yet driven by CORA, not because the Methods are new.

The novelty at ID16B is the combination and the floor: it is the fleet's first KB nanoprobe with an energy-dispersive fluorescence detector, and a further beamline on the BLISS / Tango control floor. Both are device-and-control concerns ([Model](model.md), [Controls](controls.md)), not technique concerns. Holding the Methods constant is the point: it isolates what is genuinely new.

## Not modelled yet

This cut models the source, optics, KB nanofocus, sample stack, and detection. The sample environments present in the config are noted, not modelled:

- The cryostream, furnace, and xeol sample environments (`EH/cryo`, `EH/furnace`, `EH/xeol`) and their Eurotherm / nanodac regulation. A `Cryostat` Family is not yet in the catalog, so the sample environment is deferred to keep this cut vocabulary-neutral (ENV-1).
- The `mapping` / `oda` / `taurus` / `webui` software layers (not beamline devices).

Each is named on the [Open questions](questions.md) page rather than modelled speculatively. The source walk that grounds what is and is not present is the generated [beamline](source.md) view.
