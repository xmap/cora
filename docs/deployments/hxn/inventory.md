# Inventory

*The CORA Asset model for HXN: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/hxn/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/hxn-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection. The two multilayer-Laue-lens halves bind a loose family name (`MultilayerLaueLens`, HXN is its only sighting); every other device reuses an existing catalog Family, including `EnergyDispersiveSpectrometer` (graduated with 2-ID + 7-BM) for the fluorescence detector.

## The Asset tree

Root Asset `HXN` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `HXN` | (root) | `XF:03ID*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | `SR:C3-ID:G1{IVU20:1}` | IVU20 in-vacuum undulator |
| `Monochromator` | Monochromator | `XF:03IDA-OP{Mon:1}` | double-crystal mono; Bragg + energy axis |
| `CollimatingMirror` | Mirror | `XF:03IDA-OP{HCM:1}` | horizontal collimating mirror |
| `FocusingMirror` | Mirror | `XF:03IDA-OP{HFM:1}` | horizontal focusing mirror |
| `VerticalMirror` | Mirror | `XF:03IDA-OP{VMS:1}` | vertical mirror system |
| `WhiteBeamSlit` | Slit | `XF:03IDA-OP{Slt:1}` | white-beam-defining slit |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (drives Bragg) |
| `BeamPositionMonitor` | GenericProbe | `XF:03IDA-BI{Slt:1}` | beam-position / intensity diagnostics |
| `SecondarySourceAperture` | Slit | `XF:03IDB-OP{Slt:SSA1}` | coherence-defining secondary source |
| `PhotonShutter` | Shutter | `XF:03IDB-PPS{PSh}` | PPS slow photon shutter |
| `ZonePlate` | ZonePlate | `XF:03IDC-ES` | Fresnel zone-plate objective |
| `ZonePlateAperture` | Aperture | `XF:03IDC-ES{ANC350:5}` | zone-plate order-sorting aperture |
| `ZonePlateBeamStop` | BeamStop | `XF:03IDC-ES{ANC350:8}` | zone-plate central beam stop |
| `MLL_Vertical` / `MLL_Horizontal` | MultilayerLaueLens (loose) | `XF:03IDC-ES` | crossed multilayer-Laue-lens pair |
| `MLLAperture` | Aperture | `XF:03IDC-ES` | MLL order-sorting aperture |
| `SampleStage` | LinearStage | `XF:03IDC-ES{Ppmac:1}` | fine raster stage (ssx/ssy/ssz); the scan axes |
| `SampleRotary` | RotaryStage | `XF:03IDC-ES{ANC350:1-Ax:0}` | tomographic rotation (theta) |
| `SamplePod` | Hexapod | `XF:03IDC-ES` | SmarAct Smarpod 6-DOF pod |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:03IDC-ES{Xsp:1}` | Xspress3 XRF detector (Sensor Role) |
| `MerlinDetector` | Camera | `XF:03IDC-ES{Merlin:1}` | Merlin pixel detector (ptychography) |
| `EigerDetector` | Camera | `XF:03IDC-ES{Det:Eiger1M}` | Eiger 1M pixel detector |
| `DexelaDetector` | Camera | `XF:03IDC-ES{Dexela:1}` | Dexela flat-panel detector |
| `FluxCounter` | GenericProbe | `XF:03IDC-ES{Sclr}` | scaler flux channels (normalization) |
| `Zebra` | TimingController | `XF:03IDC-ES{Zeb:3}` | position-capture trigger box |
| `SampleMotionController` | MotionController | `XF:03IDC-ES{Ppmac:1}` | Power PMAC (fine raster) |
| `NanoPositioningController` | MotionController | `XF:03IDC-ES{ANC350}` | Attocube ANC350 controllers (x8) |

Every family is in the catalog except `MultilayerLaueLens` (the two MLL halves), which is loose at its first sighting (OPTIC-3). The fluorescence detector reuses `EnergyDispersiveSpectrometer`, graduated when 2-ID and 7-BM shared it; HXN's Xspress3 is the third sighting.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the HXN team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator period / gap range | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DCM crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Zone-plate parameters (outer-zone width, diameter) | `ZonePlate` | `unknown-pending-confirmation` | (OPTIC-2) |
| Rotary hardware, encoder resolution, max speed | `SampleRotary` | `unknown-pending-confirmation` | (STAGE-1) |
| Fluorescence detector vendor, element count, resolution | `FluorescenceSpectrometer` | `unknown-pending-confirmation` | (DET-1) |
| Pixel-detector roster (live vs dormant duplicates) | `MerlinDetector` / `EigerDetector` / `DexelaDetector` | `unknown-pending-confirmation` | (CAM-1) |
| Scaler / I0 flux channel map | `FluxCounter` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | both controllers | `unknown-pending-confirmation` | (DRIVE-1) |
