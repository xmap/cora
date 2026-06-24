# Inventory

*The CORA Asset model for the part of 32-ID modelled today: the planned device tree and what still needs confirming.*

This scaffold models the shared optics spine and the TXM endstation; the other 32-ID instruments are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/32-id/beamline.yaml) descriptor that the Source page renders from.

Every device binds to a catalog [Family](../../catalog/families.md). The TXM-specific optics (`Condenser`, `ZonePlate`, `PhaseRing`) are now catalog Families, earned once a second deployment (FXI) shared them; the front-end window and beam stops reuse the `Window` / `BeamStop` Families graduated under the passive beam-path tier. No vendor Models are bound and no control handles are filled, because parts are not catalogued and PV names are not published.

## The Asset tree

Root Asset `32-ID` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`. The 32-ID-B instruments (HSI, AM) and the projection microscope are not in this tree (deferred).

| Asset | Tier | Family | Design spec / note |
| --- | --- | --- | --- |
| `32-ID` | `Unit` | (root) | bound to the APS Site; canted source, three hutches |
| `Undulator_DS` | `Device` | InsertionDevice | downstream canted undulator ("Planar 1.35") |
| `Undulator_US` | `Device` | InsertionDevice | upstream canted undulator ("Planar 2.8") |
| `FrontEndMask` | `Device` | Mask | fixed beam-defining aperture (~24 m) |
| `FrontEndWindow` | `Device` | Window | front-end window (Be assumed) |
| `WhiteBeamSlit` | `Device` | Slit | JJ X-Ray four-motor compact slits (Beckhoff) |
| `Monochromator` | `Device` | Monochromator | Si(111) DCM, 7 to 40 keV; bypassed in white-beam mode |
| `ModeShutter` | `Device` | Shutter | P4-50 mode shutter (white vs mono) |
| `WhiteBeamStop` / `MonochromaticBeamStop` | `Device` | BeamStop | set and locked per mode change |
| `StationShutter` | `Device` | Shutter | PSS safety shutter into the experimental hutches |
| `TXMGranite` | `Component` | Table | granite sample-and-optic stage support (32-ID-C) |
| `TXMRotary` | `Device` | RotaryStage | tomographic rotation axis |
| `TXMSamplePositioning` | `Device` | LinearStage | sample centring and alignment stack |
| `Condenser` | `Device` | Condenser | beam-condensing optic |
| `ZonePlate` | `Device` | ZonePlate | objective Fresnel zone plate |
| `PhaseRing` | `Device` | PhaseRing | Zernike phase ring |
| `TXMDetectorSupport` | `Component` | Table | granite detector support and follower mechanics |
| `TXMObjective` | `Device` | Objective | visible-light coupling objective |
| `TXMScintillator` | `Device` | Scintillator | X-ray to visible conversion |
| `TXMCamera` | `Device` | Camera | detector camera |

Every Family here is in the catalog: `InsertionDevice`, `Mask`, `Slit`, `Monochromator`, `Shutter`, `Table`, `RotaryStage`, `LinearStage`, `Objective`, `Scintillator`, `Camera`, plus `Window` and `BeamStop` (graduated under the passive beam-path tier) and `Condenser`, `ZonePlate`, `PhaseRing` (graduated once FXI became a second deployment sharing them). A Family is earned in when a second deployment shares it; that has now happened for all of 32-ID's device classes.

## Pending confirmations

Every value below is a published-doc value or an inference awaiting the 32-ID team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Canted branch and root topology (one vs two roots) | the root and the optics spine | `unknown-pending-confirmation` | (TOPO-1) |
| Control handles (EPICS PVs) | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| Hutch PSS permit signals | the three enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Undulator device types and periods | `Undulator_DS`, `Undulator_US` | `unknown-pending-confirmation` | (SRC-1) |
| Front-end mask aperture and window stack | `FrontEndMask`, `FrontEndWindow` | `unknown-pending-confirmation` | (SRC-2) |
| Monochromator axes and energy model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Beam-mode structure and switching sequence | `ModeShutter`, beam stops | `unknown-pending-confirmation` | (MODE-1) |
| TXM stage models and axes (pre- vs post-APS-U) | `TXMGranite`, `TXMRotary`, `TXMSamplePositioning` | `unknown-pending-confirmation` | (TXM-1) |
| Condenser optic identity and Family | `Condenser` | `unknown-pending-confirmation` | (OPTICS-1) |
| Zone-plate parameters and Family | `ZonePlate` | `unknown-pending-confirmation` | (OPTICS-2) |
| Phase-ring parameters and state model | `PhaseRing` | `unknown-pending-confirmation` | (OPTICS-3) |
| Detector camera model and sensor | `TXMCamera` | `unknown-pending-confirmation` | (DET-1) |
| Detector objective and scintillator specs | `TXMObjective`, `TXMScintillator` | `unknown-pending-confirmation` | (DET-2) |
| Layout z reference | all devices | `unknown-pending-confirmation` | (LAYOUT-1) |
| Flight-path gas and endstation supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
