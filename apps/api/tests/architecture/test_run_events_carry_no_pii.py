"""Run event payloads carry NO PII. The observed capture path lives in
the `run_capture_path` table per memory/project_witnessed_run_prelive_slices.md
slice 13 (mirroring `actor_profile` / [[project_pii_vault]]).

Fitness function: AST-walks `cora/run/aggregates/run/events.py` and
rejects any dataclass field on ANY class in that file whose name
appears in the PII deny-list. Mirrors `test_actor_events_carry_no_pii.py`'s
mechanism (main check + file-presence guard + seeded-violation
meta-test); see that file for the full rationale on why this lives
separately from structural fitness tests.

Deliberately scans every class in the file, NOT only classes whose name
starts with "Run": this module also defines `CautionAcknowledgement`,
`DecisionDebriefRequested`, and `HoldClaimReleased`, real Run-stream
events that don't carry the `Run` prefix. A name-prefix filter would
have silently exempted them.

The deny-list covers slice 13's own field (`observed_path`,
`capture_path`, plus the wire-level `full_file_name`), slice 14a's
proposal/ESAF/ESAF-DOI fields (`proposal_number`, `esaf_number`,
`esaf_doi_number` -- vaulted, never harvested onto an event: see
`cora.run.aggregates.run.experiment_identity`'s module docstring for
the full argument), and the `User*` PVs slice 14b already named as
blocked (`project_witnessed_run_prelive_slices.md`): a directory/proposal
composition embeds a surname, and those PVs carry a name, badge, and
email directly. Widen it whenever a new identifying field is found on
the substrate.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT

_EVENTS_FILE = CORA_ROOT / "run" / "aggregates" / "run" / "events.py"

# Any dataclass field anywhere in the events file whose annotation
# target name matches one of these strings counts as a violation.
_PII_FIELD_NAMES = frozenset(
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
    }
)


def _pii_field_violations(source_path: Path) -> list[str]:
    """AST-walk every class in `source_path`'s dataclass fields for a
    PII deny-list hit. Takes a path (not a hardcoded file) so the
    seeded-violation meta-test below can call this SAME function
    against a temp file, rather than maintaining a second copy of the
    walk that could silently drift from what actually runs.
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
            if isinstance(target, ast.Name) and target.id in _PII_FIELD_NAMES:
                violations.append(f"line {stmt.lineno}: {node.name}.{target.id}")
    return violations


@pytest.mark.architecture
def test_run_event_payloads_carry_no_pii() -> None:
    """Pin: dataclass fields named like PII, PLUS the slice 14a
    proposal/ESAF/ESAF-DOI fields, never land on any event class in
    `cora/run/aggregates/run/events.py`.

    The observed capture path is personal data (2-BM's directory layout
    embeds a surname and a proposal number); it lives in the
    `run_capture_path` vault accessed via `CapturePathStore`, never on
    `RunCompleted` / `RunAborted` or any other event. A regression here
    usually means someone tried to carry the resolved path (or a raw
    `User*` PV) onto an event for convenience; move it to the vault
    instead.

    `proposal_number` / `esaf_number` / `esaf_doi_number` are NOT personal
    data (institutional identifiers for a funded experiment), so their
    presence here widens this test's scope past pure PII: it also
    enforces slice 14a's own decision that a value auto-harvested off
    an unauthenticated channel, with no operator gesture behind it,
    must never ride an immutable, INSERT-only event regardless of
    whether it identifies a person. See
    `cora.run.aggregates.run.experiment_identity`'s module docstring
    for the full argument. A regression here usually means someone
    tried to carry one of these three values onto `RunStarted` for
    convenience; move it to `run_experiment_identity` via
    `ExperimentIdentityStore` instead.
    """
    violations = _pii_field_violations(_EVENTS_FILE)
    assert not violations, (
        "Run event payloads must carry NO PII and none of the slice 14a "
        "experiment-identity fields; move identifying fields to "
        "run_capture_path / run_experiment_identity via their stores (see "
        "memory/project_witnessed_run_prelive_slices.md, slices 13 and "
        "14a):\n  " + "\n  ".join(violations)
    )


@pytest.mark.architecture
def test_run_events_file_is_present() -> None:
    """Sanity: the events.py file must exist; the file move below the
    aggregate folder would silently make the PII-deny scan a no-op
    without this guard."""
    msg = f"Expected Run events file at {_EVENTS_FILE}"
    assert _EVENTS_FILE.exists(), msg


@pytest.mark.architecture
def test_pii_deny_list_actually_finds_violations_when_seeded(tmp_path: Path) -> None:
    """Meta-test: confirm the ACTUAL production walker (`_pii_field_violations`,
    not a re-implemented copy) flags a seeded violation, on a class with
    no `Run` prefix -- the exact shape `CautionAcknowledgement` /
    `DecisionDebriefRequested` / `HoldClaimReleased` already have in the
    real file, which a name-prefix filter would have missed.

    Guards against two silent-pass failure modes at once: a future
    refactor moving the event classes to a sub-module (the walker
    quietly stops seeing them), and a future re-introduction of a
    name-prefix filter (the walker stops seeing non-`Run`-prefixed
    events).
    """
    seed_file = tmp_path / "seed_events.py"
    seed_file.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class HoldClaimReleased:\n"
        "    run_id: int\n"
        "    observed_path: str  # PII violation seeded by the meta-test\n"
    )
    violations = _pii_field_violations(seed_file)
    assert violations, "seeded `observed_path` field must be flagged by the deny-list walker"
