# The beamline

*ID16B, area by area. CORA models the beamline as one root Asset (`ID16B`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference. ID16B is CORA's first nanoprobe and second non-EPICS beamline, reverse-engineered from the beamline's own public BLISS config.*

ID16B is the ESRF nano-analysis / nano-imaging beamline: a Kirkpatrick-Baez mirror pair focuses the beam to a nanoprobe, and the beamline runs nano-tomography (the `tomography` Method) and nano-XRF mapping (the pending `scanning_fluorescence_microscopy` Method), including fluorescence-tomography. This cut models the source, the optics, the KB nanofocus, the sample-scanning stack, and the two detection chains. The sample environments (cryostream, furnace, xeol) are noted, not modelled (ENV-1).

CORA models stations as containment trees: an Asset nests under its station through `parent_id`, and controls relate sideways through `controller_id`. The root Asset is `ID16B` (`tier=Unit`, `facility_code=esrf`); the optics hutch is the enclosure `id16b-optics` and the experiment hutch is `id16b-experiment` (ENC-1).

```
  id16b-optics  (optics hutch)                 id16b-experiment  (experiment hutch)
  ----------------------------------------     ------------------------------------------
  InsertionDevice (U205 undulator)             KBMirrors (nanofocus) -> nanoprobe
  Monochromator (Kohzu DCM)                    SampleRotation / SampleStage / SampleScanner
  PrimarySlits / SecondarySlits                ThirdSlits
  BeamMonitors / FastShutter                   FluoDetector / OpticalSpectrometer
                                               TomoDetector / DetectorStage
```

## Stations

- [Source](../beamline.md): the U205 undulator (`InsertionDevice`) and the conditioning optics (`Monochromator` Kohzu DCM, `PrimarySlits`, `SecondarySlits`, `BeamMonitors`) and the `FastShutter`. This page is generated from the descriptor.
- [Sample](sample.md): the KB nanofocus (`KBMirrors`), the sample-side `ThirdSlits`, and the sample-scanning stack (`SampleRotation`, `SampleStage`, `SampleScanner`) (OPT-1, SAMPLE-1).
- [Detector](detector.md): the `FluoDetector` (FalconX XRF) and `OpticalSpectrometer`, the `TomoDetector` (PCO / Zyla area detectors), and the `DetectorStage` (DET-1, DET-2).

Each modelled device binds a catalog [Family](../../../catalog/families.md) and carries its real BLISS / Tango control handle, read from the [public ID16B config](https://gitlab.esrf.fr/id16b/beamline_configuration) and carried confirm (CTRL-1). The techniques are the existing tomography and the pending scanning-fluorescence [Methods](../../../catalog/methods.md) (TECH-1, METHOD-1), not new device classes.

## Shared

- [Controls](controls.md): the seam between CORA and the ESRF floor (ESRF BLISS / Tango over the `ControlPort`, CORA's second non-EPICS floor), the IcePAP and PI piezo motion controllers, and where the deferred pieces are tracked (CTRL-1). The PSS permit signals behind the shutters are not in the config and carried pending (PSS-1).
- Resources: the photon beam delivered from the source, plus cooling water and vacuum. These site utilities are carried pending (SUP-1).

## Reference

- [Inventory](../inventory.md): the flat list of every modelled Asset, its Family, its handle, and its open question.
