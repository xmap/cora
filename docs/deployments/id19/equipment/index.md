# The beamline

*ID19, area by area. CORA models the beamline as one root Asset (`ID19`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference. ID19 is CORA's first imaging beamline on a non-EPICS control floor, reverse-engineered from the beamline's own public BLISS config.*

ID19 is the ESRF's long hard X-ray imaging / tomography beamline: its long source-to-sample distance gives the beam high spatial coherence, so a sample spun through the beam, imaged by a downstream area detector, yields microtomography, radiography, and propagation phase-contrast imaging (the `tomography` Method, TECH-1). This cut models the source, the optics, and the two main tomography endstations: micro-resolution (MR) and high-resolution (HR). The further endstations in the config (MH, MED, laminography, radiography, PCO) are noted, not modelled (ENDSTATION-1).

CORA models stations as containment trees: an Asset nests under its station through `parent_id`, and controls relate sideways through `controller_id`. The root Asset is `ID19` (`tier=Unit`, `facility_code=esrf`); the optics hutch is the enclosure `id19-optics` and the experiment hutch is `id19-experiment` (ENC-1).

```
  id19-optics  (optics hutch)                  id19-experiment  (experiment hutch)
  ----------------------------------------     ------------------------------------------
  InsertionDevices (undulators + wiggler)      MR_RotationStage -> MR_Detector
  Monochromator (TripleMono)                   MR_SampleStage      MR_DetectorStage
  PrimarySlits / SecondarySlits
  Transfocator / Attenuators                   HR_RotationStage -> HR_Detector
  FrontEndShutter / BeamShutter1 / 2           HR_SampleStage      HR_DetectorStage
```

## Stations

- [Source](../beamline.md): the insertion-device source (`InsertionDevices`: undulators + the w150b wiggler) and the conditioning optics (`Monochromator`, `PrimarySlits`, `SecondarySlits`, `Transfocator`, `Attenuators`) and the shutters (`FrontEndShutter`, `BeamShutter1`, `BeamShutter2`). This page is generated from the descriptor.
- [Sample](sample.md): the MR and HR tomographic rotation stages (`MR_RotationStage`, `HR_RotationStage`) and their sample positioning stacks (`MR_SampleStage`, `HR_SampleStage`) (SAMPLE-1).
- [Detector](detector.md): the MR and HR Lima area detectors (`MR_Detector`, `HR_Detector`, Frelon / PCO / Basler) and their propagation-distance stages (`MR_DetectorStage`, `HR_DetectorStage`) (DET-1).

Each modelled device binds a catalog [Family](../../../catalog/families.md) and carries its real BLISS / Tango control handle, read from the [public ID19 config](https://gitlab.esrf.fr/id19/beamline_configuration) and carried confirm (CTRL-1). The technique is the existing tomography [Method](../../../catalog/methods.md) (TECH-1), not a new device class.

## Shared

- [Controls](controls.md): the seam between CORA and the ESRF floor (ESRF BLISS / Tango over the `ControlPort`), the Elmo and IcePAP motion controllers, and where the deferred pieces are tracked (CTRL-1). The PSS permit signals behind the shutters are not in the config and carried pending (PSS-1).
- Resources: the photon beam delivered from the source, plus cooling water and vacuum. These site utilities are carried pending (SUP-1).

## Reference

- [Inventory](../inventory.md): the flat list of every modelled Asset, its Family, its handle, and its open question.
