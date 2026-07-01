# The beamline

*The part of P04 CORA models today, as areas you can jump to: the soft X-ray optics and the two experiment endstations, plus the controls. First cut.*

P04 is PETRA III's variable-polarization soft X-ray spectroscopy beamline, the second PETRA III beamline CORA models (after [P01](../../p01/index.md)). An APPLE-II-type undulator feeds a plane-grating monochromator and three mirrors (250-3000 eV), then the beam reaches two experiment endstations (EXP1 and EXP2). This cut models the operational core across the optics and the two endstations. The model is reverse-engineered from P04's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and energy-selects the soft X-ray beam, the [Sample](sample.md) stations that hold and position the sample at each endstation, and the [Detector](detector.md) stages (the electrometers and the diagnostic screens / cameras). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the soft X-ray optics section (`p04-optics`) and two experiment endstations (`p04-exp1`, `p04-exp2`). The optics devices report on the `haspp04exp2` Tango host but are logically the optics section (`HOST-1`).

## Stations

- [Source](../beamline.md): the P04 variable-polarization undulator (`SRC-1`); the plane-grating monochromator bound to `GratingMonochromator` (`OPT-1`), the three mirrors bound to `Mirror`, and the exit slits bound to `Slit`. This page is generated from the descriptor.
- [Sample](sample.md): EXP1's sample manipulator and secondary positioner bound to `Manipulator` (`GROUP-1`) and its viewing camera bound to `Camera`; EXP2's exit-shutter unit bound to `Slit`, its positioner bound to `Manipulator`, and its virtual axes bound to `PseudoAxis`.
- [Detector](detector.md): the drain-current electrometers bound to `FluxMonitor` (`DET-1`), and the EXP2 motorized diagnostic screens bound to the catalog `Screen` with the beam-monitor cameras bound to `Camera` (`DIAG-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
