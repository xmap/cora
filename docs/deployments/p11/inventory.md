# Inventory

*The CORA Asset model for the operational core of P11 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics hutch (the oh and granite motor banks) and the experiment hutch (the eh1 / eh2 / eh3 / piezo banks, the servo, the cryostream, the Pilatus and XIA detectors). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p11/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P11, PETRA III's first macromolecular-crystallography beamline, **coins no new Family and changes nothing in the catalog**: it is a reuse-and-reinforce MX deployment, reusing the MX Families graduated at i03 and exercised across the MX fleet. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound. The registry's sparse labelling means the experiment-hutch motions are grouped as stages rather than resolved into a goniometer (`MX-1`).

## The Asset tree

Root Asset `P11` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P11` | `Unit` | (root) | - | bound to the PETRA III Site |
| `OpticsStages` | `Device` | LinearStage | p11-oh | optics-hutch bank (oh_mot, 32 axes): mono / mirror / slit, grouped (OPT-1, GROUP-1) |
| `GraniteStage` | `Device` | LinearStage | p11-oh | granite support / table bank (granite_mot, 5 axes) (GROUP-1) |
| `ExperimentStage1` | `Device` | LinearStage | p11-eh | eh1 motor bank (eh1_mot06..16); positioning, grouped (MX-1, GROUP-1) |
| `ExperimentStage2` | `Device` | LinearStage | p11-eh | eh2 motor bank (eh2_mot01..16) (MX-1, GROUP-1) |
| `ExperimentStage3` | `Device` | LinearStage | p11-eh | eh3 motor bank (eh3_mot01..16) (MX-1, GROUP-1) |
| `PiezoStage` | `Device` | LinearStage | p11-eh | experiment-hutch piezo bank (ehpm3_mot, 16 axes); fine positioning (GROUP-1) |
| `ServoStage` | `Device` | LinearStage | p11-eh | eh1 servo motor; continuous / high-speed axis, role pending (GROUP-1) |
| `SampleTemperature` | `Device` | TemperatureController | p11-eh | Oxford Cryostream 700; MX cryocooling (TEMP-1) |
| `AreaDetector` | `Device` | Camera | p11-eh | Pilatus area detector; MX diffraction; variant pending (DET-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | p11-eh | XIA MCA fluorescence detector; edge scanning (DET-1) |

Families reused from the catalog: `LinearStage`, `TemperatureController`, `Camera`, `EnergyDispersiveSpectrometer`. No new family is coined and nothing graduates. The automated sample changer, if present, is a deferred sample-exchange Procedure, not a device (`ROBOT-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (oh / granite / eh banks) (CTRL-1) |
| `PiezoMotorControllers` | MotionController | Tango_piezomotor | piezomotor controllers (experiment-hutch fine bank) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | generic Tango motor / servo controllers (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (one Tango host, inferred split) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator source (absent from the registry) | `P11` | `unknown-pending-confirmation` | (SRC-1) |
| The optics breakdown (mono / mirrors / slits) | `OpticsStages`, `GraniteStage` | `unknown-pending-confirmation` | (OPT-1) |
| The goniometer geometry and MX instrument structure | the `ExperimentStage*` Assets | `unknown-pending-confirmation` | (MX-1) |
| The per-axis roles of the motor banks | all the grouped stages | `unknown-pending-confirmation` | (GROUP-1) |
| The cryostream sensor / setpoint handles | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| The detector model and geometry | `AreaDetector`, `FluorescenceDetector` | `unknown-pending-confirmation` | (DET-1) |
| The automated sample changer | the experiment hutch | `unknown-pending-confirmation` | (ROBOT-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
