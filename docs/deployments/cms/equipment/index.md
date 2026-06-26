# The beamline

*The part of CMS CORA models today, as areas you can jump to: the source and monochromator spine, the scattering and reflectivity sample, and the detectors, plus the controls. First cut.*

CMS (Complex Materials Scattering) is the NSLS-II soft-matter and thin-film scattering beamline at sector 11-BM, and the direct NSLS-II twin of SMI (12-ID). It resolves structure by small-, wide-, and medium-angle scattering (SAXS / WAXS / MAXS), grazing-incidence scattering (GISAXS / GIWAXS), and specular X-ray reflectivity (XR). Its PV zones run `XF:11BMA`, the first optics enclosure (`cms-optics`) that carries the monochromator, the mirrors, the FOE slit and the FOE flux monitor, and `XF:11BMB`, the endstation (`cms-endstation`) where the conditioned beam meets a film, interface, or solution sample and the pattern is recorded on the area detectors (`ENC-1`). The newer mirror sits on its own zone, `XF:11BM1`. 11-BM is a bending-magnet source, the 2-BM / 7-BM pattern, so there is no undulator or insertion device on the spine (`SRC-1`).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the incident beam, the [Sample](sample.md) that places the specimen at a chosen position and angle, and the [Detector](detector.md) that records the scattered and reflected signal. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the bending-magnet machine state read through a loose `StorageRing` (`SRC-1`, `MACHINE-1`), the double-multilayer monochromator (the DMM, a multilayer Bragg optic, calibrated near 13.5 keV, `MONO-1`), the toroidal and elliptical mirrors (`OPT-1`), the FOE slit (`OPT-2`) and the eight pneumatic attenuator foils (`ATTN-1`), and the FOE flux monitor (`DET-1`). The incident energy is a pseudo-axis over the DMM Bragg angle (`MONO-1`).
- [Sample](sample.md): the sample goniometer, whose `sth` axis is both the grazing-incidence and the specular-reflectivity angle (`SAMPLE-1`); the surface-leveling tilt stage for thin films (`SAMPLE-1`); the GIBar sample-exchange arm, a multi-axis sample-bar loader modelled by its stage axes (`ROBOT-1`); and the Linkam thermal / tensile stage (`TEMP-1`).
- [Detector](detector.md): the SAXS, WAXS, and MAXS Pilatus area detectors (`DET-1`), the SAXS beamstop (`DET-1`), and the endstation flux and beam-position monitors (`DET-1`, `DIAG-1`). Specular reflectivity (XR) is read on the fixed SAXS detector over a sliding region as the sample angle is stepped, not on a separate detector arm (`XR-1`).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, the same floor as FXI, HXN, SRX, BMM, SIX, CHX, ESM, and SMI, and the bluesky-plan orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, and vacuum for the optics and the endstation flight path); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the one loose family held at n=1.
