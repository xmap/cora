# The beamline

*The part of SST CORA models today, as areas you can jump to: the shared optics and the two monochromators, the soft (RSoXS) and tender (HAXPES) sample endstations, and their detectors, plus the controls. First cut.*

SST is the NSLS-II soft + tender spectroscopy beamline at sector 7-ID, with two branches off a shared front end. Its PV zones run `XF:07IDA` (shared front-end optics), `XF:07ID1` / `XF:07ID2` (the SST-1 soft branch + RSoXS endstation), and `XF:07ID6` / `XF:07ID-ES` (the SST-2 tender branch + HAXPES endstation). This cut models the operational core across both branches; the UCAL TES microcalorimeter and the VPPEM microscope are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, the **stations**: the [Source](../beamline.md) that delivers and energy-selects the soft and tender beams, the [Sample](sample.md) manipulators that place the specimen, and the [Detector](detector.md) that records the scattering (soft) or the photoelectrons (tender). Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the two EPUs, the shared front-end mirror and slit, the SST-1 soft plane-grating monochromator, and the SST-2 tender Si double-crystal monochromator with its mirrors.
- [Sample](sample.md): the RSoXS UHV manipulator (SST-1) and the HAXPES UHV manipulator and slit (SST-2).
- [Detector](detector.md): the RSoXS Greateyes WAXS detector and I0 monitors (SST-1), and the HAXPES Scienta SES electron analyzer and ion chamber (SST-2).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, its config-driven instrument map (devices.toml + the sst-base library), and the bluesky-orchestration seam CORA's edge replaces. Handles carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum / UHV at both endstations); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations). SST graduates `ElectronAnalyzer` and reuses the rest.
