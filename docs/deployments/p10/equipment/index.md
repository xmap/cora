# The beamline

*The part of P10 CORA models today, as areas you can jump to: the optics hutch and the three experiment areas, plus the controls. First cut.*

P10 is PETRA III's coherence-applications beamline, the sixth PETRA III beamline CORA models. An undulator feeds the optics hutch (DCM, optics stages, beam shutter), then the coherent beam reaches three experiment areas: E1 (coherent imaging), E2 (XPCS / diffraction, with the LCX piezo sub-station), and LAB (offline diffractometer + detectors). This cut models the operational core across the optics and the experiment areas. The model is reverse-engineered from P10's public OnlineXML registry; the Tango device handles are read from it and carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and monochromates the coherent beam, the [Sample](sample.md) stations that hold and position the sample at each area, and the [Detector](detector.md) suite that records the speckle / diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Four enclosures carry the beamline (`ENC-1`): the optics hutch (`p10-opt`) and three experiment areas (`p10-e1`, `p10-e2`, `p10-lab`). The LCX piezo sub-station sits within E2. Several detectors report on a bare `p10` host (`HOST-1`).

## Stations

- [Source](../beamline.md): the P10 undulator (`SRC-1`); the DCM bound to `Monochromator` (`OPT-1`), the optics stages bound to `LinearStage` (`GROUP-1`), and the beam shutter bound to `Shutter` (`PSS-1`). This page is generated from the descriptor.
- [Sample](sample.md): E1's hexapod bound to `Hexapod`, the CRL bound to `Transfocator`, the guard slit bound to `Slit`, the sample bank bound to `LinearStage` (`GROUP-1`); E2's mirrors bound to `Mirror`, the SmarAct piezos bound to `LinearStage`, the two-theta arm bound to `RotaryStage`; the LAB simulated diffractometer bound to `Goniometer`; the LCX nano-positioner bound to `LinearStage`.
- [Detector](detector.md): the Quadro / Pilatus / PCO / LCX / Lambda / Lima / Eiger / Andor / Mythen detectors bound to `Camera`, and the MCA fluorescence detectors bound to `EnergyDispersiveSpectrometer` (`DET-1`).

## Shared

- [Controls](controls.md): the PETRA III Tango device floor + Sardana scan layer, and the Sardana macro orchestration CORA's edge conducts over or drives through. The device handles are read from the public OnlineXML registry and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
