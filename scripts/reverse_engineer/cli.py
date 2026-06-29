"""CLI for the *-bits extraction pass.

Usage (from repo root; scripts/ is not a package, so run via PYTHONPATH):

    PYTHONPATH=scripts python3 -m reverse_engineer.cli \
        --repo BCDA-APS/8id-bits --repo BCDA-APS/tomo-bits

A --repo is a GitHub slug (shallow-cloned into a gitignored cache) or a local
path. Per repo it emits facts.md + beamline.candidate.yaml; across all repos it
emits the fleet recurrence report. Network access (git clone) lives only here so
the parsing/mapping/emit core stays pure and unit-testable.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import emit, mapping, parse

_GITHUB = "https://github.com"


def _clone_url(repo: str) -> str:
    """Resolve a --repo argument to a clone URL.

    Accepts a full https:// URL, a host-qualified slug (gitlab.desy.de/group/repo,
    recognised by a dotted first segment), or a bare GitHub slug (org/repo). The
    shallow clone fetches each remote's default branch as HEAD, which for the DESY
    OnlineXML packages is the deployment branch (debian/jessie etc.).
    """
    if repo.startswith(("https://", "http://")):
        return repo
    first = repo.split("/", 1)[0]
    if "." in first:
        return f"https://{repo}"
    return f"{_GITHUB}/{repo}"


def _resolve_repo(repo: str, cache: Path) -> tuple[str, Path]:
    """Return (repo_stem, local_path), shallow-cloning a slug into the cache."""
    local = Path(repo)
    if local.exists() and local.is_dir():
        return local.name, local
    stem = repo.rstrip("/").split("/")[-1]
    dest = cache / repo.replace("/", "__").replace(":", "_")
    if not dest.exists():
        cache.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", _clone_url(repo), str(dest)],
            check=True,
        )
    return stem, dest


def _read(path: Path) -> str | None:
    """Read a file as text, skipping broken symlinks and binary or absent files.

    Some *-bits repos symlink a station's devices.yml to the shared common file;
    in a shallow clone the link can dangle, so a missing or unreadable file is
    skipped rather than fatal.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _collect_instances(repo_dir: Path) -> list[parse.DeviceInstance]:
    instances: list[parse.DeviceInstance] = []
    patterns = ("**/configs/devices.yml", "**/configs/ad_devices.yml")
    seen_files: set[Path] = set()
    for pattern in patterns:
        for path in sorted(repo_dir.glob(pattern)):
            if path in seen_files:
                continue
            seen_files.add(path)
            text = _read(path)
            if text is not None:
                instances.extend(parse.parse_devices_yaml(text))
    by_name: dict[str, parse.DeviceInstance] = {}
    for instance in instances:
        by_name.setdefault(instance.name, instance)
    return list(by_name.values())


def _collect_sketches(repo_dir: Path) -> dict[str, parse.OphydSketch]:
    sketches: dict[str, parse.OphydSketch] = {}
    for path in sorted(repo_dir.glob("**/devices/*.py")):
        if path.name == "__init__.py":
            continue
        text = _read(path)
        if text is not None:
            sketches.update(parse.parse_ophyd_module(text))
    return sketches


def _collect_permissions(repo_dir: Path) -> list[parse.PermissionGroup]:
    for path in sorted(repo_dir.glob("**/user_group_permissions.yaml")):
        text = _read(path)
        if text is not None:
            return parse.parse_permissions(text)
    return []


def _collect_online_xml(repo_dir: Path) -> list[parse.TangoDevice]:
    """Parse every online_*.xml device registry under a DESY beamline package.

    A beamline's per-endstation online files each re-list shared upstream devices,
    so the same (name, Tango address) appears several times. Deduplicate on that
    pair: identical re-registrations collapse, while two distinct devices that
    happen to share a name (different addresses) are both kept.
    """
    by_key: dict[tuple[str, str | None], parse.TangoDevice] = {}
    for path in sorted(repo_dir.glob("**/online_*.xml")):
        text = _read(path)
        if text is None:
            continue
        for device in parse.parse_online_xml(text):
            by_key.setdefault((device.name, device.address), device)
    return list(by_key.values())


