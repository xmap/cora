# The beamline

*The part of P03 CORA models today, as areas you can jump to: the shared optics and the two scattering endstations, plus the controls. First cut.*

P03 is PETRA III's micro- and nanofocus SAXS / WAXS beamline, the fifth PETRA III beamline CORA models (after [P01](../../p01/index.md), [P04](../../p04/index.md), [P06](../../p06/index.md), [P11](../../p11/index.md)). An undulator feeds a multilayer monochromator and two mirrors (9-23 keV, the optics shared with P02), then the beam reaches two endstations: a microfocus endstation and the nanofocus GINIX endstation. This cut models the operational core across the optics and the two endstations. The model is reverse-engineered from P03's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, monochromates, and focuses the beam, the [Sample](sample.md) stations that hold and position the sample at each endstation, and the [Detector](detector.md) pool that records the scattering. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the shared optics (`p03-optics`, shared with P02) and two endstations (`p03-microfocus`, `p03-nanofocus`). The first defining slit reports on the P02 optics host (`HOST-1`).

## Stations

- [Source](../beamline.md): the P03 undulator (`SRC-1`); the multilayer monochromator bound to `Monochromator` (`OPT-1`), the two mirrors bound to `Mirror`, the defining slits bound to `Slit`, and the quad BPMs bound to `FluxMonitor`. This page is generated from the descriptor.
- [Sample](sample.md): the microfocus CRL hexapod bound to `Hexapod`, the guard / scatter slits bound to `Slit`, the sample bank bound to `LinearStage` (`GROUP-1`), the Eurotherm bound to `TemperatureController`; the nanofocus GINIX waveguide SmarPod and sample hexapod bound to `Hexapod`, the sample rotation bound to `RotaryStage`, the waveguide stages bound to `LinearStage`.
- [Detector](detector.md): the Pilatus 300k / 1M area detectors bound to `Camera` and the MCA / XIA fluorescence detectors bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
