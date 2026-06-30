# 12-ID-E

*The Bonse-Hart ultra-small-angle X-ray scattering (USAXS) beamline at APS Sector 12, and CORA's first USAXS deployment. The same instrument also runs pinhole SAXS and WAXS on area detectors. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `12-ID-E` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 12` (not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | The shared 12-ID double-crystal monochromator and front-end optics, observed in the `12-ID-optics` zone (`MONO-1`, `SRC-1`) |
| Control stack | APS EPICS / ophyd (the same floor as 2-BM / 2-ID / 7-BM / 32-ID / 19-BM / 4-ID / 8-ID / 9-ID); handles bound from the instrument config, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky/BITS instrument ([BCDA-APS/usaxs-bits](https://github.com/BCDA-APS/usaxs-bits)), specifically the `src/usaxs/configs/*.yml` device tables and the `src/usaxs/devices/*.py` classes. EPICS PVs are real and read from the config; vendor part numbers, serials, and physical positions are not in the config and are open questions. Every value is carried as `confirm` until 12-ID-E staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 12-ID-E different

12-ID-E is **CORA's first Bonse-Hart USAXS beamline**, the first instrument in the fleet whose primary measurement is an angular rocking curve read by a single autoranging point detector rather than an image on an area detector. What is new is the acquisition shape: a matched pair of channel-cut crystal stages, the collimator upstream of the sample and the analyzer downstream, is rocked through the Bragg condition while one photodiode counts the transmitted beam through an autoranging amplifier across several gain decades. The rocking curve reaches momentum transfer q far below the pinhole-SAXS regime.

The acquisition has three moving parts:

- **Rock the matched crystal pair through Bragg.** The Bonse-Hart collimator crystal stage upstream of the sample and the analyzer crystal stage downstream are rocked together through the Bragg condition. The angular rocking-curve scan of the analyzer against the collimator is the USAXS measurement.
- **Count the transmitted beam across gain decades.** A single photodiode, the UPD, counts the transmitted intensity through an autoranging Femto transimpedance amplifier that spans several gain decades. The gain autorange follows the signal level as the rocking curve sweeps from the direct beam into the wings.
- **Reach q below pinhole SAXS.** The angular resolution of the matched crystal pair resolves momentum transfer q far below what pinhole SAXS can access, which is the reason the instrument exists.

This angular rocking fly-scan with a multi-decade autoranging point detector is **the** novel acquisition shape. The same instrument **also** runs pinhole SAXS and WAXS on area detectors, which reuse the existing scattering Capabilities and add nothing new.

12-ID-E **coins no new family**. Every device binds an existing catalog or loose Family, and the catalog changes nothing. The two devices that could tempt a new Family do not need one:

- **The Bonse-Hart crystal stages bind the catalog `RotaryStage`.** The operative axis is the crystal rocking rotation; channel-cut versus multi-bounce is a per-Asset setting, not a new optic Family. The rocking-curve scan is an acquisition shape, not a device class (`BONSE-1`).
- **The autoranging photodiode binds the catalog `FluxMonitor`.** The UPD is a current-integrating point detector read through an autoranging Femto amplifier, the same anatomy as the I0 / I00 / I000 / TRD flux monitors and the counting scaler (the BMM quad-electrometer-as-primary precedent). The multi-decade gain autorange is a device-state setting. The pinhole SAXS and WAXS Pilatus area detectors bind the catalog `Camera` (`DET-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Source / optics (`12-ID-optics`) | Yes | The shared 12-ID double-crystal monochromator, the Al/Ti attenuator filter bank, the guard and USAXS slits, and the machine-level storage ring (observe-only) |
| USAXS endstation (`12-ID-E`) | Yes | The Bonse-Hart collimator and analyzer crystal stages, the sample stages and environment, the UPD photodiode and flux monitors, the SAXS and WAXS area detectors |
| New device classes | None | Zero new families; nothing graduates; the catalog is unchanged (see [Model](model.md)) |
| The Bonse-Hart crystal pair | Catalog `RotaryStage` | The rocking-curve scan is an acquisition shape, not a device class (`BONSE-1`) |
| The autoranging photodiode | Catalog `FluxMonitor` | A current-integrating point detector read through an autoranging amplifier (`DET-1`) |
| The matched-pair Assembly | No | The collimator-plus-analyzer Bonse-Hart pair Assembly is named, not built (`BONSE-1`) |
| The in-situ load frame | No | Present in the device library, absent from the active instrument config; not modelled, no Family coined (`LOADFRAME-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **Reuse over coin.** Every device binds an existing catalog or loose Family, and the catalog changes nothing. The Bonse-Hart crystal stages and the autoranging photodiode, the two devices that could tempt a new Family, both bind existing catalog Families; the novelty lives in the acquisition shape and the per-Asset and device-state settings, not in any new device class.
- **The Bonse-Hart pair Assembly is named, not built (`BONSE-1`).** Whether the collimator crystal stage and the analyzer crystal stage compose a single matched-pair Assembly is deferred. The first cut is two flat `RotaryStage` Assets, the collimator (rocking rotation `usxAERO:m12`) and the analyzer (rocking rotation `usxAERO:m6`), each carrying its alignment translations and r2p piezo fine-tilt.
- **The in-situ load frame is deferred (`LOADFRAME-1`).** A load frame exists in the device library (`loadframe.py`) but is not in the active instrument config, so it is not modelled. No Family is coined for an un-instantiated device.

## The beamline

- [Source](beamline.md): the generated device walk: the storage ring (observe-only), the shared 12-ID double-crystal monochromator, the Al/Ti attenuator filter bank (`12idPyFilter:`), and the guard and USAXS slits (`usxLAX:`).
- [Sample](equipment/sample.md): the sample positioning stage, the PI C-867 sample rotator, and the Linkam T96 and PTC10 temperature stages.
- [Detector](equipment/detector.md): the UPD photodiode and its autoranging Femto amplifier (the primary USAXS detector), the I0 / I00 / I000 / TRD flux monitors and the counting scaler, the detector translation stages, and the pinhole SAXS and WAXS Pilatus area detectors.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the instrument config and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/12-id-e/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 12-ID-E is designed to do, as intent. Bonse-Hart rocking-curve USAXS is a new Catalog Method (`ultra_small_angle_scattering`), deferred and rendered unlinked, carried pending (`USAXS-1`). The pinhole SAXS Practice (`small_angle_scattering`) and the WAXS Practice (`wide_angle_scattering`) reuse the existing i22 SAXS / WAXS [Methods](../../catalog/methods.md), also pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at 12-ID-E and the trust shape that gates their commands. People and autonomous agents are facility principals at the [APS Site](../aps/index.md); on the beamline they surface through the actions they take, gated by a trust shape (Zone, Conduit, Policy). The APS operator pool and safety-review structure are carried pending at the APS Site, shared across the beamlines (`GOV-1`). Clearances are issued at the [APS Site](../aps/index.md), not on the beamline.

## Model

[Model](model.md): the developer's by-kind index and the record of what is deliberately deferred. 12-ID-E coins no new Family, and the catalog is unchanged (see [Families](../../catalog/families.md)).

## Not yet documented

12-ID-E is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the instrument config and are not invented here (`PSS-1`).
