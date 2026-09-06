"""Fitness: every seeded Agent names its brain, and never fakes a model.

Eighteen seeded agents once filled the required `model_ref` slot with
`provider="deterministic"`, `model="agent:<Kind>:v1"`. That value read as a
claim to think with a language model of that name, and no such model exists
or was ever approved. All eighteen were written by copying a sibling seed,
which is how one workaround became eighteen without anyone deciding to.

Three rules, all enumerated from the git-tracked file set per
`feedback_architecture_test_git_aware`:

  1. No seed constructs a `ModelRef` with the sentinel provider. This is the
     one that stops the workaround growing back the next time a seed is
     copied.
  2. Every `AgentSeedIdentity(...)` names a `brain`. The dataclass already
     requires it, so this catches the case where the field is made optional
     later and a seed quietly stops declaring one.
  3. A `Rule` brain's name is `<Kind>:v<N>` for that module's own
     `*_AGENT_KIND`. This is what keeps the two eras agreeing: a stream
     written before `brain` existed folds through
     `brain_from_legacy_model_ref`, which reads `agent:<Kind>:v1` as
     `Rule("<Kind>:v1")`. If a new seed named its rule anything else, the
     same agent would fold to two different brains depending on when its
     deployment was first booted.
"""

import ast
import re

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_SENTINEL_PROVIDER = "deterministic"
_RULE_NAME = re.compile(r"^(?P<kind>[A-Za-z]+):v(?P<version>\d+)$")


def _agent_seed_modules() -> list[str]:
    root = CORA_ROOT / "agent"
    return sorted(
        str(path.relative_to(CORA_ROOT.parent.parent))
        for path in tracked_python_files()
        if path.parent == root and path.name.startswith("seed")
    )


def _parse(relative_path: str) -> ast.Module:
    return ast.parse((CORA_ROOT.parent.parent / relative_path).read_text())


def _kind_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `*_AGENT_KIND = "<Kind>"` assignments, by constant name."""
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.endswith("_AGENT_KIND"):
                found[target.id] = node.value.value
    return found


def _calls(tree: ast.Module, *, func_name: str, attr: str | None = None) -> list[ast.Call]:
    matched: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if attr is None:
            if isinstance(target, ast.Name) and target.id == func_name:
                matched.append(node)
        elif (
            isinstance(target, ast.Attribute)
            and target.attr == attr
            and isinstance(target.value, ast.Name)
            and target.value.id == func_name
        ):
            matched.append(node)
    return matched


@pytest.mark.parametrize("module_path", _agent_seed_modules())
def test_agent_seed_never_constructs_a_sentinel_model_ref(module_path: str) -> None:
    tree = _parse(module_path)
    for call in _calls(tree, func_name="ModelRef"):
        for keyword in call.keywords:
            if keyword.arg != "provider":
                continue
            if isinstance(keyword.value, ast.Constant):
                assert keyword.value.value != _SENTINEL_PROVIDER, (
                    f"{module_path} builds a ModelRef with provider="
                    f"{_SENTINEL_PROVIDER!r}. An agent that does not think with a "
                    f"language model declares brain=BrainRef.for_rule(...) instead."
                )


@pytest.mark.parametrize("module_path", _agent_seed_modules())
def test_agent_seed_identity_names_a_brain(module_path: str) -> None:
    tree = _parse(module_path)
    for call in _calls(tree, func_name="AgentSeedIdentity"):
        declared = {keyword.arg for keyword in call.keywords}
        assert "brain" in declared, (
            f"{module_path} builds an AgentSeedIdentity without a brain. Every "
            f"seeded Agent states what it thinks with."
        )


@pytest.mark.parametrize("module_path", _agent_seed_modules())
def test_rule_brain_is_named_for_its_own_agent_kind(module_path: str) -> None:
    tree = _parse(module_path)
    rule_calls = _calls(tree, func_name="BrainRef", attr="for_rule")
    if not rule_calls:
        pytest.skip("no Rule brain in this seed")

    kinds = set(_kind_constants(tree).values())
    assert kinds, f"{module_path} declares a Rule brain but no *_AGENT_KIND constant"

    for call in rule_calls:
        assert len(call.args) == 1, f"{module_path}: BrainRef.for_rule takes one positional name"
        argument = call.args[0]
        assert isinstance(argument, ast.Constant) and isinstance(argument.value, str), (
            f"{module_path}: a Rule brain's name must be a literal, so this check "
            f"and `brain_from_legacy_model_ref` can be compared without running the seed"
        )
        match = _RULE_NAME.match(argument.value)
        assert match is not None, (
            f"{module_path}: rule name {argument.value!r} is not `<Kind>:v<N>`"
        )
        assert match.group("kind") in kinds, (
            f"{module_path}: rule name {argument.value!r} names "
            f"{match.group('kind')!r}, which is not this module's agent kind "
            f"({sorted(kinds)}). A pre-`brain` stream for this agent folds to "
            f"Rule('<Kind>:v1'), so a mismatch gives the same agent two brains."
        )
