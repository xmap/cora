# Inventory

*The CORA Asset model for the operational core of P23 modelled today: the planned device tree and what still needs confirming.*

This cut models the P23 experiment / instrument motor bank (the optics, diffractometer, and sample positioning grouped). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p23/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P23 **coins no new Family**: it is a thin in-situ diffraction scaffold reusing `LinearStage`. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P23` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P23` | `Unit` | (root) | - | bound to the PETRA III Site |
| `ExperimentStage` | `Device` | LinearStage | p23-eh | experiment / instrument bank (eh_mot*, ~79 axes): optics + diffractometer + sample, grouped (GROUP-1, OPT-1, DIFF-1) |
| `DevStage` | `Device` | LinearStage | p23-eh | dev / commissioning axis (hasep23dev host) (STUB-1) |
| `AreaDetectors` | `Device` | Camera | p23-eh | in-situ diffraction detectors; pending placeholder (DET-1) |

Families reused from the catalog: `LinearStage`, `Camera`. No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 / VME58 steppers (experiment motor bank) (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (the single registry host) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator source (absent from this slice) | `P23` | `unknown-pending-confirmation` | (SRC-1) |
| The optics breakdown (mono / mirrors) | `ExperimentStage` | `unknown-pending-confirmation` | (OPT-1) |
| The diffractometer geometry | `ExperimentStage` | `unknown-pending-confirmation` | (DIFF-1) |
| The per-axis roles of the motor bank | `ExperimentStage` | `unknown-pending-confirmation` | (GROUP-1) |
| The dev / commissioning stub status | `DevStage` | `unknown-pending-confirmation` | (STUB-1) |
| The detectors (not in this slice) | `AreaDetectors` | `unknown-pending-confirmation` | (DET-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
