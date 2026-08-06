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
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT

_MAIN = CORA_ROOT / "api" / "main.py"
_DEPS = CORA_ROOT / "infrastructure" / "deps.py"
_BUILD_AUTHORIZE = CORA_ROOT / "trust" / "build_authorize.py"

_FACTORY_KWARG = "principal_liveness_lookup_factory"
_LOOKUP_KWARG = "liveness_lookup"


def _calls_of(path: Path, func_name: str) -> list[frozenset[str]]:
    """Keyword names for EACH call of `func_name`, one entry per call site.

    Per call rather than unioned across calls. `build_kernel` invokes
    `authorize_factory` twice, once for the in-memory test arm and once
    for the postgres arm, and a union would let the production arm drop
    the kwarg while the test arm kept it green. That is the shape of the
    original P0 (wired somewhere, unreachable where it counts), so the
    pin has to see every site separately.
    """
    tree = ast.parse(path.read_text())
    calls: list[frozenset[str]] = []
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
        calls.append(frozenset(kw.arg for kw in node.keywords if kw.arg is not None))
    return calls


@pytest.mark.architecture
def test_composition_root_binds_the_liveness_lookup_factory() -> None:
    calls = _calls_of(_MAIN, "build_kernel")
    assert calls, "no build_kernel call found in cora/api/main.py"
    assert all(_FACTORY_KWARG in kwargs for kwargs in calls), (
        f"`cora/api/main.py` does not pass `{_FACTORY_KWARG}` to build_kernel.\n\n"
        "Without it no deployment can enable liveness at all: `Settings.liveness_posture` "
        "would govern nothing, `Conjunct.LIVENESS` would never be evaluated, and "
        "deactivating a person would stay decorative while every test stayed green. "
        "This is the exact P0 a gate review caught once already."
    )


@pytest.mark.architecture
def test_kernel_builder_forwards_the_lookup_to_the_authorize_factory() -> None:
    calls = _calls_of(_DEPS, "authorize_factory")
    assert len(calls) >= 2, (
        f"expected both the test-arm and postgres-arm authorize_factory calls, saw {len(calls)}"
    )
    missing = [i for i, kwargs in enumerate(calls) if _LOOKUP_KWARG not in kwargs]
    assert not missing, (
        f"authorize_factory call site(s) {missing} do not forward `{_LOOKUP_KWARG}`.\n\n"
        "Every arm must forward it. A factory constructed and then dropped on the "
        "production path reads as wired and enforces nothing, which is exactly how "
        "the original P0 passed every test."
    )


@pytest.mark.architecture
def test_authorize_factory_accepts_the_lookup() -> None:
    tree = ast.parse(_BUILD_AUTHORIZE.read_text())
    params: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_authorize":
            args = node.args
            params.update(a.arg for a in (*args.args, *args.kwonlyargs))
    assert _LOOKUP_KWARG in params, (
        f"`build_authorize` has no `{_LOOKUP_KWARG}` parameter, so the chain from the "
        "composition root to TrustAuthorize is broken at the last step."
    )
