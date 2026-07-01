# The beamline

*The part of ID28 CORA models today, as areas you can jump to: the source and high-resolution optics, the IXS spectrometer endstation, plus the controls. First cut.*

ID28 is the ESRF beamline for momentum-resolved inelastic X-ray scattering (IXS), CORA's second ESRF deployment. Two in-vacuum undulators feed a high-resolution backscattering monochromator and focusing mirrors, and the conditioned beam meets the sample at the eh1 spectrometer endstation, where a multi-analyzer crystal arm energy-analyzes the scattered beam. This cut models the operational core across the optics and the endstation. The model is reverse-engineered from the ESRF's public BLISS Beacon device database; the BLISS / Tango / IcePAP handles are real, read from the config, and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the incident beam at meV resolution, the [Sample](sample.md) that places the specimen and conditions its temperature, and the [Detector](detector.md) that energy-analyzes and counts the scattered beam. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, grouping pending (`ENC-1`): a shared `id28-optics` zone (oh1 / oh2 / oh3) and the `id28-eh1` experiment hutch.

## Stations

- [Source](../beamline.md): the ESRF-EBS storage-ring state via the BLISS MachInfo (a loose `StorageRing`, observe-only, `MACHINE-1`) and the front-end shutter (`Shutter`, `PSS-1`); the two in-vacuum undulators bound to `InsertionDevice` (`SRC-1`); the high-resolution backscattering monochromator bound to `Monochromator`, with the incident-energy pseudo-axis realized over the ASL F700 crystal-temperature controller (`MONO-1`); the HFM / VFM focusing mirrors bound to `Mirror` (`OPT-1`); the oh2 Elettra beam-position monitor bound to the graduated catalog `PositionMonitor` (presenting `Sensor`, position-measuring, `DIAG-1`); and the primary / mono beam-defining slits bound to `Slit` (`OPT-2`). This page is generated from the descriptor.
- [Sample](sample.md): the IXS scattering-geometry sample stage bound to `LinearStage` (`SAMPLE-1`), the sample-defining slits bound to `Slit` (`OPT-2`), and the sample-temperature cryostats (the 10 K displex LakeShore 340, the Oxford 700, the nanodac gas blower) bound to `TemperatureController` (`TEMP-1`).
- [Detector](detector.md): the multi-analyzer spectrometer arm bound to the catalog `SpectrometerArm` (graduated, `RIXS-1`, `IXS-1`), and the Basler / PCO counting detectors plus the per-analyzer `deta1..deta9` counters bound to `Camera` (`DET-1`).

## Shared

- [Controls](controls.md): the ESRF BLISS / Beacon control stack over Tango + IcePAP, the same house-style as ID32, and the BLISS-plan orchestration CORA's edge conducts over. The device handles are bound from the public Beacon config and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum for the optics and the spectrometer flight path, and the cryogen the displex cryostat draws on); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the catalog `SpectrometerArm` bound at its further sighting.
