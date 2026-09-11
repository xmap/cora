"""A declared dependency nobody imports is a permission nobody asked for.

`tach.toml` says who may know about whom, and every entry is a hole
deliberately left in a wall. Holes are added when a need appears and nothing
closes them when the need goes away: over the contract's first four months it
gained 146 entries and lost 1, and that single removal was a hand-written
refactor rather than anything the process noticed.

That ratio is the problem this test exists for. A permission outlives its
reason silently, and the file that is supposed to answer "what may depend on
what" slowly turns into "what has ever depended on what". The audit that
prompted this found ten such entries, five of them guarding
`cora.equipment.ports`, a module holding a docstring and an empty `__all__`
after its one export was hoisted to `cora.shared.ports`.

Nothing here judges whether a dependency SHOULD exist. It only asks whether
the code still takes the permission up, which is the half a machine can check.

Git-tracked enumeration, not a filesystem walk, for the reason in the
`conftest` module docstring: pre-commit stashes only tracked files, so an
untracked module would be invisible here and the check would pass by not
looking. The schema-version pin was reported green that way an hour before
this test was written.
"""

from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from typing import TYPE_CHECKING

from tests.architecture.conftest import SRC_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

_TACH = SRC_ROOT.parent / "tach.toml"

_IMPORT = re.compile(r"^\s*(?:from|import)\s+(cora\.[A-Za-z0-9_.]*)", re.M)


def _declared() -> dict[str, list[str]]:
    modules = tomllib.loads(_TACH.read_text())["modules"]
    return {m["path"]: list(m.get("depends_on", ())) for m in modules}


def _dotted(path: Path) -> str:
    rel = path.relative_to(SRC_ROOT).with_suffix("")
    return ".".join(rel.parts).removesuffix(".__init__")


def _most_specific(candidates: list[str], target: str) -> str | None:
    """The longest declared path that `target` sits under, or None.

    `cora.run.aggregates.run` belongs to `cora.run.aggregates` when both it and
    `cora.run` are declared, so a module declaring BOTH is not credited for the
    broad one by an import that the narrow one already covers.
    """
    matches = [c for c in candidates if target == c or target.startswith(c + ".")]
    return max(matches, key=len) if matches else None


def _imports_by_module() -> dict[str, set[str]]:
    declared = _declared()
    owners = sorted(declared, key=len, reverse=True)
    found: dict[str, set[str]] = defaultdict(set)
    for path in tracked_python_files():
        owner = _most_specific(owners, _dotted(path))
        if owner is None:
            continue
        found[owner].update(_IMPORT.findall(path.read_text()))
    return found


def test_every_declared_dependency_is_actually_imported() -> None:
    declared = _declared()
    imports = _imports_by_module()
    unused = [
        (module, dep)
        for module, deps in sorted(declared.items())
        for dep in deps
        if not any(_most_specific(deps, i) == dep for i in imports.get(module, ()))
    ]
    assert not unused, (
        "tach.toml declares dependencies that no tracked source file takes up:\n"
        + "\n".join(f"  {module} -> {dep}" for module, dep in unused)
        + "\n\nEach is a hole in a wall with nothing passing through it. Delete "
        "the entry; add it back in the commit that needs it, which is one line "
        "and puts the reason next to the use. If the import is real but this "
        "cannot see it (a dynamic import, say), that is worth a comment here "
        "rather than an exemption, since a permission no reader can trace to a "
        "caller is one nobody can ever retire."
    )
