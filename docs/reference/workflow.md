# Workflow

*Reading order, commits, branch flow, migrations, tests.*

The mechanics a contributor (human or LLM) has to internalise before touching the code. Each section is the rule, not the rationale; rationale lives next to the artifact it constrains.

## Reading order

Stop at any step and you have a working mental model of the layer above.

1. **One vertical slice end-to-end:** [features/register_actor/](https://github.com/xmap/cora/tree/main/apps/api/src/cora/access/features/register_actor). Five files, ~430 lines. `command.py` (input), `decider.py` (pure rule), `handler.py` (shell), `route.py` + `tool.py` (REST + MCP). Every slice follows this shape.
2. **The aggregate:** [aggregates/actor/](https://github.com/xmap/cora/tree/main/apps/api/src/cora/access/aggregates/actor). State, events, evolver. Pure.
3. **The ports:** [infrastructure/ports/](https://github.com/xmap/cora/tree/main/apps/api/src/cora/infrastructure/ports). Thirty `Protocol`s, spanning infrastructure seams (`Clock`, `IdGenerator`, `EventStore`, `IdempotencyStore`, `Authorize`, `EventPublisher`, `Canonicalizer`, `Signer`, `ByteSigner`, `TokenVerifier`, `SecretStore`, `ProfileStore`, `LogbookMirror`, `LLM`) and the cross-BC `*Lookup` family (`AssetLookup`, `CapabilityLookup`, `SupplyLookup`, and the rest).
4. **One fitness test:** [test_slice_contract.py](https://github.com/xmap/cora/blob/main/apps/api/tests/architecture/test_slice_contract.py). What's enforced mechanically.
5. **Vocabulary:** [Glossary](glossary.md).

## Commits

Conventional Commits with scope: `type(scope): subject`. Imperative, lowercase, no trailing period, under 72 chars.

**Types:**

| Type | Use for |
| --- | --- |
| `feat` | New caller-visible capability |
| `fix` | Bug fix |
| `refactor` | Internal restructure, no behavior change |
| `perf` | Performance |
| `test` | Tests only |
| `docs` | Docs only |
| `build` | Build, deps, packaging |
| `ci` | CI, pre-commit, hooks |
| `chore` | Anything else not user-visible |

**Scopes:**

- *Cross-cutting*: `infra`, `api`, `db`, `obs`, `auth`, `arch`
- *BCs*: `access`, `agent`, `calibration`, `campaign`, `caution`, `data`, `decision`, `equipment`, `federation`, `operation`, `recipe`, `run`, `safety`, `subject`, `supply`, `trust`
- *Repo*: `repo`, `deps`

Multiple scopes: pick the dominant or omit.

**Examples:**

```
feat(infra): add port protocols and structured logging
feat(equipment): add register_device decider with optimistic concurrency
fix(db): drop redundant index on events(stream_id)
test(access): cover register_actor invariants
ci: add lint+typecheck+test workflow
```

**Granularity:** one commit = one cohesive change that compiles and passes tests. Port + adapter + test for one capability is one commit. Refactor + feature is two.

## Branch flow

Solo: commit directly to `main`. CI must be green before pushing.

**Cross-cutting work while WIP is in flight:** use a worktree. `git worktree add ../cora-<task> main`, work there, commit, return. Pre-commit stashes unstaged changes to tracked files but [never to untracked ones](https://github.com/pre-commit/pre-commit/issues/1212) — a half-staged WIP slice (untracked `handler.py` + unstaged `wire.py` edits hidden by stash) will false-fail architecture fitness functions and force `--no-verify` to land an otherwise-clean commit. Worktrees isolate the cleanup from the WIP entirely. Also avoid `git commit -- <paths>` with mixed staged/unstaged state — the path-form bypasses the index in a way pre-commit's stash flow doesn't expect.

## Migrations

Schema changes in `infra/atlas/migrations/<timestamp>_<short_name>.sql`.

```bash
make migrate-new name=add_foo   # new empty migration
# edit the .sql file
make migrate-hash               # update infra/atlas/migrations/atlas.sum
make migrate-apply              # apply locally
```

CI verifies `atlas.sum` and runs a grep-based safety scan on net-new files (blocks `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `ALTER COLUMN ... TYPE`). Atlas's `migrate lint` is behind atlas-cloud login (skipped). For genuine destructives, add `-- atlas:safety:allow=<reason>` per line. Forward-only: a rollback is a new compensating migration.

## Tests

Descriptive-sentence pytest style: snake_case prefixed with `test_`. Adapts Roy Osherove's `MethodName_Scenario_ExpectedBehavior` to Python.

```
test_<subject>_<expected_outcome>[_<scenario>]
```

- **subject**: unit under test (endpoint, function, layer, behavior)
- **expected_outcome**: the property pinned, not the inputs
- **scenario** (optional): conditions; introduce with `when_` or `for_`

Optimize for the property, not the inputs.

**Good:**

```
test_decide_emits_method_defined_when_stream_is_empty
test_handler_returns_capability_for_known_id
test_evolve_asset_relocated_mutates_parent_id_to_target
test_post_methods_returns_201_with_method_id
```

**Avoid:**

```
test_post_methods_with_three_capabilities_in_order_b_a_c   # describes inputs
test_handler_3                                              # opaque
test_register_subject_works                                 # outcome too vague
```

**Markers:**

- `@pytest.mark.unit`: pure / in-process
- `@pytest.mark.architecture`: structural fitness functions (AST / filesystem / SQL-text); no I/O
- `@pytest.mark.integration`: real Postgres via `db_pool`
- `@pytest.mark.contract`: REST / MCP schema verification (`TestClient(create_app())`)
- `@pytest.mark.e2e`: full end-to-end

Marker is the category; name is the property. Don't repeat the category in the name. Long names are fine.

**File naming (integration tier).** Four suffix shapes cover everything under `tests/integration/`. Same spirit as the function-name rule: lead with what the file pins, not the inputs.

- `test_<slice>_handler_postgres.py` — single-slice, single-aggregate handler against real PG. Dominant pattern, most files. `_postgres` is load-bearing here: it disambiguates from the in-memory twin at `tests/unit/<bc>/test_<slice>_handler.py`.
- `test_postgres_<infra>.py` — Postgres adapter itself is the subject (event store, `append_streams`, idempotency, lookup tables, summary projections).
- `tests/integration/scenarios/test_<beamline-or-facility>_<routine>.py` — cross-BC scenario walk stitching many slices to express one real beamline routine or facility-topology setup (today: `test_2bm_alignment_center.py`, `test_aps_facility.py`). No `_scenario` suffix on the filename: the `scenarios/` folder is the marker. No `_postgres` suffix either: there's no in-memory twin to disambiguate against. One routine per scenario, no compendiums. The seven-name phase vocabulary (`install`, `shakedown`, `commissioning`, `beta`, `operations`, `shutdown`, `decommission`) is a thinking aid only: it lives in the docstring first line (for example, `"""Phase: shakedown. Routine: motor homing at APS 2-BM."""`) and optionally as a `@pytest.mark.<phase>` marker for runtime selection. It is not part of the filename, and it is not a CI gate. When a single routine eventually needs scenarios at two different maturities, add the phase token to the filename at *that* point as `test_<beamline>_<routine>_<phase>.py`.
- `test_<subject>_postgres.py` — anything else against real PG: full-FSM walks, cross-aggregate / multi-stream atomic writes, projection-worker behavior, race tests. Use a descriptive infix when the test's specialness needs to be named (`_cross_bc_`, `_atomic_`, `_full_fsm_cycle_`, `_fsm_walk_`, `_race_`); don't force one infix where several capture different scopes.

The `_scenario` term follows DDD / BDD / Event-Storming vocabulary (Domain Storytelling, Gherkin scenarios). Avoid `_pilot` for the test tier — "pilot" decays as more beamlines integrate; the scenario shape is time-invariant. "Pilot" stays the right word for the real-world meaning (first beamline deployment) when it appears in domain text.

## Test coverage per slice

A fitness function in `tests/architecture/test_slice_test_coverage.py` enforces the slice-pyramid convention. New slices follow the matrix below or fail CI.

| slice shape | decider | handler | endpoint | mcp_tool | handler_postgres |
| --- | --- | --- | --- | --- | --- |
| **command** | ✓ | ✓ | ✓ | ✓ | create-style only |
| **entry-append** | — | ✓ | ✓ | ✓ | create-style only |
| **query** | — | ✓ | ✓ | ✓ | — |

**Create-style** = verb in `{define_*, register_*, add_*}`. These introduce a new aggregate or event stream, so the jsonb round-trip + ON CONFLICT + unique-constraint behavior gets pinned per-slice against real PG. **State-transition** slices (`abort_*`, `complete_*`, `resume_*`, `hold_*`, and so on) lean on cross-BC scenario coverage in `tests/integration/scenarios/` instead.

Detection is lenient: a slice is considered covered if either the 1:1 file `test_<slice>_<suffix>.py` exists OR another test file in the right tier mentions the slice name as a substring (catches resource-plural grouped files like `test_actors_endpoint.py` covering `register_actor`, and bundles like `test_iter2_mcp_tools.py`). The `EXEMPT_FROM_*` allowlists in `test_slice_test_coverage.py` document existing divergences with citations.

## Idempotency contract tests

Create-style slices that accept `Idempotency-Key` get a dedicated `test_<slice>_idempotency.py` contract test. State-transition slices don't need them; the FSM rejects duplicate transitions naturally.

## Event-sourcing aggregate conventions

Architecture tests pin the shape of every `cora/<bc>/aggregates/<agg>/events.py`:

- **`test_decider_purity`** — every `decider.py` is referentially transparent (no I/O, no clock, no UUID generation).
- **`test_decider_signature_canonical`** — every `decide` function takes exactly `(state, command)` as positional args; everything else is keyword-only after `*`.
- **`test_decider_docstring_invariants_block`** — every `decide` carries an `Invariants:` block enumerating its rejections inline with exception names (file-level check; module docstring placement accepted today).
- **`test_from_stored_wraps_payload`** — every `case "X":` in `from_stored` wraps `KeyError` / `TypeError` / `AttributeError` as `raise ValueError("Malformed X")` (the canonical helper `cora.infrastructure.event_payload.deserialize_or_raise` collapses each wrap into a one-liner). Decided 2026-05-18 after a 3-agent corpus survey (Marten, pyeventsourcing, Pydantic, msgspec, cattrs all wrap). Without the wrap, Sentry / Datadog group every aggregate's `KeyError` into one undifferentiated issue. The payload value itself is intentionally not echoed in the message after PII vault shipped 2026-05-23, since payloads can carry vault-correlatable identifiers. Nested-VO deserializers (`CautionTarget`, `CalibrationSource`, `ModelRef`, `ClearanceBinding`, `HazardClassification`, `HazardDeclaration`, `Identifier`) use the sibling `deserialize_vo_or_raise` from the same module, which accepts a `raise_as` parameter for typed subclass exceptions (e.g. `InvalidCalibrationSourceError`).
- **`test_event_union_from_stored_coverage`** — every class in the `<X>Event` union is constructed by at least one `case` arm, and every `case` constructs a class IN the union.
- **`test_event_payload_immutability`** — collection-typed fields on event payloads use `tuple[X, ...]` / `frozenset[X]`, not `list[X]` / `set[X]`. Event payloads share references into folded state; mutable collections invite alias bugs.
- **`test_projection_idempotency`** — every projection's `apply()` is safe to re-run on the same event.

## Per-BC test helpers

When a BC accumulates its own seeding / setup helpers (typically at rule-of-three), they live in `tests/unit/<bc>/_helpers.py`, the same name as the shared `tests/unit/_helpers.py` and `tests/integration/_helpers.py`. The architecture test `test_helper_naming_convention.py` rejects divergent names like `_iter2_seed.py` or `_seed_helpers.py`.
