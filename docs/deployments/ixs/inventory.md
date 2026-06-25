# Inventory

*The CORA Asset model for the operational core of IXS modelled today: the planned device tree and what still needs confirming.*

This cut models the `XF:10IDA/B/C` optics and the `XF:10IDD` IXS endstation; the simulated devices and the legacy SPEC macros are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/ixs/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. IXS, as the first hard inelastic-scattering beamline, introduces one device class no existing Family covers, the crystal energy analyzer, which binds a loose `EnergyAnalyzer` Family held at n=1 and graduates nothing (see [Model](model.md#new-loose-families)). Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `IXS` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `IXS` | `Unit` | (root) | - | bound to the NSLS-II Site; sector 10-ID |
| `Undulator` | `Device` | InsertionDevice | 10-ID-A | IVU22 in-vacuum undulator, gap (SRC-1) |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring current, observe-only (MACHINE-1) |
| `OrbitFeedback` | `Device` | (deferred) | - | source-orbit feedback, modelling deferred (FEEDBACK-1) |
| `FrontEndSlit` | `Device` | Slit | 10-ID-A | front-end beam-defining slit (OPT-2) |
| `Transfocator` | `Device` | Transfocator (loose) | 10-ID-A | front-end CRL transfocator (CRL-1) |
| `Monochromator` | `Device` | Monochromator | 10-ID-A | Si(111) double-crystal mono (MONO-1) |
| `IncidentEnergy` | `Device` | PseudoAxis | 10-ID-A | incident-energy axis, DCM + undulator gap (MONO-1) |
| `MonoSlit` | `Device` | Slit | 10-ID-A | post-DCM beam-defining slit (OPT-2) |
| `BeamPositionMonitor_A` | `Device` | BeamPositionMonitor (loose) | 10-ID-A | beam-position monitor + diagnostic foil (DIAG-1) |
| `HighResolutionMonochromator` | `Device` | Monochromator | 10-ID-B | HRM2 high-resolution crystal mono (HRM-1) |
| `HighResolutionEnergy` | `Device` | PseudoAxis | 10-ID-B | meV energy-transfer scan axis (HRM-1) |
| `SecondarySourceAperture` | `Device` | Slit | 10-ID-B | secondary source aperture, driven blades (OPT-2) |
| `TransportSlit` | `Device` | Slit | 10-ID-C | transport beam-defining slit (OPT-2) |
| `Table` | `Device` | Table | 10-ID-C | support / positioning table |
| `BeamPositionMonitor_C` | `Device` | BeamPositionMonitor (loose) | 10-ID-C | beam-position monitor + diagnostic foil (DIAG-1) |
| `VerticalFocusingMirror` / `HorizontalFocusingMirror` | `Device` | Mirror | 10-ID-D | KB focusing mirrors (OPT-1) |
| `EndstationSlit` | `Device` | Slit | 10-ID-D | endstation beam-defining slit (OPT-2) |
| `Pinhole` | `Device` | Aperture | 10-ID-D | positioned focusing pinhole (PH-1) |
| `AbsorberWheel` | `Device` | Filter | 10-ID-D | discrete absorber-foil wheel |
| `OpticsManipulator` | `Device` | Hexapod | 10-ID-D | six-DOF coupled optics manipulator (MCM-1) |
| `SampleTable` / `SampleEnvironment` | `Device` | LinearStage | 10-ID-D | sample table + environment translations (SAMPLE-1) |
| `Spectrometer` | `Device` | Goniometer | 10-ID-D | six-circle scattering arm, sets Q (ANALYZER-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | 10-ID-D | six-circle H/K/L reciprocal-space axis (ENERGY-1) |
| `EnergyAnalyzer` | `Device` | EnergyAnalyzer (loose) | 10-ID-D | diced crystal Bragg energy analyzer, 6 crystals (ANALYZER-1, XTAL-1) |
| `AnalyzerSlit` | `Device` | Slit | 10-ID-D | analyzer-chamber slit (OPT-2) |
| `AnalyzerThermalControl` | `Device` | TemperatureController | 10-ID-D | per-crystal PID thermal stabilization (TEMP-1) |
| `AnalyzerElectrometers` / `IncidentScaler` | `Device` | FluxMonitor | 10-ID-D | quad electrometers + I0 scaler (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Slit`, `Monochromator`, `PseudoAxis`, `Mirror`, `Aperture`, `Filter`, `Hexapod`, `Table`, `LinearStage`, `Goniometer`, `TemperatureController`, `FluxMonitor`. Loose families reused from siblings: `StorageRing`, `Transfocator`, `BeamPositionMonitor`. Coined loose at n=1 (new to the catalog, graduates nothing): `EnergyAnalyzer`.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Canted-straight / sibling beamline | the root and source | `unknown-pending-confirmation` | (TOPO-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Undulator period and type | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Orbit-feedback modelling | `OrbitFeedback` | `unknown-pending-confirmation` | (FEEDBACK-1) |
| DCM cut, energy range, pseudo-axis rule | `Monochromator`, `IncidentEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| HRM crystals, meV resolution, beamstop | `HighResolutionMonochromator`, `HighResolutionEnergy` | `unknown-pending-confirmation` | (HRM-1) |
| Transfocator catalog home | `Transfocator` | `unknown-pending-confirmation` | (CRL-1) |
| Mirror coatings and axis roles | the mirrors | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| Pinhole Aperture-vs-Mask | `Pinhole` | `unknown-pending-confirmation` | (PH-1) |
| Manipulator coupled-vs-serial | `OpticsManipulator` | `unknown-pending-confirmation` | (MCM-1) |
| Sample table-vs-environment split | `SampleTable`, `SampleEnvironment` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Analyzer Assembly / Family / Role | `EnergyAnalyzer`, `Spectrometer` | `unknown-pending-confirmation` | (ANALYZER-1) |
| Diced-crystal child-Asset identity | `EnergyAnalyzer` | `unknown-pending-confirmation` | (XTAL-1) |
| Crystal-temperature Asset count | `AnalyzerThermalControl` | `unknown-pending-confirmation` | (TEMP-1) |
| Electrometer / scaler channel map | `AnalyzerElectrometers`, `IncidentScaler` | `unknown-pending-confirmation` | (DET-1) |
| Derived-angle read-back facet | `ReciprocalSpace` | `unknown-pending-confirmation` | (ENERGY-1) |
| Beam-position-monitor Family | the beam-position monitors | `unknown-pending-confirmation` | (DIAG-1) |
| Position-vs-intensity monitor split | the beam-position monitors | `unknown-pending-confirmation` | (BPM-1) |
| Vacuum extent and thermal supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
| IXS Capability / Method | the technique | `unknown-pending-confirmation` | (TECH-1) |
