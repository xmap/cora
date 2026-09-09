# Notes

## Techniques

*What CORA would run at MX3: rotation macromolecular crystallography, each technique a [Catalog](../../catalog/methods.md) Method bound through an [Australian Synchrotron Practice](../as/index.md#the-techniques-adapted-here). MX3 reuses the MX Methods Diamond [I03](../i03/notes.md#techniques) introduced, so it coins nothing new.*

MX3's technique, rotation MX, is the macromolecular-crystallography shape CORA already saw at i03 (and, in its serial form, at i24 and LCLS-MFX). The Methods render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog, exactly as at i03.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the MD3 goniometer + the Eiger; the i03 Method, pending (TECH-1) |
| Grid scan | `grid_scan` | fast grid scan for sample location / centring on the MD3 (TECH-1) |
| Autonomous sample exchange | `sample_exchange` | the ISARA robot load / centre / collect / unmount loop, a Procedure over the spine (ROBOT-1) |

All three are recorded as pending [Practices](../as/index.md#the-techniques-adapted-here) on the Australian Synchrotron Site, reusing the same Method names Diamond i03 carries.

### Why the Methods are reused, not coined

MX3 brings a new Site, not a new technique. Rotation MX, grid-scan centring, and robot sample exchange are the i03 shapes, so MX3 binds the same pending Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) rather than coining anything; whether those Methods enter the catalog is the cross-facility owner-scope decision i03 opened (TECH-1), and MX3 reinforces the case at a further facility (after Diamond i03 and NSLS-II FMX / AMX). The device Roles already exist (the MD3 presents Positioner via the graduated `Goniometer`, the Eiger presents Detector via `Camera`), so nothing new is needed in the device model either.

The autonomous sample exchange reuses the i03 / i24 autonomous-loop shape: a Procedure over the spine threaded through `Subject` custody, not a new device family (ROBOT-1). Indexing and integration of the diffraction frames are `ComputePort` work, not beamline Methods.

The genuinely new thing MX3 contributes is below the technique layer: a sixth Site and a heterogeneous control plane (see [Controls](controls.md)), which the technique vocabulary rides over unchanged.

## Governance

*Who may act at MX3 and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [Australian Synchrotron Site](../as/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the device library (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the Australian Synchrotron Site. An MX3 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. This is the same role kernel CORA seeds at every Site; MX3 being a new Site is exactly the test that the Federation / Access kernel ports unchanged.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a collection, move the robot, change the energy, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer, and it holds the same across all four control planes (a command to the Eiger over REST or the robot over TCP is gated exactly as an EPICS motor move is). The facility proposal and cycle are a fact CORA's Campaign uses for custody.

### Unattended autonomous collection

MX3's throughput model is unattended: the ISARA robot mounts a crystal, the MD3 centres it, the Eiger collects, the robot unmounts, repeat. That loop is where CORA's custody and trust shapes earn their keep, each crystal threaded through the `Subject` aggregate so its identity and provenance is tracked, the exchange a Procedure gated by a Clearance (ROBOT-1). If an autonomous Agent were added to choose which crystal to collect or when a dataset is good enough, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's MX3 content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at MX3 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (MX3-OH optics, MX3-EH experiment) |
| Facility (Federation); Zone, Conduit, Policy (Trust); Actor (Access) | [Australian Synchrotron Site](../as/index.md), [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other reverse-engineered beamlines. Left out on purpose:

- **No new Family.** MX3's novelty is the Site and its control plane, not its devices: the MD3 goniometer binds the graduated `Goniometer` (the i03 MX precedent), the detectors `Camera`, the DMM `Monochromator`, the cryojet `TemperatureController`, the attenuator `Filter`, the flux monitor `FluxMonitor`, the beamstop `BeamStop`, the shutters `Shutter`, the stages `LinearStage` / `MotionController`.
- **The reused loose family.** `StorageRing` (the ring-current monitor) is bound loose, already allowlisted from earlier deployments; MX3 coins no new loose family. The MD3 backlight binds the catalog `Backlight` Family (graduated across the MX / imaging fleet). The beam-position monitor binds the graduated catalog `BeamPositionMonitor`, which presents `Sensor`, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux.
- **The heterogeneous control plane.** MX3 drives EPICS, the MXCuBE Exporter protocol (MD3), the SIMPLON REST API (Eiger), and a TCP robot client (ISARA). This is modelled as `ControlPort` adapters, not new aggregates; the three non-EPICS devices carry no PV and route their host / endpoint to deployment config (GONIO-1, DET-1, ROBOT-1). See [Controls](controls.md).
- **The ISARA robot as a Procedure.** Autonomous sample exchange is a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i24 shape, not a new device family.
- **The beam-steering controller.** The closed-loop PID steering paired with the BPM (`MX3DAQIOC04:`) fits no existing family cleanly; the BPM half binds `PositionMonitor` and the steering controller is a deferred new-device question (STEER-1).
- **No new Capability or Method.** Rotation MX reuses the pending i03 Methods (`mx_data_collection` / `grid_scan` / `sample_exchange`), recorded as Practices on the Site; MX3 reinforces the case without coining any (TECH-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the Australian Synchrotron / MX3 team to confirm. This model is reverse-engineered from public open source (the [`AustralianSynchrotron/mx3-beamline-library`](https://github.com/AustralianSynchrotron/mx3-beamline-library) device library): the EPICS PVs are read from it, but vendor identities, physical positions, the source, and the non-EPICS subsystem endpoints are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device / front-end source: MX3 is an undulator beamline, but no source PV is in the library, only the storage-ring current monitor (`SR11BCM01:CURRENT_MONITOR`). | An insertion-device source, identity-only, no PV; the ring-current monitor stands in as the source representation. | The Source Asset and its PV. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the photon-shutter enable / status PVs (`MX3FE01SHT01`, `MX3BLSH01SHT01`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names: which devices sit in the optics hutch versus the experiment hutch? The library exposes no enclosure structure. | An optics hutch plus an experiment hutch (the MD3 / Eiger / robot). | The Enclosure set and roles. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-multilayer monochromator coating stripes and range, and the attenuator foil set. Both (`MX3MONO01`, `MX3FLT05`) are in source. | One Monochromator and one Filter Asset, settings blank. | The Monochromator / Filter settings. |
| OPT-1 | Nice-to-have | The beam-conditioning optics not in the library: mirrors and any standalone slits (the `devices/optics.py` stub is empty). | None modelled; the `MX3FLT05` unit carries the beam-size readback. | The mirror / slit Assets. |
| ENERGY-1 | Nice-to-have | Does MX3 scan energy as the measurement (anomalous / MAD MX), or run fixed-energy per dataset? | Fixed-energy; the master energy axis is a setpoint. | The energy Capability decision. |

### Sample, detector, robot

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The MD3 microdiffractometer host / port (it is driven over the MXCuBE Exporter protocol at `MD3_ADDRESS:MD3_PORT`, an env-config default in the library, not a baked PV), and the full axis set behind the Exporter property names. | A `Goniometer` Asset (omega / kappa / phi + centring / alignment) over the Exporter seam; the host is deployment config. | The Goniometer interface and axes. |
| DET-1 | Blocks-go-live | The DECTRIS Eiger model (16M / 4M) and its SIMPLON REST endpoint (`SIMPLON_API`, an env-config default in the library). | An Eiger `Camera` over the SIMPLON REST seam; the endpoint is deployment config. | The detector Model and interface. |
| ROBOT-1 | Nice-to-have | The ISARA sample-mounting robot (a TCP client at `ROBOT_HOST`, mount / unmount trajectories gated on the MD3 state). CORA would model autonomous sample exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the i03 / i24 loops. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-exchange Procedure and Subject custody thread. |
| DIAG-1 | Nice-to-have | The flux and beam-position channel maps; the `PositionMonitor` Family is settled (graduated catalog Family presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux). | Read-only flux (`FluxMonitor`) and beam-position (graduated catalog `PositionMonitor`) probes; channel maps blank. | The FluxMonitor / PositionMonitor bindings. |
| STEER-1 | Nice-to-have | The closed-loop beam-steering controller (`MX3DAQIOC04:` PID + DAC paired with the BPM): is it a device Family of its own, or a settings-only feedback variant? It fits no existing family cleanly. | The BPM half binds the graduated catalog `PositionMonitor`; the PID steering controller is named but not modelled. | The beam-steering device boundary. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box firmware / IPs (the Australian Synchrotron Power Brick PMAC behind the `MX3STG..MOT..` axes). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Capabilities (rotation data collection, grid scan) enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i03 opened; MX3 reuses the pending `mx_data_collection` / `grid_scan` / `sample_exchange` Methods. | Methods deferred (pending Practices on the Site), no catalog Method coined. | The MX Capability scope. |
