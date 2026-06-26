# The beamline

*The I20-1 beam path, area by area. CORA models the beamline as one root Asset (`I20-1`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference. The roster is partial: the dispersive heart of EDE is an open question, not a modelled device.*

In full EDE the beam passes a bent-crystal polychromator that fans an energy band across the sample, and a strip detector reads the whole spectrum at once. The dodal commissioning module models the periphery of that, not the dispersing crystal or the strip detector:

```
  I20-1-OH  (optics hutch)                   I20-1-EH  (experiment hutch)
  ----------------------------------------   ------------------------------------
  source -> [polychromator: POLY-1] ------>  sample stage -> [strip det: STRIP-1]
            turbo slit (selects energy)                       Xspress3 (fluorescence)
            PMAC fly-scan, PandA timing
```

- [Source](../beamline.md) (`I20-1-OH`): the insertion-device source, absent from the commissioning module (SRC-1). This page is generated from the descriptor.
- [Sample](sample.md) (`I20-1-EH`): the sample alignment stage (a dodal mock, STAGE-1).
- [Detector](detector.md) (`I20-1-EH`): the fluorescence Xspress3 (a dodal skip, DET-1); the dispersive strip detector is the open question (STRIP-1).
- [Controls](controls.md): the turbo slit that selects energy from the polychromatic fan, the PMAC trajectory controller, and the PandA timing boxes.

Each modelled device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV (the source has none); none binds a vendor Model, and no loose family is coined. The bracketed items above, the polychromator (POLY-1) and the strip detector (STRIP-1), are the EDE heart and are named open questions, not modelled, because they are not in the public source.
