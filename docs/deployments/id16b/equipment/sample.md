# Sample

*The sample side. ESRF runs BLISS / Tango; the handles are the real BLISS object names read from the [public ID16B config](https://gitlab.esrf.fr/id16b/beamline_configuration), carried `confirm` (CTRL-1).*

ID16B focuses the beam to a nanoprobe with a Kirkpatrick-Baez mirror pair, then runs two acquisitions over the focused beam: nano-tomography (spin the sample, record projections) and nano-XRF mapping (raster the sample, read a fluorescence spectrum per point). So the sample side has the KB nanofocus, the sample-side slits, and a three-part stage stack: a rotation stage, a coarse positioning stage, and a fine piezo raster scanner.

| Asset | Family | Handle | What it does |
| --- | --- | --- | --- |
| `KBMirrors` | Mirror | `kbx`/`cfocus`/`cfocus2` (iceid164) | KB focusing pair; the nanoprobe |
| `ThirdSlits` | Slit | `s3fh`/`s3bh`/`s3uv`/`s3dv` | sample-side defining slits |
| `SampleRotation` | RotaryStage | `srot` (etel `id16b/dsc2p/rot16`), `srot2` | tomo / fluo-tomo rotation; the tomo master motion |
| `SampleStage` | LinearStage | `sx`/`sy`/`sz` | coarse sample positioning / centring |
| `SampleScanner` | LinearStage | `sampy`/`sampz`/`sypz` (PI piezo) | fine raster scanner; the nano-XRF mapping motion |

## The KB nanofocus

The `KBMirrors` are the Kirkpatrick-Baez focusing mirror pair (`kbx`, `cfocus`, `cfocus2` on `iceid164`): two mirrors, one focusing horizontally and one vertically, that bring the monochromatic beam to a nanoprobe at the sample. This is what makes ID16B a nano-analysis beamline. CORA binds them to the catalog [`Mirror`](../../../catalog/families.md) family; the focal spot and working distance are OPT-1. The `ThirdSlits` (`s3*`) are the sample-side defining slits that clean up the beam before the focus.

## The sample-scanning stack

Each acquisition uses a different part of the stack as its operative motion.

- `SampleRotation` is the rotation stage (`srot`, an etel Tango motor `id16b/dsc2p/rot16`, plus `srot2` on `iceid164`). It is the master motion of nano-tomography (spin the sample through the nanofocus while the [area detector](detector.md) records projections), and the added axis that turns nano-XRF into fluorescence-tomography. CORA binds it to the catalog [`RotaryStage`](../../../catalog/families.md) (SAMPLE-1).
- `SampleStage` is the coarse positioning stage (`sx`/`sy`/`sz`, encoded, on the etel and `iceid164`): centres the sample on the nanoprobe. Catalog [`LinearStage`](../../../catalog/families.md) (SAMPLE-1).
- `SampleScanner` is the fine PI piezo raster scanner (`sampy`/`sampz` on `vscanner1`, `sypz` on `vscanner2`): the operative motion of nano-XRF mapping, stepping the sample through the nanoprobe point by point while the [fluorescence detector](detector.md) reads a spectrum per point. Also catalog `LinearStage` (SAMPLE-1).

## Why no new family here

ID16B is the fleet's first KB nanoprobe, but the nanoprobe is not a new device class: the KB mirrors are `Mirror`, the stages are `RotaryStage` / `LinearStage`, and the [detectors](detector.md) are `EnergyDispersiveSpectrometer` / `Camera`. No family graduates and the catalog is unchanged. The techniques are the existing [`tomography`](../../../catalog/methods.md) and pending `scanning_fluorescence_microscopy` Methods, both further consumers, not new Methods (TECH-1, METHOD-1); the volume reconstruction and the XRF map fitting are `ComputePort` work, not beamline devices. The full deployment-level reasoning is on the [model](../model.md) page.

The genuine novelty at ID16B is the nanoprobe-and-XRF combination and the control floor. ESRF runs BLISS (Tango-based), not EPICS, so these stages are BLISS axes driven by IcePAP and PI piezo controllers (CTRL-1, see [Controls](controls.md)). The sample environments (cryostream, furnace, xeol) that would sit on this stack are noted, not modelled in this cut (ENV-1). The [beamline](../beamline.md) source-walk and the [inventory](../inventory.md) carry the flat reference.
