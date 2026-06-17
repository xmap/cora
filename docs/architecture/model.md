# Model

*Bounded contexts, aggregates, vertical slices.*

The shape under every CORA feature: a BC owns a slice of the domain, an aggregate owns a consistency boundary inside it, a vertical slice owns one command or query end-to-end. Get these three right and adding a feature stops being a refactor.

## Bounded contexts

CORA is a set of bounded contexts (BCs) organised into groups. Each BC owns its model, language, and API surface. Each aggregate inside a BC owns one consistency boundary.

Status legend: **Active** = aggregate is shipping and listed under [Modules](modules/index.md); **Planned** = scoped, not yet implemented.

<!-- arch:bc-table -->
_Generated from the code at build time._
<!-- /arch:bc-table -->

<!-- arch:count kind=bc spell=true cap=true -->Seventeen<!-- /arch:count --> BCs and <!-- arch:count kind=aggregate spell=true -->forty<!-- /arch:count --> aggregates ship today; two more BCs are reserved with single planned aggregates. Each group is named for the operational role its BCs play in running an experiment: **Foundation** owns the shared facts every other group refers to (identity, equipment); **Procedure** is the planned-work recipe ladder and its execution instances; **Resource** is the continuous and consumable substrate work runs on, plus its upkeep; **Authority** is where CORA itself decides or grants permission to act, intra- and cross-facility; **Assurance** is observed state and recorded evidence that conditions work but that CORA does not decide; **Governance** is the audit and configuration of consequential choices; and **Outcome** is what the experiment studies and produces. The ISA and peer standards that shaped several BCs (ISA-88, ISA-106, ISA-99) are documentation provenance recorded in the [glossary](../reference/glossary.md), not the partition. To place a new BC, take the first role above that fits; if none fits, the BC charter is mis-scoped rather than the scheme needing an eighth group, and a new group is added only when three homeless BCs share a genuinely new role.

## Aggregates

The unit of consistency inside a BC: state, invariants, events. Every aggregate is a stream in the event store, identified by `(stream_type, stream_id)` and folded from its events into an in-memory state per command. The same shape repeats across BCs: a `state.py` carries the fields and invariants, an `events.py` carries the closed union of events, and an `evolver.py` folds events back into state. See [Reference/Modeling](../reference/modeling.md) for the rules.

## Vertical slices

One folder per command or query, holding everything the slice needs:

```
features/<verb>_<aggregate>/
├── command.py      input shape
├── decider.py      pure rule: (state, command) -> events
├── handler.py      shell: wires core to ports
├── route.py        HTTP API adapter
└── tool.py         agent (MCP) tool adapter
```

Independently readable, testable, deletable. For the in-repo file layout, see [Reference/Layout](../reference/layout.md).

<div class="cora-aside" markdown>

What each piece does
{: .cora-kicker }

- **Command.** Immutable input shape, one per slice. Captures the caller's intent. Structurally validated at the adapter, semantically validated by the decider.
- **Functional core.** Decider takes a command and current state, returns events. Evolver folds events back into state. Both pure, no I/O.
- **Imperative shell.** Handler wires the core to side-effect ports (clock, IDs, event store, authorize, idempotency). Real ports in production, fakes in tests.
- **Thin adapters.** One per surface, translates protocol-specific input into the same handler call. Schema validation only, no business rules.

</div>

Query slices follow the same shape with `query` in place of `command` and no decider, since there's no state change. Single-record reads fold the stream; list and filter reads hit a projection. See [Reference/Patterns](../reference/patterns.md).
