# The beamline

*How FXI's areas relate. The beam runs left to right, source to detector, through three stages plus the cross-cutting controls and resources.*

FXI is a full-field transmission X-ray microscope: the condenser floods the sample with monochromatic beam, the sample sits on a rotating stage for tomography, and a zone plate magnifies the transmitted image onto a scintillator-relay camera. The structure is the same as the APS 2-BM pilot, with NSLS-II hardware and the diffractive TXM optics that 2-BM does not carry.

## The areas

```
        18-IDA (optics hutch)                 18-IDB (experiment hutch)
  +-----------------------------+   +--------------------------------------------+
  |  Source -> DCM -> mirrors   |   |  condenser -> sample(+rotary) -> zone plate |
  |  -> white-beam slit         |-->|  -> phase ring -> Bertrand lens             |
  |  -> filters -> flux monitors|   |  -> scintillator -> detector rails -> camera|
  +-----------------------------+   +--------------------------------------------+
        SOURCE stage                      SAMPLE stage        DETECTION stage

  Controls (cross-cutting): Zebra position-capture trigger + motion controllers
  Resources: photon beam, cooling water, vacuum, liquid nitrogen (DCM cooling)
```

- [Source](../beamline.md): the insertion-device source and the optics hutch (`18-IDA`). The double-crystal monochromator sets the energy, two mirrors steer and shape the beam, a white-beam slit defines it, attenuating filters trim flux, and three flux monitors diagnose it. Rendered as the generated source-stage device walk from the descriptor.
- [Sample](sample.md): the experiment hutch (`18-IDB`) sample side. The TXM sample stage places and rotates the specimen; the condenser, aperture, zone plate, phase ring, and Bertrand lens are the transmission-microscopy optics around it.
- [Detector](detector.md): the imaging detector. A scintillator converts the transmitted beam to visible light, the detector support rails set the propagation distance, and a camera records the magnified image.

Cutting across all three:

- [Controls](controls.md): the Zebra FPGA position-capture box that hardware-triggers the camera off the rotary encoder (the NSLS-II analog of 2-BM's Aerotech PSO), and the motion controllers that drive the stages.
- Resources: the supplies a run draws on, tracked under [Operations > Supplies](../operations.md#supplies).

The cross-cutting reference is the [Inventory](../inventory.md): the flat Asset tree by `parent_id`, with the PVs and the values still pending confirmation.
