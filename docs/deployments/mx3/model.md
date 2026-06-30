# Model

*The developer's by-kind index: where each CORA aggregate's MX3 content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at MX3 |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (MX3-OH optics, MX3-EH experiment) |
| Facility (Federation); Zone, Conduit, Policy (Trust); Actor (Access) | [Australian Synchrotron Site](../as/index.md), [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other reverse-engineered beamlines. Left out on purpose:

- **No new Family.** MX3's novelty is the Site and its control plane, not its devices: the MD3 goniometer binds the graduated `Goniometer` (the i03 MX precedent), the detectors `Camera`, the DMM `Monochromator`, the cryojet `TemperatureController`, the attenuator `Filter`, the flux monitor `FluxMonitor`, the beamstop `BeamStop`, the shutters `Shutter`, the stages `LinearStage` / `MotionController`.
- **The reused loose families.** `StorageRing` (the ring-current monitor), `BeamPositionMonitor` (the beam-position monitor), and `Backlight` (the MD3 backlight) are bound loose, each already allowlisted from earlier deployments; MX3 coins no new loose family.
- **The heterogeneous control plane.** MX3 drives EPICS, the MXCuBE Exporter protocol (MD3), the SIMPLON REST API (Eiger), and a TCP robot client (ISARA). This is modelled as `ControlPort` adapters, not new aggregates; the three non-EPICS devices carry no PV and route their host / endpoint to deployment config (GONIO-1, DET-1, ROBOT-1). See [Controls](equipment/controls.md).
- **The ISARA robot as a Procedure.** Autonomous sample exchange is a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i24 shape, not a new device family.
- **The beam-steering controller.** The closed-loop PID steering paired with the BPM (`MX3DAQIOC04:`) fits no existing family cleanly; the BPM half binds `BeamPositionMonitor` and the steering controller is a deferred new-device question (STEER-1).
- **No new Capability or Method.** Rotation MX reuses the pending i03 Methods (`mx_data_collection` / `grid_scan` / `sample_exchange`), recorded as Practices on the Site; MX3 reinforces the case without coining any (TECH-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
