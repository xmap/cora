# The beamline

*The part of 12-ID-E CORA models today, as areas you can jump to: the source and optics spine, the Bonse-Hart collimator and analyzer crystal stages, the USAXS sample, and the detection chain, plus the controls. First cut.*

12-ID-E is the APS ultra-small-angle X-ray scattering (USAXS) beamline at Sector 12, CORA's first Bonse-Hart USAXS deployment. It also runs pinhole SAXS and WAXS on area detectors. Its PV zones group by soft IOC and controller: `usxLAX:` (the LAX soft IOC, carrying USAXS calculations, scalers, slits, and many motors), `usxAERO:` (the Aerotech motors), `12idPyFilter:` (the attenuator), `usxRIO:` (the Femto amplifier RIO), `usxLINKAM:` and `usxTEMP:` (sample temperature), and `usxPI:` (the sample rotator). This cut models the operational core across them. The model is reverse-engineered from the beamline's bluesky/BITS instrument; EPICS PVs are real, read from the config, and carried `confirm`. Vendor part numbers, serials, and physical positions are not in the config (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the incident beam and carries the Bonse-Hart collimator and analyzer crystal stages, the [Sample](sample.md) that places and conditions the specimen, and the [Detector](detector.md) that counts the transmitted and scattered intensity. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, grouping pending (`ENC-1`): a shared `12-ID-optics` zone, and the `12-ID-E` experiment hutch.

## Stations

- [Source](../beamline.md): the storage ring state, observe-only (`MACHINE-1`); the shared 12-ID double-crystal monochromator, wrapped as a soft device with real PVs pending (`MONO-1`); the Al/Ti attenuator filter bank at `12idPyFilter:` (`ATTN-1`); the guard slit and the USAXS-defining slit, both at `usxLAX:` (`OPT-2`); and the Bonse-Hart crystal stages, the collimator upstream of the sample (rocking rotation `usxAERO:m12`, alignment translations, and a piezo fine-tilt at `usxLAX:pi:c0:m2`) and the analyzer downstream (rocking rotation `usxAERO:m6`, alignment, and a piezo at `usxLAX:pi:c0:m1`). The rocking-curve scan of the analyzer against the collimator is the USAXS measurement (`BONSE-1`, `USAXS-1`). This page is generated from the descriptor.
- [Sample](sample.md): the sample positioning stage (`SAMPLE-1`), the PI C-867 sample rotator at `usxPI:c867:c0:m1` (`SAMPLE-1`), and the sample temperature environment, the Linkam T96 stage at `usxLINKAM:tc1:` and the PTC10 multi-channel controller at `usxTEMP:tc1:`, each presenting the Regulator Role (`TEMP-1`).
- [Detector](detector.md): the UPD photodiode, the primary USAXS detector, read through an autoranging Femto transimpedance amplifier across several gain decades (amplifier `usxLAX:fem09:seq02:`, autorange `usxLAX:pd01:seq02:`, photocurrent `usxLAX:USAXS:upd`) (`DET-1`); the I0 / I00 / I000 / TRD incident and transmitted flux monitors via Femto amplifiers, for normalization (`DET-1`); the counting scaler that counts the amplifier channels (`DET-1`); the USAXS and SAXS detector translation stages (`OPT-2`); and the pinhole SAXS and WAXS Pilatus area detectors (`DET-1`).

## Shared

- [Controls](controls.md): the APS EPICS / ophyd control stack, the same floor as 2-BM, and the bluesky-style orchestration CORA conducts over where it replaces it. CORA observes the floor and does not replace EPICS. The device handles are bound from the beamline's instrument config and carried `confirm` (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, and vacuum), carried in the descriptor (`SUP-1`). The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the instrument config, carried pending, and not invented (`PSS-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
