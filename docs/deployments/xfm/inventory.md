# Inventory

*The CORA Asset model for XFM: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/xfm/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs where the profile exposes them. XFM's public profile (`NSLS2/xfm-profile-collection`) is **endstation-only**: it carries the raster stage, the Xspress3, the scaler, and a Maia detector (in a bypass file). The bending-magnet source, the monochromator, the focusing optic, and the shutters are **not in the profile**, so they are carried confirm-only with no PV (no fabricated PVs). XFM introduces **no new family and graduates nothing**: the fluorescence detectors reuse `EnergyDispersiveSpectrometer` (the 2-ID / SRX scanning-XRF vocabulary), the raster stage `LinearStage`, the scaler `FluxMonitor`, and the bending-magnet source the loose `Beam` PhotonBeam supply (the 2-BM / BMM precedent).

## The Asset tree

Root Asset `XFM` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV | What it is |
| --- | --- | --- | --- |
| `XFM` | (root) | `XF:04BM*` | bound to the NSLS-II Site (4-BM, bending magnet) |
| `Source` | Beam (loose) | `SR:C04` | bending-magnet PhotonBeam supply (not an Asset) |
| `FrontEndShutter` | Shutter | (not in profile) | front-end photon shutter (PSS-1) |
| `PhotonShutter` | Shutter | (not in profile) | photon shutter into the optics (PSS-1) |
| `Monochromator` | Monochromator | (not in profile) | Si(111) DCM; energy actuator (DCM-1) |
| `FocusingOptic` | Mirror | (not in profile) | microfocusing optic (KB / capillary) (OPT-1) |
| `BeamDefiningSlit` | Slit | (not in profile) | beam-defining slit (PROFILE-1) |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (XANES sweep) (ENERGY-1) |
| `SampleStage` | LinearStage | `XF:04BMC-ES:2{UTS:1-Ax:}` | UTS X/Y/Z raster scanning stage |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:04BMC-ES{x3m:1}:` | Xspress3 4-channel SDD (XRF mapping) |
| `MaiaDetector` | EnergyDispersiveSpectrometer | `XFM:MAIA` | Maia continuous-mapping array (MAIA-1) |
| `FluxMonitor` | FluxMonitor | `XF:04BM-ES:2{Sclr:1}` | SIS3820 scaler I0 / flux channels |
| `StageMotionController` | MotionController | (not in profile) | UTS raster-stage controller (DRIVE-1) |

Every family is in the catalog except the loose `Beam` (the bending-magnet source, a PhotonBeam supply, never an Asset). XFM coins none and graduates nothing: the SDD fluorescence detectors reuse `EnergyDispersiveSpectrometer` (graduated when 2-ID and 7-BM shared it), the raster stage `LinearStage`, and the scaler `FluxMonitor` (graduated in #353), so XFM is a clean scanning-XRF reuse deployment, the second after 2-ID.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the XFM team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The bending-magnet source parameters | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| The optics not in the profile: DCM, focusing optic, slits, shutters | `Monochromator` / `FocusingOptic` | `unknown-pending-confirmation` | (PROFILE-1) |
| PSS permit-leaf and shutter PVs | all enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The DCM crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| The microfocusing optic type (KB / capillary) | `FocusingOptic` | `unknown-pending-confirmation` | (OPT-1) |
| The Xspress3 element count and ROI map | `FluorescenceDetector` | `unknown-pending-confirmation` | (DET-1) |
| The Maia element count and live status | `MaiaDetector` | `unknown-pending-confirmation` | (MAIA-1) |
| The scaler flux-channel map | `FluxMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| The raster-stage motion-controller model | `StageMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
