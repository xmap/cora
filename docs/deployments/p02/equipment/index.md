# The beamline

*The part of P02 CORA models today, as areas you can jump to: the shared OH1 optics and the two diffraction endstations, plus the controls. First cut.*

P02 is PETRA III's hard X-ray diffraction beamline, the eighth PETRA III beamline CORA models. An undulator feeds the OH1 optics (DCM, bendable HFM / VFM mirrors, slits, CRL), shared with P03, then the high-energy beam reaches two endstations: P02.1 (powder diffraction / total scattering / PDF) and P02.2 (extreme conditions, diamond-anvil cell). This cut models the operational core across the optics and the two endstations. The model is reverse-engineered from P02's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, monochromates, and focuses the high-energy beam, the [Sample](sample.md) stations that hold and position the sample at each branch, and the [Detector](detector.md) suite that records the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the shared OH1 optics (`p02-oh1`, shared with P03) and two endstations (`p02-1-powder`, `p02-2-extreme`). The optics and both endstations report on the `haspp02oh1` host; the split is inferred from the device-name prefixes.

## Stations

- [Source](../beamline.md): the P02 undulator (`SRC-1`); the DCM bound to `Monochromator` (`OPT-1`), the bendable HFM / VFM mirrors bound to `Mirror`, the slits bound to `Slit`. This page is generated from the descriptor.
- [Sample](sample.md): the P02.1 sample stage bound to `LinearStage` (`GROUP-1`) and its sample environment bound to `TemperatureController`; the P02.2 sample stage bound to `LinearStage`, the diamond-anvil cell bound to the catalog `PressureCell` (`PRESSURE-1`), and the beam monitor bound to `FluxMonitor`.
- [Detector](detector.md): the P02.1 Pilatus 1M and PerkinElmer bound to `Camera`, and the P02.2 MCA / SIS3302 fluorescence detectors bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
