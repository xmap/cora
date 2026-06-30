# The beamline

*The part of P14 CORA models today, as areas you can jump to: the optics hutch and the two experiment hutches, plus the controls. First cut.*

P14 is EMBL Hamburg's high-end macromolecular-crystallography beamline on the PETRA III ring, the sibling of [P13](../../p13/index.md) and the second EMBL Hamburg beamline CORA models. An undulator feeds the optics hutch (the KB focusing mirrors, the CRL transfocator, the beam-defining slits), then the conditioned beam reaches two experiment hutches: EH1, where the EMBLMiniDiff holds a crystal (cryo-cooled) and rotates it while an Eiger detector reads frames, and EH2, where the EMBLBSD diffractometer reads a Pilatus 2M. This cut models the operational core across the optics hutch and both experiment hutches. The model is reverse-engineered from EMBL Hamburg's public MXCuBE HardwareObjects configuration; the Exporter / TINE control handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that conditions and focuses the beam, the [Sample](sample.md) stations that hold and orient the crystals, and the [Detector](detector.md) stations that record the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline, inferred from the device prefixes and the EMBL MX layout: one optics hutch (`p14-oh`) feeding two experiment hutches (`p14-eh1`, `p14-eh2`) (`ENC-1`, `EH-1`).

## Stations

- [Source](../beamline.md): the KB focusing-mirror motions bound to `LinearStage`, the focusing optic bound to `Mirror`, the CRL bound to `Transfocator`, the beam-defining slits bound to `Slit`, the photon-energy axis bound to `PseudoAxis`, and the beam diagnostics bound to `FluxMonitor`. Shared by both hutches. This page is generated from the descriptor.
- [Sample](sample.md): the EH1 EMBLMiniDiff and the EH2 EMBLBSD diffractometers bound to the graduated `Goniometer` (`MX-1`), their apertures / beamstops / objectives / illumination, and the EH2 positioning table.
- [Detector](detector.md): the EH1 Eiger variants (16M silicon, 16M / 4M CdTe) and the EH2 Pilatus 2M bound to `Camera`, the X-ray imaging camera, the flux monitor, and the XRF detector bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): EMBL Hamburg's MXCuBE experiment-orchestration layer over the Exporter protocol (the microdiff hosts) and TINE channels, and the orchestration seam CORA's edge conducts over or drives through. The device handles are read from the public MXCuBE configs and carried confirm (`CTRL-1`, `SEAM-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and the cryostream liquid nitrogen); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
