"""The liveness port is reachable from the composition root.

The first gate review's P0 was that `PrincipalLivenessLookup` existed,
had an adapter, had a Conjunct, and was wired to nothing: no deployment
could turn it on, and the whole slice was a mechanism rather than a
control. Every test passed, because a control nobody can enable still
behaves correctly when constructed by hand in a unit test.

That failure is invisible to ordinary tests by construction, so it needs
a fitness function. Deleting the one line in `cora/api/main.py` that
binds the factory would otherwise leave the suite entirely green and
silently restore the P0.

Pins the chain end to end: the composition root binds a factory, the
Kernel builder accepts one and forwards it to the authorize factory, and
the authorize factory accepts it. A break anywhere along it means the
posture setting governs nothing.
"""

import ast

import pytest

from tests.architecture.conftest import CORA_ROOT

_MAIN = CORA_ROOT / "api" / "main.py"
_DEPS = CORA_ROOT / "infrastructure" / "deps.py"
_BUILD_AUTHORIZE = CORA_ROOT / "trust" / "build_authorize.py"

_FACTORY_KWARG = "principal_liveness_lookup_factory"
_LOOKUP_KWARG = "liveness_lookup"


def _keywords_passed(path: object, func_name: str) -> frozenset[str]:
    """Keyword names passed to any call of `func_name` in `path`."""
    tree = ast.parse(_read(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = (
            target.id
            if isinstance(target, ast.Name)
            else target.attr
            if isinstance(target, ast.Attribute)
            else None
        )
        if name != func_name:
            continue
        found.update(kw.arg for kw in node.keywords if kw.arg is not None)
    return frozenset(found)


def _read(path: object) -> str:
    return path.read_text()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]


@pytest.mark.architecture
def test_composition_root_binds_the_liveness_lookup_factory() -> None:
    assert _FACTORY_KWARG in _keywords_passed(_MAIN, "build_kernel"), (
        f"`cora/api/main.py` does not pass `{_FACTORY_KWARG}` to build_kernel.\n\n"
        "Without it no deployment can enable liveness at all: `Settings.liveness_posture` "
        "would govern nothing, `Conjunct.LIVENESS` would never be evaluated, and "
        "deactivating a person would stay decorative while every test stayed green. "
        "This is the exact P0 a gate review caught once already."
    )


@pytest.mark.architecture
def test_kernel_builder_forwards_the_lookup_to_the_authorize_factory() -> None:
    passed = _keywords_passed(_DEPS, "authorize_factory")
    assert _LOOKUP_KWARG in passed, (
        f"`build_kernel` does not forward `{_LOOKUP_KWARG}` to authorize_factory.\n\n"
        "The factory would be constructed and then dropped, which reads as wired and "
        "enforces nothing."
    )


@pytest.mark.architecture
def test_authorize_factory_accepts_the_lookup() -> None:
    tree = ast.parse(_read(_BUILD_AUTHORIZE))
    params: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_authorize":
            args = node.args
            params.update(a.arg for a in (*args.args, *args.kwonlyargs))
    assert _LOOKUP_KWARG in params, (
        f"`build_authorize` has no `{_LOOKUP_KWARG}` parameter, so the chain from the "
        "composition root to TrustAuthorize is broken at the last step."
    )
