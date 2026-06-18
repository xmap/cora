# How 2-BM is modeled

*The developer's by-kind index: for each CORA aggregate, where its 2-BM instances are documented.*

The reader zones (As-built, Techniques, Operations, Governance, The experiment) are organized for beamline staff
and for navigating the instrument. This page is the inverse map, for someone who knows the CORA bounded contexts
and wants to find where a given aggregate's 2-BM content lives. It hosts no content of its own: every row links
into a reader zone. For the aggregate shapes themselves see [Model](../../architecture/model.md) and the per-BC
[Architecture modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 2-BM |
| --- | --- |
| Asset (Equipment) | [As-built > Assets](assets.md) |
| Fixture / Assembly (Equipment / Recipe) | [As-built > Microscope](equipment/microscope.md), [Sample tower](equipment/sample_tower.md) |
| Computed / virtual axes (Equipment) | [As-built > Computed axes](computed-axes.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Procedure (Operation) | [Operations > Procedures](procedures.md) |
| Recipe (Recipe) | [Operations > Recipes](recipes.md) |
| Enclosure (Enclosure) | [Operations > Enclosures](enclosures.md) |
| Caution (Caution) | [Operations > Cautions](cautions.md) |
| Supply (Supply) | [Operations > Supplies](operations.md#supplies) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Subject, Run, Campaign, Dataset, Decision | [The experiment](experiment.md) (live; served by the app read-API) |
