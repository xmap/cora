# The beamline

*The part of P61 CORA models today, as areas you can jump to: the experiment hutch, plus the controls. First cut.*

P61 is PETRA III's high-energy white-beam wiggler beamline, the seventeenth PETRA III beamline CORA models. The registry slice exposes one experiment hutch with a large generic motor bank; the source (damping wiggler), the Large Volume Press, and the detectors are not exposed. This cut models the operational core. The model is reverse-engineered from P61's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) / [Sample](sample.md) experiment stage (the grouped bank) and the [Detector](detector.md) (carried pending). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

One enclosure carries the modelled devices (`ENC-1`): the experiment hutch (`p61-eh2`), inferred from the OnlineXML `hasnp61eh2` host.

## Stations

- [Source](../beamline.md) / [Sample](sample.md): the experiment / instrument motor bank bound to `LinearStage` (the sample positioning and diffractometer motions, grouped, `GROUP-1`); the Large Volume Press (P61A) carried pending (`PRESS-1`). This page is generated from the descriptor.
- [Detector](detector.md): the energy-dispersive detector, carried as a pending `EnergyDispersiveSpectrometer` placeholder since it is not in the registry slice (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
