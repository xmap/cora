# The beamline

*The part of P64 CORA models today, as areas you can jump to: the optics hutch and the experiment endstation, plus the controls. First cut.*

P64 is PETRA III's advanced X-ray absorption spectroscopy beamline, the ninth PETRA III beamline CORA models, scaffolded with its applied-XAS sibling [P65](../../p65/index.md) as the PETRA III XAS pair. An undulator feeds the Tsai-geometry DCM (its energy axis coupled to the undulator) and a mirror pair, then the beam reaches the experiment endstation with its multi-element fluorescence detector. This cut models the operational core. The model is reverse-engineered from P64's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and energy-scans the beam, the [Sample](sample.md) station that holds the sample, and the [Detector](detector.md) suite that records the absorption. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline (`ENC-1`): the optics hutch (`p64-oh`) and the experiment endstation (`p64-eh`).

## Stations

- [Source](../beamline.md): the P64 undulator (`SRC-1`); the Tsai DCM bound to `Monochromator` (`OPT-1`), the two mirrors bound to `Mirror`, the slits bound to `Slit`. This page is generated from the descriptor.
- [Sample](sample.md): the sample / instrument bank and the DAC sub-stage bound to `LinearStage` (`GROUP-1`), and the NewFocus picomotor fine stages bound to `LinearStage`.
- [Detector](detector.md): the two Lambda 750k detectors bound to `Camera`, and the multi-element fluorescence detector bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
