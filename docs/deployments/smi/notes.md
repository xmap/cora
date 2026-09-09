# Notes

## Techniques

*What CORA would run at SMI: scattering techniques, each a [Catalog](../../catalog/methods.md) Method. SMI is the NSLS-II twin of the Diamond [I22](../i22/notes.md#techniques) (SAXS / WAXS) beamline, and it follows i22's deferral exactly, adding the grazing-incidence variants.*

SMI's techniques are small- and wide-angle scattering, the science domain Diamond i22 brought to CORA. As there, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Mode | Notes |
| --- | --- | --- |
| Small-angle scattering (SAXS) | monochromatic, long camera | low-Q on the SAXS Pilatus 2M; the i22 Capability, new Capability pending (TECH-1) |
| Wide-angle scattering (WAXS) | monochromatic, swing arc | wide-Q on the WAXS Pilatus 900KW; the i22 Capability, new Capability pending (TECH-1) |
| Simultaneous SAXS+WAXS | both detectors at once | coordinated Runs under one Campaign, the routine mode, not a third technique (TECH-1) |
| Grazing-incidence (GISAXS / GIWAXS) | shallow incidence, reflected geometry | the same scattering Methods with the sample at a grazing angle and the WAXS arc swung; a sample-orientation variant (TECH-1) |

All the scattering techniques need the [grazing-incidence sample stack](sample.md) and the [SAXS / WAXS detectors](detector.md); the fast shutter gates the exposure.

### Why the Capabilities stay deferred

Diamond i22 opened the question of whether the SAXS and WAXS Capabilities enter CORA's catalog (TECH-1), and `main` deliberately left them pending: SAXS and WAXS do not reduce to the imaging-heritage `tomography` / `acquisition` Capabilities, and a modelling exercise does not mint cross-facility vocabulary until a technique enters a real scope. The device Roles already exist (the Pilatus detectors present the Detector Role, the flux monitor presents Sensor), so what is new is the science Capability, not a device shape. SMI reinforces the case for both at a second facility without coining either, the same earn-the-abstraction discipline the deferred `scanning` (HXN), `energy_scan` (BMM), and powder / total-scattering (XPD) Capabilities follow.

Grazing incidence (GISAXS / GIWAXS) is the genuinely new wrinkle SMI adds over i22, but it is a sample-orientation variant of the same scattering Capability (the sample sits at a shallow angle, the WAXS arc swings), not a new Capability of its own. Simultaneous SAXS+WAXS is coordinated Runs under one Campaign over a shared trigger, the same way 7-BM and i22 model parallel detector reads, not a combined technique. Because the defining Capabilities are not in the catalog, SMI records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); the binding lands when the Capability does.

The azimuthal integration and reduction (turning the 2D scattering frames into I(Q) curves and GISAXS maps) are `ComputePort` work, not beamline Methods.

## Governance

*Who may act at SMI and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An SMI beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start an acquisition, change the camera length or grazing angle, run an in-situ environment program, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### In-situ studies and time series

