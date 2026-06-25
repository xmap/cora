"""Render the extraction outputs and self-validate the candidate descriptor.

Three renderers (facts report, candidate beamline.yaml, fleet recurrence) plus a
self_validate that round-trips the candidate through the real scripts/
beamline_descriptor loader, and a graduated_families reader over catalog.yaml.
Loading the sibling scripts modules by path mirrors the bridge in
apps/api/tests/integration/scenarios/conftest.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from types import ModuleType

    from .mapping import CandidateDevice
    from .parse import PermissionGroup

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent

_CANDIDATE_HEADER = (
    "# CANDIDATE beamline descriptor: machine-extracted from a *-bits repo, NOT authoritative.\n"
    "# Every device carries new: true and a confirm note. Grouping by stage is a placeholder;\n"
    "# Family suggestions, enclosures, and per-axis PVs all need human curation and, for any\n"
    "# new Family, the naming-r3 gate. Do not copy into deployments/ without review.\n"
)


def _load_sibling(module_name: str) -> ModuleType:
    path = _SCRIPTS_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def graduated_families(catalog_path: Path) -> set[str]:
    """Return the set of Family names already graduated into catalog.yaml."""
    catalog_descriptor = _load_sibling("catalog_descriptor")
    catalog = catalog_descriptor.load(catalog_path)
    return {family.name for family in catalog.families}


def self_validate(candidate_path: Path) -> tuple[bool, str]:
    """Round-trip a candidate beamline.yaml through the real descriptor loader."""
    beamline_descriptor = _load_sibling("beamline_descriptor")
    try:
        beamline_descriptor.load(candidate_path)
    except Exception as exc:
        return False, str(exc)
    return True, "ok"


def _confirm_value(device: CandidateDevice) -> bool | str:
    if not device.confirm_reasons:
        return False
    return "; ".join(device.confirm_reasons)


def build_candidate_dict(
    beamline_name: str, facility: str, devices: list[CandidateDevice]
) -> dict[str, Any]:
    """Build the candidate descriptor as a plain dict matching BeamlineDescriptor."""
    real = [d for d in devices if not d.is_sim]
    enclosures = sorted({d.enclosure for d in real if d.enclosure})

    data: dict[str, Any] = {
        "beamline": {
            "name": beamline_name,
            "facility": facility,
            "tier": "Unit",
            "source": "unknown-pending-confirmation",
        },
        "enclosures": [
            {
                "name": name,
                "facility_code": facility,
                "confirm": "enclosure inferred from PV prefix or station label",
            }
            for name in enclosures
        ],
    }

    for stage in ("source", "sample", "detection"):
        stage_devices = [d for d in real if d.stage == stage]
        if not stage_devices:
            continue
        data[stage] = {
            "stage": stage,
            "intro": "Candidate grouping by inferred stage; grouping and stage need confirm.",
            "devices": [_candidate_device_dict(d) for d in stage_devices],
        }
    return data


def _candidate_device_dict(device: CandidateDevice) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": device.name, "family": device.family}
    if device.pv is not None:
        entry["pv"] = device.pv
    if device.enclosure:
        entry["enclosure"] = device.enclosure
    entry["new"] = True
    entry["confirm"] = _confirm_value(device)
    if device.labels:
        entry["labels"] = list(device.labels)
    if device.role_hints:
        entry["role_hints"] = list(device.role_hints)
    entry["source_class"] = device.source_class
    return entry


def render_candidate_yaml(beamline_name: str, facility: str, devices: list[CandidateDevice]) -> str:
    """Render the candidate beamline.yaml text (header comment + YAML body)."""
    data = build_candidate_dict(beamline_name, facility, devices)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return _CANDIDATE_HEADER + "\n" + body


def render_facts_md(
    repo: str,
    beamline_name: str,
    facility: str,
    devices: list[CandidateDevice],
    permissions: list[PermissionGroup],
) -> str:
    """Render the human-readable per-beamline facts report."""
    real = [d for d in devices if not d.is_sim]
    sims = [d for d in devices if d.is_sim]
    lines: list[str] = []
    lines.append(f"# Extracted facts: {repo}")
    lines.append("")
    lines.append(
        f"Machine-extracted candidate facts for `{beamline_name}` (facility `{facility}`). "
        "Candidates only; confirm every row before modeling. Source: the repo's Guarneri "
        "`devices.yml` plus ophyd device classes."
    )
    lines.append("")

    lines.append("## Device inventory")
    lines.append("")
    lines.append("| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for d in sorted(real, key=lambda d: (d.stage, d.name)):
        family = d.family if d.family_confirmed else f"{d.family} (?)"
        lines.append(
            f"| {d.name} | {family} | {_fmt_pv(d.pv)} | {d.enclosure or '?'} | {d.stage} "
            f"| {', '.join(d.labels) or '-'} | {'yes' if d.confirm_reasons else 'no'} |"
        )
    lines.append("")

    enclosures = sorted({d.enclosure for d in real if d.enclosure})
    lines.append("## Candidate enclosures")
    lines.append("")
    if enclosures:
        lines.append(", ".join(f"`{e}`" for e in enclosures) + " (all inferred, confirm).")
    else:
        lines.append("None inferred from prefixes or labels.")
    lines.append("")

    role_hints = sorted({hint for d in real for hint in d.role_hints})
    lines.append("## Role hints (from labels)")
    lines.append("")
    lines.append(", ".join(f"`{r}`" for r in role_hints) if role_hints else "None.")
    lines.append("")

    lines.append("## Trust hints (from user_group_permissions.yaml)")
    lines.append("")
    if permissions:
        lines.append("Candidate Trust Zones / Policies, one per queueserver user group:")
        lines.append("")
        for group in permissions:
            plans = ", ".join(group.allowed_plans) or "(none)"
            devs = ", ".join(group.allowed_devices) or "(none)"
            lines.append(f"- `{group.name}`: allowed plans `{plans}`; allowed devices `{devs}`")
    else:
        lines.append("No user_group_permissions.yaml found.")
    lines.append("")

    if sims:
        lines.append("## Simulated devices (excluded from the candidate)")
        lines.append("")
        lines.append(", ".join(f"`{d.name}`" for d in sims))
        lines.append("")

    lines.append("## Open confirms")
    lines.append("")
    any_reasons = False
    for d in sorted(real, key=lambda d: d.name):
        if d.confirm_reasons:
            any_reasons = True
            lines.append(f"- **{d.name}** (`{d.source_class}`)")
            for reason in d.confirm_reasons:
                lines.append(f"    - {reason}")
    if not any_reasons:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def _fmt_pv(pv: str | dict[str, str] | None) -> str:
    if pv is None:
        return "-"
    if isinstance(pv, str):
        return f"`{pv}`"
    return "; ".join(f"{k}=`{v}`" for k, v in pv.items())


def render_recurrence_md(per_repo: dict[str, list[CandidateDevice]], graduated: set[str]) -> str:
    """Render the cross-fleet recurrence report ranking Family graduation candidates."""
    family_repos: dict[str, set[str]] = {}
    class_repos: dict[str, set[str]] = {}
    label_repos: dict[str, set[str]] = {}
    for repo, devices in per_repo.items():
        for d in devices:
            if d.is_sim:
                continue
            family_repos.setdefault(d.family, set()).add(repo)
            class_repos.setdefault(d.source_class, set()).add(repo)
            for label in d.labels:
                label_repos.setdefault(label, set()).add(repo)

    lines: list[str] = []
    lines.append("# Fleet recurrence")
    lines.append("")
    lines.append(
        f"Cross-fleet frequency over {len(per_repo)} repos: "
        + ", ".join(f"`{r}`" for r in sorted(per_repo))
        + ". A suggested family in >= 2 repos is a catalog Family graduation candidate "
        "(human + naming-r3 gated). 'graduated' marks families already in catalog.yaml."
    )
    lines.append("")

    lines.append("## Suggested families by repo count")
    lines.append("")
    lines.append("| Family | Repos | Status |")
    lines.append("| --- | --- | --- |")
    for family, repos in sorted(family_repos.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if family in graduated:
            status = "graduated"
        elif len(repos) >= 2:
            status = "GRADUATION CANDIDATE"
        else:
            status = "single repo"
        lines.append(f"| {family} | {len(repos)} | {status} |")
    lines.append("")

    lines.append("## Ophyd classes by repo count")
    lines.append("")
    lines.append("| ophyd class path | Repos |")
    lines.append("| --- | --- |")
    for class_path, repos in sorted(class_repos.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(repos) >= 2:
            lines.append(f"| `{class_path}` | {len(repos)} |")
    lines.append("")

    lines.append("## Labels by repo count")
    lines.append("")
    lines.append("| label | Repos |")
    lines.append("| --- | --- |")
    for label, repos in sorted(label_repos.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(repos) >= 2:
            lines.append(f"| `{label}` | {len(repos)} |")
    lines.append("")
    return "\n".join(lines)
