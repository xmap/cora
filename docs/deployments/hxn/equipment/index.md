# The beamline

*How HXN's areas relate. The beam runs left to right, source to detector; the sample is a focused spot the specimen is rastered through.*

HXN is a scanning hard X-ray nanoprobe: the optics hutch conditions and monochromates the beam, a focusing optic (zone plate or multilayer Laue lens) brings it to a nano-spot in the endstation, and the sample is scanned across that spot while several detectors record per dwell point.

```
        3-ID-A (optics hutch)                    3-ID-C (endstation)
  +------------------------------+   +-------------------------------------------+
  |  IVU20 undulator -> DCM ->   |   |  focusing optic (zone plate / MLL) -> OSA |
  |  3 mirrors (HCM/HFM/VMS) ->  |-->|  -> sample raster stack (+ rotary) ->     |
  |  white-beam slit -> SSA      |   |  fluorescence + pixel + flux detectors    |
  +------------------------------+   +-------------------------------------------+
        SOURCE stage                     SAMPLE stage        DETECTION stage

  Controls (cross-cutting): Zebra position-capture trigger; PMAC + Attocube ANC350 motion
  Resources: photon beam, cooling water, vacuum, power
```

- [Source](../beamline.md): the IVU20 undulator and the optics hutch (`3-ID-A`). The double-crystal monochromator sets the energy, three mirrors (collimating, focusing, vertical) steer and shape the beam, a white-beam slit defines it, and a secondary-source aperture defines the coherent probe. Rendered as the generated source-stage device walk.
- [Sample](sample.md): the endstation (`3-ID-C`). The zone plate or the crossed multilayer-Laue-lens pair focuses to the nano-spot; the order-sorting aperture and beam stop clean the focus; the nano-positioning stack rasters the sample through it.
- [Detector](detector.md): the per-point detectors read together during a scan: an energy-dispersive fluorescence spectrometer (element maps), pixel detectors (ptychography / diffraction), and flux counters (normalization).

Cutting across all three:

- [Controls](controls.md): the Zebra FPGA position-capture box that hardware-gates the per-point triggers off the scan position, and the motion controllers (Power PMAC for the fine raster, Attocube ANC350 for coarse nano-positioning).

The cross-cutting reference is the [Inventory](../inventory.md).
