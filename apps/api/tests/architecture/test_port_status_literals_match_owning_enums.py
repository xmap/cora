"""Architecture fitness: a port's status `Literal` must match its owning StrEnum.

A cross-BC lookup port cannot import the owning BC's StrEnum: the ports package
holds `depends_on = []` in `tach.toml`, and that neutrality is what lets several
BCs answer the same question. So a status axis crosses the port surface as a
value, and a consumer in another BC partitions on it by writing the string out
by hand.

Typing that field as a `Literal` alias instead of a bare `str` keeps the port
neutral (`Literal` is stdlib) while pinning the exact value set, so a consumer
comparing against a value the enum does not have is a type error at the call
site. That only holds while the alias and the enum agree, which is what the
first test below asserts.

Why the value set and not "a value of SOME StrEnum": `"Active"` is a member of
14 different StrEnums in this codebase, so a check that only asked whether a
literal belongs to some enum would pass a `ClearanceStatus` value handed to an
enclosure gate. It would also have passed the `permit_status="Denied"` fixture
this pin caught on its first application, since `"Denied"` is a real
`RatificationStatus` value.

The registry is hand-maintained, which is the failure mode described in
`project_field_drop_bug_class`: a new port field added without a registry entry
would be silently unguarded. `test_every_port_status_literal_is_registered`
closes that by enumerating the aliases from source, so the registry has to keep
up with the ports rather than the other way round.
"""

import ast
from enum import StrEnum
from typing import Final, get_args

import pytest

from cora.enclosure.aggregates.enclosure.state import (
    EnclosureLifecycle,
    EnclosurePermitStatus,
)
from cora.infrastructure.ports.enclosure_lookup import (
    EnclosureLifecycleValue,
    EnclosurePermitStatusValue,
)
from tests.architecture.conftest import tracked_python_files

_PORTS_DIR: Final = "infrastructure/ports"

_ALIAS_SUFFIX: Final = "Value"

REGISTRY: Final[tuple[tuple[str, object, type[StrEnum]], ...]] = (
    ("EnclosurePermitStatusValue", EnclosurePermitStatusValue, EnclosurePermitStatus),
    ("EnclosureLifecycleValue", EnclosureLifecycleValue, EnclosureLifecycle),
)


def _declared_aliases() -> dict[str, str]:
    """Every `<Name>Value = Literal[...]` alias defined under the ports package.

    Read from source rather than by importing the package, so an alias that
    fails to import is a visible failure here rather than a silent absence.
    """
    found: dict[str, str] = {}
    for path in tracked_python_files():
        if _PORTS_DIR not in path.as_posix():
            continue
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name) or not target.id.endswith(_ALIAS_SUFFIX):
                continue
            if not isinstance(node.value, ast.Subscript):
                continue
            if ast.unparse(node.value.value).split(".")[-1] != "Literal":
                continue
            found[target.id] = path.name
    return found


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("name", "alias", "enum"), REGISTRY, ids=lambda v: getattr(v, "__name__", v)
)
def test_port_status_literal_matches_owning_enum(
    name: str, alias: object, enum: type[StrEnum]
) -> None:
    literal_values = set(get_args(alias))
    enum_values = {member.value for member in enum}
    assert literal_values == enum_values, (
        f"{name} and {enum.__name__} have drifted: "
        f"the alias has {sorted(literal_values)}, the enum has {sorted(enum_values)}. "
        "Widen both together. The alias exists to pin the enum's value set on a "
        "port that cannot import the enum, so a one-sided change silently "
        "un-guards every cross-BC comparison against this field."
    )


@pytest.mark.architecture
def test_every_port_status_literal_is_registered() -> None:
    declared = _declared_aliases()
    registered = {name for name, _, _ in REGISTRY}
    unregistered = {name: mod for name, mod in declared.items() if name not in registered}
    assert not unregistered, (
        "port Literal aliases with no owning-enum pin: "
        + ", ".join(f"{name} ({mod})" for name, mod in sorted(unregistered.items()))
        + ". Add each to REGISTRY with the StrEnum it mirrors, or the alias is a "
        "hand-written value set that nothing keeps in step with its source."
    )
