# The beamline

*The SMI beam path, area by area. CORA models the beamline as one root Asset (`SMI`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

SMI runs from an in-vacuum undulator through a first-optics hutch into an experiment hutch where the focused beam meets a film, interface, or bulk sample and the scattering pattern is recorded on two Pilatus detectors at once. Two enclosures carry it:

```
  12-ID-A  (optics hutch / FOE)            12-ID-C  (experiment hutch)
  ----------------------------------       --------------------------------------
  IVU -> DCM -> HF / VF mirrors            CRL -> sample -> SAXS 2M (flight path, Q)
         WB slit -> attenuators                   (grazing)   WAXS 900KW (swing arc)
```

- [Source](../beamline.md) (`12-ID-A`): the in-vacuum undulator and the front-end shutter, then the optics, the double-crystal monochromator, the horizontal and vertical focusing mirrors, the compound-refractive-lens transfocator, the white-beam and secondary-source slits, and the attenuator banks. This page is generated from the descriptor.
- [Sample](sample.md) (`12-ID-C`): the experiment-hutch beam-defining and guard slits, the HUB sample stack with grazing-incidence axes, and the Linkam sample environment.
- [Detector](detector.md) (`12-ID-C`): the simultaneous SAXS and WAXS Pilatus detectors, the SAXS camera-length stage and beamstops, the flux monitor, and the fluorescence detector.
- [Controls](controls.md): the fast shutter that gates the exposure, and the motion controllers.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). The loose families are the `Transfocator` and the `BeamPositionMonitor`, both shared with other deployments and held for gate-review.
