# Policies

*Trust BC boundary shape at 2-BM.*

Three aggregates per ISA-99: Zone (trust grouping), Conduit (governed comms path), Policy (authorization rule). See [Model](../../architecture/model.md) for the aggregate shape.

## Zone

A Zone groups assets with homogeneous trust requirements (orthogonal to the Equipment hierarchy).

- `2-BM Zone`

## Conduit

A Conduit is a governed comms path between Zones.

| Conduit | Endpoints |
| --- | --- |
| `2-BM Local Conduit` | `2-BM Zone` → `2-BM Zone` |

## Policies

A Policy is an authorization rule attached to a Conduit, governing who may issue which command.

| Policy | Permitted principals | Permitted commands |
| --- | --- | --- |
| `2-BM Operations Policy` | `2-BM Operator 1..3` (see [Actors](actors.md)) | Operator-driven commands (Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign) |
| `2-BM Agent Policy` | `Run Debrief` (see [APS principals](../aps/index.md#who-acts-here)) | Decision family: `RegisterDecision`, `RateDecision`, `AppendInferences` |

## Pending

- A second Zone (Storage Zone, Control Zone)
- Policy enforcement (switch to `TrustAuthorize`)
- Policy status lifecycle (`Drafted → Approved → Active → Superseded`)
