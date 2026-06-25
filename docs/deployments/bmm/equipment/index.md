# The beamline

*How BMM's areas relate. The beam runs left to right, source to detector; the measurement is a sweep of the beam energy across an absorption edge.*

BMM is an X-ray absorption spectroscopy beamline: the optics hutch monochromates and focuses the bending-magnet beam, the endstation holds the sample (often a wheel of many samples) between ion chambers, and the experiment sweeps the monochromator energy while recording the per-energy detector readings.

```
        6-BM-A (optics hutch)                      6-BM-B (endstation)
  +------------------------------+   +-------------------------------------------+
  |  bending magnet -> M1 ->     |   |  I0 ion chamber -> sample (wheel) ->      |
  |  DCM (Si111) -> M2 ->        |-->|  It ion chamber -> reference foil -> Ir   |
  |  slits -> filters            |   |  (+ fluorescence Xspress3 off the sample) |
  +------------------------------+   +-------------------------------------------+
        SOURCE stage                     SAMPLE stage        DETECTION stage

  The measurement: sweep the DCM energy across an edge; record I0/It/Ir (+ fluorescence) per point.
  Controls (cross-cutting): the conducting engine sweeps energy; endstation motion controller.
  Resources: photon beam, cooling water, vacuum, liquid nitrogen (DCM cooling), power.
```

- [Source](../beamline.md): the bending-magnet source and the optics hutch (`6-BM-A`). The double-crystal monochromator sets the energy, two mirrors collimate and focus (and reject harmonics), slits define the beam, and filters attenuate it. Rendered as the generated source-stage device walk.
- [Sample](sample.md): the endstation (`6-BM-B`). The sample positioning table, the rotating sample wheel for batch XAS, and the reference-foil holder for per-scan energy calibration.
- [Detector](detector.md): the XAS detectors read at each energy point: the ion chambers (I0 incident, It transmitted, Ir reference) for transmission XAS, and the energy-dispersive detector for fluorescence XAS of dilute samples.

Cutting across all three:

- [Controls](controls.md): the conducting engine that sweeps the monochromator energy and reads the detectors per point (the energy-scan), and the endstation motion controller.

The cross-cutting reference is the [Inventory](../inventory.md).
