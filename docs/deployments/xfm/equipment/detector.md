# Detector

*The fluorescence detectors that make the XRF maps, and the flux scaler. PVs verified against the xfm-profile-collection startup files.*

XFM reads the fluorescence spectrum at each raster point on a multi-element silicon-drift detector; a Maia array enables fast continuous mapping. The scaler counts the I0 flux for normalization.

| Asset | Family | PV | What it serves |
| --- | --- | --- | --- |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:04BMC-ES{x3m:1}:` | step / fly XRF mapping (Xspress3 SDD) |
| `MaiaDetector` | EnergyDispersiveSpectrometer | `XFM:MAIA` | fast continuous XRF mapping (Maia array) |
| `FluxMonitor` | FluxMonitor | `XF:04BM-ES:2{Sclr:1}` | I0 / flux normalization (SIS3820 scaler) |

## The fluorescence detectors

The `FluorescenceDetector` is a four-channel silicon-drift detector read by an Xspress3 mini (`XF:04BMC-ES{x3m:1}:`, channels C1-C4 with per-channel ROIs and an HDF5 stream); it is the primary XRF-mapping detector and reuses the `EnergyDispersiveSpectrometer` family, the same Family 2-ID and SRX bind for their SDDs. Element count and ROI map are to confirm (DET-1).

The `MaiaDetector` is XFM's signature instrument: a large (hundreds-of-element) detector array that reads fluorescence continuously during a fly-scan, enabling fast, high-definition element maps. It reuses the `EnergyDispersiveSpectrometer` family (a large continuous-readout array is a per-Asset variant of the energy-dispersive Sensor, not a new Family). It is read from the bypass profile (`rvt/bypass40-maia.py`), not the active startup, so its element count and live status are flagged to confirm (MAIA-1).

## The flux scaler

The `FluxMonitor` is the SIS3820 scaler (`XF:04BM-ES:2{Sclr:1}`) counting the I0 / flux channels that each map pixel is normalized against; it reuses the `FluxMonitor` family (graduated in #353). The full channel map is to confirm (DIAG-1).
