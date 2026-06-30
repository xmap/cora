# The beamline

*The part of P11 CORA models today, as areas you can jump to: the optics hutch and the experiment hutch, plus the controls. First cut.*

P11 is PETRA III's bio-imaging and macromolecular-crystallography beamline, the fourth PETRA III beamline CORA models (after [P01](../../p01/index.md), [P04](../../p04/index.md), [P06](../../p06/index.md)). An undulator feeds the optics hutch, then the beam reaches the experiment hutch where a goniometer holds a crystal (cryostream-cooled) and rotates it while the Pilatus area detector reads frames. This cut models the operational core across the optics and the experiment hutch. The model is reverse-engineered from P11's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that conditions the beam, the [Sample](sample.md) station that holds and orients the crystal, and the [Detector](detector.md) that records the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, inferred from the device-name prefixes since the registry exposes one Tango host (`haspp11oh`) for the whole beamline (`ENC-1`): an optics hutch (`p11-oh`) and an experiment hutch (`p11-eh`).

## Stations

- [Source](../beamline.md): the optics-hutch motor bank and the granite stage bound to `LinearStage` (the monochromator / mirror / slit motions, grouped, `OPT-1`). This page is generated from the descriptor.
- [Sample](sample.md): the experiment-hutch positioning stages (eh1 / eh2 / eh3 / piezo banks) bound to `LinearStage` (`MX-1`, `GROUP-1`), the servo stage, and the Oxford Cryostream bound to the graduated `TemperatureController` (`TEMP-1`).
- [Detector](detector.md): the Pilatus area detector bound to `Camera` and the XIA fluorescence detector bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and the cryostream liquid nitrogen); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