SMI's soft-matter science often follows a sample as it changes: a film drying under a blade coater, a polymer responding to humidity or a temperature ramp. Those are time series under an in-situ environment program, where CORA's custody and trust shapes earn their keep, holding the gated acquisition while the trust boundary bounds what may change mid-series and who may intervene. If an autonomous Agent were added to steer such a study (adjust the environment, decide when enough frames are collected), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's SMI content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SMI |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (12-ID-A optics, 12-ID-C experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new Family.** SMI is a reuse-and-reinforce deployment, the NSLS-II twin of Diamond i22 (SAXS / WAXS): the Pilatus detectors bind `Camera`, the flux monitor `FluxMonitor`, the sample environment `TemperatureController`, the fluorescence MCA `EnergyDispersiveSpectrometer`, the beamstops `BeamStop`, the mirrors `Mirror`, the monochromator `Monochromator`, the slits `Slit`, the attenuators `Filter`, and the compound-refractive-lens `Transfocator`, which reuses the graduated `Transfocator` catalog Family (a CRL focusing optic, distinct from `Mirror` / `ZonePlate` / `Condenser`, bound at 4-ID, 8-ID, 9-ID, i22, and CHX too); the residual open item is the per-Asset lens material and count (`CRL-1`), which graduation does not resolve.
- **The graduated `PositionMonitor`.** One device binds the graduated catalog `PositionMonitor` Family that other deployments also share (4-ID, 8-ID, 9-ID): it presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux. The per-Asset residual that stays open is the beam-position channel map (`DIAG-1`), recorded in the promotion-review register.
- **No new Capability or Method.** SAXS, WAXS, and GISAXS sit on the deferred scattering Capabilities Diamond i22 left pending (`TECH-1`); SMI reinforces them without coining any, and records no Practice. Grazing incidence is a sample-orientation variant, not a new Capability; simultaneous SAXS+WAXS is coordinated Runs, not a combined technique. The integration and reduction are `ComputePort` work.
- **The in-situ soft-matter cells.** The humidity cell (driven via Moxa analog IO, relative humidity computed in software) and the blade coater (a SmarAct stage plus a syringe pump) are SMI's specialty; they would each need their own family or Procedure decision, so they are deferred to a named question (`INSITU-1`) rather than modelled.
- **The in-vacuum WAXS / SAXS chamber.** The active sample chamber (pressure gauges, gate valves, turbo pump, pump / vent automation) is carried as the facility `Vacuum` Supply, the i22 precedent; whether the active chamber enters CORA as its own device is the named question `VAC-1`.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the SMI team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/smi-profile-collection`](https://github.com/NSLS2/smi-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector and in-situ-cell configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The in-vacuum undulator period, gap range, and harmonic usage. The device (`SR:C12-ID:G1{IVU:1}`) is confirmed; working gap range is about 6200-15100. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the front-end photon shutter (`XF:12IDA-PPS:2{PSh}`) is in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-crystal monochromator energy range (the crystal is Si(111) per the source energy math, on bare motor records `XF:12ID:m65`-`m68`, driven by the coupled energy pseudopositioner). | One Monochromator Asset, Si(111) recorded, range blank. | The Monochromator settings. |
| CRL-1 | Blocks-go-live | The transfocator (`XF:12IDC-OP:2{Lens:CRL}`) lens material and count (twelve elements). The cross-deployment abstraction is resolved: the compound refractive lens reuses the graduated `Transfocator` catalog Family (a CRL focusing optic), bound at 4-ID, 8-ID, 9-ID, i22, and CHX too; only the per-Asset lens spec is still open. | The graduated `Transfocator` Family is bound; lens material and count blank. | The transfocator lens specification. |
| ENERGY-1 | Nice-to-have | Does SMI ever scan energy as the measurement, or is it always fixed-energy per experiment? | Fixed-energy; energy_scan not modelled. | The energy Capability decision. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full HUB sample-stack axis set (x / y / z / theta / phi / chi) and the SmarAct piezo, and whether the grazing-incidence orientation axes warrant a `Goniometer` plus an Assembly. | A `LinearStage` sample stack, orientation axes and the Assembly deferred. | The SampleStage axes and orientation modelling. |
| DET-1 | Blocks-go-live | Which Pilatus detectors are live (the SAXS 2M, the WAXS 900KW) versus the retired set (a 1M, a 300KW), and the SAXS camera-length range. | 2M (SAXS) and 900KW (WAXS) live; all Cameras; camera-length range blank. | The detector roster and Q-range. |
| TEMP-1 | Nice-to-have | Which sample-environment thermal units are live (the Linkam thermal / tensile stages, the LakeShore controller)? | One `TemperatureController` Asset (the Linkam); the others noted. | The sample-environment Assets. |
| INSITU-1 | Nice-to-have | The in-situ soft-matter cells: the humidity cell (driven via Moxa analog IO, no dedicated PV) and the blade coater (a SmarAct stage plus a syringe pump). How does CORA model these in-situ environments? | Deferred; they would need their own family / Procedure decisions when they land. | The in-situ cell Assets and Procedures. |
| VAC-1 | Nice-to-have | The WAXS / SAXS in-vacuum sample chamber (`Sample_Chamber`: pressure gauges, gate valves, a turbo pump, and pump / vent automation, used to set the in-vacuum vs in-air measurement mode). Does the active chamber enter CORA as a device, or stay a facility Supply? | Vacuum carried as a facility Supply (the i22 precedent); the active chamber deferred. | The vacuum-chamber Asset boundary. |
| DIAG-1 | Nice-to-have | The flux-monitor and beam-position channel maps; the `PositionMonitor` Family is settled (graduated catalog Family presenting `Sensor`), so only the per-Asset channel map stays open. | Read-only flux (`FluxMonitor`) and beam-position (graduated catalog `PositionMonitor`) probes; channel maps blank. | The FluxMonitor and PositionMonitor channel-map bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CAM-1 | Nice-to-have | Which beam-viewing cameras (the SAM / HEX sample cameras, the FOE FS / WBStop / VFM cameras) are live. | The on-axis SAM camera modelled; others noted. | The beam-viewing camera set. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs (SmarAct MCS, MDrive, Thorlabs are named). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the SAXS / WAXS / GISAXS Capabilities enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i22 opened. Simultaneous SAXS+WAXS would be coordinated Runs, not a new technique. | Capabilities deferred (rendered unlinked), no Practice recorded. | The scattering Capability scope. |
