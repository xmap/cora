# Reference

For humans and LLM agents writing CORA code, and for code reviewers. Not a tutorial. The rules to honor when modifying CORA so the codebase doesn't drift. If the code disagrees with this page, the code is wrong. For collaboration on the design (not the code), see [Contributing](contributing.md).

## Pages

<div class="grid cards" markdown>

-   :material-source-branch:{ .lg .middle } __Workflow__

    ---

    Reading order, commits, branch flow, migrations, tests.

    [Read →](workflow.md)

-   :material-file-tree-outline:{ .lg .middle } __Layout__

    ---

    BC structure, imports, naming, bootstrap, shared code.

    [Read →](layout.md)

-   :material-graph-outline:{ .lg .middle } __Modeling__

    ---

    Event sourcing, value objects, field grouping.

    [Read →](modeling.md)

-   :material-hand-back-right-outline:{ .lg .middle } __Affordances__

    ---

    The closed 30-value vocabulary of device primitives, and the two naming patterns behind it.

    [Read →](affordances.md)

-   :material-puzzle-outline:{ .lg .middle } __Patterns__

    ---

    Read side, query slices, projections, idempotency, cross-aggregate validation.

    [Read →](patterns.md)

-   :material-ruler-square-compass:{ .lg .middle } __Conventions__

    ---

    Identifiers, units of measurement, personal data, schema-validated values.

    [Read →](conventions.md)

-   :material-tag-text-outline:{ .lg .middle } __Naming__

    ---

    The R1-R6 rules for naming aggregates, events, commands, slices, and Families.

    [Read →](naming.md)

-   :material-rocket-launch-outline:{ .lg .middle } __Runtime__

    ---

    Production hardening, logging, HTTP errors.

    [Read →](runtime.md)

-   :material-book-alphabet:{ .lg .middle } __Glossary__

    ---

    Terms defined once and used the same way in code, commits, and prose.

    [Read →](glossary.md)

-   :material-handshake-outline:{ .lg .middle } __Contributing__

    ---

    What this project is and isn't asking for. Beamline collaborators welcome; drive-by code PRs not.

    [Read →](contributing.md)

</div>
