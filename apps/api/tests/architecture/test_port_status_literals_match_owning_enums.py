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

from cora.agent.aggregates.language_model import LanguageModelStatus
from cora.data.aggregates.distribution import DistributionStatus
from cora.enclosure.aggregates.enclosure.state import (
    EnclosureLifecycle,
    EnclosurePermitStatus,
)
from cora.equipment.aggregates.assembly import AssemblyStatus
from cora.equipment.aggregates.asset import AssetLifecycle, AssetTier
from cora.equipment.aggregates.family import FamilyStatus
from cora.federation.aggregates.credential import CredentialStatus
from cora.federation.aggregates.facility import FacilityKind, FacilityStatus
from cora.federation.aggregates.permit.state import (
    AbiTier,
    Direction,
    PermitStatus,
)
from cora.infrastructure.ports.assembly_lookup import AssemblyStatusValue
from cora.infrastructure.ports.asset_lookup import AssetLifecycleValue, AssetTierValue
from cora.infrastructure.ports.capability_lookup import CapabilityStatusValue
from cora.infrastructure.ports.clearance_lookup import ClearanceStatusValue
from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateStatusValue,
)
from cora.infrastructure.ports.credential_lookup import CredentialStatusValue
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DistributionStatusValue,
)
from cora.infrastructure.ports.enclosure_lookup import (
    EnclosureLifecycleValue,
    EnclosurePermitStatusValue,
)
from cora.infrastructure.ports.facility_lookup import (
    FacilityKindValue,
    FacilityStatusValue,
)
from cora.infrastructure.ports.family_lookup import FamilyStatusValue
from cora.infrastructure.ports.federation import (
    AbiTierValue,
    DirectionValue,
    PermitStatusValue,
)
from cora.infrastructure.ports.language_model_lookup import LanguageModelStatusValue
from cora.infrastructure.ports.supply_lookup import SupplyStatusValue
from cora.recipe.aggregates.capability import CapabilityStatus
from cora.safety.aggregates.clearance import ClearanceStatus
from cora.safety.aggregates.clearance_template import ClearanceTemplateStatus
from cora.supply.aggregates.supply import SupplyStatus
from tests.architecture.conftest import tracked_python_files

_PORTS_DIR: Final = "infrastructure/ports"

_ALIAS_SUFFIX: Final = "Value"

REGISTRY: Final[tuple[tuple[str, object, type[StrEnum]], ...]] = (
    ("EnclosurePermitStatusValue", EnclosurePermitStatusValue, EnclosurePermitStatus),
    ("EnclosureLifecycleValue", EnclosureLifecycleValue, EnclosureLifecycle),
    ("AssetTierValue", AssetTierValue, AssetTier),
    ("AssetLifecycleValue", AssetLifecycleValue, AssetLifecycle),
    ("AssemblyStatusValue", AssemblyStatusValue, AssemblyStatus),
    ("FamilyStatusValue", FamilyStatusValue, FamilyStatus),
    ("CapabilityStatusValue", CapabilityStatusValue, CapabilityStatus),
    ("LanguageModelStatusValue", LanguageModelStatusValue, LanguageModelStatus),
    ("DistributionStatusValue", DistributionStatusValue, DistributionStatus),
    ("ClearanceStatusValue", ClearanceStatusValue, ClearanceStatus),
    ("ClearanceTemplateStatusValue", ClearanceTemplateStatusValue, ClearanceTemplateStatus),
    ("CredentialStatusValue", CredentialStatusValue, CredentialStatus),
    ("FacilityStatusValue", FacilityStatusValue, FacilityStatus),
    ("FacilityKindValue", FacilityKindValue, FacilityKind),
    ("SupplyStatusValue", SupplyStatusValue, SupplyStatus),
    ("DirectionValue", DirectionValue, Direction),
    ("PermitStatusValue", PermitStatusValue, PermitStatus),
    ("AbiTierValue", AbiTierValue, AbiTier),
)


_AXIS_FIELD_NAMES: Final = frozenset(
    {"status", "lifecycle", "tier", "state", "direction", "permit_status", "kind"}
)

UNPINNED_AXIS_FIELDS: Final[dict[tuple[str, str], str]] = {
    ("SupplyLookupResult", "kind"): (
        "Supply.kind is free-form text today; no SupplyKind StrEnum exists to "
        "pin against. Pin this the moment that enum lands."
    ),
}


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


@pytest.mark.architecture
def test_no_port_axis_field_is_left_as_bare_str() -> None:
    """Range over port FIELDS, not over the aliases that happen to exist.

    The registry check above asks whether every alias is pinned, which is blind
    to a field that never got an alias at all. That blindness is not
    hypothetical: it is how `federation/permit_lookup.py` was missed when the
    other ports were converted, and it is the shape described in
    `project_aggregate_coverage_blindness`. The subject of this check is
    therefore the field.

    A genuine exception is recorded in `UNPINNED_AXIS_FIELDS` with its reason,
    so the absence of a pin is a written claim rather than a silent gap.
    """
    bare: list[str] = []
    for path in tracked_python_files():
        if _PORTS_DIR not in path.as_posix():
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                    continue
                field = stmt.target.id
                if field not in _AXIS_FIELD_NAMES:
                    continue
                if ast.unparse(stmt.annotation) != "str":
                    continue
                if (node.name, field) in UNPINNED_AXIS_FIELDS:
                    continue
                bare.append(f"{path.name}:{node.name}.{field}")
    assert not bare, (
        "port fields on a closed axis still typed as a bare str: "
        + ", ".join(sorted(bare))
        + ". Give each a Literal alias pinning its owning StrEnum and register "
        "it, or record it in UNPINNED_AXIS_FIELDS with the reason no enum "
        "exists to pin against. A bare str here means a consumer in another BC "
        "can compare it against a value the owner never defined."
    )
