# Inventory

*The CORA Asset model for 19-BM: the planned device tree and what still needs confirming.*

19-BM is in the design phase, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/19-bm/beamline.yaml) descriptor that the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md). No vendor Model is bound: 19-BM is white-beam, reuses families 2-BM already established, and its hardware is not yet procured, so part numbers are carried as open questions, not bindings. Control handles are omitted because the EPICS PV names are not yet assigned.

## The Asset tree

Root Asset `19-BM` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`. The active families (`Slit`, `Filter`, `Shutter`, `RotaryStage`, `LinearStage`, `Table`, `Camera`, `Scintillator`, `TimingController`) are all shared with 2-BM. Being white-beam, 19-BM uses no `Monochromator` or `Mirror`.

| Asset | Tier | Family | Design spec (FDR) |
| --- | --- | --- | --- |
| `19-BM` | `Unit` | (root) | bound to the APS Site, Sector 19 |
| `Source` | (Supply) | Beam | bending magnet (M3); 0.8 mrad horizontal acceptance, 0.4 mrad inboard offset |
| `FEExitWindow` | `Device` | Window | single front-end exit Be window (~23 m), bolted to the exit mask |
| `ExitMask` | `Device` | Mask | A359-M20; 0.8 mrad acceptance, water-cooled, RSS / PSS-tracked, fiducialised |
| `UpstreamCollimator` | `Device` | Collimator | K1-20, Pb (reused former ID front-end collimator) |
| `WhiteBeamSlit` | `Device` | Slit | water-cooled; defines the footprint and limits vacuum conductance |
| `FilterUnit` | `Device` | Filter | F3-30 Si/Ge/Cu, two selectable banks (reused from 1-ID) |
| `BeamlineVacuum` | (Supply) | Vacuum | UHV, ion-pumped; the isolation gate valve, BLEPS-interlocked |
| `DownstreamCollimator` | `Device` | Collimator | A359-K2, Pb (reused from the previous 19-BM) |
| `DEntryWindow` | `Device` | Window | water-cooled Be, 250 um (~50 m); water in series with the photon stop |
| `RoughVacuumSection` | (Supply) | Vacuum | rough-vacuum volume protecting the Be window from oxidation |
| `KaptonWindow` | `Device` | Window | transition to the in-air experimental volume |
| `SampleRotary` | `Device` | RotaryStage | tomographic rotation, in air; candidate trigger master clock |
| `SamplePositioning` | `Device` | LinearStage | sample centring; hosts the robotic sample changer |
| `DetectorStage` | `Component` | Table | positions the indirect-detection system in air |
| `Scintillator` | `Device` | Scintillator | X-ray-to-visible conversion |
| `Microscope` | `Component` | Housing (Microscope Assembly) | visible-light relay optics chassis, presenting the Detector Role |
| `Camera` | `Device` | Camera | records 2-D projections |
| `PhotonStop` | `Device` | BeamStop | A359-M100, water-cooled Cu; water in series with the Be window |
| `BremsstrahlungStop` | `Device` | BeamStop | A359-K3, chevron Pb-brick stack |
| `DownstreamGuillotines` | `Device` | Shielding | two movable Pb guillotines (>= 12 mm), APS TB-44 |
| `Triggering` | (controls) | TimingController | high-throughput trigger / sync scheme |

`Window`, `Mask`, `Collimator`, and `BeamStop` are catalog Families, graduated under the passive beam-path tier (19-BM's two more Be windows and two more Pb collimators are what pushed `Window` and `Collimator` past the rule-of-three threshold). The remaining passive families (`Beam`, `Shielding`, `Vacuum`) render as plain text: they are bound by intent and not yet in the catalog. The indirect detector reuses the cross-facility `Microscope` Assembly (a `Housing` anchoring scintillator + optics + camera, presenting the Detector Role), the same blueprint 2-BM uses.

## Pending confirmations

Every value below is a design specification awaiting the beamline team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Control handles (EPICS PV names) | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| PSS permit signals | all three enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Shielded-volume permit arrangement (one search for 19-BM-C + 19-BM-D?) | `19-BM-C`, `19-BM-D` | `unknown-pending-confirmation` | (ENC-1) |
| BLEPS equipment-protection mapping (vacuum + series cooling water) | `BeamlineVacuum`, `DEntryWindow`, `PhotonStop` | `unknown-pending-confirmation` | (BLEPS-1) |
| Filter selector modelling and bank 2 slot 5 | `FilterUnit` | `unknown-pending-confirmation` | (FILTER-1) |
| Sample stage models (rotary + linear) | `SampleRotary`, `SamplePositioning` | `unknown-pending-confirmation` | (STAGE-1) |
| Robotic sample changer design + separate safety review | the endstation | `unknown-pending-confirmation` | (ROBOT-1) |
| Trigger / sync scheme (master clock, PSO) | `Triggering` | `unknown-pending-confirmation` | (TRIG-1) |
| Detector hardware (scintillator / optics / camera) | `Scintillator`, `Microscope`, `Camera` | `unknown-pending-confirmation` | (DET-1) |
