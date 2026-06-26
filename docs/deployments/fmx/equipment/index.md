# The beamline

*The FMX beam path, area by area. CORA models the beamline as one root Asset (`FMX`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

FMX is a microfocus MX branch at sector 17-ID: a shared undulator and a front-end / optics enclosure (17-ID-A) feeding a dedicated experiment enclosure (17-ID-C) that holds the KB microfocus mirrors, the goniometer, the robot, and the Eiger.

```
  17-ID-A  (FOE, shared with AMX)              17-ID-C  (FMX experiment)
  ------------------------------------------   -------------------------------------
  IVU21 -> HDCM -> HFM -> high-heat slit ----> KB mirrors -> CRL -> attenuators
           (energy)                            goniometer (omega) + robot
                                               Eiger 16M  <- rotation data
                                               Mercury XRF <- edge selection
```

- [Source](../beamline.md) (`17-ID-A`): the shared IVU21 undulator, the front-end and photon shutters, and the high-heat-load slit, then the optics, the horizontal double-crystal monochromator, the horizontal focusing mirror, the KB microfocus pair, the CRL transfocator, the BCU and RI attenuators, and the slits. This page is generated from the descriptor.
- [Sample](sample.md) (`17-ID-C`): the micro-goniometer, the automated sample-changing robot, the on-axis viewing camera and illumination, and the sample cooling.
- [Detector](detector.md): the Eiger area detector, the Mercury fluorescence detector, the beamstop, and the beam-position and flux monitors.
- [Controls](controls.md): the rotation vector controller, the Zebra trigger box, and the LSDC / mxtools seam.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). FMX graduates nothing: it reuses the i03 MX vocabulary (the graduated `Goniometer`, `Camera`, and `Transfocator`); the loose families are the held `Backlight` and `BeamPositionMonitor`, and the robot is a Positioner Asset with no Family.
