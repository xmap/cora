# Model

*The developer's index into where 12-ID-E content lives, why this first Bonse-Hart USAXS deployment coins no new family, and the record of what is deliberately deferred. First cut.*

12-ID-E is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's bluesky / BITS instrument: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/12-id-e/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/12-id-e/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface; `12-ID-E` added to its beamline list, with USAXS / SAXS / WAXS Practices |
| Extraction provenance | [BCDA-APS/usaxs-bits](https://github.com/BCDA-APS/usaxs-bits) | the `src/usaxs/configs/*.yml` device tables and `src/usaxs/devices/*.py` classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the USAXS Method is not yet coined (USAXS-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 12-ID-E Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes 12-ID-E new

12-ID-E is CORA's first Bonse-Hart ultra-small-angle X-ray scattering (USAXS) beamline. The fleet already has pinhole small- and wide-angle scattering (i22, 8-ID), grazing-incidence scattering (9-ID), total scattering and powder diffraction (i15-1, i11), and coherent XPCS (8-ID, CHX), but no crystal-analyzer USAXS. The novelty is the acquisition shape: a matched pair of channel-cut crystal stages, the collimator upstream of the sample and the analyzer downstream, is rocked through the Bragg condition while a single photodiode counts the transmitted intensity through an autoranging transimpedance amplifier across several gain decades. The rocking curve resolves momentum transfer far below the pinhole-SAXS regime. That angular rocking fly-scan with a multi-decade autoranging point detector is a new Capability, deferred as a question (USAXS-1, BONSE-1). The same instrument also runs pinhole SAXS and WAXS on area detectors, which reuse the existing scattering Capabilities. The novelty forces no new device families: every device below reuses an existing catalog or loose Family.

## No new families

12-ID-E coins no new Family and changes nothing in the catalog. The two devices that could have tempted a new kind both fold into existing vocabulary:

- **The Bonse-Hart crystal stages bind the catalog `RotaryStage`, not a new optic family.** The collimator and analyzer are channel-cut crystal stages whose operative axis is the crystal rocking rotation (plus alignment translations and a piezo fine-tilt). The rocking rotation is what `RotaryStage` already models; channel-cut versus multi-bounce is a per-Asset setting, not a new optic Family. The rocking-curve scan against the matched crystal is the USAXS measurement, an acquisition shape (USAXS-1), not a device class.

- **The autoranging photodiode binds the catalog `FluxMonitor`, not a new detector family.** The UPD photodiode is the primary USAXS detector, but it is a current-integrating point detector read through an autoranging Femto transimpedance amplifier, the same anatomy as the I0 / I00 / I000 / TRD monitors and the counting scalers. This is the BMM precedent (a quad-electrometer-as-primary-detector). The multi-decade gain autorange is a device-state setting, not a new family (DET-1). The pinhole SAXS and WAXS Pilatus area detectors bind the catalog `Camera`.

The Linkam T96 and the PTC10 reuse the graduated `TemperatureController` Family (presents the `Regulator` Role), the same Family three Diamond beamlines and IXS already use. The attenuator binds the `Filter` Family (the i03 / i15-1 precedent, ATTN-1). The machine source state reuses the loose `StorageRing` (MACHINE-1).

## Deliberately not here yet

- **The Bonse-Hart pair as an Assembly (`BONSE-1`).** Whether the matched collimator and analyzer crystal stages compose one `Assembly` (a Bonse-Hart camera presenting a single rocking-pair unit) is deferred, exactly as the diffractometer beamlines deferred materializing their Assemblies in descriptor mode. The first cut is two flat `RotaryStage` Assets with the Assembly named as the follow-on. An Assembly is earned at n=2 across independent beamlines; coining one at n=1 would be over-modelling.

- **The channel-cut crystal identity.** Each crystal stage carries its crystal as a setting on the one `RotaryStage` Asset; promoting a crystal to a child Asset via `parent_id` is the nested-component-identity convention, itself at a rule-of-three gate (applied only for `RotaryDriveChassis` so far). The first cut carries the crystal as a setting rather than asserting a child Asset.

- **The in-situ load frame (`LOADFRAME-1`).** A load frame exists in the instrument's device library but is not in the active instrument config, so it is not modelled here. No Family is coined for an un-instantiated device; it lands if it enters the active beamline.

- **The USAXS Method.** Whether the Bonse-Hart rocking-curve technique enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending (`USAXS-1`). The pinhole SAXS / WAXS Practices share the i22 SAXS / WAXS Methods, also pending (TECH-1 at the Site level).

- **The simulated devices and full asset-tree scenarios.** No `test_12_id_e_*.py` registers the asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
