# The beamline

*The XFM beam path, area by area. CORA models the beamline as one root Asset (`XFM`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

XFM is a bending-magnet scanning-XRF microprobe at sector 4-BM: a bending-magnet source and an optics enclosure (4-BM-A) feeding the endstation (4-BM-C) that holds the raster stage and the fluorescence detectors. The public profile exposes only the endstation, so the optics are carried confirm-only.

```
  4-BM-A  (optics)                              4-BM-C  (endstation)
  ------------------------------------------    -------------------------------------
  BM source -> DCM -> focusing optic -------->  UTS raster stage (X/Y/Z)
               slits  (confirm-only)            Xspress3 SDD  -> XRF map
                                                Maia array    -> fast fly map
                                                SIS3820 scaler -> I0 flux
```

- [Source](../beamline.md) (`4-BM-A`): the bending-magnet source and the front-end / photon shutters, then the optics, the double-crystal monochromator, the microfocusing optic, and the beam-defining slits. The optics are not in the profile collection, so they are carried confirm-only. This page is generated from the descriptor.
- [Sample](sample.md) (`4-BM-C`): the UTS raster scanning stage.
- [Detector](detector.md): the Xspress3 silicon-drift fluorescence detector, the Maia continuous-mapping array, and the scaler flux channels.
- [Controls](controls.md): the scaler-counted raster, the Maia fly-scan, and the seam with the floor.

Each device that the profile exposes binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; the source and optics bind their Families confirm-only (no PV, not in the profile). XFM graduates nothing: it reuses the 2-ID / SRX scanning-XRF vocabulary, and the bending-magnet source binds the loose `Beam` supply.
