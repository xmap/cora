# The beamline

*The part of P65 CORA models today, as areas you can jump to: the optics and the experiment endstation, plus the controls. First cut.*

P65 is PETRA III's applied X-ray absorption spectroscopy beamline, the tenth PETRA III beamline CORA models, the applied-XAS sibling of [P64](../../p64/index.md) (sharing the optics host). An undulator feeds a channel-cut DCM energy axis, then the beam reaches the experiment endstation. This cut models the operational core. The model is reverse-engineered from P65's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and energy-scans the beam, the [Sample](sample.md) station that holds the sample, and the [Detector](detector.md) (carried pending). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline (`ENC-1`): the optics (`p65-oh`, shared with P64 on the `hasnp64` host) and the experiment endstation (`p65-eh`).

## Stations

- [Source](../beamline.md): the P65 undulator (`SRC-1`); the CDCM energy axis bound to `Monochromator` (reports on the shared P64 host, `HOST-1`, `OPT-1`), and the optics / front-end banks bound to `LinearStage` (`GROUP-1`). This page is generated from the descriptor.
- [Sample](sample.md): the experiment sample bank bound to `LinearStage` (`GROUP-1`), the experiment slit bound to `Slit`, and the table bound to `Table`.
- [Detector](detector.md): the XAS detection (ion chambers / fluorescence), carried as a pending `FluxMonitor` placeholder since it is not in the registry slice (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
