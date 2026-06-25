# The beamline

*The ISS beam path, area by area. CORA models the beamline as one root Asset (`ISS`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

ISS is a single hard-X-ray branch at sector 8: an undulator source, an optics enclosure (8-ID-A) that conditions and sets the energy, and an experiment enclosure (8-ID-B) that holds the sample, the absorption detectors, and the two crystal emission spectrometers.

```
  8-ID-A  (optics / FOE)                         8-ID-B  (experiment)
  ------------------------------------------     -------------------------------------
  undulator -> HHM (trajectory) -> mirrors  -->  sample stage / goniometer
               HRM                  filter box    ion chambers (I0/It/Ir) -> EXAFS
               slits                              Xspress3 SDD            -> fluorescence
                                                  Johann / von Hamos      -> XES / HERFD
```

- [Source](../beamline.md) (`8-ID-A`): the 8-ID undulator and the front-end slit and shutters, then the optics, the high-heat-load trajectory monochromator (HHM), the high-resolution monochromator (HRM), the collimating and focusing mirrors, the harmonic-rejection mirror, the filter box, and the slits. This page is generated from the descriptor.
- [Sample](sample.md) (`8-ID-B`): the sample stage and goniometer, the energy-calibration reference foil wheel, and the thermal environment.
- [Detector](detector.md): the transmission / fluorescence ion chambers, the silicon-drift fluorescence detector, the area detector, and the Johann and von Hamos crystal emission spectrometers.
- [Controls](controls.md): the trajectory fly-scan, the analog pizza box readout, and the motion controllers.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). The crystal `EmissionSpectrometer` graduated this PR (its second sighting, after LCLS-MFX); the one loose family is the `BeamPositionMonitor`, held for gate-review.
