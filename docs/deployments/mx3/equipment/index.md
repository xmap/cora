# The beamline

*The MX3 beam path, area by area. CORA models the beamline as one root Asset (`MX3`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

MX3 runs from the storage-ring source through optics into an experiment hutch where a cryocooled crystal on the MD3 microdiffractometer rotates through an oscillation while the Eiger reads frames, with the ISARA robot mounting samples between datasets.

```
  MX3-OH  (optics hutch)                    MX3-EH  (experiment hutch)
  ----------------------------------        --------------------------------------
  ring -> WB shutter -> DMM mono ---------> MD3 goniometer -> Eiger (SIMPLON REST)
          attenuator                        (Exporter)        ISARA robot, cryojet
```

- [Source](../beamline.md) (`MX3-OH`): the storage-ring current monitor and the front-end shutter, then the optics, the double-multilayer monochromator, the master energy axis, and the attenuator. This page is generated from the descriptor.
- [Sample](sample.md) (`MX3-EH`): the MD3 microdiffractometer goniometer, the cryojet cooling, the backlight, and the beamstop, plus the ISARA sample-exchange robot.
- [Detector](detector.md) (`MX3-EH`): the DECTRIS Eiger, its translation stage, the on-axis viewing camera, the flux monitor, and the beam-position / steering monitor.
- [Controls](controls.md): the shutters, the motion controllers, and the heterogeneous control-plane seam (EPICS + Exporter + SIMPLON REST + robot TCP).

Each device binds a catalog [Family](../../../catalog/families.md). Most carry a verified EPICS PV; the `Goniometer` (Exporter), `EigerDetector` (SIMPLON REST), and the MD3 `Backlight` / `BeamStop` (Exporter) are on non-EPICS control planes and carry no PV. None binds a vendor Model (part numbers are not in the library). The loose families are `StorageRing`, `BeamPositionMonitor`, and `Backlight`.
