# The beamline

*The I13-1 coherence-branch endstation, area by area. CORA models the beamline as one root Asset (`I13-1`) with the devices nested below it; this page is the human walk, the [Inventory](../inventory.md) is the flat reference. This is a partial first cut: only the coherence-branch endstation is modelled, because that is all the public source exposes.*

I13-1 is the coherence branch of Diamond's I13 (Hard X-ray Imaging and Coherence), where a coherent hard X-ray beam is raster-scanned across the sample and a real-space image is reconstructed from the far-field diffraction it records (ptychography and coherent diffraction imaging, TECH-1). The PV prefix is `BL13J`. The public dodal module (`src/dodal/beamlines/i13_1.py`) exposes only the endstation: the sample-scanning stage, a side viewing camera, and the Merlin coherent-diffraction detector. The shared I13 source and optics (undulator, monochromator, mirrors, slits) are upstream and absent from that module, so they are deferred, not invented (SRC-1, OPT-1). This is the same partial-first-cut posture as I20-1.

CORA models stations as containment trees: an Asset nests under its station through `parent_id`, and controls relate sideways through `controller_id`. The root Asset is `I13-1` (`tier=Unit`, `facility_code=diamond`); the coherence-branch experiment hutch is the enclosure `i13-1` (ENC-1).

```
  Source  (storage ring, observe-only)        i13-1  (coherence-branch hutch, BL13J)
  ----------------------------------------     ------------------------------------------
  storage ring [shared src/optics: SRC-1,      sample stage  ->  Merlin detector
                OPT-1]                          side camera (alignment)
```

## Stations

- [Source](../beamline.md): the machine-level storage ring (a loose `StorageRing`, machine state, observe-only). The shared I13 source and optics are upstream of the endstation and absent from the dodal module, so they are deferred (MACHINE-1, SRC-1, OPT-1). This page is generated from the descriptor.
- [Sample](sample.md): the PI piezo sample-scanning stage (`BL13J-MO-PI-02:`), whose raster is the operative ptychography motion (SAMPLE-1).
- [Detector](detector.md): the Merlin / Medipix3 photon-counting area detector that records the far-field coherent-diffraction pattern (`BL13J-EA-DET-04:`), plus the Aravis / GenICam side viewing camera used for sample alignment (`BL13J-OP-FLOAT-03:`) (DET-1).

Each modelled device binds a catalog [Family](../../../catalog/families.md) and a verified EPICS PV (the storage ring has none); none binds a vendor Model, and no loose family is coined for coherent imaging. The novelty of this beamline is an acquisition shape and a reconstruction, that is a [Method](../../../catalog/methods.md) (ptychography / CDI, TECH-1), not a new device class: the devices are a raster `LinearStage` and two `Camera` instances.

## Shared

- [Controls](controls.md): the seam between CORA and the Diamond floor (Diamond EPICS / ophyd-async over the `ControlPort`), and where the deferred and absent pieces are tracked (CTRL-1). The PSS search-and-secure permit signals and the photon / front-end shutters are absent from the dodal module and carried pending, not invented (PSS-1).
- Resources: the photon beam delivered from the shared source, plus cooling water and vacuum. These site utilities are not in the endstation module and are carried pending (SUP-1).

## Reference

- [Inventory](../inventory.md): the flat list of every modelled Asset, its Family, its PV, and its open question.
