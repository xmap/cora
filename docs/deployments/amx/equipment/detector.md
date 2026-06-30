# Detector

*The Eiger area detector, the fluorescence detector, the beamstop, and the beam monitors. PVs verified against the amx-profile-collection startup files.*

AMX's science detector is the Eiger, reading the rotation diffraction; a Mercury multi-element detector reads fluorescence to pick the absorption edge for anomalous data collection.

| Asset | Family | PV | What it serves |
| --- | --- | --- | --- |
| `AreaDetector` | Camera | (not in profile) | rotation diffraction (the MX data, DET-1) |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:17IDB-ES:AMX{Det:Mer}` | XRF edge selection (anomalous MX) |
| `BeamStop` | BeamStop | `XF:17IDB-ES:AMX{BS:1}` | blocks the direct beam ahead of the Eiger |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:17IDA-BI:AMX{BPM:1}` | beam-position diagnostics |
| `FluxMonitor` | FluxMonitor | `XF:17IDB-BI:AMX{Keith:1}` | beam-intensity photocurrent (I0) |

## The Eiger

The `AreaDetector` is the Eiger pixel-array detector (the MX science detector); it reuses the `Camera` family (Detector Role), as i03's and FMX's Eigers do. Unlike FMX, the AMX profile collection does not expose the Eiger PV, so it is carried confirm-only: model, beam centre, and threshold energy are pending (DET-1). The detector frames flow through the LSDC / mxtools data plane, referenced by CORA as a Dataset rather than re-modelled.

## The fluorescence detector

The `FluorescenceDetector` is a Mercury multi-element detector (`XF:17IDB-ES:AMX{Det:Mer}`), an energy-dispersive multi-channel analyzer that reads the XRF spectrum so the operator can pick the absorption edge for SAD / MAD anomalous phasing. It reuses the catalog `EnergyDispersiveSpectrometer` family; element count and ROI map are pending (DET-1).

## Beam monitors

The `BeamStop` reuses `BeamStop`. The `BeamPositionMonitor` binds the loose `BeamPositionMonitor` family (the four-quadrant BPMs `XF:17IDA-BI:AMX{BPM:1}`, `XF:17IDB-BI:AMX{BPM:2 / BPM:3}`; held, DIAG-1). The `FluxMonitor` is a Keithley picoammeter reading the I0 photocurrent, reusing `FluxMonitor`.
