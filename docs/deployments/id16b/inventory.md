# Inventory

*The CORA Asset model for ID16B as modelled today: the planned device tree and what still needs confirming.*

This cut models the source, the optics (including the KB nanofocus), the sample-scanning stack, and the two detection chains. The sample environments (cryostream, furnace, xeol) are noted, not modelled (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id16b/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. ID16B, the fleet's first KB nanoprobe with XRF and CORA's third non-EPICS beamline, coins **no new Family and changes nothing in the catalog** (see [Model](model.md#no-new-families-two-reused-methods)). Control handles are filled with the real BLISS object and Tango device names read from the [public ID16B config](https://gitlab.esrf.fr/id16b/beamline_configuration), carried confirm; no vendor Models are bound.

## The Asset tree

Root Asset `ID16B` (`tier = Unit`, `facility_code = esrf`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Handle / note |
| --- | --- | --- | --- | --- |
| `ID16B` | `Unit` | (root) | - | bound to the ESRF Site; the nano-analysis beamline |
| `InsertionDevice` | `Device` | InsertionDevice | id16b-optics | U205 undulator (SRC-1) |
| `Monochromator` | `Device` | Monochromator | id16b-optics | Kohzu DCM (mono/Edcm, iceid162), Si111/333/311 (OPT-1) |
| `PrimarySlits` | `Device` | Slit | id16b-optics | s1h_slits / s1v_slits |
| `SecondarySlits` | `Device` | Slit | id16b-optics | s2_slits |
| `BeamMonitors` | `Device` | FluxMonitor | id16b-optics | EBV bpm2/bpm3/bpm5 (Lima + diode) (DIAG-1) |
| `FastShutter` | `Device` | Shutter | id16b-optics | fshut (iceid164) (PSS-1) |
| `KBMirrors` | `Device` | Mirror | id16b-experiment | KB nanofocus pair (kbx/cfocus/cfocus2, iceid164) (OPT-1) |
| `ThirdSlits` | `Device` | Slit | id16b-experiment | s3h_slits / s3v_slits (iceid164) |
| `SampleRotation` | `Device` | RotaryStage | id16b-experiment | srot (etel id16b/dsc2p/rot16), srot2 (SAMPLE-1) |
| `SampleStage` | `Device` | LinearStage | id16b-experiment | sx/sy/sz coarse positioning (SAMPLE-1) |
| `SampleScanner` | `Device` | LinearStage | id16b-experiment | sampy/sampz/sypz PI piezo raster (SAMPLE-1) |
| `FluoDetector` | `Device` | EnergyDispersiveSpectrometer | id16b-experiment | FalconX fxb (id16b/moscav1/fxb), fx8 (DET-1) |
| `OpticalSpectrometer` | `Device` | EnergyDispersiveSpectrometer | id16b-experiment | QEPro / Hamamatsu (id16b/moscav1/*) (DET-2) |
| `TomoDetector` | `Device` | Camera | id16b-experiment | PCO pco1/pco2, Zyla (Lima) (DET-1) |
| `DetectorStage` | `Device` | LinearStage | id16b-experiment | DETPOS detector positioning (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Slit`, `FluxMonitor`, `Shutter`, `Mirror`, `RotaryStage`, `LinearStage`, `EnergyDispersiveSpectrometer`, `Camera`. Also two `MotionController` Assets on the [Controls](equipment/controls.md) page (the IcePAP racks and the PI piezo scanners). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| BLISS / Tango handles current against the live system | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| U205 undulator energy reach and gap mapping | `InsertionDevice` | `unknown-pending-confirmation` | (SRC-1) |
| Kohzu crystal-pair selection, KB focal spot / working distance | `Monochromator`, `KBMirrors` | `unknown-pending-confirmation` | (OPT-1) |
| Operative rotation / coarse / piezo-scanner axes per mode | the sample stages | `read-from-config-pending-confirmation` | (SAMPLE-1) |
| Operative XRF and area detectors per mode, detector-stage axes | the detectors | `read-from-config-pending-confirmation` | (DET-1) |
| Optical spectrometer role (xeol / diagnostic / science) | `OpticalSpectrometer` | `unknown-pending-confirmation` | (DET-2) |
| PSS permit signals behind the shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Sample environments (cryo / furnace / xeol) | scope | `noted-not-modelled` | (ENV-1) |
| Vacuum extent and run supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
