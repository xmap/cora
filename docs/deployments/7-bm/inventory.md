# Inventory

*The CORA Asset model for 7-BM: the planned device tree and what still needs confirming.*

7-BM is in the design phase, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/7-bm/beamline.yaml) descriptor that the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) where one fits. No vendor Model is bound: the 7-BM docs name vendors (Photron, Sierra, Kaeser, IDT, Rigaku) but none is procured into the CORA catalog yet, so models are open questions, not bindings. Control handles are omitted because the EPICS PV names are not yet recorded here.

## The Asset tree

Root Asset `7-BM` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`. The families in bold are loose design-intent names that are not in the catalog yet (they render as plain text); each is tagged with the open question that decides whether it is earned into the catalog or folds into an existing Family plus settings. `FlowController` is no longer among them: it is a graduated catalog Family (presents the Regulator Role, the settable-actuator sibling of TemperatureController).

| Asset | Tier | Family | Notes (from the 7-BM docs) |
| --- | --- | --- | --- |
| `7-BM` | `Unit` | (root) | bound to the APS Site, Sector 7 |
| `Source` | `Device` | Beam | the storage-ring source; loose source representation, never a catalog Family |
| `StationShutterA` | `Device` | Shutter | 7-BM-A station shutter |
| `Filters` | `Device` | Filter | water-cooled filter set, two units |
| `Chopper` | `Device` | **Chopper** | rotary chopper, notched Cu disks, photoeye pickoff; white-beam duty-cycle reduction |
| `WhiteBeamSlit` | `Device` | Slit | white-beam slits, repositioned per DMM stripe |
| `Monochromator` | `Device` | Monochromator | double multilayer monochromator, 6 to 18 keV |
| `MultilayerMirror` | `Device` | Mirror | single-bounce multilayer mirror, white-beam mode |
| `FocusingMirrors` | `Device` | Mirror | Kirkpatrick-Baez focusing pair, focused-beam mode |
| `SafetyShutter` | `Device` | Shutter | safety shutter between the hutches |
| `TomographyRotation` | `Device` | RotaryStage | sample rotation; tomoScan-driven, as at 2-BM |
| `SamplePositioning` | `Device` | LinearStage | sample centring and translation |
| `EDDSlit` | `Device` | Slit | energy-dispersive-diffraction gauge slits |
| `FlowController` | `Device` | FlowController | Sierra Smart-Trak mass-flow controllers; binds the graduated catalog `FlowController` Family (presents Regulator), the settable-actuator sibling of `TemperatureController` |
| `Scintillator` | `Device` | Scintillator | for indirect x-ray imaging |
| `TomographyCamera` | `Device` | Camera | area camera via visible optics |
| `HighSpeedCamera` | `Device` | Camera | high-speed movie camera (Photron Nova S16) |
| `Photodiode` | `Device` | **Photodiode** | PIN diode for time-resolved radiography; presents the Sensor Role |
| `EnergyDispersiveSpectrometer` | `Device` | EnergyDispersiveSpectrometer | germanium energy-dispersive detector; presents the Sensor Role |
| `Timing` | `Device` | TimingController | two DG645 generators plus softGlue; ring-sync and top-up inhibit |

Reused catalog Families (no new Family needed): `Beam`, `Shutter`, `Filter`, `Slit`, `Monochromator`, `Mirror`, `RotaryStage`, `LinearStage`, `Scintillator`, `Camera`, `TimingController`, `EnergyDispersiveSpectrometer` (graduated once 2-ID and 7-BM shared it), and `FlowController` (graduated across i22 / 7-BM / LIX / XFP; presents the Regulator Role, the settable-actuator sibling of `TemperatureController`). The tomography path (scintillator plus visible optics plus area camera) is the same shape as 2-BM and could later compose the cross-facility `Microscope` Assembly. The two loose families (`Chopper`, `Photodiode`) are bound by design intent and earned into the catalog only when a confirmed device and the naming review settle them; this mirrors how TomoWISE carried `HeatAbsorber` and `SlipRing`.

## Pending confirmations

Every value below is taken from the 7-BM docs or inferred, awaiting the beamline team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| EPICS control handles (PV names) | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| Hutch PSS permit signals | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Source type after APS-U | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| Beam mode (white / mono / focused) per technique | all techniques | `unknown-pending-confirmation` | (BEAM-1) |
| Which optics are in the routine pilot path (polycapillary, channel-cut deferred) | `Monochromator`, `MultilayerMirror`, `FocusingMirrors` | `unknown-pending-confirmation` | (OPT-1) |
| Chopper modelling boundary (Family vs Shutter / RotaryStage plus settings) | `Chopper` | `unknown-pending-confirmation` | (CHOP-1) |
| Energy-dispersive detector identity and camera models | `EnergyDispersiveSpectrometer`, `HighSpeedCamera`, `TomographyCamera` | `unknown-pending-confirmation` | (DET-1) |
| Radiography point-detector chain and data unit | `Photodiode` | `unknown-pending-confirmation` | (RAD-1) |
| High-speed acquisition unit and top-up blanking | `HighSpeedCamera` | `unknown-pending-confirmation` | (HSI-1) |
| Settable-actuator command path for flow and air setpoints | `FlowController` | `unknown-pending-confirmation` | (FLOW-1) |
| Combustion / spray rig reality (installed device vs intended use) | sample environment | `unknown-pending-confirmation` | (ENV-1) |

Assertion-style questions that do not leave a value blank (the technique scope TECH-1, the hazard-workflow boundary HAZ-1, the timing-subsystem shape TIMING-1, and the sector and resource-sharing question SECTOR-1) are on [Open questions](questions.md) without a placeholder here.
