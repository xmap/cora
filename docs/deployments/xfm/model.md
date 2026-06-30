# Model

*The developer's by-kind index: where each CORA aggregate's XFM content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at XFM |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (4-BM-A optics, 4-BM-C endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What this deployment graduates: nothing

XFM is a clean **pure-reuse** scanning-XRF deployment, the second after 2-ID. It coins no Family and graduates nothing: the multi-element silicon-drift fluorescence detectors (the Xspress3 and the Maia) reuse `EnergyDispersiveSpectrometer` (graduated when 2-ID and 7-BM shared it), the raster stage reuses `LinearStage`, the scaler I0 channels reuse `FluxMonitor` (graduated in #353), the bending-magnet source binds the loose `Beam` PhotonBeam supply (the 2-BM / BMM precedent), and the monochromator / focusing optic / slits bind the catalog `Monochromator` / `Mirror` / `Slit`. The scanning XRF technique reuses the `scanning_fluorescence_microscopy` Method 2-ID left pending: XFM is its second consumer, which strengthens but does not coin it.

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring 2-ID / SRX and the other NSLS-II beamlines. Left out on purpose:

- **No catalog change.** XFM graduates nothing and coins nothing. `scanning_fluorescence_microscopy` stays pending (2-ID + XFM = 2 consumers; Methods have no mechanical promotion, the `energy_scan` deferral discipline; METHOD-1). XANES microspectroscopy leans on the deferred `energy_scan` Capability (ENERGY-1), no practice recorded.
- **The endstation-only profile.** The public profile collection exposes only the raster stage, the Xspress3, the scaler, and the Maia (in a bypass file). The bending-magnet source, the monochromator, the focusing optic, and the shutters are not in the profile, so they are carried confirm-only with no PV (no fabricated PVs; PROFILE-1). The model is honest about being thin: it asserts the device classes a BM XRF / XANES microprobe must have, with their handles pending the team.
- **The Maia detector.** XFM's signature fast continuous-mapping array (`XFM:MAIA`) is read from the bypass profile (`rvt/bypass40-maia.py`), not the active startup; it is modelled as a second `EnergyDispersiveSpectrometer` Asset and flagged (MAIA-1).
- **XRF-tomography.** Out of scope: the profile exposes an X/Y/Z raster stage but no rotation axis, so the raster-x-rotation XRF-tomography (the SRX shape) is not modelled (TECH-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
