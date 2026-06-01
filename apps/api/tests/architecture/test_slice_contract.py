"""Every vertical slice has its required files.

Three slice shapes are recognised:

  - Command slices need: __init__, command, decider, handler, route, tool.
  - Query slices need:   __init__, query, handler, route, tool.
  - Entry-append slices need: __init__, command, handler, route, tool
    (no decider; the handler writes directly to a typed entries store
    via a per-category port rather than emitting events through a
    decider). Detected by membership in `_ENTRY_APPEND_SLICES`.

A directory under `<bc>/features/` that has neither `command.py`
nor `query.py` is treated as a stub (in-flight, not yet wired)
and skipped. As soon as `command.py` (or `query.py`) appears,
the rest of the contract becomes mandatory.

WIP_SLICES is an explicit allowlist for slices that are mid-flight
between phases. Each entry SHOULD include a phase reference. Empty
the entry as soon as the slice ships.
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

_COMMAND_SLICE_FILES: frozenset[str] = frozenset(
    {"__init__.py", "command.py", "decider.py", "handler.py", "route.py", "tool.py"}
)
_QUERY_SLICE_FILES: frozenset[str] = frozenset(
    {"__init__.py", "query.py", "handler.py", "route.py", "tool.py"}
)
# Entry-append shape, hoisted from WIP_SLICES at n=3. Identical to
# command-slice file-set minus `decider.py`:
# the handler writes to a typed entries store via a per-category
# port (ReasoningStore / ReadingStore / StepStore) rather than
# folding events through a pure decider. New entry-append slices
# must be added to `_ENTRY_APPEND_SLICES` below.
_ENTRY_APPEND_SLICE_FILES: frozenset[str] = frozenset(
    {"__init__.py", "command.py", "handler.py", "route.py", "tool.py"}
)
_ENTRY_APPEND_SLICES: frozenset[str] = frozenset(
    {
        "cora.decision.features.append_reasoning_entries",
        "cora.run.features.append_run_readings",
        "cora.operation.features.append_procedure_steps",
    }
)
# Orchestration slices: command-shaped but no decider; the handler
# delegates to a runtime (Conductor) that internally calls other
# slices. Same file set as entry-append (no decider.py).
_ORCHESTRATION_SLICES: frozenset[str] = frozenset(
    {
        # Conductor entry: delegates start_procedure / append_procedure_steps /
        # complete_procedure / abort_procedure handlers; no direct event
        # emission. See [[project_edge_runtime_design]].
        "cora.operation.features.conduct_procedure",
    }
)
_NO_DECIDER_SLICES: frozenset[str] = _ENTRY_APPEND_SLICES | _ORCHESTRATION_SLICES

# Slices currently in flight. Each entry MUST cite the phase that
# will close it; reviewers should reject additions that don't.
WIP_SLICES: frozenset[str] = frozenset(
    {
        # First per-BC publish slice canary; event shapes + pure
        # decider landed first so the cross-BC PublishedArtifact
        # contract is provable before any handler IO lands. The
        # handler + route + tool + arch fitness for ai-cannot-sign-off
        # + cross-BC dual-stream land in the follow-up commit per
        # the planning workflow's 3d1 -> 3d2 -> 3d3 split.
        "cora.calibration.features.publish_revision",
    }
)


def _qualified(slice_dir: Path) -> str:
    rel = slice_dir.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.parts)


def _all_slices() -> list[Path]:
    tracked = tracked_python_files()
    dirs: set[Path] = set()
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        for f in tracked:
            if f.parent.parent != features:
                continue
            slice_dir = f.parent
            if slice_dir.name.startswith("_"):
                continue
            dirs.add(slice_dir)
    return sorted(dirs)


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_slice_has_required_files(slice_dir: Path) -> None:
    qualified = _qualified(slice_dir)
    if qualified in WIP_SLICES:
        pytest.skip(f"{qualified} is in WIP_SLICES (mid-phase)")

    files = {p.name for p in tracked_python_files() if p.parent == slice_dir}
    has_command = "command.py" in files
    has_query = "query.py" in files

    if not has_command and not has_query:
        pytest.skip(f"{qualified} is a stub (no command.py or query.py)")

    assert not (has_command and has_query), (
        f"{qualified}: a slice is either a command (command.py + decider.py) or a "
        f"query (query.py), never both."
    )

    if qualified in _NO_DECIDER_SLICES:
        required = _ENTRY_APPEND_SLICE_FILES
    elif has_command:
        required = _COMMAND_SLICE_FILES
    else:
        required = _QUERY_SLICE_FILES
    missing = required - files
    assert not missing, f"{qualified}: missing required files {sorted(missing)}"


@pytest.mark.architecture
def test_wip_slices_actually_exist() -> None:
    """WIP_SLICES entries must point at real directories. Drift catcher."""
    for qualified in WIP_SLICES:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:])
        assert path.is_dir(), f"WIP_SLICES entry {qualified} no longer exists; remove it"


@pytest.mark.architecture
def test_entry_append_slices_actually_exist() -> None:
    """`_ENTRY_APPEND_SLICES` entries must point at real directories."""
    for qualified in _ENTRY_APPEND_SLICES:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:])
        assert path.is_dir(), f"_ENTRY_APPEND_SLICES entry {qualified} no longer exists; remove it"
