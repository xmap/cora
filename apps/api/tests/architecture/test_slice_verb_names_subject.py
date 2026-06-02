"""Pin: every slice directory name carries a SUBJECT, not a bare verb.

Slice directories under `cora/<bc>/features/<verb>_<subject>[_<qualifier>]/`
follow a verb-then-subject shape. The historical violator was
`enter_maintenance` / `exit_maintenance` (the sibling of every other
asset-scoped slice that DOES carry the subject: `activate_asset`,
`decommission_asset`, `add_asset_family`, `degrade_asset`, ...). The
rename to `enter_asset_maintenance` / `exit_asset_maintenance` (and
the matching command + MCP tool) closed the outliers.

This fitness keeps that closure sticky: every slice directory under
any BC's `features/` must contain at least one token that is a known
SUBJECT noun. The known set is:

  - every aggregate name across the 16-BC codebase (asset, family,
    mount, frame, model, caution, clearance, ..., visit, zone), and
  - their `-s` / `-ies` plural forms (families, policies, supplies,
    cautions, etc.) used by `list_<plural>` query slices, and
  - a small allowlist of bona-fide domain nouns that name a
    persisted value type rather than an aggregate (reasoning,
    entries, permission, permissions) used by Decision's
    `append_reasoning_entries` and Trust's `list_permissions`.

A future slice whose verb genuinely doesn't take a SUBJECT noun is
almost certainly a smell (a bare `arrive`, `ping`, `health_check`
would belong somewhere else, not under a BC's `features/`). When it
isn't a smell, i.e. when a new persisted-value-type domain noun
lands, extend `_DOMAIN_NOUN_ALLOWLIST` here AND document the rationale.
"""

import subprocess
from functools import cache
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT

_AGGREGATE_NAMES: frozenset[str] = frozenset(
    {
        "actor",
        "agent",
        "assembly",
        "asset",
        "calibration",
        "campaign",
        "capability",
        "caution",
        "clearance",
        "conduit",
        "credential",
        "dataset",
        "decision",
        "family",
        "frame",
        "method",
        "model",
        "mount",
        "permit",
        "plan",
        "policy",
        "practice",
        "procedure",
        "run",
        "seal",
        "subject",
        "supply",
        "surface",
        "visit",
        "zone",
    }
)

# Domain nouns that name a persisted value type rather than an aggregate.
# Add an entry here and document in `docs/reference/conventions.md` when
# a new domain noun earns a slice verb that doesn't take an aggregate
# subject.
_DOMAIN_NOUN_ALLOWLIST: frozenset[str] = frozenset(
    {
        "reasoning",  # Decision: append_reasoning_entries
        "entry",  # Decision: append_reasoning_entries (plural-stripped)
        "permission",  # Trust: list_permissions
        "event",  # Agent: dismiss_event_in_reaction
        "reaction",  # Agent: dismiss_event_in_reaction (Reaction = subscriber class)
    }
)


def _plural_to_singular(token: str) -> str:
    """Map common English plural forms back to singular for matching."""
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"  # families -> family, policies -> policy
    if token.endswith("ches") or token.endswith("shes"):
        return token[:-2]  # branches -> branch (rare; harmless)
    if token.endswith("s") and len(token) > 1 and not token.endswith("ss"):
        return token[:-1]  # supplies -> supplie? actually supplies isn't covered here
    return token


def _normalized(token: str) -> str:
    """Return the singular-form lowercase token used for subject lookup."""
    singular = _plural_to_singular(token)
    # `supplies` would stripto `supplie` here -- handle the `-ies` family
    # explicitly above, but also accept the bare singular if a re-strip
    # still leaves an `e` tail.
    return singular


@cache
def _known_subjects() -> frozenset[str]:
    return _AGGREGATE_NAMES | _DOMAIN_NOUN_ALLOWLIST


@cache
def _slice_dirs() -> list[Path]:
    """All tracked slice directories under any BC's features/."""
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        if not features.is_dir():
            continue
        # Use git ls-tree to discover tracked subdirectories under
        # features/, mirroring tracked_python_files()'s git-aware
        # enumeration. A slice dir is tracked iff it contains at least
        # one tracked Python file; `git ls-files` surfaces those files.
        result = subprocess.run(
            ["git", "ls-files", f"src/cora/{bc}/features"],
            cwd=features.parent.parent.parent.parent,  # apps/api
            capture_output=True,
            text=True,
            check=True,
        )
        seen: set[str] = set()
        for line in result.stdout.splitlines():
            parts = line.split("/")
            # src/cora/<bc>/features/<slice>/<file.py>
            if len(parts) >= 6 and parts[3] == "features" and parts[5].endswith(".py"):
                slice_name = parts[4]
                if slice_name in seen:
                    continue
                seen.add(slice_name)
                out.append(features / slice_name)
    return sorted(out)


def _slice_id(p: Path) -> str:
    return p.parent.parent.name + "." + p.name


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _slice_dirs(), ids=_slice_id)
def test_slice_dir_carries_subject(slice_dir: Path) -> None:
    """Slice directory name contains at least one known subject token."""
    known = _known_subjects()
    tokens = slice_dir.name.split("_")
    if any(_normalized(token) in known or token in known for token in tokens):
        return
    bc = slice_dir.parent.parent.name
    qualified = f"cora.{bc}.features.{slice_dir.name}"
    pytest.fail(
        f"Slice {qualified} carries no recognized SUBJECT noun.\n"
        f"  Tokens: {tokens}\n"
        f"  Known aggregates: {sorted(_AGGREGATE_NAMES)}\n"
        f"  Domain-noun allowlist: {sorted(_DOMAIN_NOUN_ALLOWLIST)}\n\n"
        "Slice directories follow `<verb>_<subject>[_<qualifier>]/`. The "
        "subject names the aggregate (or persisted value type) the slice "
        "mutates or reads, not just the verb's grammatical object. If this "
        "slice names a NEW persisted-value-type domain noun, add it to "
        "`_DOMAIN_NOUN_ALLOWLIST` AND document the rationale in "
        "`docs/reference/conventions.md`. If the rename is the right answer, "
        "carry the SUBJECT into the slice / command / MCP-tool name (the URL "
        "may stay terse per the URL-scope convention)."
    )
