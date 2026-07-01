# Inventory

*The CORA Asset model for ID19 as modelled today: the planned device tree and what still needs confirming.*

This cut models the source, the optics, and the two main tomography endstations, micro-resolution (MR) and high-resolution (HR). The further endstations in the config (MH, MED, laminography, radiography, PCO) are noted, not modelled (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id19/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. ID19, an imaging beamline on the ESRF BLISS floor, coins **no new Family and changes nothing in the catalog**: microtomography is the existing `tomography` Method (see [Model](model.md#no-new-families-no-new-methods)). Control handles are filled with the real BLISS object and Tango device names read from the [public ID19 config](https://gitlab.esrf.fr/id19/beamline_configuration), carried confirm; no vendor Models are bound.

## The Asset tree

Root Asset `ID19` (`tier = Unit`, `facility_code = esrf`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Handle / note |
| --- | --- | --- | --- | --- |
| `ID19` | `Unit` | (root) | - | bound to the ESRF Site; the long imaging / tomography beamline |
| `InsertionDevices` | `Device` | InsertionDevice | id19-optics | undulators u13a/u32a/u17-6c/u32c + w150b wiggler (SRC-1) |
| `Monochromator` | `Device` | Monochromator | id19-optics | TripleMono (Id19Mono), Bragg 17-99 keV + Laue / multilayer (OPT-1) |
| `PrimarySlits` | `Device` | Slit | id19-optics | psu/psd/psf/psb + gap/offset (iceid193) |
| `SecondarySlits` | `Device` | Slit | id19-optics | ssu/ssd/ssf/ssb (iceid192) |
| `Transfocator` | `Device` | Transfocator | id19-optics | id19wbtfctrl, 8 Be lenses + pinhole (OPT-1) |
| `Attenuators` | `Device` | Filter | id19-optics | wba1/wba2 WhiteBeamAttenuator banks (OPT-1) |
| `FrontEndShutter` | `Device` | Shutter | id19-optics | //acs.esrf.fr:10000/fe/master/id19 (PSS-1) |
| `BeamShutter1` | `Device` | Shutter | id19-optics | id19/bsh/1 TangoShutter (PSS-1) |
| `BeamShutter2` | `Device` | Shutter | id19-optics | id19/bsh/2 TangoShutter (PSS-1) |
| `MR_RotationStage` | `Device` | RotaryStage | id19-experiment | mrsrot (Elmo); master motion, 900 deg/s (SAMPLE-1) |
| `MR_SampleStage` | `Device` | LinearStage | id19-experiment | mrsx/mrsy/mrxc/mryc/mryrot/mrsz; mrxyonsrot (SAMPLE-1) |
| `MR_Detector` | `Device` | Camera | id19-experiment | Lima frelon1/frelon2/pco4k/dimax_lid19det1 (DET-1) |
| `MR_DetectorStage` | `Device` | LinearStage | id19-experiment | hdx/hdy/hdz/hdthz propagation stages (DET-1) |
| `HR_RotationStage` | `Device` | RotaryStage | id19-experiment | hrsrot (Elmo_whistle); master motion, 900 deg/s (SAMPLE-1) |
| `HR_SampleStage` | `Device` | LinearStage | id19-experiment | hrsx/hrsy/hrsz/hrz0/hryrot; hrxyonsrot (SAMPLE-1) |
| `HR_Detector` | `Device` | Camera | id19-experiment | Lima frelon1/pco4k/dimax_lid19det2/basler1 (DET-1) |
| `HR_DetectorStage` | `Device` | LinearStage | id19-experiment | hrxc/hryc/hrzc carriage (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Slit`, `Transfocator`, `Filter`, `Shutter`, `RotaryStage`, `LinearStage`, `Camera`. Also two `MotionController` Assets on the [Controls](equipment/controls.md) page (the Elmo and IcePAP controllers). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| BLISS / Tango handles current against the live system | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| Insertion-device per-mode selection and energy reach | `InsertionDevices` | `unknown-pending-confirmation` | (SRC-1) |
| Mono mode mapping, transfocator recipe, attenuator foils | `Monochromator`, `Transfocator`, `Attenuators` | `unknown-pending-confirmation` | (OPT-1) |
| Operative rotation / sample axis set per endstation | the sample stages | `read-from-config-pending-confirmation` | (SAMPLE-1) |
| Operative Lima detector(s) and propagation axes per endstation | the detectors | `read-from-config-pending-confirmation` | (DET-1) |
| PSS permit signals behind the shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The further endstations (MH/MED/laminography/radio/PCO) | scope | `noted-not-modelled` | (ENDSTATION-1) |
| Vacuum extent and run supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
