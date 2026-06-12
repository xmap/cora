# Model

*Bounded contexts, aggregates, vertical slices.*

The shape under every CORA feature: a BC owns a slice of the domain, an aggregate owns a consistency boundary inside it, a vertical slice owns one command or query end-to-end. Get these three right and adding a feature stops being a refactor.

## Bounded contexts

CORA is a set of bounded contexts (BCs) organised into tracks. Each BC owns its model, language, and API surface. Each aggregate inside a BC owns one consistency boundary.

Status legend: **Active** = aggregate is shipping and listed under [Modules](modules/index.md); **Planned** = scoped, not yet implemented.

<!-- arch:bc-table -->
_Generated from the code at build time._
<!-- /arch:bc-table -->

<!-- arch:count kind=bc spell=true cap=true -->Seventeen<!-- /arch:count --> BCs and <!-- arch:count kind=aggregate spell=true -->forty<!-- /arch:count --> aggregates ship today; two more BCs are reserved with single planned aggregates. Tracks group BCs by the lens they take on operations: Foundation owns the shared facts every other track refers to, Track A is the batch-shaped recipe ladder, Track B is the always-on resource and procedure side, Track C is the trust topology that gates the others, Governance owns the formal and informal operator controls, Decisions and agents own the audit and configuration of consequential choices, and Independent covers what doesn't sit on any single track.

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
