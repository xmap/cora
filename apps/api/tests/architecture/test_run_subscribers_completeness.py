"""Pin: every subscriber file in `cora.run.subscribers/` is registered.

Mirror of `test_agent_subscribers_completeness.py` for the Run BC. The
Run BC grew its first event-reaction subscriber with the
authority-revocation kill-switch; without this pin a second subscriber
could silently regress the registry glue the same way the Agent BC's
did before its pin landed.

Rule: for every `cora/run/subscribers/<name>.py` (excluding `__init__.py`
and leading-underscore helpers), the file MUST export a
`make_<name>_subscriber` factory AND that factory MUST be called inside
`cora/run/_subscribers.py`'s `register_run_subscribers` function.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_SUBSCRIBERS_DIR = CORA_ROOT / "run" / "subscribers"
_REGISTRY_FILE = CORA_ROOT / "run" / "_subscribers.py"


def _subscriber_modules() -> list[Path]:
    """Every concrete subscriber module under `cora/run/subscribers/`.

    Enumerates from git's tracked-file set (not the filesystem) so a
    half-staged addition does not false-fail under pre-commit.
    """
    out: list[Path] = []
    for path in sorted(tracked_python_files()):
        if path.parent != _SUBSCRIBERS_DIR:
            continue
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        out.append(path)
    return out


def _called_function_names(tree: ast.AST) -> set[str]:
    """Names called as `Name(...)` or `module.Name(...)` anywhere in the tree."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                out.add(func.id)
            elif isinstance(func, ast.Attribute):
                out.add(func.attr)
    return out


def _module_stem(path: Path) -> str:
    return path.stem


@pytest.mark.architecture
@pytest.mark.parametrize("path", _subscriber_modules(), ids=_module_stem)
def test_subscriber_factory_is_registered(path: Path) -> None:
    """Each subscriber's `make_*_subscriber` factory is called in the registry."""
    stem = _module_stem(path)
    expected_factory = f"make_{stem}_subscriber"

    subscriber_tree = ast.parse(path.read_text())
    defined: set[str] = set()
    for node in ast.walk(subscriber_tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            defined.add(node.name)
    assert expected_factory in defined, (
        f"cora.run.subscribers.{stem} does not define {expected_factory}; "
        "every subscriber module must export a "
        "`make_<module-stem>_subscriber(deps: Kernel) -> <Subscriber>` factory."
    )

    registry_tree = ast.parse(_REGISTRY_FILE.read_text())
    called = _called_function_names(registry_tree)
    assert expected_factory in called, (
        f"cora.run._subscribers does not call {expected_factory}; "
        "register_run_subscribers must wire every subscriber under "
        "cora.run.subscribers/ into the projection-worker registry."
    )
