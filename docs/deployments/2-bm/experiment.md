# The experiment

*The live operational view: what the beamline is measuring now and what it has measured. This page describes the
shape; the running system holds the data.*

The zones before this one (As-built, Techniques, Operations, Governance) are static configuration: they change
deliberately, when the beamline is built or re-fitted, and they live in these docs. This zone is different. The
subjects mounted, the runs executed, the campaigns that group them, the datasets produced, and the per-run
decisions recorded are **live per-experiment data**. They are created and updated continuously while the beamline
operates, so the system of record is CORA's running read-API, not a documentation page. This page describes the
SHAPE of that operational view: what each thing is and the status axes it moves along. One worked example at the
end shows how the shapes fit together. See [Model](../../architecture/model.md) for the aggregate shapes.

## Subjects

A Subject is the sample or thing being measured: proposal-anchored at the operations phase, kinematically mounted
at acquisition time. Each Subject runs a custody lifecycle from intake (`Received`) through mount and measurement
to a terminal disposition: `Returned` to the proposal team, `Stored` for a follow-up beamtime, or `Discarded`
with an audited reason.

## Runs

A Run is the operator-started execution of a Plan: the measurement batch (ISA-88 lens), normally against a
Subject and grouped by a Campaign. Its companion is the [Procedure](procedures.md), the operational-task lens
(ISA-106): alignment, homing, recovery, energy change. The split is the lens, not the data product: both a Run
and a Procedure can produce a Dataset. Dark- and flat-field baselines are subject-less calibration Runs captured
ahead of a scan.

## Campaigns

A Campaign groups Runs under a coordinated study, proposal-scoped and technique-tagged. Its intent axis records
why the Runs belong together: `Coordination` (one beamtime), `Series` (a repeated acquisition), `Sweep` (an
N-point parameter scan), or `Block` (a block-design experiment).

## Datasets

A Dataset records an already-existing data artifact (URI, checksum, byte size, encoding) plus optional
cross-aggregate references to its producing Run or Procedure, its Subject, and the upstream Datasets it was
derived from. Its intent axis (`Trial` or `Production`) and its lineage are what let a later reader trust it.

## Decisions

A Decision is a structured-audit record of a consequential choice, attributed to a human or agent Actor. At 2-BM
the `RunDebriefer` agent records run-completion choices in the `RunDebrief` context: `NominalCompletion`,
`DegradedCompletion`, or `EquipmentAbort`. Decisions are the live accountability ledger; the static authorization
boundary that governs who may issue commands is separate, on [Governance](governance.md).

## An illustrative run

The following is one illustrative thread, not a live record, to show how the shapes connect. A `porous sandstone
core` Subject arrives under Proposal 2026-1234, is `Received`, and is mounted on the sample tower. A tomography
Run executes a Plan against it, grouped in the `Proposal 2026-1234 beamtime` Campaign (intent `Coordination`).
The Run produces a `Proposal_2026-1234_sample_A_tomo` Dataset (intent `Production`), with lineage back to the Run
and Subject. At completion the `RunDebriefer` agent records a `NominalCompletion` Decision. When the beamtime
ends, the Subject transitions to `Returned`.

The real subjects, runs, campaigns, datasets, and decisions for this beamline are served live by CORA's read-API
once the system is operating; they are not enumerated here, because a documentation page cannot stay current with
per-experiment data.
