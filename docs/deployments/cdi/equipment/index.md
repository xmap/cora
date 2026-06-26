# The beamline

*The CDI beam path, area by area. CORA models the beamline as one root Asset (`CDI`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

CDI runs from the in-vacuum undulator through a first-optics hutch into an endstation where a KB mirror pair focuses the coherent beam onto the sample and the far-field diffraction pattern is recorded. Two enclosures carry it:

```
  9-ID-A  (optics hutch / FOE)              9-ID-C  (endstation)
  ----------------------------------        --------------------------------------
  IVU18 -> HDCM / DMM -> VPM / HPM          KB nanofocus -> BCU -> sample (Gon)
           white-beam / branch slits        towers          Eiger2 / Merlin
```

- [Source](../beamline.md) (`9-ID-A`): the IVU18 undulator and the storage-ring readback, then the optics, the silicon double-crystal monochromator and the double-multilayer monochromator, the vertical and horizontal pre-mirrors, the white-beam and branch slits, the attenuator foils, the master energy, and the upstream beam diagnostics. This page is generated from the descriptor.
- [Sample](sample.md) (`9-ID-C`): the KB nanofocusing mirror pair that forms the coherent spot, the beam-conditioning unit that trims it just before the sample, the sample goniometer, the endstation positioning towers, and the endstation diagnostic cameras.
- [Detector](detector.md) (`9-ID-C`): the Eiger2 and Merlin photon-counting area detectors that record the far-field coherent-diffraction pattern.
- [Controls](controls.md): the motion controllers and the timing seam, where the CDI profile collection's missing trigger box is the headline question.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). The one detail to flag is that the 09IDB branch zone (the `BranchSlit` and the quadrant `BeamPositionMonitor`) may be a distinct enclosure (ENC-1); it is folded into the optics hutch here. The loose families are the `BeamPositionMonitor`, shared with other deployments and held for gate-review, and the `StorageRing` machine-state supply.
