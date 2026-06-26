# I20-1

*Energy-dispersive EXAFS (EDE) at Diamond Light Source: time-resolved X-ray absorption spectroscopy, where a bent-crystal polychromator fans an energy band across the sample and a strip detector reads the whole spectrum in one shot. This page describes how CORA would model and run I20-1; the model is reverse-engineered from the dodal controls library, not yet confirmed by Diamond staff, and is a deliberately partial first cut.*

| Property | Value |
| --- | --- |
| Asset | `I20-1` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`) |
| Sector | i20-1, the EDE branch of i20 (PV root `BL51P`, dodal module `p51`) |
| Status | Reverse-engineered from dodal (design-phase, partial) |
| Source | insertion device (not in the commissioning module, SRC-1) |

!!! note "How CORA would land on I20-1, and why this scaffold is partial"
    These pages describe how CORA would model, govern, and conduct I20-1, the eighth Diamond beamline. They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs) are read from the public [dodal](https://github.com/DiamondLightSource/dodal) controls library (`src/dodal/beamlines/p51.py`, the commissioning name for i20-1) and verified against it; every read value is carried `confirm` until staff verify it ([Open questions](questions.md)). **This is a deliberately partial first cut:** the dodal module is a thin commissioning roster that carries the EDE *peripherals* but not the two devices that define energy-dispersive EXAFS, the bent-crystal polychromator and the position-sensitive strip detector. Those are named as open questions, not fabricated. This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: dispersive, single-shot, time-resolved

I20-1 fills an axis the fleet did not have. CORA already models scanning XAS (NSLS-II BMM steps a monochromator through an absorption edge); EDE is the **dispersive** complement: a bent-crystal polychromator disperses a band of energies across the sample simultaneously, and a position-sensitive strip detector captures the entire absorption spectrum in one exposure, so a spectrum lands in sub-second time and a reaction can be followed as it happens. No energy scan, no moving mono.

The honest catch is that the dispersive heart of that, the polychromator and the strip detector, is not in the public commissioning module. What CORA can model from source is the EDE periphery: the turbo slit that selects an energy out of the dispersed fan, the trajectory PMAC and PandA timing that drive the fly-scan, the sample stage, and a fluorescence Xspress3. So I20-1 enters the fleet as a partial scaffold whose open questions name exactly what the dispersive technique still needs (POLY-1, STRIP-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the insertion-device source (absent from the commissioning module, SRC-1).
- [Sample](equipment/sample.md): the sample alignment stage (currently a dodal mock, STAGE-1).
- [Detector](equipment/detector.md): the fluorescence Xspress3 (currently dodal-skipped, DET-1); the dispersive strip detector is the open question (STRIP-1).

Cutting across, and central to EDE:

- [Controls](equipment/controls.md): the turbo slit that selects energy from the polychromatic fan, the trajectory PMAC, and the PandA timing boxes that gate the fly-scan.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): energy-dispersive / time-resolved EXAFS, the dispersive complement to scanning XAS, recorded as a pending Diamond Practice.

## Governance

[Governance](governance.md): who may act at I20-1 and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I20-1 content lives, and what the partial roster defers.
