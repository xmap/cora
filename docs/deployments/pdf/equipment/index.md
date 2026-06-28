# The beamline

*The PDF beam path, area by area. CORA models the beamline as one root Asset (`PDF`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

PDF runs from the shared 28-ID damping wiggler through a first-optics hutch into an endstation where a high-energy beam meets a powder or capillary sample and the total-scattering pattern is recorded on flat-panel and pixel detectors at two distances. Two enclosures carry it:

```
  28-ID-1-A  (optics hutch / FOE)           28-ID-1-B  (endstation)
  ----------------------------------        --------------------------------------
  wiggler -> SBM mono -> VFM mirror         cleanup slit -> spinner -> sample env
             white-beam slit                near / far detector towers (PE, Pilatus)
```

- [Source](../beamline.md) (`28-ID-1-A`): the shared 28-ID damping wiggler and the storage-ring readback, then the optics, the side-bounce monochromator, the vertical focusing mirror, the white-beam slit, and the master energy. This page is generated from the descriptor.
- [Sample](sample.md) (`28-ID-1-B`): the endstation cleanup slit, the fast shutter, the capillary spinner, the sample-environment stage, and the thermal-environment cluster (cryostream, cryostat, furnace).
- [Detector](detector.md) (`28-ID-1-B`): the PerkinElmer flat-panel and Pilatus pixel area detectors, the two detector towers that set the near and far distances, the beamstops, and the flux monitor.
- [Controls](controls.md): the software-triggered acquisition (no hardware timing box, as at XPD), the two-detector plan, and the motion controllers.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). PDF is the twin of [XPD](../../xpd/equipment/index.md) on the shared 28-ID damping wiggler and reuses its modelling; the one loose family is the `StorageRing` machine-state supply.
