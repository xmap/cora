# Notes

## Techniques

*What the modelled part of 12-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md) is how a facility adapts it. 12-ID is CORA's first Bonse-Hart ultra-small-angle X-ray scattering (USAXS) beamline, and it also runs pinhole SAXS and WAXS on area detectors. The lead technique, USAXS, is a new Capability for the fleet, so its Method renders unlinked and is carried pending until a technique enters scope (USAXS-1); the SAXS and WAXS Methods share the [i22](../i22/notes.md#techniques) scattering vocabulary and are pending the same owner-scope decision (TECH-1).

### Bonse-Hart ultra-small-angle scattering

USAXS reaches momentum transfer q far below the pinhole-SAXS regime by rocking a matched pair of channel-cut crystal stages through the Bragg condition: the collimator sits upstream of the sample, the analyzer downstream, and as the analyzer rocks against the collimator a single photodiode counts the transmitted intensity through an autoranging transimpedance amplifier across several gain decades (BONSE-1, USAXS-1). The measurement is the rocking curve, the transmitted intensity as a function of the small angular offset between the two crystals, which maps to q. This angular rocking fly-scan against a multi-decade autoranging point detector is the acquisition shape that is new for the fleet, not a new device class.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Ultra-small-angle scattering (USAXS) | `ultra_small_angle_scattering` | the Bonse-Hart rocking curve: the [analyzer crystal stage](detector.md) rocks against the [collimator crystal stage](sample.md) through the Bragg condition while the [UPD photodiode](detector.md) point-counts the transmitted flux through an autoranging amplifier; new Capability, pending (USAXS-1, BONSE-1) |
| Pinhole small-angle scattering (SAXS) | `small_angle_scattering` | low-q on the [SAXS Pilatus area detector](detector.md); shares the i22 SAXS Capability, pending (TECH-1) |
| Wide-angle scattering (WAXS) | `wide_angle_scattering` | wide-q on the [WAXS Pilatus area detector](detector.md) on its translation; shares the i22 WAXS Capability, pending (TECH-1) |

USAXS needs the [incident beam chain](source.md) (the shared 12-ID double-crystal monochromator and the attenuator filter bank), the [sample stack](sample.md) (positioning stage, rotator, and the Linkam and PTC10 temperature stages), the [Bonse-Hart crystal stages](detector.md), and the [autoranging photodiode with its flux monitors and scaler](detector.md) for normalization. The same instrument runs pinhole SAXS and WAXS on their Pilatus area detectors, which reuse the existing scattering Capabilities and the same beam.

### A new operating axis for the fleet

USAXS is genuinely new for the fleet. The catalog already carries pinhole and grazing-incidence scattering on area detectors (i22, SMI) and a range of imaging, microprobe, and spectroscopy methods, but no crystal-analyzer rocking-curve technique. The new axis is the acquisition shape itself: rock one optic (the analyzer crystal) against a second, fixed-geometry optic (the collimator crystal) while a current-integrating point detector autoranges across several gain decades, rather than expose an area detector at one geometry (BONSE-1, USAXS-1). Pinhole SAXS resolves the scattering pattern by where photons land on a 2D detector; USAXS resolves much smaller angles by where the analyzer crystal passes the beam, read as one transmitted current per angular step. That is a new Capability, deferred as a question (USAXS-1).

