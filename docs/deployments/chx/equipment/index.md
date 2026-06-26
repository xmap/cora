# The beamline

*The CHX beam path, area by area. CORA models the beamline as one root Asset (`CHX`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

CHX runs from the in-vacuum undulator through a first-optics hutch into a long endstation where the coherent beam meets the sample and the speckle pattern is recorded. Two enclosures carry it:

```
  11-ID-A  (optics hutch / FOE)            11-ID-B  (endstation)
  ----------------------------------       --------------------------------------
  IVU20  ->  DCM / DMM  ->  HDM mirror      BDS / guard slits -> sample -> Eiger
             transfocator -> slits          GI mirror                      beamstop
```

- [Source](../beamline.md) (`11-ID-A`): the IVU20 undulator and the front-end shutter, then the optics, the silicon and multilayer monochromators, the horizontal-deflecting mirror, the compound-refractive-lens transfocator, and the pink/mono-beam slits. This page is generated from the descriptor.
- [Sample](sample.md) (`11-ID-B`): the endstation beam-defining and guard slits that condition the coherent beam, the grazing-incidence mirror, the sample stack positioned in the coherent focus, and the Linkam thermal stage.
- [Detector](detector.md) (`11-ID-B`): the Eiger area detectors that record the speckle time series, the SAXS detector positioner and beamstop, the flux counter, and the occasional fluorescence detector.
- [Controls](controls.md): the Zebra trigger gating the fast shutter and detector frames, and the motion controllers.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). The compound-refractive-lens optic reuses the graduated `Transfocator` catalog Family (a CRL focusing optic, shared with other deployments). The one loose family is the `BeamPositionMonitor`, shared with other deployments and held for gate-review.
