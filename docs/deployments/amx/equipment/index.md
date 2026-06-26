# The beamline

*The AMX beam path, area by area. CORA models the beamline as one root Asset (`AMX`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

AMX is the high-throughput microfocus MX branch at sector 17-ID, FMX's sibling: a shared undulator and a front-end / optics enclosure (17-ID-A) feed a dedicated experiment enclosure (17-ID-B) that holds the KB mirrors, the goniometer, the EMBL robot, and the Eiger.

```
  17-ID-A  (FOE, shared with FMX)              17-ID-B  (AMX experiment)
  ------------------------------------------   -------------------------------------
  IVU21 -> VDCM -> TDM -> high-heat slit ----> KB mirrors -> BCU attenuator
           (energy)                            goniometer (omega) + EMBL robot
                                               Eiger     <- rotation data
                                               Mercury XRF <- edge selection
```

- [Source](../beamline.md) (`17-ID-A`): the shared IVU21 undulator, the front-end and photon shutters, and the high-heat-load slit, then the optics, the vertical double-crystal monochromator, the tandem-deflection mirrors, the KB microfocus pair, the beam-conditioning attenuator, and the slits. This page is generated from the descriptor.
- [Sample](sample.md) (`17-ID-B`): the micro-goniometer, the automated EMBL robot, and the on-axis viewing camera.
- [Detector](detector.md): the Eiger area detector, the Mercury fluorescence detector, the beamstop, and the beam-position and flux monitors.
- [Controls](controls.md): the Zebra trigger box, the rotation motion, and the LSDC / mxtools seam.

Each device the profile exposes binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; the shutters, the Eiger, and the motion controller are carried confirm-only where the profile omits them. AMX graduates nothing: as FMX's sibling it reuses the i03 / FMX MX vocabulary (the graduated `Goniometer`, `Camera`); the loose family is the held `BeamPositionMonitor`, and the robot is a Positioner Asset with no Family.
