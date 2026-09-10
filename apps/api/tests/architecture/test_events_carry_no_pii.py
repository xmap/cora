"""Event payloads carry NO PII, across every tracked aggregate `events.py`.

Fitness function: AST-walks every git-tracked `events.py` under
`src/cora` (discovered via `tracked_python_files()`, never `glob()` /
`iterdir()` -- see conftest.py's module docstring for why a filesystem
scan would see a different file set than pre-commit does) and rejects
any dataclass field on any class in that file whose name appears in
the applicable PII deny-list.

Supersedes `test_run_events_carry_no_pii.py` and
`test_actor_events_carry_no_pii.py`. Those two hardcoded exactly one
file each (`cora/run/aggregates/run/events.py` and
`cora/access/aggregates/actor/events.py`); every other bounded
context's `events.py` was scanned by nothing. A new event anywhere
else carrying `observed_path` (or any other deny-listed field) would
have shipped with zero objection -- 2-BM's directory layout embeds a
surname and a proposal number, so a path-shaped field is personal
data wherever it lands, not only on the Run stream.

Deliberately scans every class in every file, NOT only classes whose
name matches the aggregate (mirrors the original Run test's own
rationale): `cora/run/aggregates/run/events.py` defines
`CautionAcknowledgement`, `DecisionDebriefRequested` and
`HoldClaimReleased`, real Run-stream events that don't carry the
`Run` prefix, and a name-prefix filter would have silently exempted
them. Dropping the original Actor test's `Actor*`-prefix filter
changes nothing there today (every class in that file already carries
the `Actor` prefix); it only removes a foot-gun for tomorrow.

## Why `name` / `display_name` are scoped to Actor, not global

Actor's original deny-list included bare `name` and `display_name`
because on that aggregate they hold a person's name. Unioning them
into the deny-list applied to every tracked `events.py` is unsound:
`name` is also the ordinary field almost every OTHER aggregate in
this codebase uses for its own entity's label. Scanning all 43
tracked `events.py` files with `name` / `display_name` in a
codebase-wide deny-list flags 28 fields across 15 files -- every one
of them an equipment, recipe, agent, campaign, dataset, procedure,
sample, or Trust-zone label, never a person's name. That count
includes `RunStarted.name` (the run's own label, e.g. the Bluesky
start-document precedent cited in that class's docstring), present in
the very file whose hand-curated deny-list already omits bare `name`
for exactly this reason. So `name` and `display_name` stay scoped to
`_ACTOR_EVENTS_FILE` via `_deny_list_for`, while every other deny term
from both original lists applies to every tracked `events.py` file
without exception. That is a widening for both originally-covered
files: Run's file is now also checked for `email` / `phone` / `orcid`
/ `affiliation` (Actor's terms; never observed on Run's file), and
Actor's file is now also checked for `path` / `directory` / `surname`
/ `proposal_number` / etc. (Run's terms; never observed on Actor's
file either).

See `cora.run.aggregates.run.experiment_identity`'s module docstring
for the slice 14a proposal/ESAF-number argument, and
[[project_pii_vault]] / [[project_pii_vault_implementation_design]]
for the Actor vault.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

_ACTOR_EVENTS_FILE = CORA_ROOT / "access" / "aggregates" / "actor" / "events.py"
_RUN_EVENTS_FILE = CORA_ROOT / "run" / "aggregates" / "run" / "events.py"

# Applies to every tracked events.py file without exception: none of these
# terms have ever matched a legitimate, non-personal field name anywhere in
# the codebase (see module docstring).
_GLOBAL_PII_FIELD_NAMES = frozenset(
    {
        "observed_path",
        "capture_path",
        "full_file_name",
        "path",
        "directory",
        "file_path",
        "surname",
        "proposal_number",
        "esaf_number",
        "esaf_doi_number",
        "user_name",
        "user_last_name",
        "user_badge",
        "user_email",
        "user_institution",
        "email",
        "phone",
        "orcid",
        "affiliation",
    }
)

# Only meaningful as PII on Actor's own events: everywhere else in this
# codebase `name` / `display_name` is the ordinary label field of a
# non-person entity (see module docstring for the 28-hit false-positive
# count that justifies keeping this scoped rather than global).
_ACTOR_ONLY_PII_FIELD_NAMES = frozenset({"name", "display_name"})


def _tracked_events_files() -> tuple[Path, ...]:
    """Every git-tracked `events.py` under `src/cora`, sorted for a
    deterministic (and readable) failure ordering."""
    return tuple(sorted(p for p in tracked_python_files() if p.name == "events.py"))


def _deny_list_for(events_file: Path) -> frozenset[str]:
    if events_file == _ACTOR_EVENTS_FILE:
        return _GLOBAL_PII_FIELD_NAMES | _ACTOR_ONLY_PII_FIELD_NAMES
    return _GLOBAL_PII_FIELD_NAMES


def _pii_field_violations(source_path: Path, deny_list: frozenset[str]) -> list[str]:
    """AST-walk every class in `source_path`'s dataclass fields for a
    deny-list hit. Takes both the path and the deny list as arguments
    (never a hardcoded global) so the seeded-violation meta-tests below
    can call this SAME function against synthetic input, rather than
    maintaining a second copy of the walk that could silently drift
    from what actually runs.
    """
    tree = ast.parse(source_path.read_text())
    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            target = stmt.target
            if isinstance(target, ast.Name) and target.id in deny_list:
                violations.append(f"line {stmt.lineno}: {node.name}.{target.id}")
    return violations


@pytest.mark.architecture
def test_event_payloads_carry_no_pii() -> None:
    """Pin: no dataclass field on any class in any tracked `events.py`
    is named like PII, or (Actor's file specifically) like a person's
    name.

    A regression here usually means someone tried to carry a resolved
    path, a raw `User*` PV, or an actor identity field onto an event
    for convenience; move it to the appropriate vault instead
    (`run_capture_path` / `run_experiment_identity` via their stores
    for Run, `actor_profile` via `ProfileStore` for Actor).
    """
    violations: list[str] = []
    for events_file in _tracked_events_files():
        rel = events_file.relative_to(CORA_ROOT)
        for hit in _pii_field_violations(events_file, _deny_list_for(events_file)):
            violations.append(f"{rel} {hit}")
    assert not violations, (
        "Event payloads must carry NO PII; move identifying fields to the "
        "appropriate vault (see this test module's docstring):\n  " + "\n  ".join(violations)
    )


@pytest.mark.architecture
def test_run_and_actor_events_files_are_present() -> None:
    """Sanity: the two originally-hardcoded files must still exist at
    their expected paths. A silent move would otherwise just drop out
    of the `events.py` filter with no other signal."""
    assert _RUN_EVENTS_FILE.exists(), f"Expected Run events file at {_RUN_EVENTS_FILE}"
    assert _ACTOR_EVENTS_FILE.exists(), f"Expected Actor events file at {_ACTOR_EVENTS_FILE}"


@pytest.mark.architecture
def test_pii_scan_discovers_events_file_for_every_bounded_context() -> None:
    """Sanity: every bounded context in `BCS` contributes at least one
    discovered `events.py`. Guards the discovery mechanism itself: a
    `tracked_python_files()` regression (or a filter bug above) that
    silently returned an empty or partial set would make the main test
    pass trivially, over zero files.
    """
    discovered = _tracked_events_files()
    covered_bcs = {events_file.relative_to(CORA_ROOT).parts[0] for events_file in discovered}
    missing = set(BCS) - covered_bcs
    assert not missing, f"No tracked events.py discovered for bounded context(s): {sorted(missing)}"


@pytest.mark.architecture
def test_pii_deny_list_actually_finds_violations_when_seeded(tmp_path: Path) -> None:
    """Meta-test: confirm the ACTUAL production walker
    (`_pii_field_violations`, not a re-implemented copy) flags a
    seeded violation on a class with an unrelated name. Guards against
    a future refactor moving event classes to a sub-module (the walker
    quietly stops seeing them) or reintroducing a name-prefix filter
    (the walker stops seeing non-prefixed events), the exact shape
    `CautionAcknowledgement` / `DecisionDebriefRequested` /
    `HoldClaimReleased` already have in the real Run file.
    """
    seed_file = tmp_path / "seed_events.py"
    seed_file.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class SomeUnrelatedEvent:\n"
        "    run_id: int\n"
        "    observed_path: str  # PII violation seeded by the meta-test\n"
    )
    violations = _pii_field_violations(seed_file, _GLOBAL_PII_FIELD_NAMES)
    assert violations, "seeded `observed_path` field must be flagged by the deny-list walker"


@pytest.mark.architecture
def test_actor_only_pii_terms_scoped_to_actor_events_file() -> None:
    """Pin: `name` / `display_name` apply only when scanning Actor's
    events file, never as part of the deny-list every other tracked
    `events.py` is checked against (see module docstring for why: both
    terms are the ordinary entity-label field on every other aggregate
    in this codebase)."""
    actor_deny_list = _deny_list_for(_ACTOR_EVENTS_FILE)
    other_deny_list = _deny_list_for(_RUN_EVENTS_FILE)
    assert actor_deny_list >= _ACTOR_ONLY_PII_FIELD_NAMES
    assert not (_ACTOR_ONLY_PII_FIELD_NAMES & other_deny_list)
