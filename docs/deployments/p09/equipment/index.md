# The beamline

*The part of P09 CORA models today, as areas you can jump to: the resonant-scattering hutch, the diffraction hutch, and the magnetism endstation, plus the controls. First cut.*

P09 is PETRA III's resonant-scattering, diffraction, and magnetism beamline, the seventh PETRA III beamline CORA models. An undulator feeds the MONO hutch (DCM, mirrors, CRL), which carries both the conditioning optics and the resonant-scattering experiment; the beam also serves the DIF diffraction hutch and the MAG high-field magnetism endstation (a 14 T magnet). This cut models the operational core across the three areas. The model is reverse-engineered from P09's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stations that orient the sample at each area, and the [Detector](detector.md) suite that records the scattering. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Three enclosures carry the beamline (`ENC-1`): the resonant-scattering optics-and-experiment hutch (`p09-mono`), the diffraction hutch (`p09-dif`), and the magnetism endstation (`p09-mag`).

## Stations

- [Source](../beamline.md): the P09 undulator (`SRC-1`); the DCM bound to `Monochromator` (`OPT-1`), the two mirrors bound to `Mirror`, the CRL bound to `Transfocator`, the defining slit bound to `Slit`, the absorber bound to `Filter`. This page is generated from the descriptor.
- [Sample](sample.md): the MONO phase retarder bound to `PhaseRetarder`, the analyzer bound to `PolarizationAnalyzer`, the goniometer bound to `Goniometer`; the DIF goniometer; the MAG magnet bound to `Magnet`, the goniometer, the hexapod bound to `Hexapod`, the piezos bound to `LinearStage`, the temperature controllers bound to `TemperatureController`.
- [Detector](detector.md): the PerkinElmer / Pilatus / Andor area detectors bound to `Camera`, and the SIS3302 / MCA fluorescence detectors bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and the magnet liquid helium); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
