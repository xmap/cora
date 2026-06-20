"""Architecture fitness: the prod signing-posture guard stays wired.

`cora.api.main.create_app` selects the signing factories
(`signature_port_factory` / `signer_factory` / `publish_port_factory`)
and MUST call `_enforce_production_signing_posture(...)` on them BEFORE
the lifespan reaches `build_kernel(...)`. The guard is what stops the
crypto-free `InMemorySignaturePort` / ephemeral-key `InMemorySigner`
stubs from shipping under `app_env in {prod, production}`.

A refactor that drops the guard call, or moves it after `build_kernel`,
would silently re-open the in-memory-default footgun (the Kernel would
be built with the stubs before anything refused). This AST check fails
CI in that case. It is the signing-side analogue of
`test_make_inmemory_kernel_production_call_sites.py`.
"""

import ast
from pathlib import Path

import pytest

# tests/architecture/<file>.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]
_MAIN = _API_ROOT / "src" / "cora" / "api" / "main.py"

_GUARD = "_enforce_production_signing_posture"
_KERNEL = "build_kernel"


def _call_lines(tree: ast.AST, func_name: str) -> list[int]:
    """Line numbers of every `func_name(...)` bare-Name call expression."""
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == func_name
    )


@pytest.mark.architecture
def test_signing_posture_guard_called_before_build_kernel() -> None:
    tree = ast.parse(_MAIN.read_text(), filename=str(_MAIN))
    guard_lines = _call_lines(tree, _GUARD)
    kernel_lines = _call_lines(tree, _KERNEL)

    assert guard_lines, (
        f"{_MAIN.name} no longer calls {_GUARD}(...). The prod boot guard "
        "for in-memory signing stubs has been removed; re-wire it before "
        "build_kernel or the crypto-free SignaturePort / ephemeral-key "
        "Signer can ship to production."
    )
    assert kernel_lines, (
        f"{_MAIN.name} no longer calls {_KERNEL}(...); this fitness test's "
        "ordering assumption is stale and must be revisited."
    )
    assert min(guard_lines) < min(kernel_lines), (
        f"{_GUARD}(...) at line {min(guard_lines)} must run BEFORE "
        f"{_KERNEL}(...) at line {min(kernel_lines)} in {_MAIN.name}. As "
        "written the Kernel would be built with the in-memory signing "
        "stubs before the guard could refuse the prod boot."
    )
