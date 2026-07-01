# Inventory

*The CORA Asset model for the operational core of P61 modelled today: the planned device tree and what still needs confirming.*

This cut models the P61 experiment / instrument motor bank. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p61/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P61 **coins no new Family**: it is a thin high-energy white-beam scaffold reusing `LinearStage`. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P61` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P61` | `Unit` | (root) | - | bound to the PETRA III Site; damping-wiggler source (SRC-1) |
| `ExperimentStage` | `Device` | LinearStage | p61-eh2 | experiment / instrument bank (eh_mot*, ~64 axes): sample + diffractometer, grouped (GROUP-1) |
| `EnergyDispersiveDetector` | `Device` | EnergyDispersiveSpectrometer | p61-eh2 | energy-dispersive (Ge) detector; pending placeholder (DET-1) |

Families reused from the catalog: `LinearStage`, `EnergyDispersiveSpectrometer`. No new family is coined and nothing graduates here. The Large Volume Press (P61A), when exposed, would reuse the catalog `PressureCell` Family (graduated across 13-id and P02, `PRESS-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (experiment motor bank) (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (the single registry host) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The damping-wiggler source parameters | `P61` | `unknown-pending-confirmation` | (SRC-1) |
| The per-axis roles of the motor bank | `ExperimentStage` | `unknown-pending-confirmation` | (GROUP-1) |
| The Large Volume Press (P61A) | the experiment hutch | `unknown-pending-confirmation` | (PRESS-1) |
| The energy-dispersive / area detectors | `EnergyDispersiveDetector` | `unknown-pending-confirmation` | (DET-1) |
| The Tango handle freshness (debian/stretch branch) | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
