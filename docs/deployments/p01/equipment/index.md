# The beamline

*The part of P01 CORA models today, as areas you can jump to: the two optics hutches and the three experiment hutches, plus the controls. First cut.*

P01 is PETRA III's nuclear-resonant-scattering and inelastic / resonant-inelastic-scattering beamline, the first PETRA III beamline CORA models. An undulator feeds a double-crystal monochromator and two deflection mirrors in the optics hutches (2.5-80 keV), then the beam branches to three experiment hutches: EH1 (nuclear resonant scattering, the high-resolution monochromator stack), EH2 (diffraction), and EH3 (RIXS, a KB-focused spectrometer). This cut models the operational core across the optics and the three endstations. The model is reverse-engineered from P01's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and conditions the incident beam, the [Sample](sample.md) stations that monochromate / focus and hold the sample at each endstation, and the [Detector](detector.md) stages that position the detectors. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Five enclosures carry the beamline (`ENC-1`): two optics hutches (`p01-oh1`, `p01-oh2`) and three experiment hutches (`p01-eh1` nuclear resonant scattering, `p01-eh2` diffraction, `p01-eh3` RIXS).

## Stations

- [Source](../beamline.md): the P01 undulator (gap / taper virtual axes, `SRC-1`); the OH1 double-crystal monochromator bound to `Monochromator` (`MONO-1`), the two deflection mirrors bound to `Mirror` (`OPT-1`), the front-end slits bound to `Slit`; the OH2 secondary slit, the diamond monitor bound to `FluxMonitor`, and the RIXS pre-optic bound to `LinearStage` (`OPT-1`). This page is generated from the descriptor.
- [Sample](sample.md): EH1's four high-resolution monochromators bound to `Monochromator` (`NRS-1`), the CRL bound to `Transfocator`, the beam-defining slit, the BPM / ion chamber bound to `FluxMonitor`, the table bound to `Table`; EH2's goniometer bound to `Goniometer` (`DIFF-1`) and sample stage bound to `LinearStage`; EH3's KB mirror pair bound to `Mirror` (`OPT-1`) and sample stage.
- [Detector](detector.md): the EH2 and EH3 detector positioning stages bound to `LinearStage`; the detector devices themselves carried pending (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
