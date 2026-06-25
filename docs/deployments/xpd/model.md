# Model

*The developer's by-kind index: where each CORA aggregate's XPD content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at XPD |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (28-ID-A optics, 28-ID-C experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new Family.** XPD is a reuse-and-reinforce deployment, the NSLS-II twin of Diamond i11 (powder diffraction) and i15-1 (total scattering / PDF): the flat panels bind `Camera`, the flux counters `FluxMonitor`, the sample environment `TemperatureController` (which i11 graduated, reinforced here at a second facility), the double-Laue monochromator `Monochromator`, the mirror `Mirror`, the pinhole `Aperture`, the exposure shutter `Shutter`.
- **The held `BeamPositionMonitor`.** The optics-hutch beam-position monitor binds the loose `BeamPositionMonitor` family that several APS and NSLS-II deployments use; it stays loose pending the sensor fold-vs-promote decision (DIAG-1), recorded in the promotion-review register.
- **No new Capability or Method.** Powder diffraction and total scattering sit on the deferred `powder_diffraction` / `total_scattering` Capabilities Diamond i11 and i15-1 left pending (TECH-1); XPD reinforces both without coining either and records no Practice. The azimuthal integration and PDF reduction are `ComputePort` work.
- **The autonomous sample robot.** Modelled as a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i15-1 autonomous-loop shape, not a new device family.
- **The high-resolution channel** alongside the modelled main PDF channel: the high-resolution monochromator (`Mono:HRM`, in the 28-ID-C hutch) and the downstream high-resolution endstation (28-ID-D) are noted and deferred together (ENDSTATION-1), the way SRX deferred its micro endstation and 32-ID modelled one of several instruments.
- **The calibration diffractometer (`Dif:2`)** and its Ecal wavelength-calibration routine (scanning against a standard to fit the beam wavelength) are a routine powder/PDF operation, deferred to a named question (CALIB-1) rather than modelled at this design phase. The dormant multi-analyzer stage (`MAD:DMS`) and the mono beam-defining slits (`Slt:MB1` / `Slt:MB2`) are deferred alongside it.
- **The in-situ / operando accessories**: a QEPro UV-Vis spectrometer read in parallel with the diffraction pattern (a distinct optical-spectroscopy modality, not a `Camera`), the gas switcher, and the flash-sintering / electrochemistry power system, deferred to a named question (OPERANDO-1); the UV-Vis channel would need its own family decision when it lands.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
