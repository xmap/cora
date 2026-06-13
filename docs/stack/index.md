# Stack

For implementers and operators modifying `pyproject.toml`, `docker-compose.yml`, or `Makefile`. Every pick is a starting point with a written escape hatch. Roles are pinned in [Architecture](../architecture/index.md); seam discipline (ports, adapters, BC isolation) means any pick can be swapped without touching the core. Picks marked deferred are *not yet warranted*, not unwanted.

## Pages

<div class="grid cards" markdown>

-   :material-server-outline:{ .lg .middle } __Backend__

    ---

    Language, HTTP, async DB, agent SDK, validation, settings, IDs, server.

    [Read →](backend.md)

-   :material-monitor-dashboard:{ .lg .middle } __Frontend__

    ---

    Framework, lint, format.

    [Read →](frontend.md)

-   :material-database:{ .lg .middle } __Data__

    ---

    Relational store, event store, vector index, migrations.

    [Read →](data.md)

-   :material-shield-key-outline:{ .lg .middle } __Auth__

    ---

    Authentication wiring, authorization model, policy language.

    [Read →](auth.md)

-   :material-chart-line:{ .lg .middle } __Observability__

    ---

    Logging, metrics, tracing, receivers.

    [Read →](observability.md)

-   :material-tools:{ .lg .middle } __Operations__

    ---

    Deployment, tooling.

    [Read →](operations.md)

-   :material-rocket-launch-outline:{ .lg .middle } __Deployment__

    ---

    Env vars, bootstrap authz workflow, edge auth, recovery.

    [Read →](deployment.md)

-   :material-clock-outline:{ .lg .middle } __Deferred__

    ---

    Picks held until a real consumer demands them.

    [Read →](deferred.md)

</div>
