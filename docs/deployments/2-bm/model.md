# Model

*The developer's by-kind index: where each CORA aggregate's 2-BM content lives. It hosts no content of its own.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 2-BM |
| --- | --- |
| Asset (Equipment) | [Hardware > Assets](assets.md) |
| Fixture / Assembly (Equipment / Recipe) | [Hardware > Microscope](equipment/microscope.md), [Sample tower](equipment/sample_tower.md) |
| Computed / virtual axes (Equipment) | [Hardware > Computed axes](computed-axes.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Procedure (Operation) | [Operations > Procedures](procedures.md) |
| Recipe (Recipe) | [Operations > Recipes](recipes.md) |
| Enclosure (Enclosure) | [Operations > Enclosures](enclosures.md) |
| Caution (Caution) | [Operations > Cautions](cautions.md) |
| Supply (Supply) | [Operations > Supplies](operations.md#supplies) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Subject, Run, Campaign, Dataset, Decision | [The experiment](experiment.md) (live; app read-API) |
