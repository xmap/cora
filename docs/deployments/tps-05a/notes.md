# Notes

## Techniques

*What CORA would run at TPS 05A: rotation macromolecular crystallography, each technique a [Catalog](../../catalog/methods.md) Method bound through an [NSRRC Practice](../nsrrc/index.md#the-techniques-adapted-here). TPS 05A reuses the same MX Methods as [TPS 07A](../tps-07a/notes.md#techniques) and Diamond [I03](../i03/notes.md#techniques), so it coins nothing new.*

TPS 05A's technique, rotation MX (in its microcrystallography form), is the macromolecular-crystallography shape CORA already saw at i03, TPS 07A, and MX3. The Methods render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the MD3 goniometer + the EIGER2 X 9M, orchestrated through Blu-Ice/DCSS; the i03 Method, pending (TECH-1) |
| Mesh / grid scan | `grid_scan` | mesh scan for crystal location / centring on the MD3; the i03 Method (TECH-1) |
| Autonomous sample exchange | `sample_exchange` | the ISARA robot load / centre / collect / unmount loop, a Procedure over the spine (ROBOT-1) |

All three are recorded as pending [Practices](../nsrrc/index.md#the-techniques-adapted-here) on the NSRRC Site (the `TPS05A_*` practices), reusing the same Method names TPS 07A and Diamond i03 carry.

### Why the Methods are reused, not coined

TPS 05A brings nothing new at the technique layer: it is the MX-cluster sibling of TPS 07A. Rotation MX, mesh-scan centring, and robot sample exchange are the i03 shapes, so 05A binds the same pending Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) rather than coining anything; whether those Methods enter the catalog is the cross-facility owner-scope decision i03 opened (TECH-1), and 05A reinforces the case at a **further MX deployment** (after i03, NSLS-II FMX / AMX, MX3, Sirius MANACA, and TPS 07A). The device Roles already exist (the MD3 presents Positioner via the graduated `Goniometer`, the EIGER2 presents Detector via `Camera`), so nothing new is needed in the device model either.

The autonomous sample exchange reuses the i03 / i24 / 07A / MX3 autonomous-loop shape: a Procedure over the spine threaded through `Subject` custody, not a new device family (ROBOT-1).

TPS 05A contributes no new vocabulary anywhere; its value is reinforcing that the NSRRC Site, the Blu-Ice/DCSS-over-EPICS seam, and the MX Methods cover the cluster, not just 07A.

## Governance

*Who may act at TPS 05A and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSRRC Site](../nsrrc/index.md#safety-and-governance); on the beamline they surface through the actions they take. TPS 05A's governance is **identical to [TPS 07A](../tps-07a/notes.md#governance)'s**, because both beamlines share the one NSRRC Site: the same principals, the same LDAP-backed staff (`ldap://10.7.1.1`), and the same mandatory radiation-safety-training portal (`safetytraining.nsrrc.org.tw`). The human roster is not in public source (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSRRC Site. A TPS 05A beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. This is the same role kernel CORA seeds at every Site, and at 05A it is literally reused from 07A, both share the NSRRC Site, so the second beamline registers no new facility principals. That reuse is the point: the Access kernel scopes at the Site, not per-beamline.

The NSRRC mandatory training portal maps to CORA's **worldwide-invariant training axis**: a fact carried on the Access principals, not a separate Clearance kind (GOV-1).

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a collection, move the robot, change the energy, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer or its LDAP groups. It holds across the seam: a command CORA's EdgeConductor issues in place of DCSS (start an oscillation, drive a motor, arm the detector) is gated exactly as any spine command is. The facility proposal and cycle are a fact CORA's Campaign uses for custody.

### Unattended autonomous collection

TPS 05A's throughput model is unattended, the same as 07A: the ISARA robot mounts a crystal, the MD3 centres it (mesh scan), the EIGER2 collects, the robot unmounts, repeat. That loop is where CORA's custody and trust shapes earn their keep, each crystal threaded through the `Subject` aggregate so its identity and provenance is tracked, the exchange a Procedure gated by a Clearance (ROBOT-1). If an autonomous Agent were added to choose which crystal to collect or when a dataset is good enough, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

The PSS search-and-secure permit leaves that gate the hutch are not in public source (PSS-1) and are carried as a confirm.

## Model

*The developer's by-kind index: where each CORA aggregate's TPS 05A content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at TPS 05A |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (TPS-05A-OH optics, TPS-05A-EH experiment) |
| Facility (Federation); Zone, Conduit, Policy (Trust); Actor (Access) | [NSRRC Site](../nsrrc/index.md), [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other reverse-engineered beamlines and especially its sibling [TPS 07A](../tps-07a/notes.md#model). Left out on purpose:

- **No new Family.** TPS 05A reuses every Family TPS 07A binds: the graduated `Goniometer` for the MD3, `Camera` for the EIGER2 / OAV, `Monochromator`, `Filter`, `BeamStop`, `Shutter`, `Mirror`, `TemperatureController`, `LinearStage` / `MotionController`, plus the loose `StorageRing` and `PositionMonitor`. The only device-level difference from 07A is the EIGER2 size (9M vs 16M), a per-Asset fact.
- **No new Site, principals, or seam.** The NSRRC Site, its Access principals, and the Blu-Ice/DCSS-over-EPICS seam were all created by 07A; 05A reuses them unchanged. This is the deployment's whole point: demonstrating that the Site, the device-library, and the seam generalize across the MX cluster.
- **The ISARA robot as a Procedure.** Autonomous sample exchange is a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i24 / 07A / MX3 shape.
- **The frame egress and any mesh-scan compute.** The EIGER2 frame stream is a `TransferPort` leg into the Dataset of record; spot-scoring / indexing is `ComputePort` work, an Observe / Compute leg off the control seam (DET-1).
- **No new Capability or Method.** Rotation MX reuses the pending i03 Methods, recorded as the `TPS05A_*` Practices on the Site; 05A reinforces the case at a further MX deployment without coining any (TECH-1).
- **A verified PV namespace.** Unlike 07A (whose `07a:` / `07a-ES:` namespace was read from its control tree), 05A has no dedicated public tree, so its `05a:` / `05a-ES:` namespace is inferred by cluster convention and carried pending (PV-1), the fleet's most conservative PV posture.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the NSRRC / TPS 05A team to confirm. This model is reverse-engineered from public open source, but TPS 05A's source is thinner than [TPS 07A](../tps-07a/notes.md#open-questions)'s: there is no dedicated 05A control tree (the public `NSRRC_TPS05A_BeamMonitor` repo is an empty stub), so the device kit is read from the [SPXF facility pages](https://nsrrcspxf.github.io/nsrrcspxf/index.html) and the 2025 J. Synchrotron Rad. cluster paper, and the seam / PV model is inherited from the 07A reading. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Provenance (05A-specific)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PV-1 | Blocks-go-live | The EPICS PV namespace. 07A's `07a:` / `07a-ES:` was read from its control tree; 05A has no public tree, so its namespace is **inferred** as `05a:` / `05a-ES:` by cluster convention. Is that correct? | The 05A beamline namespace is `05a:` and the endstation `05a-ES:`, inferred, not verified. | The PV namespace for every Asset. |

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device / front-end source: TPS 05A is fed by a TPS undulator (per the SPXF page), but no source PV is in public source. | An insertion-device source, identity-only, no PV; the ring-current monitor stands in as the source representation. | The Source Asset and its PV. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. No PSS permit signals are in public source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names: which devices sit in the optics hutch versus the experiment hutch? Public source exposes no enclosure structure. | An optics hutch (DCM, mirrors) plus an experiment hutch (the MD3 / EIGER2 / robot). | The Enclosure set and roles. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-crystal monochromator crystal cut and exact range, and the attenuator foil set. | A Si DCM over ~5.7-20 keV and one Filter Asset, settings blank. | The Monochromator / Filter settings. |
| OPT-1 | Nice-to-have | The focusing optic and the microcrystallography spot size (not stated in public source for 05A). | A KB focusing mirror system (`KBMirrors`, Mirror family), configuration and spot blank. | The mirror Assets, spot size, and PVs. |
| ENERGY-1 | Nice-to-have | Does TPS 05A scan energy as the measurement (anomalous / MAD MX), or run fixed-energy per dataset? | Fixed-energy; the master energy axis is a setpoint. | The energy Capability decision. |

### Sample, detector, robot

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The MD3 microdiffractometer axis PV records, the full axis set, and the settling confirmation that 05A's live scan orchestration is Blu-Ice/DCSS and not a live MXCuBE deployment (the 2025 cluster paper says Blu-Ice/DCS for all three MX endstations; high confidence, but per-beamline confirmation is owed). | A `Goniometer` Asset on the EPICS floor; the DCSS-over-EPICS seam (the 07A / 2-BM pattern), not MXCuBE; PV records deployment config. | The Goniometer interface, axes, and the seam confirmation. |
| DET-1 | Blocks-go-live | The EIGER2 X 9M detector PV records, its SIMPLON REST endpoint, and any detector minimum-distance interlock (07A has one at 139 mm; 05A's is unknown). | An EIGER2 X 9M `Camera` commanded through the DCSS workflow; endpoint and interlock deployment config. | The detector interface and safety limit. |
| ENV-1 | Nice-to-have | The cryostream sample-cooling vendor and PV. | A `TemperatureController` Asset, settings blank. | The cryostream Model and PV. |
| ROBOT-1 | Nice-to-have | The ISARA sample-mounting robot (the same model as 07A). CORA would model autonomous sample exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the i03 / i24 / 07A / MX3 shape. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-exchange Procedure and Subject custody thread. |
| DIAG-1 | Nice-to-have | The beam-position / XBPM and OAV-camera channel maps and PVs. | Read-only beam-position (graduated catalog `PositionMonitor`) and OAV (`Camera`) probes; channel maps blank. | The diagnostic bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box firmware / IPs behind the endstation, goniometer-base, and detector stages. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Capabilities enter CORA's catalog, or stay deferred? The same owner-scope decision i03 opened; 05A reuses the pending `mx_data_collection` / `grid_scan` / `sample_exchange` Methods. | Methods deferred (pending Practices on the Site), no catalog Method coined. | The MX Capability scope. |
