# Model

*The developer's by-kind index: where each CORA aggregate's AMX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at AMX |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (17-ID-A optics, 17-ID-B experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Subject (the crystal custody thread) | [Governance](governance.md#the-autonomous-loop-under-custody) (deferred, ROBOT-1) |
| Procedure, Recipe, Caution, Supply, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What this deployment graduates: nothing (and that is the finding)

AMX is a clean **pure-reuse** deployment, completing the NSLS-II MX pair as FMX's sibling. Its finding is that the MX vocabulary generalizes across a third independent beamline with no new modelling: the graduated `Goniometer` (single-omega micro-goniometer), the `Camera` (Eiger), the `Monochromator` (here vertical), the `Mirror` (tandem-deflection + KB), the `Filter` (BCU attenuator), the `BeamStop`, the `EnergyDispersiveSpectrometer` (Mercury), the `FluxMonitor` (Keithley), the `TimingController` (Zebra), and the loose `BeamPositionMonitor` all bind unchanged. The robot is one Positioner-presenting Asset, not a new Family (the i03 / 19-BM / FMX precedent).

### FMX-vs-AMX differences

The 17-ID pair is not identical, and the differences exercise the modelling: AMX uses a **vertical** DCM (FMX horizontal), **tandem-deflection** mirrors (FMX a horizontal focusing mirror), an **EMBL** robot, and has **no CRL transfocator** and **no on-axis backlight** in source. Each is a per-Asset settings or device-presence difference, not a Family split; both beamlines bind the same Families.

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring FMX and the other NSLS-II beamlines. Left out on purpose:

- **No catalog change.** AMX graduates nothing and coins nothing. The three MX Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) stay pending: AMX is their third consumer, which strengthens but does not coin them. Methods coin on a **conduct-path** (a deployment that runs them), not on a sighting count, which is why even at n=3 they defer (the `energy_scan` discipline; TECH-1). Coining them is a follow-on that needs an **MX conduct-path scenario** (event-sourced spine work), the genuine MX-graduation path.
- **The robot is not a Family.** The EMBL sample-changing robot is one Positioner-presenting Asset, gated by a Clearance, loading a `Subject`, vendor in a bound Model; not a new SampleChanger Family (the i03 / 19-BM precedent, ROBOT-1).
- **The autonomous loop and the Subject custody thread.** The unattended exchange loop is a Procedure over the spine threaded through the `Subject` aggregate; deferred with i03 / FMX (ROBOT-1).
- **Sample cryo-cooling.** The cold-gas cryostream is not exposed in the profile collection, so it is deferred (CRYO-1); it would bind `TemperatureController` (the i03 cryostream precedent) when its PV is supplied.
- **The area detector PV.** The Eiger is not exposed in the AMX profile collection; it is carried `Camera` confirm-only (DET-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
