# Model

*The developer's by-kind index: where each CORA aggregate's FXI content lives. It hosts no content of its own.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at FXI |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory > Computed axes](inventory.md#computed-axes) (in this zone) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Procedure (Operation) | [Operations > Procedures](procedures.md) |
| Recipe (Recipe) | [Operations > Recipes](recipes.md) |
| Enclosure (Enclosure) | [Operations > Enclosures](enclosures.md) |
| Caution (Caution) | [Operations > Cautions](cautions.md) |
| Supply (Supply) | [Operations > Supplies](operations.md#supplies) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Subject, Run, Campaign, Dataset, Decision | [Experiment](experiment.md) (shape; CORA not connected) |
