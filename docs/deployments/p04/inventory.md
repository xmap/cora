# Inventory

*The CORA Asset model for the operational core of P04 modelled today: the planned device tree and what still needs confirming.*

This cut models the soft X-ray optics (the undulator, the plane-grating monochromator, the three mirrors, the exit slits) and the two experiment endstations (EXP1, EXP2 with their manipulators, electrometers, diagnostic screens, and cameras). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p04/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P04, CORA's second PETRA III beamline, **coins no new Family**: it binds the catalog `GratingMonochromator` (the soft X-ray analog of the crystal `Monochromator`, introduced at SIX and graduated at CSX), and reuses optics / motion Families otherwise. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P04` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P04` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p04-optics | variable-polarization (APPLE-II) undulator, 250-3000 eV; row-phase axes pending (SRC-1); reports on the exp2 host (HOST-1) |
| `PlaneGratingMonochromator` | `Device` | GratingMonochromator | p04-optics | plane-grating monochromator (MonoP04); grating line densities pending (OPT-1) |
| `Mirror1` | `Device` | Mirror | p04-optics | first soft X-ray mirror (roty / transx); coating / role pending (OPT-1) |
| `Mirror2` | `Device` | Mirror | p04-optics | second soft X-ray mirror; coating / role pending (OPT-1) |
| `Mirror3` | `Device` | Mirror | p04-optics | third (refocusing) mirror (roty / transx / transy); pending (OPT-1) |
| `ExitSlitVertical` | `Device` | Slit | p04-optics | vertical exit slit (vgap / voffs); resolving-power control (OPT-1) |
| `ExitSlit` | `Device` | Slit | p04-optics | exit slit (h blades + v gap/offset + virtual axis) (OPT-1) |
| `SampleManipulator` | `Device` | Manipulator | p04-exp1 | EXP1 sample manipulator bank (exp1_mot01..16); axis roles pending (GROUP-1) |
| `SecondaryPositioner` | `Device` | Manipulator | p04-exp1 | EXP1 secondary positioner bank (ps2.01..14); roles pending (GROUP-1) |
| `ViewCamera` | `Device` | Camera | p04-exp1 | EXP1 Prosilica viewing camera (DET-1) |
| `Electrometer` (EXP1) | `Device` | FluxMonitor | p04-exp1 | EXP1 Keithley 6517A drain-current electrometer (DET-1) |
| `ExitShutterUnit` | `Device` | Slit | p04-exp2 | EXP2 exit-shutter / diagnostic unit (EXSU2); bpm / baffle roles pending (EXSU-1) |
| `ExperimentPositioner` | `Device` | Manipulator | p04-exp2 | EXP2 generic positioner axes (exp2_mot06/08); roles pending (GROUP-1) |
| `VirtualPositioners` | `Device` | PseudoAxis | p04-exp2 | EXP2 virtual position axes (ps / screen position) (GROUP-1) |
| `DiagnosticScreens` | `Device` | Screen (loose) | p04-exp2 | EXP2 motorized phosphor screens for beam-path diagnostics (DIAG-1) |
| `BeamMonitorCameras` | `Device` | Camera | p04-exp2 | EXP2 Vimba cameras imaging the diagnostic screens (DIAG-1) |
| `Electrometer` (EXP2) | `Device` | FluxMonitor | p04-exp2 | EXP2 Keithley 6517A drain-current electrometer (DET-1) |

Families reused from the catalog: `InsertionDevice`, `GratingMonochromator`, `Mirror`, `Slit`, `Manipulator`, `Camera`, `FluxMonitor`, `PseudoAxis`. Loose family reused from siblings: `Screen` (motorized phosphor diagnostic flag, the 2-BM FLAG-1 precedent). No new family is coined and nothing graduates. The `GratingMonochromator` is its first deployment but is already a catalog Family.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 stepper controllers (experiment + screen motors) (CTRL-1) |
| `SPKControllers` | MotionController | Tango_spk | SmarPod-style controllers (mirror + exit-slit axes) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | generic Tango motor controllers (mono, undulator, virtual axes) (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + two experiment) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator polarization / row-phase axes | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The optics reporting on the exp2 host | `Undulator`, `PlaneGratingMonochromator`, the mirrors, the exit slits | `unknown-pending-confirmation` | (HOST-1) |
| The grating line densities, mirror coatings, exit-slit calibration | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the manipulator banks | `SampleManipulator`, `SecondaryPositioner`, `ExperimentPositioner` | `unknown-pending-confirmation` | (GROUP-1) |
| The EXSU2 sub-roles (slit / bpm / baffle) | `ExitShutterUnit` | `unknown-pending-confirmation` | (EXSU-1) |
| The electrometer channels and the photoemission analyzer | the `Electrometer` Assets | `unknown-pending-confirmation` | (DET-1) |
| The screen positions and camera-to-screen mapping | `DiagnosticScreens`, `BeamMonitorCameras` | `unknown-pending-confirmation` | (DIAG-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
