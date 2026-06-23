# Scenarios

Each test in this folder exercises one operator routine end-to-end through CORA's BC stack. The pattern is **Living Documentation** (Gojko Adzic, *Specification by Example*, 2011; Cyrille Martraire, *Living Documentation*, 2019): scenario tests are both machine-runnable verification AND the source of truth for per-beamline doc pages under `docs/deployments/` and for the scenario taxonomy surface at `docs/scenarios/`.

A doc page may only name an aggregate that some scenario here has registered. That makes scenario coverage the bottleneck on doc completeness.

## Filename

`test_<beamline-or-facility>_<routine>.py`

Where:

- `<beamline-or-facility>` is `aps`, `2bm`, `7bm`, `maxiv`, ... (lowercase, no dashes). It maps directly to `docs/deployments/<beamline-or-facility>/`.
- `<routine>` is the operator routine in snake_case (`motor_homing`, `alignment_center`, `dark_field`, `facility`).

The `scenarios/` folder is the marker; no `_scenario.py` suffix.

## Rules

1. **One scenario = one routine.** No compendium scenarios that test multiple routines back-to-back. If two routines must run together (state dependency), they are still two scenarios; the second consumes a fixture that runs the first.

   **Named exception**: when an operator-perceived routine genuinely IS multi-step (for example, a cross-Plan pivot like `energy_change`, or a cross-BC orchestration), name the file `test_<beamline>_<verb>_<condition>.py` (Grzybek `*Scenario_When*` precedent). FSM-walk scenarios use the `_lifecycle` or `_cycle` suffix.

2. **Filename matches doc folder.** `test_aps_*` populates `docs/deployments/aps/`; `test_2bm_*` populates `docs/deployments/2-bm/`. Cross-facility vocabulary the scenario registers (Methods, Capabilities) also lands in `docs/catalog/`.

3. **Multi-maturity discriminator (deferred).** If a single routine ever needs scenarios at two different maturities (for example, an unattended-operations variant of an alignment routine), add a suffix at *that* point: `test_<beamline>_<routine>_<suffix>.py`. Until then, single scenario per routine.

4. **Multi-axis tag surface.** Each scenario gets a docstring header carrying its cluster + archetype + primary BC + touched BCs + one-line gist. The taxonomy surface at `docs/scenarios/` reads these headers and pivots the corpus by each axis (cluster, shape, BC). Cluster + archetype vocabularies are CLOSED — typo equals build failure. See `Taxonomy` below.

5. **No empty cluster pages.** A cluster page exists only when at least one scenario lives in it (Diataxis "complete not finished"; Write the Docs "complete" principle). Empty cluster surfaces are not pre-created.

## Taxonomy

Locked 2026-05-17 (see [`project_scenario_taxonomy`](../../../../../../.claude/projects/-Users-dgursoy-Documents-Github-cora/memory/project_scenario_taxonomy.md) for the full memo with growth notes).

### Clusters (5, single-word, growth-aware)

| Name | Theme | Growth |
| --- | --- | --- |
| `Seed` | Facility install + Agent config + Supply state | Moderate |
| `Commissioning` | Alignment chain + bring-up + detector baselines | HIGH |
| `Staging` | Pre-Run intake + clearance gates | Low-moderate |
| `Runs` | Acquisition variants + lifecycle edges | HIGH |
| `Advisories` | Agent-driven subscriber output | Moderate |

Growth axes: `Seed` widens per-deployment / per-agent-kind / per-supply-kind. `Commissioning` and `Runs` are open-ended per beamline + modality / per scan mode. `Advisories` widens per agent (RunDebriefer + CautionDrafter + future).

Split trigger: when a cluster crosses 15 scenarios, split via its pre-organized H2 sections.

### Archetypes (6, single-word, closed)

- `setup` — registers entities, no Run
- `routine` — one Procedure or one slice exercise
- `cycle` — Plan → start → readings → terminal → Dataset
- `fsm` — deliberately walks an aggregate through full FSM
- `gate` — proves a cross-BC guard blocks/allows
- `agent` — writes via Agent BC subscriber

Cluster = theme (the operator-perceived purpose). Archetype = shape (how the test is constructed). Same scenario gets one of each.

### BC vocabulary

`bc_touches` tracks all BCs that exist in CORA's codebase, not just those with scenario coverage today. The registry page at `docs/scenarios/by-bc.md` lists every BC with its scenario count (zero is a visible signal, OpenTelemetry pattern). When a new BC ships, its name lands in `tags_allowed` at ship time.

### Docstring header

Every scenario's module docstring carries:

```python
"""<one-line gist of the operator routine>

cluster: <Seed|Commissioning|Staging|Runs|Advisories>
archetype: <setup|routine|cycle|fsm|gate|agent>
bc_primary: <Equipment|Recipe|...>
bc_touches: <Equipment, Recipe, ...>
"""
```

The `conftest.py` hook at this folder collects these into `site_data/scenarios.json` at test-collect time; `docs/scenarios/` reads from that file. Missing or invalid fields fail the test session.

## Template

Copy from a recent sibling. [`test_2bm_dark_field.py`](test_2bm_dark_field.py) and [`test_2bm_alignment_resolution.py`](test_2bm_alignment_resolution.py) are good starting points; both consume [`_facility_fixture.py`](_facility_fixture.py) for the standard install ceremony.
