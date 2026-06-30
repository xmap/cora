# Inventory

*The CORA Asset model for the operational core of P21 modelled today: the planned device tree and what still needs confirming.*

This cut models the P21.2 optics, the EH3 endstation, and the LAB station, all as grouped motor banks (the registry slice is thin). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p21/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P21 **coins no new Family**: it is a thin high-energy materials scaffold reusing `LinearStage` / `Slit`. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P21` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P21` | `Unit` | (root) | - | bound to the PETRA III Site |
| `OpticsStages` | `Device` | LinearStage | p21-oh | P21.2 optics bank (oh_u*, ~32 axes); grouped (OPT-1, GROUP-1) |
| `SampleStage` (EH3) | `Device` | LinearStage | p21-eh3 | EH3 sample bank (eh3_u*, ~16 axes); grouped (GROUP-1) |
| `SampleStage` (LAB) | `Device` | LinearStage | p21-lab | LAB sample bank (lab*, ~7 axes); grouped (GROUP-1) |
| `DefiningSlits` | `Device` | Slit | p21-lab | LAB slits (s1 / s2 virtual axes) (OPT-1) |
| `AreaDetectors` | `Device` | Camera | p21-eh3 | high-energy diffraction detectors; pending placeholder (DET-1) |

Families reused from the catalog: `LinearStage`, `Slit`, `Camera`. No new family is coined and nothing graduates. The P21.1 station (`hasep211eh`) exposed only bookkeeping devices and is noted, not modelled (`HOST-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + sample banks) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | coupled / virtual axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (P21.2 optics + EH3 + LAB; P21.1) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator source (absent from this slice) | `P21` | `unknown-pending-confirmation` | (SRC-1) |
| The optics breakdown (mono / mirrors / slits) | `OpticsStages` | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the motor banks | the `SampleStage` Assets | `unknown-pending-confirmation` | (GROUP-1) |
| The detectors (not in this slice) | `AreaDetectors` | `unknown-pending-confirmation` | (DET-1) |
| The P21.1 station (hasep211eh) | the beamline | `unknown-pending-confirmation` | (HOST-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
