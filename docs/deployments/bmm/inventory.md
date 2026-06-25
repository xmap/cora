# Inventory

*The CORA Asset model for BMM: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/bmm/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/bmm-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection. BMM introduces **no new family**: it reuses existing catalog Families (the ion chambers reuse `FluxMonitor`, graduated in #353; the fluorescence detector the catalog `EnergyDispersiveSpectrometer`) and one loose family already carried by a sibling deployment (the diagnostic screens reuse the loose `Screen` from 2-BM).

## The Asset tree

Root Asset `BMM` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `BMM` | (root) | `XF:06BM*` | bound to the NSLS-II Site |
| `Source` | Beam | `SR:C06` | 6-BM bending-magnet source (PhotonBeam Supply) |
| `FrontEndShutter` | Shutter | `XF:06BM-PPS{Sh:FE}` | front-end safety shutter |
| `PhotonShutter` | Shutter | `XF:06BM-PPS{Sh:A}` | photon shutter into the optics |
| `CollimatingMirror` | Mirror | `XF:06BM-OP{Mir:M1}` | first mirror (M1), collimating |
| `Monochromator` | Monochromator | `XF:06BMA-OP{Mono:DCM1}` | double-crystal mono, Si(111); Bragg = energy actuator |
| `FocusingMirror` | Mirror | `XF:06BMA-OP{Mir:M2}` | second mirror (M2), focusing + harmonic rejection |
| `ConditioningSlit` | Slit | `XF:06BMA-OP{Slt:01}` | optics-hutch beam-defining slit |
| `SampleSlit` | Slit | `XF:06BM-BI{Slt:02}` | endstation entrance slit |
| `Filter` | Filter | `XF:06BMA-BI{Fltr:01}` | attenuating filter paddles |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (drives Bragg); the axis an XAS scan sweeps |
| `DiagnosticScreen` | Screen (loose) | `XF:06BMA-BI{Diag:02}` | fluorescent beam-viewing screens |
| `BeamPositionMonitor` | GenericProbe | `XF:06BM-BI{BPM:1}` | beam-position monitor + current transmitter |
| `SampleStage` | LinearStage | `XF:06BM-ES{MC:09}` | XAFS sample positioning table (x/y/pitch/roll) |
| `SampleWheel` | RotaryStage | `XF:06BMA-BI{XAFS-Ax:RotB}` | rotating sample wheel (batch XAS) |
| `ReferenceHolder` | LinearStage | `XF:06BMA-BI{XAFS-Ax:RefX}` | reference-foil holder (energy calibration, Ir channel) |
| `IonChambers` | FluxMonitor | `XF:06BM-BI{EM:1}EM180:` | quad electrometer (I0 / It / Ir), transmission-XAS signal |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:06BM-ES` | Xspress3 fluorescence detector (Sensor Role) |
| `ScalerCounter` | GenericProbe | `XF:06BM-ES:1{Sclr:1}` | scaler / point counter for alignment |
| `EndstationMotionController` | MotionController | `XF:06BM-ES{MC:09}` | endstation motion controller |

Every family is in the catalog except the loose `Screen` (the diagnostic screens, shared with 2-BM; held pending FLAG-1). The ion chambers reuse `FluxMonitor`, graduated in #353 from the i03/i15-1/i22 ion chambers; the fluorescence detector reuses `EnergyDispersiveSpectrometer`, graduated when 2-ID and 7-BM shared it.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the BMM team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Bending-magnet source parameters | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DCM crystal sets and energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Mirror coatings / harmonic-rejection stripes | `CollimatingMirror` / `FocusingMirror` | `unknown-pending-confirmation` | (OPTIC-1) |
| Sample-wheel positions and sample-changer model | `SampleWheel` | `unknown-pending-confirmation` | (WHEEL-1) |
| Fluorescence detector element count and vendor | `FluorescenceSpectrometer` | `unknown-pending-confirmation` | (DET-1) |
| Ion-chamber gas fill and Family (FluxMonitor vs dedicated) | `IonChambers` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box model / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
