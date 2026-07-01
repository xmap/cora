# Inventory

*The CORA Asset model for the operational core of P22 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared P09 / P22 optics (the undulator, the DCM, the mirrors, the phase retarder, the absorber) and the HAXPS experiment endstation (the sample manipulator, the electron analyzer). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p22/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P22 **coins no new Family**: it reuses the optics Families, the allowlisted-loose `PhaseRetarder`, the `Manipulator` sample stage, and the `ElectronAnalyzer` detector Family. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P22` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P22` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p22-optics | shared P09 undulator; period pending (SRC-1, SHARED-1) |
| `Monochromator` | `Device` | Monochromator | p22-optics | shared P09 DCM (energyfmb / mnchrmtr); cut pending (OPT-1, SHARED-1) |
| `Mirror1` | `Device` | Mirror | p22-optics | shared P09 first mirror (spk); coating pending (OPT-1, SHARED-1) |
| `Mirror2` | `Device` | Mirror | p22-optics | shared P09 second mirror (spk + bender); coating pending (OPT-1, SHARED-1) |
| `PhaseRetarder` | `Device` | PhaseRetarder (loose) | p22-optics | shared P09 phase-retarder circles; graduation-due (POL-1, SHARED-1) |
| `Absorber` | `Device` | Filter | p22-optics | shared P09 beam absorber (OPT-1, SHARED-1) |
| `SampleStage` | `Device` | Manipulator | p22-haxps | HAXPS sample manipulator bank (p22/motor, ~64 axes); grouped (GROUP-1) |
| `ElectronAnalyzer` | `Device` | ElectronAnalyzer | p22-haxps | HAXPES hemispherical analyzer; not in the registry slice, pending (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Filter`, `Manipulator`, `ElectronAnalyzer`. Allowlisted-loose Family reused: `PhaseRetarder` (the 4-ID / P09 precedent, graduation-due, a further consumer via the shared optics, `POL-1`). No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (HAXPS sample bank) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | shared P09 optics (mono, mirrors, phase retarder) + coupled axes (CTRL-1, SHARED-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (shared optics + HAXPS) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The shared P09 / P22 optics relationship | the optics Assets | `unknown-pending-confirmation` | (SHARED-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM crystal cut, mirror coatings, phase-retarder detail | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the HAXPS manipulator bank (incl. the haxps_dmy stubs) | `SampleStage` | `unknown-pending-confirmation` | (GROUP-1) |
| The electron analyzer model and control interface | `ElectronAnalyzer` | `unknown-pending-confirmation` | (DET-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
