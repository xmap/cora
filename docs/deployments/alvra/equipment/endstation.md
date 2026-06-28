# Endstation

*The Alvra Prime endstation: the sample manipulator, the optical table, the sample-view microscope, the pump-probe laser, and the von Hamos emission spectrometer. Design-phase, with the `eco`-derived handles recorded.*

The Alvra experiment hutch is where the focused beam meets the sample and the pump-probe experiment happens. As at [LCLS-MFX](../../lcls-mfx/equipment/optics.md), every endstation device folds into an existing Family; the one post-sample analyzer instrument (the von Hamos spectrometer) reuses the `EmissionSpectrometer` family LCLS-MFX introduced and ISS graduated, here on its fourth sighting.

## Positioning the sample

- **Sample manipulator** (`SARES11-XSAM125`): a Huber sample XYZ stage (the `eco` driver derives x / y / z motors). It folds into `LinearStage`. The fixed-target or liquid-jet sample delivery mounted on it is endstation-specific, with no storage-ring analog; it is carried with its shape and the `Subject` custody lifecycle deferred, and no Family is coined (SAMPLE-1), mirroring how LCLS-MFX carries its liquid jet.
- **Optical table** (`SARES11-XOTA125`): the Prime optical table (the `eco` driver derives six physical motors and virtual x / y / z / pitch / yaw axes). It reuses the `Table` Family, the same one the 2-BM hutch tables bind.
- **Sample microscope** (`SARES11-XMI125`): an on-axis sample-view microscope (focus and zoom, with appended SmarAct goniometer / rotation axes). It presents the Detector Role for sample viewing and alignment and binds `Camera`, the same way the i13-1 side camera does.

## The pump-probe laser

The femtosecond optical laser (`SLAAR11-LMOT`: waveplate, pump-delay, and compressor motors) excites the sample before the X-ray probe. The laser device folds into the loose `Laser` family (the LCLS-MFX / 4-ID precedent, model-vs-hazard open), and its delay stages are `LinearStage`s. What does not fold is the synchronization: the `eco` `lxt` timing chain holds the optical-laser and FEL timing domains together at the femtosecond level, a cross-timing-domain relationship CORA's single-domain `PartitionRule` cannot express (LASER-1). The PALM and PSEN arrival-time monitors in the [optics hutch](../beamline.md) correct the residual jitter shot by shot. The laser is also a class-4 hazard gated by a Clearance (see [Governance](../governance.md)). The laser shutter (`SLAAR11-LTIM01-EVR0`) is driven through a SwissFEL event receiver, which is the beam-synchronous timing system (TIMING-1).

## The emission spectrometer

**Von Hamos emission spectrometer** (`SARES11-XCRY125`): a crystal-analyzer X-ray emission spectrometer for XES and HERFD. It composes its analyzer-crystal translation stage (the `eco` `vonHamosBragg` driver, two crystal axes) with the Jungfrau detector along a wavelength-dispersive geometry, structurally distinct from a `Monochromator` (a beam-conditioning Bragg optic upstream of the sample). It binds the `EmissionSpectrometer` family, which **graduated into the catalog** once NSLS-II ISS earned the second sighting (after LCLS-MFX introduced it; MAX IV Balder is a near-sighting). Alvra is its fourth sighting, reinforcing the graduation. Whether each analyzer crystal is a child Asset or a setting on the one spectrometer Asset is the residual question (SPEC-1).

See the [Detector](detector.md) page for how the recorded shots leave the hutch, and [Open questions](../questions.md) for the endstation items still to confirm.
