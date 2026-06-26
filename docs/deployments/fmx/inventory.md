# Inventory

*The CORA Asset model for FMX: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/fmx/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against the `NSLS2/fmx-profile-collection` `startup/*.py` device classes; the real MX acquisition logic lives in the `lsdc` / `mxtools` libraries, referenced not modelled). No vendor Model is bound: part numbers are not in the profile collection. FMX introduces **no new Family and graduates nothing**: every device reuses the MX vocabulary Diamond i03 established, including the graduated `Goniometer`, `Camera` (the Eiger), and `Transfocator` (the CRL). The robotic sample changer is one Positioner-presenting Asset (not a new Family, the i03 / 19-BM precedent, ROBOT-1); the on-axis illumination and the beam-position monitors bind the loose `Backlight` (FMX is the 3rd sighting, held, DET-1) and `BeamPositionMonitor` (held, DIAG-1) families; see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `FMX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `FMX` | (root) | `XF:17ID*` | bound to the NSLS-II Site (17-ID-2 branch) |
| `Undulator` | InsertionDevice | `SR:C17-ID:G1{IVU21:2}` | IVU21 undulator (shared with AMX) |
| `FrontEndShutter` | Shutter | `XF:17ID-PPS:FAMX{Sh:FE}` | shared FOE photon shutter |
| `PhotonShutter` | Shutter | `XF:17IDA-PPS:FMX{PSh}` | FMX photon shutter |
| `HighHeatLoadSlit` | Slit | `XF:17IDA-OP:FMX{Slt:0}` | white-beam high-heat-load slit |
| `Monochromator` | Monochromator | `XF:17IDA-OP:FMX{Mono:DCM}` | horizontal double-crystal mono |
| `HorizontalFocusingMirror` | Mirror | `XF:17IDA-OP:FMX{Mir:HFM}` | horizontal focusing mirror (bimorph) |
| `KBMirrors` | Mirror | `XF:17IDC-OP:FMX{Mir:KBH/KBV}` | KB microfocus mirror pair (bimorph) |
| `Transfocator` | Transfocator | `XF:17IDC-OP:FMX{CRL:}` | compound-refractive-lens transfocator |
| `BeamConditioningAttenuator` | Filter | `XF:17IDC-OP:FMX{Attn:BCU}` | BCU 4-foil attenuator |
| `ResearchIrisAttenuator` | Filter | `XF:17IDC-OP:FMX{Attn:RI}` | 12-foil rotary attenuator |
| `ExperimentSlits` | Slit | `XF:17IDC-OP:FMX{Slt:2}` | experiment-hutch beam-defining slits |
| `EnergyAxis` | PseudoAxis | (computed) | master energy axis (LUT-coordinated) |
| `Goniometer` | Goniometer | `XF:17IDC-ES:FMX{Gon:1}` | single-omega MX micro-goniometer |
| `Robot` | (Positioner Asset) | `XF:17IDC-ES:FMX{Gov:Robot}` | robotic sample changer (ROBOT-1) |
| `Backlight` | Backlight (loose) | `XF:17IDC-ES:FMX{Light:1}` | on-axis sample illumination |
| `SampleCamera` | Camera | `XF:17IDC-ES:FMX{Cam:7}` | on-axis sample-viewing camera |
| `AreaDetector` | Camera | `XF:17IDC-ES:FMX{Det:Eig16M}` | Eiger 16M pixel detector |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:17IDC-ES:FMX{Det:Mer}` | Mercury XRF (edge selection) |
| `BeamStop` | BeamStop | `XF:17IDC-ES:FMX{BS:1}` | on-axis direct-beam stop |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:17IDA-BI:FMX{BPM:1}` | beam-position diagnostics |
| `FluxMonitor` | FluxMonitor | `XF:17IDC-BI:FMX{Keith:1}` | Keithley photocurrent monitor |
| `VectorMotionController` | MotionController | `XF:17IDC-ES:FMX{Gon:1-Vec}` | PowerBrick rotation vector controller |
| `Zebra` | TimingController | `XF:17IDC-ES:FMX{Zeb:3}` | FPGA trigger / position capture |

Every family is in the catalog except the loose `Backlight` and `BeamPositionMonitor` (both held), and the `Robot`, which is a Positioner-presenting Asset with no Family (the i03 / 19-BM precedent). FMX graduates nothing: the `Goniometer`, `Camera`, and `Transfocator` reuse is the point, making FMX a clean second MX deployment after i03.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the FMX team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator identity, period, gap range; the AMX-shared straight | `Undulator` | `unknown-pending-confirmation` | (SRC-1) (TOPO-1) |
| PSS search-and-secure permit-leaf PVs | all enclosures | `unknown-pending-confirmation` | (PSS-1) |
| HDCM crystal cut, d-spacing, energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Mirror coatings, bimorph calibration, CRL lens count | `KBMirrors` / `Transfocator` | `unknown-pending-confirmation` | (KB-1) |
| Goniometer axis decomposition + centre-of-rotation calibration | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| Robot model, the exchange workflow, the Subject custody lifecycle | `Robot` | `unknown-pending-confirmation` | (ROBOT-1) |
| Eiger model + beam centre, fluorescence ROI map | `AreaDetector` / `FluorescenceDetector` | `unknown-pending-confirmation` | (DET-1) |
| Beam-position channel map and fold-vs-promote hold | `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Sample cryo-cooling (cryostream) modelling | `Goniometer` | `unknown-pending-confirmation` | (CRYO-1) |
| Motion-controller box models / firmware / IP | `VectorMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
