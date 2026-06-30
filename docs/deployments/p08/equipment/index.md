# The beamline

*The part of P08 CORA models today, as areas you can jump to: the optics hutch and the experiment endstation, plus the controls. First cut.*

P08 is PETRA III's high-resolution diffraction beamline, the twelfth PETRA III beamline CORA models. An undulator feeds a DCM and a multilayer monochromator (selectable) and a CRL, then the beam reaches the experiment endstation with its six-circle Kohzu diffractometer and rich detector set. This cut models the operational core. The model is reverse-engineered from P08's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and monochromates the beam, the [Sample](sample.md) station that orients the sample on the diffractometer, and the [Detector](detector.md) suite that records the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline (`ENC-1`): the optics hutch (`p08-oh`) and the experiment endstation (`p08-eh`).

## Stations

- [Source](../beamline.md): the P08 undulator (`SRC-1`); the DCM and multilayer mono bound to `Monochromator` (`OPT-1`), the CRL bound to `Transfocator`, the absorber bound to `Filter`, the slits bound to `Slit`. This page is generated from the descriptor.
- [Sample](sample.md): the six-circle Kohzu diffractometer bound to `Goniometer` (`DIFF-1`, `GROUP-1`) and the hexapod bound to `Hexapod`.
- [Detector](detector.md): the Eiger / Pilatus / Mythen / PerkinElmer / Lambda detectors bound to `Camera`, and the Vortex SDD bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
