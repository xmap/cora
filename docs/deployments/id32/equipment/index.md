# The beamline

*The part of ID32 CORA models today, as areas you can jump to: the shared soft X-ray source and optics, the RIXS spectrometer endstation, and the XMCD high-field-magnet endstation, plus the controls. First cut.*

ID32 is the ESRF soft X-ray beamline for resonant inelastic X-ray scattering (RIXS) and X-ray magnetic dichroism (XMCD), CORA's first ESRF deployment. Twin APPLE-II undulators feed a soft X-ray plane-grating monochromator that serves two experiment endstations: the RIXS spectrometer endstation and the 9 Tesla XMCD high-field-magnet endstation. This cut models the operational core across them. The model is reverse-engineered from the ESRF's public BLISS Beacon device database; the Tango / IcePAP / BLISS handles are real, read from the config, and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, polarizes, and energy-selects the incident beam, the [Sample](sample.md) that orients the specimen (the RIXS diffractometer) or holds it in the magnet (the XMCD endstation), and the [Detector](detector.md) that disperses and records the scattered and emitted beam. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline, grouping pending (`ENC-1`): a shared `id32-optics` zone, the `id32-rixs` RIXS endstation, and the `id32-xmcd` magnet endstation.

## Stations

- [Source](../beamline.md): the ESRF-EBS storage-ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the twin APPLE-II undulators bound to `InsertionDevice` (`SRC-1`); the polarization and incident-energy pseudo-axes over them (`POL-1`, `MONO-1`); the soft X-ray plane-grating monochromator bound to `GratingMonochromator` (`MONO-1`); the focusing mirrors (`OPT-1`) and beam slits (`OPT-2`). This page is generated from the descriptor.
- [Sample](sample.md): the RIXS 4-circle diffractometer bound to `Goniometer` with a reciprocal-space `PseudoAxis` (`DIFF-1`, `DIFF-2`); the 9 T XMCD magnet bound to the loose `Magnet` (`MAG-1`); the LakeShore VTI and coil-diagnostic temperature controllers (`TEMP-1`); and the XMCD sample stage (`SAMPLE-1`).
- [Detector](detector.md): the RIXS and XES dispersive spectrometer arms bound to the loose `SpectrometerArm` (`RIXS-1`); the scattered-beam polarimeter bound to the loose `PolarizationAnalyzer` (`POL-2`); and the two Andor CCDs bound to `Camera` (`DET-1`).

## Shared

- [Controls](controls.md): the ESRF BLISS / Beacon control stack over Tango + IcePAP, the fleet's first non-EPICS, non-Sardana house-style, and the BLISS-plan orchestration CORA's edge conducts over. The device handles are bound from the public Beacon config and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, ultra-high vacuum for the soft X-ray path, and the liquid helium the 9 T magnet draws on); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the three loose families held at the rule-of-three.
