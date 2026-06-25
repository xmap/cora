# The beamline

*The SST beam path, area by area. CORA models the beamline as one root Asset (`SST`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference.*

SST is two beamlines in one sector: a soft branch and a tender branch, each with its own undulator and monochromator, feeding several endstations. The endstation in control selects the active branch.

```
  7-ID-A  (optics / FOE)                       SST-1 (soft) / SST-2 (tender)
  ------------------------------------------   -------------------------------------
  EPU60 -> PGM (soft) ---> M1/M3 mirrors ----> RSoXS CCD / NEXAFS calorimeter (SST-1)
  U42   -> DCM (tender) -> L1 mirror --------> HAXPES electron analyzer (SST-2)
          slits / exit slit
```

- [Source](../beamline.md) (`7-ID-A`): the two branch undulators (soft EPU60, tender U42) and the front-end shutter, then the optics, the soft plane-grating monochromator, the tender double-crystal monochromator, the first and per-branch mirrors, and the white-beam, exit, and `HAXPESSlit` slits. This page is generated from the descriptor.
- [Sample](sample.md) (`SST-1` / `SST-2`): the soft (RSoXS) and tender (HAXPES) sample manipulators, and the thermal environment.
- [Detector](detector.md): the soft-scattering CCD, the hemispherical electron analyzer, the microcalorimeter, the flux monitors, and the beamstop.
- [Controls](controls.md): the fast shutter, the branch-selection, and the motion controllers.

Each device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV; none binds a vendor Model (part numbers are not in the public config). The loose families are the hemispherical `ElectronAnalyzer` (a graduation candidate at its second sighting) and the `BeamPositionMonitor`, both held for gate-review.
