# The beamline

*The part of 8-ID CORA models today, as areas you can jump to: the optics and focusing spine, the diffractometer endstation, and the XPCS endstation, plus the controls. First cut.*

8-ID is the XPCS beamline, with four stations: `8-ID-A` (optics), `8-ID-D` (focusing transfocators), `8-ID-E` (the six-circle diffractometer endstation), and `8-ID-I` (the XPCS sample and coherent-detector endstation). This cut models the operational core across all four; the robotic sample changer and the full softGlue timing graph are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and focuses the beam, the [Sample](sample.md) stage that places the specimen in it, and the [Detector](detector.md) that records what scatters. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the `8-ID-A` optics (two undulators, the MN1 monochromator, the FMBO mirrors, the white-beam and mono slits) and the `8-ID-D` focusing (the two CRL transfocators).
- [Sample](sample.md): the `8-ID-E` six-circle Huber diffractometer with its temperature controllers and beam-position monitor, and the `8-ID-I` XPCS sample endstation (the Aerotech sample and rheometer stages, the temperature-controlled holders).
- [Detector](detector.md): the coherent area detectors (Eiger, Lambda, Rigaku), their stage, the evacuated flight path and beam stop, and the beam-position monitors.

## Shared

- [Controls](controls.md): the APS EPICS control stack and the softGlue timing fabric. The device handles are bound from the beamline's instrument config and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the flight path and sample environments); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including which loose families are held for gate-review.
