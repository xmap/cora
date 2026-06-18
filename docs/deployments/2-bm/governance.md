# Governance

*The static authorization boundary at 2-BM: who may act, and the trust shape that gates their commands.*

This page holds the configured, slow-changing authorization facts: the operator pool and the Trust boundary that
decides who may issue which command. It is static config, set when the beamline is brought online and changed
deliberately. The per-run choices an operator or agent makes during a measurement (overrides, completions,
steering) are live accountability data, not config; they live with [Decisions](experiment.md#decisions).

## Who acts

The operator pool on shift, conceptually beamline-scoped. Facility-process principals (proposal PIs, the safety
review board, the beamline scientist acting in a review-chain capacity) are facility-wide and live at
[APS](../aps/index.md#who-acts-here). See [Model](../../architecture/model.md) for the aggregate shape.

| Actor | Kind |
| --- | --- |
| `2-BM Operator 1` | `human` |
| `2-BM Operator 2` | `human` |
| `2-BM Operator 3` | `human` |

## The trust boundary

Three aggregates per ISA-99 shape the boundary: a Zone (a trust grouping), a Conduit (a governed comms path
between Zones), and a Policy (an authorization rule attached to a Conduit). The Zone is orthogonal to the
Equipment hierarchy: it groups assets by homogeneous trust requirement, not by where they sit in the asset tree.

| Zone | Conduit | Endpoints |
| --- | --- | --- |
| `2-BM Zone` | `2-BM Local Conduit` | `2-BM Zone` -> `2-BM Zone` |

A Policy governs who may issue which command across a Conduit.

| Policy | Permitted principals | Permitted commands |
| --- | --- | --- |
| `2-BM Operations Policy` | `2-BM Operator 1..3` (above) | Operator-driven commands (Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign) |
| `2-BM Agent Policy` | `Run Debrief` (see [APS principals](../aps/index.md#who-acts-here)) | Decision family: `RegisterDecision`, `RateDecision`, `AppendInferences` |
