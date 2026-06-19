# Experiment

*The live operational view. This page describes the shape; the running app serves the data.*

Unlike the configured zones (Hardware, Techniques, Operations, Governance), the subjects, runs, campaigns,
datasets, and decisions are live per-experiment data. Their system of record is CORA's read-API, not a doc page,
so this page gives only the shape and one illustrative example. See [Model](../../architecture/model.md) for the
aggregate shapes.

- **Subject**: the sample being measured; custody runs `Received` to `Returned` / `Stored` / `Discarded`.
- **Run**: the operator-started execution of a Plan (the measurement batch); its task-lens companion is the
  [Procedure](procedures.md). Both can produce a Dataset.
- **Campaign**: Runs grouped under a coordinated study; intent `Coordination` / `Series` / `Sweep` / `Block`.
- **Dataset**: a data artifact (URI, checksum, lineage) with intent `Trial` or `Production`.
- **Decision**: a structured-audit choice by a human or agent; at 2-BM the `RunDebriefer` records
  `NominalCompletion` / `DegradedCompletion` / `EquipmentAbort`.

## An illustrative thread

Not a live record. A sandstone-core Subject arrives under a proposal, is mounted on the sample tower, and a
tomography Run (in a `Coordination` Campaign) produces a `Production` Dataset; at completion the `RunDebriefer`
records `NominalCompletion`, and the Subject is `Returned`. The real instances are served live by the app.

## Shutter state at run start

Both 2-BM safety shutters are open before a tomography run begins, opened by the operator at session start. The front-end `FrontEndShutter` (FES) is then kept open continuously for the thermal stability of the beamline optics and is not toggled per scan. The B-station `StationShutter` (the P6-50 SBS) is what 2-BM operators and TomoScan call the "fast shutter": there is no separate fast actuator at 2-BM-B today, so TomoScan cycles this same shutter closed for dark-field and white (flat) field acquisition and open for projections, many times per scan. CORA's run-start gate therefore expects both shutters open (the open predicate `BeamBlockingM == 0` is defined on [Enclosures](enclosures.md)), and should treat `StationShutter` close events during a run as normal dark / flat sequencing rather than anomalies. No separate `FastShutter` Asset is modelled. Confirmed by 2-BM staff (BEAM-1).

## Pending

Design backlog not yet modeled (shape, not live data):

- **Subjects**: proposal co-I sample roster; calibration phantom (Siemens star, USAF 1951, sphere); channel-cut crystal (energy-calibration standard of known lattice spacing; the measuring tool for the `energy_characterization` [Procedure](procedures.md), as the phantom is for alignment; the crystal, its 2d, and removable-vs-installed are open question `ENERGY-7`).
- **Runs**: an operator-decision `Aborted` Run; alignment-chain composed Runs; a vibration-baseline Run ([item_070](https://docs2bm.readthedocs.io/en/latest/source/ops/item_070.html)).
- **Campaigns**: alignment-chain orchestration (`Coordination`); in-situ / operando study (`Coordination`); energy sweep, N-point (`Sweep`); block-design experiment (`Block`).
- **Datasets**: rocking curve (energy-characterization Procedure, channel-cut crystal); vibration baseline ([item_070](https://docs2bm.readthedocs.io/en/latest/source/ops/item_070.html)); reconstructed volume; segmentation mask; dark-subtracted flat.
- **Decisions**: `RunDebriefer` `OperatorAbort` and `DataSuspect`; a Strategy agent decision.
