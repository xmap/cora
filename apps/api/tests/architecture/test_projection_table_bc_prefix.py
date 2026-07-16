"""Pin: projection table names follow `proj_[<bc>_]<aggregate>_<rowtype>`.

Projection tables under `infra/atlas/migrations/` follow one of two
shapes, codified in `docs/reference/conventions.md` under
"Projection tables use `proj_<bc>_<aggregate>_<rowtype>`":

  - `proj_<bc>_<aggregate>_<rowtype>` for multi-aggregate BCs and
    single-aggregate BCs whose name differs from the aggregate name
    (e.g., `proj_equipment_asset_summary`, `proj_access_actor_summary`,
    `proj_data_dataset_summary`).
  - `proj_<aggregate>_<rowtype>` for single-aggregate BCs whose name
    equals the aggregate name (e.g., `proj_run_summary`,
    `proj_caution_summary`, `proj_supply_summary`).

This fitness function walks every projection registered via the
`register_<bc>_projections` entry points, derives the BC from the
class's module path, and checks that the projection's `.name`
attribute is consistent with the BC + aggregate per the above shape.

The check is structural: the name must start with either
`proj_<bc>_` (BC prefix present) or `proj_<aggregate>_` (single-
aggregate BC whose name equals the aggregate). A future regression
that drops or adds a redundant BC prefix breaks the rule.

Discovery mirrors `test_projection_table_match.py`: import each BC,
call `register_<bc>_projections` against an empty registry, walk
the resulting set of (class, name) pairs.
"""

import importlib
from typing import TYPE_CHECKING

import pytest

from cora.infrastructure.projection import ProjectionRegistry
from tests.architecture.conftest import BCS

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel

# Single-aggregate BCs whose BC name equals the aggregate name. For
# these, the projection table drops the redundant BC prefix:
# `proj_<aggregate>_<rowtype>` (e.g., proj_run_summary, not
# proj_run_run_summary). Add a BC here only after confirming it has
# exactly one aggregate AND the BC name matches the aggregate name.
# `agent` left this set when the LanguageModel aggregate landed: its
# proj_agent_summary and proj_agent_language_model_summary both pass
# via the prefix-present branch.
_BCS_WITH_MATCHING_SINGLE_AGGREGATE: frozenset[str] = frozenset(
    {
        "calibration",
        "campaign",
        "caution",
        "decision",
        "run",
        "subject",
        "supply",
    }
)


def _populate_registry_from_bcs() -> tuple[ProjectionRegistry, dict[str, str]]:
    """Return the populated registry plus a map of projection name -> BC
    (so the fitness can match a class's BC even when the BC prefix is
    not in the name)."""
    registry = ProjectionRegistry()
    deps_stub: Kernel | None = None
    name_to_bc: dict[str, str] = {}
    for bc in BCS:
        try:
            module = importlib.import_module(f"cora.{bc}")
        except ModuleNotFoundError:
            continue
        register = getattr(module, f"register_{bc}_projections", None)
        if register is None:
            continue
        before = set(registry.names())
        register(registry, deps_stub)
        after = set(registry.names())
        for name in after - before:
            name_to_bc[name] = bc
    return registry, name_to_bc


_REGISTRY, _NAME_TO_BC = _populate_registry_from_bcs()


def _all_projection_names() -> list[str]:
    return sorted(_REGISTRY.names())


@pytest.mark.architecture
@pytest.mark.parametrize("table_name", _all_projection_names())
def test_projection_table_bc_prefix(table_name: str) -> None:
    """Projection table starts with `proj_<bc>_` or `proj_<aggregate>_`."""
    bc = _NAME_TO_BC[table_name]
    if not table_name.startswith("proj_"):
        pytest.fail(
            f"Projection `{table_name}` from BC `{bc}` does not start with `proj_`. "
            "All projection table names must use the `proj_` prefix."
        )
    rest = table_name[len("proj_") :]

    if bc in _BCS_WITH_MATCHING_SINGLE_AGGREGATE:
        # Convention: drop the redundant prefix. Table starts with the
        # aggregate name (which equals the BC name).
        expected_prefix = f"{bc}_"
        if not rest.startswith(expected_prefix):
            pytest.fail(
                f"Projection `{table_name}` from BC `{bc}` should follow the dropped-prefix "
                f"shape `proj_{bc}_<rowtype>` (BC name equals the single aggregate's name; "
                "the redundant BC prefix is dropped). See `docs/reference/conventions.md` "
                "under 'Projection tables use ...'."
            )
        return

    # Convention: prefix-present. Table starts with the BC name.
    expected_prefix = f"{bc}_"
    if not rest.startswith(expected_prefix):
        pytest.fail(
            f"Projection `{table_name}` from BC `{bc}` should start with `proj_{bc}_` "
            "(multi-aggregate BC, or BC name differs from aggregate name). See "
            "`docs/reference/conventions.md` under 'Projection tables use ...'. If this BC "
            "is genuinely a single-aggregate-with-matching-name case that should drop the "
            "prefix, add it to `_BCS_WITH_MATCHING_SINGLE_AGGREGATE` in this test."
        )
