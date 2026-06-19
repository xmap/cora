# Governance

*Who may act at 2-BM, and the trust policies that gate their commands. Static config; the per-run
[decisions](experiment.md) operators and agents make are live, not here.*

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

2-BM's boundary is shaped by the Trust BC aggregates (Zone, Conduit, Policy); the
[Trust module](../../architecture/modules/trust/index.md) defines what each one is. This page records only the
2-BM instances:

| Zone | Conduit | Endpoints |
| --- | --- | --- |
| `2-BM Zone` | `2-BM Local Conduit` | `2-BM Zone` -> `2-BM Zone` |

A Policy governs who may issue which command across a Conduit.

| Policy | Permitted principals | Permitted commands |
| --- | --- | --- |
| `2-BM Operations Policy` | `2-BM Operator 1..3` (above) | Operator-driven commands (Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign) |
| `2-BM Agent Policy` | `Run Debrief` (see [APS principals](../aps/index.md#who-acts-here)) | Decision family: `RegisterDecision`, `RateDecision`, `AppendInferences` |

## Pending

- A second Zone (Storage Zone, Control Zone).
- Policy enforcement (switch to `TrustAuthorize`).
- Policy status lifecycle (`Drafted -> Approved -> Active -> Superseded`).
- Per-beamline named staff rosters (Actors).
