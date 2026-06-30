# Model

*The developer's by-kind index: where each CORA aggregate's PDF content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at PDF |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (`EnergyAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (28-ID-1-A optics, 28-ID-1-B endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring its twin [XPD](../xpd/model.md) and the other reverse-engineered deployments. Left out on purpose:

- **No new Family.** PDF is a reuse-and-reinforce deployment: the flat-panel and pixel detectors bind `Camera`, the photodiode `FluxMonitor`, the thermal cluster `TemperatureController`, the side-bounce mono `Monochromator`, the focusing mirror `Mirror`, the spinner `Goniometer`, the slits `Slit`, the fast shutter `Shutter`, the beamstops `BeamStop`, the detector and sample-environment stages `LinearStage`, the master energy a `PseudoAxis`. Nothing graduates and the catalog is unchanged.
- **The held loose family.** The `StorageRing` current readback is a loose supply observation (machine state), never an Asset Family.
- **No new Capability or Method.** Total scattering / PDF and powder diffraction sit on the deferred `total_scattering` / `powder_diffraction` Methods Diamond i11 and i15-1 left pending (`TECH-1`); PDF reinforces them at a second NSLS-II endstation without coining either, and records no Practice until they land. The PDF reduction (azimuthal integration and the Fourier transform to G(r)) is `ComputePort` work, not a Method.
- **The gas-handling and humidity rig.** Present in the profile collection but carried deferred (`ENV-1`): a design-phase scaffold models the thermal environment that is settled (`TemperatureController`) and defers the in-situ gas / humidity actuators until they earn modelling, the same discipline the other deployments follow.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
