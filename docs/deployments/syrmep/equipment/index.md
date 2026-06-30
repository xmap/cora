# The beamline

*The part of SYRMEP CORA models today, as areas you can jump to: the source and white-beam optics, the sample stage, and the detector, plus the controls. First cut.*

SYRMEP is Elettra's hard X-ray radiology and microtomography beamline, CORA's first Elettra deployment. A bending-magnet beam is energy-selected by a double-crystal Si(111) monochromator (or passed as white / pink beam), shaped into a wide laminar beam, and delivered to a heavy-payload rotation stage with an sCMOS / CCD detector on a long propagation rail. This cut models that operational core. The model is reverse-engineered from public material; the Tango / DonkiOrchestra handles are **not** in public source and are carried confirm-pending (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, energy-selects, shapes, and filters the incident beam, the [Sample](sample.md) that holds and rotates the specimen, and the [Detector](detector.md) that converts and records the transmitted beam. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, grouping pending (`ENC-1`): a `syrmep-optics` white-beam zone and the `syrmep-experiment` imaging endstation.

## Stations

- [Source](../beamline.md): the Elettra storage-ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the bending-magnet beam recorded as a Supply (`SRC-1`); the double-crystal Si(111) monochromator bound to `Monochromator` with the mono / white beam as a setting (`MONO-1`, `MODE-1`); the incident-energy `PseudoAxis` (`MONO-1`); the laminar-beam slits bound to `Slit` (`OPT-2`); and the filters bound to `Filter` (`FOIL-1`). This page is generated from the descriptor.
- [Sample](sample.md): the heavy-payload rotation stage bound to `RotaryStage` (`STAGE-1`) and the five-axis sample positioner bound to `LinearStage` (`SAMPLE-1`).
- [Detector](detector.md): the sample-to-detector propagation rail bound to `LinearStage` (`DET-2`); the scintillator bound to `Scintillator` (`DET-3`); and the sCMOS, CCD, and photon-counting cameras bound to `Camera` (`DET-1`, `DET-4`).

## Shared

- [Controls](controls.md): the Elettra Tango control floor with the in-house DonkiOrchestra scan engine (Elettra 2.0: the "Executer" device server), the fleet's first Tango + DonkiOrchestra house-style, and the orchestration CORA's edge conducts over. The device handles are not in public source and are carried confirm-pending (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water for the optics, and the vacuum of the white-beam path); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
