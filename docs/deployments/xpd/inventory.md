# Inventory

*The CORA Asset model for XPD: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/xpd/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/xpd-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection. XPD introduces **no new catalog family**: every device reuses an existing Family, including the ones graduated from earlier deployments (`Camera` for the flat panels, `FluxMonitor` for the ion chamber and electrometer, `TemperatureController` for the sample environment, which Diamond i11 graduated). Its one loose family, the `BeamPositionMonitor`, is shared across several APS and NSLS-II deployments and held for gate-review (see [Model](model.md#deliberately-not-here-yet)).

## The Asset tree

Root Asset `XPD` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `XPD` | (root) | `XF:28ID*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | (pending) | 28-ID insertion device (damping wiggler, SRC-1) |
| `Monochromator` | Monochromator | `XF:28IDA-OP:1{Mono:DLM}` | bent double-Laue mono (high flux) |
| `VerticalFocusingMirror` | Mirror | `XF:28IDA-OP:1{Mir:VFM}` | vertical focusing mirror |
| `WhiteBeamSlit` | Slit | `XF:28IDA-OP:2{Slt:H}` | horizontal beam-defining slit |
| `Filters` | Filter | `XF:28IDA-OP:2{Fltr:1}` | attenuator filters |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (double-Laue mono) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:28IDA-BI:0{BPM:1}` | optics-hutch beam-position monitor |
| `SampleStage` | LinearStage | `XF:28IDC-ES:1{Dif:1}` | sample / detector-arm diffractometer |
| `SampleArrayStage` | LinearStage | `XF:28IDC-ES:1{SampArray}` | multi-sample array stage |
| `Pinhole` | Aperture | `XF:28IDC-ES:1{PinHole:XRD}` | beam-defining pinhole |
| `SampleTemperature` | TemperatureController | `XF:28IDC-ES:1{CS:800}` | cryostream / furnace thermal control |
| `AreaDetector` | Camera | `XF:28IDC-ES:1{Det:PE1}` | PerkinElmer flat panel (primary) |
| `DexelaDetector` | Camera | `XF:28IDC-ES:1{Det:DEX}` | Dexela flat panel (commented-out in source) |
| `DetectorStage` | LinearStage | `XF:28IDC-ES:1{Det:PE1-Ax:}` | detector distance stage (sets Q) |
| `IonChamber` | FluxMonitor | `XF:28IDC-BI{IC101}` | incident-flux ion chamber |
| `QuadElectrometer` | FluxMonitor | `XF:28IDC-BI{IM:02}EM180:` | I0 quad electrometer |
| `ExposureShutter` | Shutter | `XF:28IDC-ES:1{Sh:Exp}` | endstation exposure shutter |
| `EndstationMotionController` | MotionController | (pending) | diffractometer / stage controllers |

Every family is in the catalog except the loose `BeamPositionMonitor` (shared, held); XPD coins none. Notably the flat panels reuse `Camera`, the flux counters reuse `FluxMonitor` (graduated in #353), and the sample-environment stages reuse `TemperatureController` (graduated by Diamond i11, #350), so XPD is a clean reuse-and-reinforce deployment, the NSLS-II twin of i11 and i15-1.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the XPD team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Damping-wiggler source PV and parameters | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Double-Laue monochromator crystal / range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Full diffractometer axis set; Goniometer / Assembly modelling | `SampleStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Live flat-panel set and detector distance range | `AreaDetector` / `DexelaDetector` / `DetectorStage` | `unknown-pending-confirmation` | (DET-1) |
| Live sample-environment units | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| Ion-chamber / electrometer channel map | `IonChamber` / `QuadElectrometer` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
