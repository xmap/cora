# The beamline

*The TPS 07A beam path, area by area. CORA models the beamline as one root Asset (`TPS 07A`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

TPS 07A runs from the IU22 undulator source through optics into an experiment hutch where a cryocooled crystal on the Arinax MD3 microdiffractometer rotates through an oscillation while the EIGER2 X 16M reads frames, with the ISARA robot mounting samples between datasets.

```
  TPS-07A-OH  (optics hutch)                  TPS-07A-EH  (experiment hutch)
  ----------------------------------          --------------------------------------
  ring -> WB shutter -> DCM ---------------->  MD3 goniometer -> EIGER2 X 16M (ZMQ)
          attenuator -> KB mirrors            ISARA robot, cryostream
```

- [Source](../beamline.md) (`TPS-07A-OH`): the storage-ring current monitor and the front-end shutter, then the optics, the double-crystal monochromator, the master energy axis, the attenuator, and the micro-focus mirrors. This page is generated from the descriptor.
- [Sample](sample.md) (`TPS-07A-EH`): the MD3 microdiffractometer goniometer, the cryostream cooling, and the beamstop, plus the ISARA sample-exchange robot.
- [Detector](detector.md) (`TPS-07A-EH`): the DECTRIS EIGER2 X 16M, its translation stage, the on-axis viewing camera, and the beam-position diagnostics.
- [Controls](controls.md): the shutters, the motion controllers, and the DCSS-over-EPICS orchestration seam.

Each device binds a catalog [Family](../../../catalog/families.md). Every device is on the EPICS floor (the `07a:` / `07a-ES:` namespace), reached through the EPICS Device Handler Server; unlike [MX3](../../mx3/equipment/index.md), no device sits on a separate transport. The EPICS PV namespace is verified, but per-device PV record strings are not in the public tree, so they are carried pending. None binds a vendor Model (part numbers are not in the source). The loose families are `StorageRing` and `PositionMonitor`.
