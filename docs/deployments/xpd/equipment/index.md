# The beamline

*The XPD beam path, area by area. CORA models the beamline as one root Asset (`XPD`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

XPD runs from a high-flux insertion-device source through a first-optics hutch into an experiment hutch where the high-energy beam meets a powder or capillary sample and the scattering pattern is recorded on a large flat panel. Two enclosures carry it (a downstream high-resolution endstation, 28-ID-D, is deferred):

```
  28-ID-A  (optics hutch / FOE)            28-ID-C  (experiment hutch)
  ----------------------------------       --------------------------------------
  source -> double-Laue mono -> VFM        pinhole -> sample -> flat panel
            slit -> filters                          (diffractometer)   (distance = Q)
```

- [Source](../beamline.md) (`28-ID-A`): the insertion-device source, then the optics, the bent double-Laue monochromator, the vertical focusing mirror, the white-beam slit, and the filters. This page is generated from the descriptor. A high-resolution monochromator in the 28-ID-C hutch feeds the high-resolution endstation, deferred with it (ENDSTATION-1).
- [Sample](sample.md) (`28-ID-C`): the diffractometer holding the sample and detector arm, the sample-array stage, the beam-defining pinhole, and the cryostream / furnace sample environment.
- [Detector](detector.md) (`28-ID-C`): the large flat-panel area detectors, the distance stage that sets the accessible Q, the flux counters, and the exposure shutter.
- [Controls](controls.md): the software-triggered acquisition gated by the exposure shutter, and the motion controllers.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV (the insertion-device source has no PV in the public config); none binds a vendor Model (part numbers are not in the public config). The one loose family is the `BeamPositionMonitor`, shared with other deployments and held for gate-review.
