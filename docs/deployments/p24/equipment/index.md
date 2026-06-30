# The beamline

*The part of P24 CORA models today, as areas you can jump to: the optics hutch and the two experiment hutches, plus the controls. First cut.*

P24 is PETRA III's chemical crystallography beamline, the sixteenth PETRA III beamline CORA models. An undulator feeds the optics (the conditioning bank + slits), then the beam reaches two experiment hutches: EH2 (the main diffractometer hutch) and EH1. This cut models the operational core. The model is reverse-engineered from P24's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) optics, the [Sample](sample.md) stations (the EH2 diffractometer, the EH1 bank), and the [Detector](detector.md) (the MCA + the pending area detector). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the optics hutch (`p24-oh`) and two experiment hutches (`p24-eh2` main, `p24-eh1`).

## Stations

- [Source](../beamline.md): the optics motor bank bound to `LinearStage` (the monochromator / mirror motions, grouped, `OPT-1`) and the ps1 / ps2 slits bound to `Slit`. This page is generated from the descriptor.
- [Sample](sample.md): the EH2 diffractometer / sample bank bound to `LinearStage` (`GROUP-1`, `DIFF-1`) and the coupled axes bound to `PseudoAxis`; the EH1 sample bank bound to `LinearStage`.
- [Detector](detector.md): the MCA fluorescence detectors bound to `EnergyDispersiveSpectrometer`, and the area detector bound to `Camera` (carried pending, `DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
