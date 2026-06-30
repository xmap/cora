# The beamline

*The part of P22 CORA models today, as areas you can jump to: the shared P09 optics and the HAXPS endstation, plus the controls. First cut.*

P22 is PETRA III's hard X-ray photoelectron spectroscopy beamline (HAXPES), the fourteenth PETRA III beamline CORA models. It shares its optics chain with P09: the undulator, DCM, mirrors, and phase retarder are P09 devices, and P22 adds the HAXPS experiment endstation with its electron analyzer. This cut models the operational core. The model is reverse-engineered from P22's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) (the shared P09 optics), the [Sample](sample.md) station (the HAXPS manipulator), and the [Detector](detector.md) (the electron analyzer, carried pending). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline (`ENC-1`): the shared P09 / P22 optics (`p22-optics`) and the HAXPS endstation (`p22-haxps`). The optics report on the P09 host, shared with P09 (`HOST-1`, `SHARED-1`).

## Stations

- [Source](../beamline.md): the shared P09 undulator (`SRC-1`); the DCM bound to `Monochromator` (`OPT-1`), the two mirrors bound to `Mirror`, the phase retarder bound to the loose `PhaseRetarder` (`POL-1`), the absorber bound to `Filter`, all on the P09 host (`SHARED-1`). This page is generated from the descriptor.
- [Sample](sample.md): the HAXPS sample / instrument bank bound to `Manipulator` (`GROUP-1`).
- [Detector](detector.md): the HAXPES electron analyzer bound to the catalog `ElectronAnalyzer` Family, carried pending since not exposed in the registry slice (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
