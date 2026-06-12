# Architecture

For architects reading or evaluating CORA's design. Roles defined by what they do in the system; product picks live one layer down in [Stack](../stack/index.md), so a swap is a stack change, not an architecture change.

## Pages

<div class="grid cards" markdown>

-   :material-cube-outline:{ .lg .middle } __Model__

    ---

    Bounded contexts, aggregates, vertical slices, FCIS.

    [Read →](model.md)

-   :material-database-outline:{ .lg .middle } __State__

    ---

    Event sourcing, projections, read models.

    [Read →](state.md)

-   :material-layers-triple-outline:{ .lg .middle } __Surfaces__

    ---

    Surface adapters, handlers, cross-cutting concerns.

    [Read →](surfaces.md)

-   :material-ruler-square-compass:{ .lg .middle } __Standards__

    ---

    ISA lenses, recipe ladder, in-code map.

    [Read →](standards.md)

-   :material-view-grid-outline:{ .lg .middle } __Modules__

    ---

    Per bounded context: events, slices, aggregates, FSM. Reference detail you reach for by name, not the way in.

    [Read →](modules/index.md)

</div>