def _beamline_name(devices: list[mapping.CandidateDevice], fallback: str) -> str:
    sectors = Counter(
        d.enclosure.rsplit("-", 1)[0]
        for d in devices
        if d.enclosure and d.enclosure.count("-") >= 2
    )
    if sectors:
        return sectors.most_common(1)[0][0]
    return fallback


_BITS_SOURCE_DESC = "the repo's Guarneri `devices.yml` plus ophyd device classes"
_ONLINEXML_SOURCE_DESC = "DESY OnlineXML (the beamline's online_*.xml Tango device registry)"


def _process_repo_bits(
    stem: str, repo_dir: Path
) -> tuple[list[mapping.CandidateDevice], list[parse.PermissionGroup], str, int | None]:
    instances = _collect_instances(repo_dir)
    sketches = _collect_sketches(repo_dir)
    permissions = _collect_permissions(repo_dir)
    devices = [
        mapping.to_candidate_device(instance, sketches.get(instance.class_name))
        for instance in instances
    ]
    return devices, permissions, _BITS_SOURCE_DESC, None


def _process_repo_onlinexml(
    stem: str, repo_dir: Path
) -> tuple[list[mapping.CandidateDevice], list[parse.PermissionGroup], str, int | None]:
    tango_devices = _collect_online_xml(repo_dir)
    devices = [
        candidate
        for device in tango_devices
        if (candidate := mapping.to_candidate_device_tango(device)) is not None
    ]
    skipped = len(tango_devices) - len(devices)
    return devices, [], _ONLINEXML_SOURCE_DESC, skipped


def _process_repo(
    repo: str, cache: Path, out_root: Path, facility: str, source: str
) -> tuple[str, list[mapping.CandidateDevice]]:
    stem, repo_dir = _resolve_repo(repo, cache)
    if source == "onlinexml":
        devices, permissions, source_desc, skipped = _process_repo_onlinexml(stem, repo_dir)
    else:
        devices, permissions, source_desc, skipped = _process_repo_bits(stem, repo_dir)
    beamline_name = _beamline_name(devices, stem)

    out_dir = out_root / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    facts = emit.render_facts_md(
        stem, beamline_name, facility, devices, permissions, source_desc, skipped
    )
    (out_dir / "facts.md").write_text(facts, encoding="utf-8")

    candidate = emit.render_candidate_yaml(beamline_name, facility, devices)
    candidate_path = out_dir / "beamline.candidate.yaml"
    candidate_path.write_text(candidate, encoding="utf-8")

    ok, message = emit.self_validate(candidate_path)
    status = "valid" if ok else f"INVALID: {message}"
    real = sum(1 for d in devices if not d.is_sim)
    skip_note = f", {skipped} filtered" if skipped else ""
    print(f"{stem}: {real} devices{skip_note}, candidate {status}")
    return stem, devices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract candidate CORA facts from beamline controls sources."
    )
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        help="Repo slug (org/repo, host.tld/group/repo), full https URL, or local path",
    )
    parser.add_argument(
        "--source",
        choices=("bits", "onlinexml"),
        default="bits",
        help="Source format: EPICS *-bits (default) or DESY OnlineXML",
    )
    parser.add_argument("--out", default="research/aps-reverse-engineering/extracted")
    parser.add_argument("--cache", default="research/aps-reverse-engineering/.cache")
    parser.add_argument("--catalog", default="catalog/catalog.yaml")
    parser.add_argument(
        "--recurrence-out", default="research/aps-reverse-engineering/recurrence.md"
    )
    parser.add_argument("--facility", default="aps")
    args = parser.parse_args(argv)

    cache = Path(args.cache)
    out_root = Path(args.out)

    per_repo: dict[str, list[mapping.CandidateDevice]] = {}
    for repo in args.repo:
        stem, devices = _process_repo(repo, cache, out_root, args.facility, args.source)
        per_repo[stem] = devices

    graduated = emit.graduated_families(Path(args.catalog))
    recurrence = emit.render_recurrence_md(per_repo, graduated)
    recurrence_path = Path(args.recurrence_out)
    recurrence_path.parent.mkdir(parents=True, exist_ok=True)
    recurrence_path.write_text(recurrence, encoding="utf-8")
    print(f"recurrence: {recurrence_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
