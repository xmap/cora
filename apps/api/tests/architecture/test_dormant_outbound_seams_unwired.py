"""Dormant outbound seams stay unwired until someone accounts for the posture.

`derive_actuation` (`cora.api._readiness`) summarises whether CORA can drive
the beamline, reading two inputs: the ControlPort write switch and the
ComputePort substrate. Its `inert` answer is only honest while the OTHER
outbound seams remain dormant, and three of them are dormant code that
exists but is constructed nowhere:

  - `FdtTransferPort` and `GlobusTransferPort` move data to remote storage
    (the EGRESS axis; `FdtTransferPort` also spawns a subprocess). Neither
    is wired at the composition root.
  - `GlobusComputePort` runs a job on a remote endpoint (remote execution,
    which leans on both the actuation and spend axes). `build_compute_port`
    has a `prebuilt_port` seam for it, but no `GlobusComputePort` is ever
    constructed and passed in.

If a future change wires any of these, the actuation summary and the
observe-only story go stale silently: `derive_actuation` would keep saying
`inert` while a new path to the outside had opened. This fitness makes that
a build break instead, pointing the author back at the derivation and the
egress/spend axes it does not yet cover. It is the honest form of "we do not
bound these today": it does not stop anyone wiring them, it stops anyone
wiring them WITHOUT the conversation.

Enumerated from git's tracked-file set (never `rglob`), so a half-staged
refactor does not false-fail under pre-commit.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files

# Classes whose construction anywhere in production `src` is the trigger.
_DORMANT_OUTBOUND: frozenset[str] = frozenset(
    {
        "FdtTransferPort",
        "GlobusTransferPort",
        "GlobusComputePort",
    }
)

# Modules permitted to construct a dormant seam. Empty by design: the day
# one is wired, add its composition-root module here WITH a note that
# `cora.api._readiness.derive_actuation` (and the egress/spend axes) were
# revisited, or the observe-only report goes stale unnoticed.
_ALLOWLIST: frozenset[str] = frozenset()

# tests/architecture/<file>.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]


def _qualified(path: Path) -> str:
    return str(path.relative_to(_API_ROOT))


def _construction_lines(tree: ast.AST) -> dict[str, list[int]]:
    """Line numbers where a dormant seam is CONSTRUCTED (a bare-Name call).

    `FdtTransferPort(...)` counts; an import or a type annotation does not.
    """
    hits: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DORMANT_OUTBOUND
        ):
            hits.setdefault(node.func.id, []).append(node.lineno)
    return hits


def _candidate_files() -> list[Path]:
    """Tracked src files that textually mention any dormant seam with a `(`.

    Cheap heuristic; the AST scan below confirms a real call. The class
    definition files themselves mention the name at `class X:` (no `X(`
    call), so they do not become candidates.
    """
    needles = tuple(f"{name}(" for name in _DORMANT_OUTBOUND)
    out: list[Path] = []
    for path in tracked_python_files():
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in needles):
            out.append(path)
    return sorted(out)


@pytest.mark.architecture
@pytest.mark.parametrize("py_file", _candidate_files(), ids=_qualified)
def test_dormant_outbound_seam_is_not_constructed(py_file: Path) -> None:
    qualified = _qualified(py_file)
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    hits = _construction_lines(tree)
    if not hits:
        return
    if qualified in _ALLOWLIST:
        return
    detail = ", ".join(f"{name} at line {min(lines)}" for name, lines in sorted(hits.items()))
    pytest.fail(
        f"{qualified} constructs a dormant outbound seam ({detail}). Wiring one "
        f"opens a new path to the outside that `cora.api._readiness.derive_actuation` "
        f"does not account for, so the /readyz `actuation` summary and the observe-only "
        f"story would go stale silently. Revisit the derivation (and the egress/spend "
        f"axes it does not yet cover), then add {qualified!r} to this test's _ALLOWLIST "
        f"with a note that you did."
    )


@pytest.mark.architecture
def test_dormant_outbound_allowlist_has_no_stale_entries() -> None:
    """Every _ALLOWLIST entry must still construct a seam, or it is stale."""
    live = {
        _qualified(p)
        for p in _candidate_files()
        if _construction_lines(ast.parse(p.read_text(encoding="utf-8")))
    }
    stale = sorted(_ALLOWLIST - live)
    assert stale == [], (
        f"_ALLOWLIST names {stale}, which no longer construct a dormant outbound "
        f"seam. Prune them from {Path(__file__).name}."
    )
