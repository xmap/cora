# Detector

*The Eiger area detector, the fluorescence detector, the beamstop, and the beam monitors. PVs verified against the fmx-profile-collection startup files.*

FMX's science detector is the Eiger, reading the rotation diffraction; a Mercury multi-element detector reads fluorescence to pick the absorption edge for anomalous data collection.

| Asset | Family | PV | What it serves |
| --- | --- | --- | --- |
| `AreaDetector` | Camera | `XF:17IDC-ES:FMX{Det:Eig16M}` | rotation diffraction (the MX data) |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:17IDC-ES:FMX{Det:Mer}` | XRF edge selection (anomalous MX) |
| `BeamStop` | BeamStop | `XF:17IDC-ES:FMX{BS:1}` | blocks the direct beam ahead of the Eiger |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:17IDA-BI:FMX{BPM:1}` | beam-position diagnostics |
| `FluxMonitor` | FluxMonitor | `XF:17IDC-BI:FMX{Keith:1}` | beam-intensity photocurrent (I0) |

## The Eiger

The `AreaDetector` is an Eiger 16M pixel-array detector (`XF:17IDC-ES:FMX{Det:Eig16M}`, with a detector cover at `XF:17IDC-ES:FMX{Det:FMX-Cover}`); it reuses the `Camera` family (Detector Role), as i03's Eiger does. Its threshold energy, beam centre, and exact model are calibration to confirm (DET-1). The detector frames flow through the LSDC / mxtools data plane (the `MXFlyer`), referenced by CORA as a Dataset rather than re-modelled.

## The fluorescence detector

The `FluorescenceDetector` is a Mercury multi-element detector (`XF:17IDC-ES:FMX{Det:Mer}`), an energy-dispersive multi-channel analyzer that reads the XRF spectrum so the operator can pick the absorption edge for SAD / MAD anomalous phasing. It reuses the catalog `EnergyDispersiveSpectrometer` family (a small modelling step beyond i03, which deferred its fluorescence detector); element count and ROI map are pending (DET-1).

## Beam monitors

The `BeamStop` reuses `BeamStop`. The `BeamPositionMonitor` binds the loose `BeamPositionMonitor` family (the Prosilica BPM cameras and the sector XBPM `SR:C17-BI{XBPM:2}` for photon local feedback; held, DIAG-1). The `FluxMonitor` is a Keithley picoammeter reading the I0 photocurrent, reusing `FluxMonitor`.
