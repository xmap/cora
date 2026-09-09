# Notes

## Techniques

*What CORA would run at CHX: coherent-scattering techniques, each a [Catalog](../../catalog/methods.md) Method. CHX is the second coherent beamline CORA models, after APS [8-ID](../8-id/notes.md#techniques), and it follows 8-ID's deferral exactly.*

CHX's techniques are coherent-scattering, new to CORA's imaging- and spectroscopy-heritage catalog. As at 8-ID, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| XPCS | `xpcs` | coherent-speckle intensity time series on the Eiger, gated by the Zebra / fast shutter (TIMING-1); Method not yet in catalog |
| Small-angle scattering | `small_angle_scattering` | static SAXS/WAXS on the same detectors; a Plan setting over the same chain |
| Grazing-incidence scattering | `small_angle_scattering` | GISAXS: the same scattering Method with the beam steered onto a surface by the `GrazingIncidenceMirror` (GI-1) |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, mirror, transfocator, and slit tuning; reuses the existing Method |

All three scattering techniques need the [sample stack](sample.md) and the [coherent detectors](detector.md); the fast shutter and Zebra (TIMING-1) gate the exposure.

### Why the Methods stay deferred

8-ID opened the question of whether the XPCS and small-angle-scattering Methods enter CORA's catalog (TECH-1), and `main` deliberately left them pending: the concrete acquisition recipes (correlation time series, frame rates, exposures) join as the deployment approaches the point where CORA drives the beamline. CHX reinforces the case for both Methods at a second facility without coining either, the same earn-the-abstraction discipline the deferred `scanning` (HXN) and `energy_scan` (BMM) Capabilities follow. Because the defining Methods are not in the catalog, CHX records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here), exactly as 8-ID records none at APS; the binding lands when the Method does.

The correlation analysis itself (the g2 / multi-tau computation that turns the frame series into dynamics) is `ComputePort` work, not a beamline Method.

## Governance

*Who may act at CHX and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A CHX beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may arm a long XPCS series, change the q-range, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### Long unattended runs

XPCS time series can run long and unattended, which is where CORA's trust shape earns its keep: the engine holds the gated exposure while the trust boundary bounds what may change mid-series and who may intervene. If an autonomous Agent were added to steer acquisition (choose the next sample temperature, decide when enough frames are collected), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's CHX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CHX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (11-ID-A optics, 11-ID-B endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring HXN, BMM, SRX, and the Diamond beamlines. Left out on purpose:

- **No new Family.** CHX is a reuse-and-reinforce deployment: the area detectors bind `Camera`, the flux counter `FluxMonitor`, the thermal stage `TemperatureController`, the fluorescence detector `EnergyDispersiveSpectrometer`, the beamstop `BeamStop`, the mirrors `Mirror`, both monochromators `Monochromator`, the coherence-defining and guard slits `Slit`, and the compound-refractive-lens focusing optic the graduated `Transfocator` catalog Family (a CRL focusing optic, also bound at 4-ID, 8-ID, 9-ID, i22). The `Transfocator` graduation settled the focusing-optic abstraction, so it is a normal catalog reuse like `Mirror`; what remains open for the transfocator is only its per-Asset lens material and count, tracked as `CRL-1`. CHX also carries a **second**, distinct kind of refractive focusing optic, the endstation kinoform lenses (`k1`/`k2`): a single profiled refractive lens, not a compound-lens transfocator, so it does not bind the `Transfocator` Family. It is named but not modelled as a device; whether a kinoform earns its own Family is a separate future question if a deployment binds one, not part of `CRL-1`.
- **The graduated `PositionMonitor`.** The `PositionMonitor` (4-ID, 8-ID, 9-ID) binds the graduated catalog Family, which presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux.
- **No new Capability or Method.** XPCS and small-angle scattering sit on the deferred `xpcs` / `small_angle_scattering` Methods 8-ID left pending (`TECH-1`); CHX reinforces both without coining either, and records no Practice until they land. The correlation analysis is `ComputePort` work, not a Method.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the CHX team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/chx-profile-collection`](https://github.com/NSLS2/chx-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector/timing configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU20 undulator period, gap range, and harmonic usage. The device (`SR:C11-ID:G1{IVU20:1}`) is confirmed. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:11ID-PPS{Sh:FE}`, `XF:11IDA-PPS{PSh}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The Si DCM cryo detail and full range (the Si(111) cut and harmonic 5 are read from the production `move_E` routine), and the DMM multilayer coating and bandpass. Both monochromators (`Mono:DCM`, `Mono:DMM`) are in source. | Two Monochromator Assets, Si(111) cut recorded, other settings blank. | The Monochromator settings. |
| CRL-1 | Blocks-go-live | The FOE transfocator (`XF:11IDA-OP{Lens:`) lens material and lenslet count. Its catalog home is settled: it binds the graduated `Transfocator` CRL Family; only the per-Asset lens spec is open. (The endstation kinoform lenses `k1`/`k2`, `XF:11IDB-OP{Lens:1` / `{Lens:2`, are a distinct refractive optic, not a compound-lens transfocator; they are named but not modelled as devices, and whether they earn their own Family is a separate future question, not part of CRL-1.) | The transfocator binds the graduated `Transfocator` Family; lens material and count left blank. | The transfocator lens spec. |
| GI-1 | Nice-to-have | Is grazing-incidence scattering (GISAXS) a live routine, and does the `Mir:GI` mirror steer the beam for it? | A `Mirror` Asset; GISAXS noted as a technique. | The GISAXS geometry. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full diffractometer axis set behind the `SamplePositioner` pseudomotor, and whether the goniometric axes warrant a `Goniometer` plus a Diffractometer Assembly (the 8-ID precedent). | A `LinearStage` sample stack, rotation axes and the Assembly deferred. | The SampleStage axes and orientation modelling. |
| DET-1 | Blocks-go-live | Which Eiger (4M / 1M / 500K) is the primary XPCS detector vs the spare set, whether a separate along-beam stage sets the sample-to-detector distance (the `Det:SAXS` motor is transverse X/Y only), and the Xspress3 element count. | Eiger 4M primary; all Cameras; no distance stage modelled. | The detector roster and q-range. |
| CAM-1 | Nice-to-have | Which beam-viewing cameras (the Prosilica x-ray-eyes, the PointGrey, the OAV) are live. | The OAV modelled as a Camera; others noted. | The beam-viewing camera set. |
| DIAG-1 | Nice-to-have | The scaler flux channel map (which channel is I0) and the BPM / AH401B electrometer channels. | Read-only flux and beam-position probes; channel maps blank. | The FluxCounter and PositionMonitor bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIMING-1 | Blocks-go-live | The XPCS exposure-gating chain: how the Zebra, the delay generator (`delaygen:DG0:`), and the fast shutter co-time the Eiger frame triggers, and their vendor identities. | One `TimingController` (Zebra) gating the fast shutter and frames; chain detail blank. | The triggering chain. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| ENERGY-1 | Nice-to-have | Is CHX always fixed-energy, or does anomalous XPCS scan energy as the measurement (the `energy_scan` Capability the catalog anticipates, shared with BMM)? | Fixed-energy; energy_scan deferred (the BMM question). | The energy Capability decision. |
| TECH-1 | Blocks-go-live | Do the XPCS and small-angle-scattering Methods enter CORA's catalog, or stay deferred? This is the same owner-scope decision 8-ID opened. | Methods deferred (rendered unlinked), no Practice recorded. | The coherent-scattering Method scope. |
