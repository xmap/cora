# Detector

*The hemispherical electron energy analyzer and the beam-current flux monitors. First cut; PVs read from the profile collection, carried confirm.*

ESM detection is photoemission: the Scienta SES hemispherical electron energy analyzer collects the photoelectrons and disperses them by kinetic energy and emission angle, while the QuadEM electrometers read the incident-beam current. They are modelled in the detection stage of the [descriptor](../inventory.md).

The analyzer binds the **`ElectronAnalyzer` Family** (graduated across ESM + SST; no photon-detector Family fits an electron spectrometer; see [Model](../model.md#what-this-deployment-graduates)); the flux monitors reuse the catalog `FluxMonitor`.

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `ElectronAnalyzer` | `ElectronAnalyzer` | Scienta SES hemispherical analyzer; pass-energy / lens-mode / kinetic-energy-window controls; the ARPES detector (`ARPES-1`) |
| `FluxMonitor_Upstream` / `FluxMonitor_Branch` | `FluxMonitor` | QuadEM electrometers (qem01-12); I0 / drain-current monitors (`DET-1`) |

The analyzer is the defining instrument of the beamline: it measures electrons, not photons, so it sat outside the photon-detector families CORA had (`Camera`, `EnergyDispersiveSpectrometer`, `FluxMonitor`). ESM introduced the `ElectronAnalyzer` Family for it, and it graduated into the catalog once SST (NSLS-II 7-ID HAXPES) earned the second Scienta SES; a future ESM XPEEM branch would reinforce it. Its lens modes, pass energies, and acquisition modes are `ARPES-1`.

## Families

`ElectronAnalyzer` for the SES (graduated across ESM + SST). Reused from the catalog: `FluxMonitor` for the QuadEM monitors. The flux-monitor channel map is `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
