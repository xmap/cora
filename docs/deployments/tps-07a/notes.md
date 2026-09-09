# Notes

## Techniques

*What CORA would run at TPS 07A: rotation macromolecular crystallography, each technique a [Catalog](../../catalog/methods.md) Method bound through an [NSRRC Practice](../nsrrc/index.md#the-techniques-adapted-here). TPS 07A reuses the MX Methods Diamond [I03](../i03/notes.md#techniques) introduced, so it coins nothing new.*

TPS 07A's technique, rotation MX, is the macromolecular-crystallography shape CORA already saw at i03 (and at the Australian Synchrotron [MX3](../mx3/notes.md#techniques), and in its serial form at i24 and LCLS-MFX). The Methods render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog, exactly as at i03 and MX3.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the MD3 goniometer + the EIGER2 X 16M, orchestrated through Blu-Ice/DCSS; the i03 Method, pending (TECH-1) |
| Mesh / grid scan | `grid_scan` | mesh scan for crystal location / centring on the MD3, with Dozor spot-scoring (the Meshbest path); the i03 Method (TECH-1) |
| Autonomous sample exchange | `sample_exchange` | the ISARA robot load / centre / collect / unmount loop, a Procedure over the spine (ROBOT-1) |

All three are recorded as pending [Practices](../nsrrc/index.md#the-techniques-adapted-here) on the NSRRC Site, reusing the same Method names Diamond i03 carries.

### Why the Methods are reused, not coined

TPS 07A brings a new Site and a new seam, not a new technique. Rotation MX, mesh-scan centring, and robot sample exchange are the i03 shapes, so TPS 07A binds the same pending Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) rather than coining anything; whether those Methods enter the catalog is the cross-facility owner-scope decision i03 opened (TECH-1), and TPS 07A reinforces the case at a further MX facility (after i03, NSLS-II FMX / AMX, MX3, and Sirius MANACA). The device Roles already exist (the MD3 presents Positioner via the graduated `Goniometer`, the EIGER2 presents Detector via `Camera`), so nothing new is needed in the device model either.

The autonomous sample exchange reuses the i03 / i24 / MX3 autonomous-loop shape: a Procedure over the spine threaded through `Subject` custody, not a new device family (ROBOT-1). The mesh-scan Dozor spot-scoring and CHiMP crystal detection are `ComputePort` work (an Observe / Compute leg), not beamline Methods.

The genuinely new things TPS 07A contributes are below the technique layer: a new Site (NSRRC) and the Blu-Ice/DCSS-over-EPICS orchestration seam at an MX beamline (see [Controls](controls.md)), which the technique vocabulary rides over unchanged.

## Governance

*Who may act at TPS 07A and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSRRC Site](../nsrrc/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the public control trees (GOV-1), so the principals are the design shape, not a registered list. The trees do expose two governance facts CORA maps onto its own model: LDAP-backed authentication (`ldap://10.7.1.1`) and a mandatory radiation-safety-training portal (`safetytraining.nsrrc.org.tw`).

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSRRC Site. A TPS 07A beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. This is the same role kernel CORA seeds at every Site; NSRRC being a new Site is exactly the test that the Federation / Access kernel ports unchanged.

The NSRRC mandatory training portal maps to CORA's **worldwide-invariant training axis**: a fact carried on the Access principals (has-this-person-completed-the-required-training), not a separate Clearance kind. CORA records it as a property of the principal rather than coining a new facility form (GOV-1).

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a collection, move the robot, change the energy, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer or its LDAP groups. It holds across the seam: a command CORA's EdgeConductor issues in place of DCSS (start an oscillation, drive a motor, arm the detector) is gated exactly as any spine command is. The facility proposal and cycle are a fact CORA's Campaign uses for custody.

### Unattended autonomous collection

TPS 07A's throughput model is unattended: the ISARA robot mounts a crystal, the MD3 centres it (mesh scan + Dozor scoring), the EIGER2 collects, the robot unmounts, repeat. That loop is where CORA's custody and trust shapes earn their keep, each crystal threaded through the `Subject` aggregate so its identity and provenance is tracked, the exchange a Procedure gated by a Clearance (ROBOT-1). If an autonomous Agent were added to choose which crystal to collect or when a dataset is good enough (the CHiMP crystal-detection output is the natural input), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

### The detector safety interlock

The control tree exposes a hard detector minimum-distance interlock (139 mm): the detector stage may not approach the sample closer than that. This is a floor-level hardware safety limit, not a CORA-owned gate; CORA's conduct path respects it as a constraint on the detector-distance command, the same way it respects an EPICS soft limit. The PSS search-and-secure permit leaves that gate the hutch are not in the public source (PSS-1) and are carried as a confirm.

## Model

*The developer's by-kind index: where each CORA aggregate's TPS 07A content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at TPS 07A |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (TPS-07A-OH optics, TPS-07A-EH experiment) |
| Facility (Federation); Zone, Conduit, Policy (Trust); Actor (Access) | [NSRRC Site](../nsrrc/index.md), [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other reverse-engineered beamlines. Left out on purpose:

- **No new Family.** TPS 07A's novelty is the Site and the seam, not its devices: the MD3 goniometer binds the graduated `Goniometer` (the i03 / MX3 MX precedent), the detectors `Camera`, the DCM `Monochromator`, the cryostream `TemperatureController`, the attenuator `Filter`, the beamstop `BeamStop`, the shutters `Shutter`, the mirrors `Mirror`, the stages `LinearStage` / `MotionController`.
- **The reused loose families.** `StorageRing` (the ring-current monitor) and `BeamPositionMonitor` (the beam-position diagnostic) are bound loose, each already allowlisted from earlier deployments; TPS 07A coins no new loose family.
- **The DCSS-over-EPICS seam.** TPS 07A drives a single EPICS floor with a Blu-Ice/DCSS orchestration layer above it, reached through an EPICS Device Handler Server. This is modelled as `ControlPort` actuation over EPICS plus a CORA EdgeConductor that replaces the DCSS orchestration, not new aggregates; it is the 2-BM TomoScan seam, not the MX3 multi-transport seam. See [Controls](controls.md). The MD3 axis PV records and the DCSS-vs-MXCuBE confirmation are GONIO-1.
- **The ISARA robot as a Procedure.** Autonomous sample exchange is a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i24 / MX3 shape, not a new device family.
- **The frame egress and mesh-scan compute.** The EIGER2 ZMQ / ASAP::O frame stream is a `TransferPort` leg into the Dataset of record; the Dozor spot-scoring and CHiMP crystal-detection are `ComputePort` work, an Observe / Compute leg off the control seam, not beamline Methods or Assets (DET-1).
- **No new Capability or Method.** Rotation MX reuses the pending i03 Methods (`mx_data_collection` / `grid_scan` / `sample_exchange`), recorded as Practices on the Site; TPS 07A reinforces the case at a further MX facility without coining any (TECH-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the NSRRC / TPS 07A team to confirm. This model is reverse-engineered from public open source (the [`light911/NSRRC_TPS07A`](https://github.com/light911/NSRRC_TPS07A) control tree and [`light911/TPS07A-Meshbest`](https://github.com/light911/TPS07A-Meshbest) app): the EPICS PV namespace (`07a:` / `07a-ES:`) is read from it, but per-device PV records, vendor identities, physical positions, the source, and the PSS signals are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device / front-end source: TPS 07A is fed by the IU22 in-vacuum undulator (per the SPXF spec page), but no source PV is in the public tree. | An insertion-device source, identity-only, no PV; the ring-current monitor stands in as the source representation. | The Source Asset and its PV. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. No PSS permit signals are in the public source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names: which devices sit in the optics hutch versus the experiment hutch? The trees expose no enclosure structure. | An optics hutch (DCM, mirrors) plus an experiment hutch (the MD3 / EIGER2 / robot). | The Enclosure set and roles. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-crystal monochromator crystal cut and exact range, and the attenuator foil set. | A Si DCM over 6-20 keV and one Filter Asset, settings blank. | The Monochromator / Filter settings. |
| OPT-1 | Nice-to-have | The micro-focus optic delivering the ~2.9 x 1.8 micron spot: is it a KB mirror pair, and what are its PVs? The SPXF page states the focal spot, not the optic. | A KB micro-focus mirror system (`KBMirrors`, Mirror family), configuration blank. | The mirror Assets and PVs. |
| ENERGY-1 | Nice-to-have | Does TPS 07A scan energy as the measurement (anomalous / MAD MX), or run fixed-energy per dataset? | Fixed-energy; the master energy axis is a setpoint. | The energy Capability decision. |

### Sample, detector, robot

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The MD3 microdiffractometer axis PV records (`07a-ES:` namespace, reached through the EPICS DHS), the full axis set, and the settling confirmation that the live scan orchestration is Blu-Ice/DCSS and not a live MXCuBE `mxcubecore` HardwareObjects deployment. (Public evidence is high-confidence DCSS; a live MXCuBE config for 07A would flip the seam to mixed.) | A `Goniometer` Asset (omega / kappa / phi + centring / alignment) on the EPICS floor; the DCSS-over-EPICS seam (the 2-BM pattern), not MXCuBE; PV records deployment config. | The Goniometer interface, axes, and the seam confirmation. |
| DET-1 | Blocks-go-live | The EIGER2 X 16M detector PV records and its SIMPLON REST endpoint, and whether the ZMQ frame egress has migrated to DESY ASAP::O in production. | An EIGER2 `Camera` commanded through the DCSS workflow; frames over ZMQ migrating to ASAP::O; endpoint deployment config. | The detector Model, interface, and frame-egress path. |
| ENV-1 | Nice-to-have | The cryostream sample-cooling vendor and PV. | A `TemperatureController` Asset, settings blank. | The cryostream Model and PV. |
| ROBOT-1 | Nice-to-have | The ISARA sample-mounting robot (mount / unmount trajectories gated on the MD3 state). CORA would model autonomous sample exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the i03 / i24 / MX3 loops. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-exchange Procedure and Subject custody thread. |
| DIAG-1 | Nice-to-have | The beam-position / XBPM and OAV-camera channel maps and PVs. | Read-only beam-position (graduated catalog `PositionMonitor`) and OAV (`Camera`) probes; channel maps blank. | The diagnostic bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box firmware / IPs behind the endstation, goniometer-base, and detector stages (EPICS motor records reached through the DHS). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Capabilities (rotation data collection, mesh / grid scan) enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i03 opened; TPS 07A reuses the pending `mx_data_collection` / `grid_scan` / `sample_exchange` Methods. | Methods deferred (pending Practices on the Site), no catalog Method coined. | The MX Capability scope. |
| GOV-1 | Nice-to-have | The operator / beamline-scientist roster and review structure (the trees show LDAP auth at `ldap://10.7.1.1` and a mandatory training portal at `safetytraining.nsrrc.org.tw`, but no roster). | CORA's role kernel scoped at the Site; the training portal maps to the worldwide-invariant training axis on the principal. | The Actor roster and training-axis binding. |
