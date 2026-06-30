# The beamline

*The part of P21 CORA models today, as areas you can jump to: the P21.2 optics, the EH3 endstation, and the LAB station, plus the controls. First cut.*

P21 is PETRA III's Swedish Materials Science beamline, the thirteenth PETRA III beamline CORA models. It is a high-energy materials beamline with two branches (P21.1 powder / total scattering, P21.2 diffraction / imaging); this registry slice exposes the P21.2 optics, an EH3 endstation, and a LAB station. This cut models the operational core. The model is reverse-engineered from P21's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) optics, the [Sample](sample.md) stations (EH3, LAB), and the [Detector](detector.md) (carried pending). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`), inferred from the OnlineXML host names: the P21.2 optics (`p21-oh`), the EH3 endstation (`p21-eh3`), and the LAB station (`p21-lab`). The P21.1 station (`hasep211eh`) exposed only bookkeeping devices and is noted, not modelled (`HOST-1`).

## Stations

- [Source](../beamline.md): the P21.2 optics motor bank bound to `LinearStage` (the monochromator / mirror / slit motions, grouped, `OPT-1`). This page is generated from the descriptor.
- [Sample](sample.md): the EH3 sample bank bound to `LinearStage` (`GROUP-1`); the LAB sample bank bound to `LinearStage` and the LAB slits bound to `Slit`.
- [Detector](detector.md): the high-energy diffraction detectors, carried as a pending `Camera` placeholder since they are not in the registry slice (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
