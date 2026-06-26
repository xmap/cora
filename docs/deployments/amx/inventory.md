# Inventory

*The CORA Asset model for AMX: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/amx/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against the `NSLS2/amx-profile-collection` `startup/*.py` device classes; the real MX acquisition logic lives in the `lsdc` / `mxtools` libraries, referenced not modelled). No vendor Model is bound: part numbers are not in the profile collection. AMX introduces **no new Family and graduates nothing**: as FMX's sibling it reuses the same MX vocabulary, including the graduated `Goniometer` and `Camera`. The robotic sample changer is one Positioner-presenting Asset (not a new Family, the i03 / 19-BM / FMX precedent, ROBOT-1); the beam-position monitors bind the loose, held `BeamPositionMonitor` family (DIAG-1); see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `AMX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV | What it is |
| --- | --- | --- | --- |
| `AMX` | (root) | `XF:17ID*` | bound to the NSLS-II Site (17-ID-1 branch) |
| `Undulator` | InsertionDevice | `SR:C17-ID:G1{IVU21:1}` | IVU21 undulator (shared with FMX) |
| `FrontEndShutter` | Shutter | (not in profile) | shared FOE photon shutter (PSS-1) |
| `PhotonShutter` | Shutter | (not in profile) | AMX photon shutter (PSS-1) |
| `FrontEndSlit` | Slit | `FE:C17A-OP{Slt}` | front-end white-beam slit |
| `HighHeatLoadSlit` | Slit | `XF:17IDA-OP:AMX{Slt:0}` | high-heat-load slit |
| `Monochromator` | Monochromator | `XF:17IDA-OP:AMX{Mono:DCM}` | vertical double-crystal mono (VDCM) |
| `TandemMirror` | Mirror | `XF:17IDA-OP:AMX{Mir:TDM}` | tandem-deflection harmonic-rejection mirrors |
| `KBMirrors` | Mirror | `XF:17IDB-OP:AMX{Mir:KBH/KBV}` | KB microfocus mirror pair |
| `BeamConditioningAttenuator` | Filter | `XF:17IDB-OP:AMX{Attn:BCU}` | BCU 4-foil attenuator |
| `ExperimentSlits` | Slit | `XF:17IDB-OP:AMX{Slt:2}` | experiment-hutch beam-defining slits |
| `EnergyAxis` | PseudoAxis | (computed) | master energy axis (LUT-coordinated) |
| `Goniometer` | Goniometer | `XF:17IDB-ES:AMX{Gon:1}` | single-omega MX micro-goniometer |
| `Robot` | (Positioner Asset) | `XF:17IDB-ES:AMX{EMBL}:` | EMBL robotic sample changer (ROBOT-1) |
| `SampleCamera` | Camera | `XF:17IDB-ES:AMX{Cam:7}` | on-axis sample-viewing camera |
| `AreaDetector` | Camera | (not in profile) | Eiger pixel detector (DET-1) |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:17IDB-ES:AMX{Det:Mer}` | Mercury XRF (edge selection) |
| `BeamStop` | BeamStop | `XF:17IDB-ES:AMX{BS:1}` | on-axis direct-beam stop |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:17IDA-BI:AMX{BPM:1}` | beam-position diagnostics |
| `FluxMonitor` | FluxMonitor | `XF:17IDB-BI:AMX{Keith:1}` | Keithley photocurrent monitor |
| `MotionController` | MotionController | (not in profile) | goniometer / optics controllers (DRIVE-1) |
| `Zebra` | TimingController | `XF:17IDB-ES:AMX{Zeb:1}` | FPGA trigger / position capture |

Every family is in the catalog except the loose `BeamPositionMonitor` (held), and the `Robot`, a Positioner-presenting Asset with no Family (the i03 / 19-BM / FMX precedent). AMX graduates nothing: as FMX's sibling it reuses the MX vocabulary wholesale, completing the 17-ID MX pair.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the AMX team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator identity, period, gap range; the FMX-shared straight | `Undulator` | `unknown-pending-confirmation` | (SRC-1) (TOPO-1) |
| PSS permit-leaf and shutter PVs | all enclosures | `unknown-pending-confirmation` | (PSS-1) |
| VDCM crystal cut, d-spacing, energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Mirror coatings, KB calibration | `TandemMirror` / `KBMirrors` | `unknown-pending-confirmation` | (KB-1) |
| Goniometer axis decomposition + centre-of-rotation calibration | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| Robot model, the exchange workflow, the Subject custody lifecycle | `Robot` | `unknown-pending-confirmation` | (ROBOT-1) |
| Eiger model + beam centre (not in profile); fluorescence ROI map | `AreaDetector` / `FluorescenceDetector` | `unknown-pending-confirmation` | (DET-1) |
| Beam-position channel map and fold-vs-promote hold | `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Sample cryo-cooling (cryostream) modelling | `Goniometer` | `unknown-pending-confirmation` | (CRYO-1) |
| Motion-controller box models / firmware / IP | `MotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
