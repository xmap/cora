# The beamline

*How SRX's areas relate. The beam runs left to right, source to detector; the sample is a KB-focused spot the specimen is rastered through, with several detectors selecting the technique.*

SRX is a multi-technique hard X-ray microprobe: the optics hutch monochromates and pre-focuses the undulator beam, a KB mirror pair brings it to a submicron spot in the nano endstation, and the detector read selects the technique (fluorescence for XRF/XANES, a pixel detector for diffraction, the PCO for imaging).

```
        5-ID-A (optics hutch)                    5-ID-D (nano endstation)
  +------------------------------+   +-------------------------------------------+
  |  IVU21 undulator -> HDCM ->  |   |  KB nanofocus -> sample raster (+ rotary) |
  |  focusing mirror -> slits -> |-->|  -> Xspress3 (XRF/XANES) | Merlin/Dexela/  |
  |  secondary-source aperture   |   |     Eiger (diffraction) | PCO (imaging)   |
  +------------------------------+   +-------------------------------------------+
        SOURCE stage                     SAMPLE stage        DETECTION stage

  Techniques select by detector: XRF mapping, XANES, XRF-tomography, diffraction, imaging.
  Controls (cross-cutting): Zebra position-capture trigger; endstation motion controllers.
  Resources: photon beam, cooling water, vacuum, liquid nitrogen (HDCM cryocooler), power.
```

- [Source](../beamline.md): the IVU21 undulator and the optics hutch (`5-ID-A`). The high-heat-load monochromator sets the energy, the focusing mirror pre-focuses, slits define the white/pink beam, and a secondary-source aperture defines the coherent source for the nano endstation. Rendered as the generated source-stage device walk.
- [Sample](sample.md): the nano endstation (`5-ID-D`). The KB nanofocus mirror pair, the sample raster stack (plus a rotation for XRF-tomography), the attenuators, and sample-environment thermal control.
- [Detector](detector.md): the detector set that selects the technique: the energy-dispersive fluorescence detector (XRF/XANES), the pixel detectors (diffraction), the PCO imaging camera, and the flux counters.

Cutting across all three:

- [Controls](controls.md): the Zebra FPGA position-capture box that hardware-gates per-point triggers during a fly XRF raster, and the endstation motion controllers.

The cross-cutting reference is the [Inventory](../inventory.md).
