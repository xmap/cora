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


def _alias_names(tree: ast.AST) -> dict[str, str]:
    """Local name -> dormant class, for `from ... import X as Y` forms.

    Without this an aliased import (`import GlobusComputePort as _G`, then
    `_G(...)`) constructs a seam under a name the bare scan never sees.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom | ast.Import):
            continue
        for imported in node.names:
            if imported.name in _DORMANT_OUTBOUND and imported.asname:
                aliases[imported.asname] = imported.name
    return aliases


def _construction_lines(tree: ast.AST) -> dict[str, list[int]]:
    """Line numbers where a dormant seam is CONSTRUCTED.

    Counts three call shapes, because a guard that only sees the obvious
    one is a guard someone routes around without meaning to:

      - bare name: `FdtTransferPort(...)`
      - attribute: `adapters.FdtTransferPort(...)`
      - aliased import: `from ... import FdtTransferPort as _F` then `_F(...)`

    An import alone, a type annotation, and a `class X:` definition do not
    count; only a call does.
    """
    aliases = _alias_names(tree)
    hits: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            if func.id in _DORMANT_OUTBOUND:
                name = func.id
            elif func.id in aliases:
                name = aliases[func.id]
        elif isinstance(func, ast.Attribute) and func.attr in _DORMANT_OUTBOUND:
            name = func.attr
        if name is not None:
            hits.setdefault(name, []).append(node.lineno)
    return hits


def _candidate_files() -> list[Path]:
    """Tracked src files that textually mention any dormant seam.

    Cheap heuristic; the AST scan confirms a real call. The needle is the
    BARE class name, not `name(`, so a file that imports under an alias
    and calls the alias still becomes a candidate. That admits the class
    definition files themselves (`class FdtTransferPort:`), which is
    harmless: the AST scan finds no call there.
    """
    out: list[Path] = []
    for path in tracked_python_files():
        text = path.read_text(encoding="utf-8")
        if any(name in text for name in _DORMANT_OUTBOUND):
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


@pytest.mark.architecture
def test_every_guarded_seam_still_names_a_real_class() -> None:
    """A rename must break this build, not silently disarm the guard.

    `_DORMANT_OUTBOUND` holds bare strings, so renaming `FdtTransferPort`
    would leave the guard scanning for a name nothing defines: green, and
    watching nothing. This pins each entry to a class that actually exists
    in tracked source.
    """
    defined: set[str] = set()
    for path in tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    missing = sorted(_DORMANT_OUTBOUND - defined)
    assert missing == [], (
        f"{missing} appear in _DORMANT_OUTBOUND but no tracked src file defines a "
        f"class by that name. Either the seam was renamed (update the set, the "
        f"guard is currently watching nothing) or it was deleted (drop the entry)."
    )


@pytest.mark.architecture
def test_the_scan_enumerates_source_files() -> None:
    """A blinded enumerator would make every scan vacuously green."""
    assert tracked_python_files(), (
        "tracked_python_files() returned nothing, so the dormant-seam scan "
        "inspected no source at all and its silence means nothing."
    )


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("source", "shape"),
    [
        ("port = FdtTransferPort()", "bare name"),
        ("port = adapters.FdtTransferPort()", "module attribute"),
        (
            "from cora.operation.adapters.fdt_transfer_port import "
            "FdtTransferPort as _F\nport = _F()",
            "aliased import",
        ),
    ],
)
def test_the_detector_fires_on_each_construction_shape(source: str, shape: str) -> None:
    """Positive control: the detector must actually detect.

    Without this, an empty parameter set and a broken detector look
    identical, and the guard's silence proves nothing.
    """
    hits = _construction_lines(ast.parse(source))
    assert hits == {"FdtTransferPort": [hits["FdtTransferPort"][0]]}, (
        f"the detector missed a {shape} construction, so a real one would pass unnoticed"
    )


@pytest.mark.architecture
def test_the_detector_ignores_imports_and_annotations() -> None:
    """Negative control: only a CALL counts, or the guard cries wolf."""
    source = (
        "from cora.operation.adapters.fdt_transfer_port import FdtTransferPort\n"
        "def f(port: FdtTransferPort) -> None: ...\n"
    )
    assert _construction_lines(ast.parse(source)) == {}
