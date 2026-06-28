# The beamline

*The part of ID28 CORA models today, as areas you can jump to: the source and high-resolution optics, the IXS spectrometer endstation, plus the controls. First cut.*

ID28 is the ESRF beamline for momentum-resolved inelastic X-ray scattering (IXS), CORA's second ESRF deployment. An undulator feeds a high-resolution backscattering monochromator and focusing mirrors, and the conditioned beam meets the sample at the eh1 spectrometer endstation, where a multi-analyzer crystal arm energy-analyzes the scattered beam. This cut models the operational core across the optics and the endstation. The model is reverse-engineered from the ESRF's public BLISS Beacon device database; the BLISS / Tango / IcePAP handles are real, read from the config, and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the incident beam at meV resolution, the [Sample](sample.md) that places the specimen and conditions its temperature, and the [Detector](detector.md) that energy-analyzes and counts the scattered beam. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, grouping pending (`ENC-1`): a shared `id28-optics` zone (oh2 / oh3) and the `id28-eh1` experiment hutch.

## Stations

- [Source](../beamline.md): the ESRF-EBS storage-ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the undulator bound to `InsertionDevice` (`SRC-1`); the incident-energy pseudo-axis (`MONO-1`); the high-resolution backscattering monochromator bound to `Monochromator` (`MONO-1`); the HFM / VFM focusing mirrors bound to `Mirror` (`OPT-1`); and the oh2 Elettra beam-position monitor bound to the loose `BeamPositionMonitor` (`DIAG-1`). This page is generated from the descriptor.
- [Sample](sample.md): the IXS sample-positioning stage bound to `LinearStage` (`SAMPLE-1`), and the sample-temperature cryostats (the 10 K displex LakeShore 340, the Oxford 700, the nanodac gas blower) bound to `TemperatureController` (`TEMP-1`).
- [Detector](detector.md): the multi-analyzer spectrometer arm bound to the loose `SpectrometerArm` (`RIXS-1`, `IXS-1`), and the Basler / PCO counting detectors bound to `Camera` (`DET-1`).

## Shared

- [Controls](controls.md): the ESRF BLISS / Beacon control stack over Tango + IcePAP, the same house-style as ID32, and the BLISS-plan orchestration CORA's edge conducts over. The device handles are bound from the public Beacon config and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum for the optics and the spectrometer flight path, and the cryogen the displex cryostat draws on); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the loose `SpectrometerArm` held at its further sighting.
