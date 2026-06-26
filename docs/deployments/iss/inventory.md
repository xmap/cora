# Inventory

*The CORA Asset model for ISS: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/iss/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against the `NSLS2/iss-profile-collection` `startup/*.py` device classes). No vendor Model is bound: part numbers are not in the profile collection. ISS introduces no new loose family, and it brings the crystal `EmissionSpectrometer` family to its **second** sighting (after LCLS-MFX), which GRADUATED it into the catalog (SPEC-1); the one loose family it reuses is the `BeamPositionMonitor` (held, DIAG-1); see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `ISS` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `ISS` | (root) | `XF:08ID*` | bound to the NSLS-II Site |
| `Undulator` | InsertionDevice | (not in source) | 8-ID in-vacuum undulator source (SRC-1) |
| `FrontEndSlit` | Slit | `FE:C08A-OP{Slt:12}` | front-end white-beam slit |
| `FrontEndShutter` | Shutter | `XF:08ID-PPS{Sh:FE}` | front-end photon shutter |
| `PhotonShutter` | Shutter | `XF:08IDA-PPS{PSh}` | photon shutter into the optics hutch |
| `HighHeatLoadMonochromator` | Monochromator | `XF:08IDA-OP{Mono:HHM}` | trajectory fly-scan DCM (energy) |
| `HighResolutionMonochromator` | Monochromator | `XF:08IDA-OP{Mono:HRM}` | high-resolution mono |
| `CollimatingMirror1` | Mirror | `XF:08IDA-OP{Mir:1-CM}` | collimating mirror (Rh/Si/Pt) |
| `CollimatingMirror2` | Mirror | `XF:08IDA-OP{Mir:2-CM}` | collimating mirror + bender (Pt/Rh) |
| `FocusingMirror` | Mirror | `XF:08IDA-OP{Mir:FM}` | focusing mirror + bender (Pt/Rh) |
| `HarmonicRejectionMirror` | Mirror | `XF:08IDB-OP{Mir:HRM}` | harmonic-rejection mirror (Si/Pt/Rh) |
| `FilterBox` | Filter | `XF:08IDA-OP{Fltr:FB}` | five-filter attenuator box |
| `HutchSlit` | Slit | `XF:08IDB-OP{Slt}` | experiment-hutch beam-defining slit |
| `EnergyAxis` | PseudoAxis | (computed) | master energy axis (trajectory) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:08IDA-BI{BPM:FM}` | beam-position diagnostics |
| `SampleStage` | LinearStage | `XF:08IDB-OP{Stage:Sample}` | X/Y/Z sample translation |
| `SampleGoniometer` | Goniometer | `XF:08IDB-OP{Gon:Th}` | sample rotation |
| `ReferenceFoilWheel` | RotaryStage | `XF:08IDB-OP{FoilWheel1:Rot}` | energy-calibration foil wheel |
| `SampleTemperature` | TemperatureController | `XF:08ID-ES{LS:331-1}:` | Lakeshore 331 thermal control |
| `IonChambers` | FluxMonitor | `XF:08IDB-CT{Amp-I0}` | I0/It/Ir/If transmission chambers |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:08IDB-ES{Xsp:1}:` | 4-channel Xspress3 SDD |
| `AreaDetector` | Camera | `XF:08IDB-ES{Det:PIL1}:` | Pilatus 100k pixel detector |
| `JohannSpectrometer` | EmissionSpectrometer | `XF:08IDB-OP{HRS:1}` | Johann XES / HERFD spectrometer |
| `VonHamosSpectrometer` | EmissionSpectrometer | `XF:08IDB-OP{MC:3-Ax}` | von Hamos XES spectrometer |
| `TrajectoryMotionController` | MotionController | `XF:08IDA-OP{MC:06}` | Delta-Tau HHM trajectory controller |
| `AnalogPizzaBox` | TimingController | `XF:08IDB-CT{PBA:1}:` | synchronized ADC + trigger (fly-scan) |

Every family is in the catalog except the loose `BeamPositionMonitor` (held); the crystal `EmissionSpectrometer` GRADUATED this PR (its second sighting, after LCLS-MFX's von Hamos); ISS coins no new loose family. The two crystal emission spectrometers (`JohannSpectrometer`, `VonHamosSpectrometer`) are the signature ISS instruments and the reuse-and-graduate point.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the ISS team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator identity, period, gap range | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | all enclosures | `unknown-pending-confirmation` | (PSS-1) |
| HHM / HRM crystal cuts, reflections, ranges | `HighHeatLoadMonochromator` / `HighResolutionMonochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Emission-spectrometer crystal cut, Rowland radius, analyzer-crystal composition | `JohannSpectrometer` / `VonHamosSpectrometer` | `unknown-pending-confirmation` | (SPEC-1) |
| Ion-chamber channel map, Xspress3 element count, Pilatus per-spectrometer roster | `IonChambers` / `FluorescenceDetector` / `AreaDetector` | `unknown-pending-confirmation` | (DET-1) |
| Sample-environment units (Lakeshore, cryostat / furnace) | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| Ion-chamber fill-gas flow and the in-situ environment | `IonChambers` | `unknown-pending-confirmation` | (ENV-1) |
| Beam-position channel map and fold-vs-promote hold | `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | `TrajectoryMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
