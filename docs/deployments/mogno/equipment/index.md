# The beamline

*The part of MOGNO CORA models today, as areas you can jump to: the shared source and optics, the nanotomography station, the microtomography station, and the detector chain, plus the controls. First cut.*

MOGNO is the Sirius cone-beam X-ray micro and nanotomography beamline, CORA's first deployment at a South American facility. A quasi-monochromatic dipole source feeds two tomography endstations: a nanotomography station at the elliptical-mirror nanofocus, and a microtomography station with a large field of view. This cut models the operational core across them. The model is reverse-engineered from two published papers and the public facility page; there is no public controls config, so no device carries a handle and every value is `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and focuses the incident cone beam, the two sample stations ([Nanotomography](nanotomography.md) and [Microtomography](microtomography.md)) that rotate the specimen in the beam, and the [Detector](detector.md) that records the transmitted projections. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, one per experiment station: the `mogno-nano` nanotomography station and the `mogno-micro` microtomography station, with the source and optics shared upstream. PSS permit grouping is pending (`PSS-1`).

## Stations

- [Source](../beamline.md): the Sirius 3 GeV ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the dipole / superbend source bound to `InsertionDevice` (`SRC-1`); the elliptical focusing mirrors bound to `Mirror` (`OPT-1`); and the beam-defining slits (`OPT-2`). This page is generated from the descriptor.
- [Nanotomography](nanotomography.md): the rotation axis bound to `RotaryStage` (the master clock, `STAGE-1`) and the fine three-axis sample positioner bound to `LinearStage` (`STAGE-2`), at the elliptical-mirror nanofocus.
- [Microtomography](microtomography.md): the large-field-of-view rotation axis (`RotaryStage`, `STAGE-3`) and sample positioner (`LinearStage`, `STAGE-3`).
- [Detector](detector.md): the high-Z photon-counting detector and the indirect scintillator + sCMOS chain bound to `Camera` and `Scintillator` (`CAM-1`, `CAM-2`); and the cone-beam magnification bound to `PseudoAxis` (`MAG-1`).

## Shared

- [Controls](controls.md): the EPICS + TATU control floor and the beamline's custom `mgn-*` PyEpics orchestration the edge conducts over. No device handles are public; all carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
