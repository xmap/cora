# Model

*The developer's by-kind index: where each CORA aggregate's FMX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at FMX |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (17-ID-A optics, 17-ID-C experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Subject (the crystal custody thread) | [Governance](governance.md#the-autonomous-loop-under-custody) (deferred, ROBOT-1) |
| Procedure, Recipe, Caution, Supply, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What this deployment graduates: nothing (and that is the finding)

FMX is a clean **pure-reuse** deployment. As CORA's second MX beamline (after i03), its finding is that the MX vocabulary i03 earned generalizes to a second, independent facility with no new modelling: the graduated `Goniometer` (the single-omega micro-goniometer), the `Camera` (the Eiger), the graduated `Transfocator` (the CRL), the `Monochromator`, the `Mirror` (HFM + KB), the `Filter` (the BCU / RI attenuators), the `BeamStop`, the `FluxMonitor`, and the loose `Backlight` and `BeamPositionMonitor` all bind unchanged. The robot is one Positioner-presenting Asset, not a new Family (the i03 / 19-BM precedent). The one small modelling step beyond i03 is binding the Mercury fluorescence detector to the catalog `EnergyDispersiveSpectrometer` (i03 deferred its fluorescence detector); no new Family is coined.

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring i03 and the other NSLS-II beamlines. Left out on purpose:

- **No catalog change.** FMX graduates nothing and coins nothing. The three MX Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) stay pending: FMX is their second consumer (after i03), which strengthens but does not force coining (Methods have no mechanical promotion, the `energy_scan` deferral discipline; TECH-1). The loose `Backlight` reaches its third sighting (i03 + i24 + FMX) but stays held, fold-vs-promote still open (DET-1).
- **The robot is not a Family.** The sample-changing robot is one Positioner-presenting Asset, gated by a Clearance, loading a `Subject`, vendor in a bound Model; not a new SampleChanger Family (the i03 / 19-BM precedent, adversarially verified there; ROBOT-1).
- **The autonomous loop and the Subject custody thread.** The unattended exchange loop is a Procedure over the spine threaded through the `Subject` aggregate; it is the genuinely non-obvious MX modelling, deferred with i03 (ROBOT-1).
- **Sample cryo-cooling.** The cold-gas cryostream is not exposed in the profile collection (an annealer / thaw-air actuator is), so it is deferred (CRYO-1); it would bind `TemperatureController` (the i03 cryostream precedent) when its PV is supplied.
- **The fixed-target serial mode.** The chip-scanner serial-crystallography raster is named but not modelled; it would reuse the `serial_crystallography` Method (i24 / LCLS-MFX), deferred (SERIAL-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