The new acquisition shape forces no new device families. The Bonse-Hart crystal stages bind the catalog `RotaryStage`: the operative axis is the crystal rocking rotation, and channel-cut versus multi-bounce is a per-Asset setting, not a new optic Family (BONSE-1). The autoranging photodiode binds the catalog `FluxMonitor`: it is a current-integrating point detector read through an autoranging Femto amplifier, the same anatomy as the I0 / I00 / I000 / TRD flux monitors and the counting scaler, and the multi-decade gain autorange is a device-state setting (DET-1). The SAXS and WAXS Pilatus detectors bind the catalog `Camera`. So what is new is the science Capability and the acquisition shape, not a device class; see [Model](#model) for why nothing graduates and the catalog is unchanged.

### Not modelled yet

The concrete acquisition recipes (the rocking-curve angular ranges, the gain-autorange behaviour and counting times for the photodiode, the pinhole-SAXS and WAXS camera geometries, and the temperature-ramp sequences) are not written yet; they join as the deployment approaches the point where CORA conducts over the floor. Whether USAXS enters CORA's catalog is an owner-scope decision and is deferred (USAXS-1); minting a cross-facility Method is not done from a modelling exercise until a technique enters a real scope, the same earn-the-abstraction discipline the SAXS and WAXS Methods follow (TECH-1). The Practices are carried pending on the [APS Site](../aps/index.md): `12ID_usaxs_practice` (`ultra_small_angle_scattering`, USAXS-1), `12ID_saxs_practice` (`small_angle_scattering`), and `12ID_waxs_practice` (`wide_angle_scattering`). See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at 12-ID, and the trust shape that will gate it. First cut.*

Governance at 12-ID follows the same model as the other APS beamlines: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

12-ID is not yet driven by CORA, so this shape is not yet instantiated. As a reverse-engineered scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The instrument config exposes device tables, not the human roster, so the APS operator pool and safety-review structure is carried pending at the [APS Site](../aps/index.md#safety-and-governance), shared across the beamlines (`GOV-1`).

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the instrument config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and the beamline links up to them rather than restating them. 12-ID adds the hazard classes that come with a hard X-ray USAXS endstation under vacuum and the in-situ temperature environments at the sample (the Linkam T96 and PTC10 stages, `TEMP-1`); those land with the instruments that bring them, and an experiment Clearance would carry them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 12-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 12-ID content lives, the first Bonse-Hart USAXS deployment that coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 12-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes 12-ID new

12-ID is CORA's first Bonse-Hart ultra-small-angle X-ray scattering (USAXS) beamline. The fleet already has pinhole small- and wide-angle scattering (i22, 8-ID), grazing-incidence scattering (9-ID), total scattering and powder diffraction (i15-1, i11), and coherent XPCS (8-ID, CHX), but no crystal-analyzer USAXS. The novelty is the acquisition shape: a matched pair of channel-cut crystal stages, the collimator upstream of the sample and the analyzer downstream, is rocked through the Bragg condition while a single photodiode counts the transmitted intensity through an autoranging transimpedance amplifier across several gain decades. The rocking curve resolves momentum transfer far below the pinhole-SAXS regime. That angular rocking fly-scan with a multi-decade autoranging point detector is a new Capability, deferred as a question (USAXS-1, BONSE-1). The same instrument also runs pinhole SAXS and WAXS on area detectors, which reuse the existing scattering Capabilities. The novelty forces no new device families: every device below reuses an existing catalog or loose Family.

### No new families

12-ID coins no new Family and changes nothing in the catalog. The two devices that could have tempted a new kind both fold into existing vocabulary:

- **The Bonse-Hart crystal stages bind the catalog `RotaryStage`, not a new optic family.** The collimator and analyzer are channel-cut crystal stages whose operative axis is the crystal rocking rotation (plus alignment translations and a piezo fine-tilt). The rocking rotation is what `RotaryStage` already models; channel-cut versus multi-bounce is a per-Asset setting, not a new optic Family. The rocking-curve scan against the matched crystal is the USAXS measurement, an acquisition shape (USAXS-1), not a device class.

- **The autoranging photodiode binds the catalog `FluxMonitor`, not a new detector family.** The UPD photodiode is the primary USAXS detector, but it is a current-integrating point detector read through an autoranging Femto transimpedance amplifier, the same anatomy as the I0 / I00 / I000 / TRD monitors and the counting scalers. This is the BMM precedent (a quad-electrometer-as-primary-detector). The multi-decade gain autorange is a device-state setting, not a new family (DET-1). The pinhole SAXS and WAXS Pilatus area detectors bind the catalog `Camera`.

The Linkam T96 and the PTC10 reuse the graduated `TemperatureController` Family (presents the `Regulator` Role), the same Family three Diamond beamlines and IXS already use. The attenuator binds the `Filter` Family (the i03 / i15-1 precedent, ATTN-1). The machine source state reuses the loose `StorageRing` (MACHINE-1).

### Deliberately not here yet

- **The Bonse-Hart pair as an Assembly (`BONSE-1`).** Whether the matched collimator and analyzer crystal stages compose one `Assembly` (a Bonse-Hart camera presenting a single rocking-pair unit) is deferred, exactly as the diffractometer beamlines deferred materializing their Assemblies in descriptor mode. The first cut is two flat `RotaryStage` Assets with the Assembly named as the follow-on. An Assembly is earned at n=2 across independent beamlines; coining one at n=1 would be over-modelling.

- **The channel-cut crystal identity.** Each crystal stage carries its crystal as a setting on the one `RotaryStage` Asset; promoting a crystal to a child Asset via `parent_id` is the nested-component-identity convention, itself at a rule-of-three gate (applied only for `RotaryDriveChassis` so far). The first cut carries the crystal as a setting rather than asserting a child Asset.

- **The in-situ load frame (`LOADFRAME-1`).** A load frame exists in the instrument's device library but is not in the active instrument config, so it is not modelled here. No Family is coined for an un-instantiated device; it lands if it enters the active beamline.

- **The USAXS Method.** Whether the Bonse-Hart rocking-curve technique enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending (`USAXS-1`). The pinhole SAXS / WAXS Practices share the i22 SAXS / WAXS Methods, also pending (TECH-1 at the Site level).

- **The simulated devices and full asset-tree scenarios.** No `test_12_id_e_*.py` registers the asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 12-ID team to confirm before the model can be trusted.*

12-ID was reverse-engineered from the beamline's own bluesky / BITS instrument ([BCDA-APS/usaxs-bits](https://github.com/BCDA-APS/usaxs-bits)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `src/usaxs/configs/*.yml` device tables and `src/usaxs/devices/*.py` classes rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Is 12-ID one experiment hutch served by a shared upstream 12-ID optics zone, or do the optics live in the same hutch? | Two enclosures: a shared `12-ID-optics` zone and the `12-ID-E` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 12-ID undulator period and type (absent from the USAXS instrument config). | An insertion-device sector; the undulator gap is not exposed as a device. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state 12-ID reads (current, fill, top-up). | Observe-only machine state, a loose `StorageRing`; the exact PVs are pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The 12-ID monochromator crystal cut / d-spacing, the incident-energy range, and the real energy PVs (the instrument wraps it as a soft device). | A double-crystal `Monochromator`; cut and range carried pending. | The monochromator Asset. |
| ATTN-1 | Nice-to-have | The attenuator foil set (`12idPyFilter:`) and whether it folds into the `Filter` Family or earns a distinct `Attenuator` kind (the fleet-wide question). | An Al/Ti filter bank bound to `Filter`, the i03 / i15-1 precedent. | The attenuator's catalog home. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (guard, USAXS-defining) and the detector / SAXS translation stage axes. | Four-blade variable openings bound to `Slit`; translation stages bound to `LinearStage`. | The slit and stage axis detail. |

### USAXS optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BONSE-1 | Blocks-build | The Bonse-Hart crystal cut (channel-cut versus multi-bounce), the collimator / analyzer rocking-axis map, and the rocking-curve tolerance. | Matched channel-cut crystal stages on `RotaryStage`, each a rocking rotation plus alignment translations and a piezo fine-tilt. | The Bonse-Hart geometry; the CORA structural modelling is on [Model](#deliberately-not-here-yet). |
| USAXS-1 | Blocks-go-live | Does the Bonse-Hart rocking-curve ultra-small-angle-scattering technique enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice, no `cora.capability.usaxs` coined. | The USAXS Capability. |

### Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The sample-stage axis set, the PI C-867 sample rotator role, and what is mounted on them. | A `LinearStage` sample stage plus a `RotaryStage` rotator; the axis set carried pending. | The sample-stage modelling. |
| TEMP-1 | Nice-to-have | The Linkam T96 temperature range and the PTC10 channel map, and whether they coexist or swap per experiment. | Two `TemperatureController` Assets presenting the `Regulator` Role; range and channels pending. | The temperature-environment modelling. |
| LOADFRAME-1 | Nice-to-have | Is the in-situ load frame (in the device library but not the active instrument config) part of the operating beamline, and what is it? | Not modelled: deferred until it appears in the active config; no Family coined for an un-instantiated device. | The load-frame modelling. |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The UPD autoranging photodiode gain-decade map, the I0 / I00 / I000 / TRD flux-monitor channel assignment, the scaler channels, and the SAXS / WAXS area-detector prefixes. | The UPD photodiode + the I0 family + the scalers bound to `FluxMonitor` (gain autorange a device-state setting); the SAXS / WAXS Pilatus detectors bound to `Camera`. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the usaxs-bits instrument current and correct? | The handles in the descriptor are taken from the instrument config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the front-end / photon shutters (absent from the instrument config). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the optics and flight paths. | Photon beam, cooling water, and vacuum on the optics and flight paths. | The Supply observations. |
| GOV-1 | Nice-to-have | The APS operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the APS Site, not instantiated per beamline. | The governance principals. |
