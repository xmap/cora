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
