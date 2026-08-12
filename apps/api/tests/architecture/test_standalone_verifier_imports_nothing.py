"""`scripts/verify_record_hash.py` must import stdlib and nothing else.

The verifier's entire value is that it is INDEPENDENT: a checker sharing
code with the thing it checks confirms that thing's own idea of the
answer, which is not a check. `project_record_export_v3.md` F4 pays a
real price for this (~30 lines of canonicalization deliberately
duplicated from `cora.shared.content_hash`, plus a second copy of the
bundle reassembly), so the property is worth a test rather than a
comment.

The duplication is a standing temptation to "clean up". This test is
what makes that cleanup fail loudly instead of quietly destroying the
independence the design bought.

AST-based rather than import-based: importing the module to inspect it
would defeat the point on a machine where `cora` happens to be
installed, which is every developer machine.
"""

import ast
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_record_hash.py"


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_standalone_verifier_imports_no_cora_and_no_third_party() -> None:
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    roots = _imported_roots(tree)

    assert "cora" not in roots, (
        "scripts/verify_record_hash.py imports cora. That makes it a check of "
        "CORA by CORA, which is not a check. The duplication it removes is "
        "deliberate; see the module docstring and F4."
    )

    non_stdlib = roots - set(sys.stdlib_module_names)
    assert not non_stdlib, (
        f"scripts/verify_record_hash.py imports non-stdlib module(s) {sorted(non_stdlib)}. "
        "It must run on a bare Python 3.13 on a machine that has never "
        "installed CORA or pip-installed anything."
    )


def test_standalone_verifier_uses_no_relative_imports() -> None:
    """A relative import would tie the script to a package layout it is
    supposed to be liftable out of: a reviewer should be able to copy
    this one file somewhere else and run it."""
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    relative = [
        node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level > 0
    ]
    assert not relative, "the verifier must be a single liftable file, with no relative imports"
