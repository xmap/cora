# The beamline

*The part of P06 CORA models today, as areas you can jump to: the optics / mono hutch and the two scanning-probe endstations, plus the controls. First cut.*

P06 is PETRA III's hard X-ray micro- and nano-probe beamline, the third PETRA III beamline CORA models (after [P01](../../p01/index.md) and [P04](../../p04/index.md)). An undulator feeds a double-crystal and a multilayer monochromator (selectable), then the beam reaches two scanning-probe endstations: a micro-probe (MC01) and a nano-probe (NC1), each focusing the beam with KB optics and rastering the sample while the Maia XRF array and the area detectors read. This cut models the operational core across the optics and the two endstations. The model is reverse-engineered from P06's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, monochromates, and conditions the beam, the [Sample](sample.md) stations that focus and raster the sample at each endstation, and the [Detector](detector.md) pool that records the fluorescence and scattering. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the optics / monochromator hutch (`p06-mono`) and two scanning-probe endstations (`p06-mc01` micro-probe, `p06-nc1` nano-probe). The shared detectors report on a bare `p06` / `petra3` host and are homed in the endstation that operates them (`HOST-1`).

## Stations

- [Source](../beamline.md): the P06 undulator (`SRC-1`); the double-crystal monochromator and the multilayer monochromator bound to `Monochromator` (`OPT-1`), the optics-hutch and secondary slits bound to `Slit`, and the quad BPM bound to `FluxMonitor`. This page is generated from the descriptor.
- [Sample](sample.md): MC01's six-axis hexapod bound to `Hexapod`, its sample / scan / pin stages bound to `LinearStage` (`GROUP-1`); NC1's two KB-lens hexapods bound to `Hexapod`, its lens fine stages bound to `PseudoAxis`, its sample piezos and nano stages bound to `LinearStage`, and its sample rotation bound to `RotaryStage`.
- [Detector](detector.md): the Maia XRF array and the XIA fluorescence detectors bound to `EnergyDispersiveSpectrometer`, and the Eiger / Lambda / Pilatus / PCO / view cameras bound to `Camera` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
