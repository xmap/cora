"""Deployment scenarios attribute baseline Datasets to a Run, not a Procedure.

Per the Run vs Procedure boundary rule (docs/reference/modeling.md#run-vs-procedure-boundary),
a Dataset-of-record makes the act a Run. The 2-BM acquisition baselines (dark / flat /
normalization) are subject-less Runs that produce their Dataset via `producing_run_id`;
the conducting Procedure is a phase of the Run and produces no Dataset-of-record.

This test scans every `tests/integration/scenarios/*.py` for `RegisterDataset(...)` calls
and rejects any that set `producing_procedure_id` to a non-None value. The Data BC still
supports the `producing_procedure_id` arm (exercised by unit / contract / gate tests
outside `scenarios/`, where the general "a conducted standalone Procedure can produce a
Dataset" provenance guarantee is locked); this fitness is scoped to deployment scenarios.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_test_files

_SCENARIOS_MARKER = "tests/integration/scenarios/"


def _scenario_files() -> list[Path]:
    return sorted(p for p in tracked_test_files() if _SCENARIOS_MARKER in p.as_posix())


@pytest.mark.architecture
def test_no_scenario_registers_dataset_via_producing_procedure_id() -> None:
    """No deployment scenario registers a Dataset with a non-None producing_procedure_id.

    Baselines attribute to the Run (producing_run_id); the boundary rule keeps a
    Procedure's output of record off the Dataset-of-record path.
    """
    scenario_files = _scenario_files()
    assert scenario_files, "no scenario files discovered via tracked_test_files()"

    violations: list[str] = []
    for path in scenario_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "RegisterDataset":
                continue
            for kw in node.keywords:
                if kw.arg != "producing_procedure_id":
                    continue
                if not (isinstance(kw.value, ast.Constant) and kw.value.value is None):
                    violations.append(f"{path.name}:{kw.value.lineno}")

    assert not violations, (
        "Deployment scenarios must attribute baseline Datasets to a Run "
        "(producing_run_id), not a Procedure. Found RegisterDataset(producing_procedure_id=...) "
        f"set to a non-None value in: {violations}. See "
        "docs/reference/modeling.md#run-vs-procedure-boundary."
    )
