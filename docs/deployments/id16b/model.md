# Model

*The developer's by-kind index: where each CORA aggregate's ID16B content lives, why this nanoprobe deployment coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID16B |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes ID16B new

ID16B is CORA's **third non-EPICS deployment** (after ID32 and ID19) and the fleet's **first KB nanoprobe with XRF**. The novelty sits on two axes, both below the technique layer:

- **A second BLISS / Tango floor.** ID16B confirms the ID19 seam pattern is repeatable: motion stages are BLISS axes (IcePAP racks, PI piezo scanners, etel Tango motors), the fluorescence detector is a MOSCA / FalconX Tango device, the area detectors are Lima device servers, and CORA's edge conducts over the `ControlPort` against that floor (CTRL-1, see [Controls](controls.md)).
- **The first KB nanoprobe with XRF.** The Kirkpatrick-Baez mirror pair focuses the beam to a nanoprobe, and an energy-dispersive fluorescence detector reads a spectrum per raster point. This device combination is new to the fleet, but every part binds an existing Family.

## No new families, two reused methods

ID16B holds the vocabulary constant; that is deliberate, so the new axes (floor, nanoprobe device set) are isolated.

- **The KB mirrors bind the catalog `Mirror`.** The Kirkpatrick-Baez focusing pair is the nanoprobe; a focusing mirror is what `Mirror` is (OPT-1).
- **The fluorescence detector binds the catalog `EnergyDispersiveSpectrometer`.** ID16B's FalconX silicon-drift detector reads a per-point energy spectrum, a Sensor not a 2D Frame, the same shape as the XFM Xspress3 and the 2-ID / SRX detectors (DET-1). The optical spectrometer (QEPro / Hamamatsu) reuses the same Family (DET-2).
- **The area detectors bind the catalog `Camera`, which presents the Detector Role.** The PCO and Zyla indirect-detection cameras for nano-tomography are thin `Camera` instances (DET-1).
- **The stages bind `RotaryStage` and `LinearStage`.** Sample rotation (the tomo / fluo-tomo master motion), coarse positioning, and the PI piezo raster scanner (the nano-XRF mapping motion) (SAMPLE-1).
- **The optics bind existing Families.** `Monochromator` (the Kohzu DCM), `Slit` (primary / secondary / sample-side), `FluxMonitor` (the EBV beam monitors), `Shutter` (the fast shutter), `InsertionDevice` (the U205 undulator).
- **The Methods are reused.** Nano-tomography is the existing `tomography` Method; nano-XRF mapping is the pending `scanning_fluorescence_microscopy` Method (2-ID / XFM / LIX). ID16B is a further consumer of each (TECH-1, METHOD-1).

ID16B coins no new Family, nothing graduates, and the catalog is unchanged.

## Deliberately not here yet

- **The sample environments (`ENV-1`).** The config carries a cryostream, a furnace, and a xeol environment with Eurotherm / nanodac regulation. A `Cryostat` Family is not yet in the catalog; the sample environment is deferred to keep this cut vocabulary-neutral. It is the natural first candidate for a future cut (and a rule-of-three watch for a sample-environment Family across ID16B, the 4-ID magnet / temperature stack, and others).
- **The PSS permit signals (`PSS-1`).** The shutter handles are known; the permit signals behind them are not in the config; carried pending, not invented.
- **Vendor models, serials, focal-spot sizes, and physical positions.** Not in the config; carried confirm.
- **The simulated devices and full asset-tree scenarios.** No `test_id16b_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
