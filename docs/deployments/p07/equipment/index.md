# The beamline

*The part of P07 CORA models today, as areas you can jump to: the optics hutch and the two experiment hutches, plus the controls. First cut.*

P07 is PETRA III's high-energy materials-science beamline (HEMS), the eleventh PETRA III beamline CORA models, jointly operated by Helmholtz-Zentrum Hereon and DESY. An undulator feeds a multi-bounce DCM for high-energy operation, then the beam reaches the EH2 main hutch (four-circle diffractometer, hexapod, 17 T magnet, Linkam) and the EH2B secondary hutch. This cut models the operational core. The model is reverse-engineered from P07's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and monochromates the high-energy beam, the [Sample](sample.md) stations that orient the sample, and the [Detector](detector.md) suite that records the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the optics hutch (`p07-oh2`) and two experiment hutches (`p07-eh2` main, `p07-eh2b` secondary). Only the EH2 registry slice is public; the other P07 hutches (EH1 / EH3 / EH4) are noted but not in this slice (`HOST-1`).

## Stations

- [Source](../beamline.md): the P07 undulator (`SRC-1`); the multi-bounce DCM bound to `Monochromator` (`OPT-1`), the OH z-stage bound to `LinearStage`, the slits bound to `Slit`. This page is generated from the descriptor.
- [Sample](sample.md): the EH2 four-circle diffractometer bound to `Goniometer` (`DIFF-1`), the hexapod bound to `Hexapod`, the 17 T magnet bound to the graduated catalog `Magnet` (`MAG-1`), the Linkam bound to `TemperatureController`; the EH2B sample bank bound to `LinearStage` (`GROUP-1`).
- [Detector](detector.md): the Pilatus and PerkinElmer area detectors bound to `Camera`, and the MCA fluorescence detectors bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and the magnet liquid helium); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
