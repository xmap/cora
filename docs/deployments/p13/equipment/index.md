# The beamline

*The part of P13 CORA models today, as areas you can jump to: the optics hutch and the experiment hutch, plus the controls. First cut.*

P13 is EMBL Hamburg's macromolecular-crystallography beamline on the PETRA III ring, the first EMBL Hamburg beamline CORA models and the first non-DESY operator on the [PETRA III Site](../../petra-iii/index.md). An undulator feeds the optics hutch (the KB focusing mirrors), then the beam reaches the experiment hutch where the EMBLMiniDiff microdiffractometer holds a crystal (cryo-cooled) and rotates it while an Eiger or Pilatus area detector reads frames. This cut models the operational core across the optics and the experiment hutch. The model is reverse-engineered from EMBL Hamburg's public MXCuBE HardwareObjects configuration; the Exporter / TINE control handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that conditions and focuses the beam, the [Sample](sample.md) station that holds and orients the crystal, and the [Detector](detector.md) that records the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, inferred from the device prefixes and the EMBL MX layout: an optics hutch (`p13-oh`) and an experiment hutch (`p13-eh`) (`ENC-1`).

## Stations

- [Source](../beamline.md): the KB focusing-mirror motions bound to `LinearStage` (the monochromator / mirror Assets grouped, `OPT-1`), the photon-energy axis bound to `PseudoAxis`, and the beam diagnostics bound to `FluxMonitor`. This page is generated from the descriptor.
- [Sample](sample.md): the EMBLMiniDiff diffractometer bound to the graduated `Goniometer` (`MX-1`), its centring stage bound to `LinearStage`, and the aperture / beamstop / objective / illumination bound to `Aperture` / `BeamStop` / `Objective` / `Backlight`.
- [Detector](detector.md): the Eiger 16M and Pilatus 6M area detectors bound to `Camera`, the flux monitor, the cameras, and the XRF detector bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): EMBL Hamburg's MXCuBE experiment-orchestration layer over the Exporter protocol (the microdiff host) and TINE channels, and the orchestration seam CORA's edge conducts over or drives through. The device handles are read from the public MXCuBE config and carried confirm (`CTRL-1`, `SEAM-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and the cryostream liquid nitrogen); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
