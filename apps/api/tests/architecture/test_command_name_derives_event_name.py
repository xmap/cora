"""Pin: a command class name mechanically derives the event class it emits.

`RegisterAsset` emits `AssetRegistered`. `UpdateAssetSettings` emits
`AssetSettingsUpdated`. `BindPlanRole` emits `PlanRoleBound`. The rule
behind all three: move the leading verb to the end, put it in the past
participle, keep every other token unchanged AND IN ORDER.

Order matters and the comparison is positional. This repo's R3 rule is
noun-LAST, and a prior audit was burned reading it backwards, so a check
that accepted `AgentPlanTargetUpdated` for `UpdateAgentTargetPlan` would
be blind to exactly the mistake it exists to catch.

    <Verb><Subject...>   ->   <Subject...><VerbPastParticiple>

Across the corpus 191 of 210 single-event command slices already obey
this. It was never written down and nothing enforced it, so the 2026-08-01
naming audit could rename an event class and leave its command behind
without a single one of the other fitness functions noticing. This
function is that missing check.

## Why derivability is worth pinning

The command and the event are the same fact told twice, once as a request
that may be refused and once as a record that cannot be. When the two
names drift apart a reader has to hold a translation table in their head
to follow one intent through the system, and every downstream artifact
(handler, decider, projection subscription, scenario test) inherits the
ambiguity. Keeping them derivable means a reader who knows either name
knows the other.

## Scope: single-event command slices only

A slice that emits two events is emitting either a cross-aggregate pair
(`add_run_to_campaign` writes `CampaignRunAdded` AND `RunAddedToCampaign`)
or a state-dependent choice (`resume_run` emits `HoldClaimReleased` when
other holds stand, `RunResumed` when the last one clears). Neither shape
has a single event for the command name to derive, so both are out of
scope. Query slices (no `command.py`), orchestration slices that emit
nothing of their own (the `conduct_*` family), and factory-built update
handlers are likewise out of scope.

## Identifying the command class

Three strategies, in order. All 235 command slices resolve today:

  1. The `_COMMAND_NAME` constant in `handler.py` when it names a class
     declared in `command.py` (138 slices). This is the authoritative
     label already pinned by `test_wire_command_name_matches_handler`.
  2. The PascalCase of the slice directory when that class exists
     (95 slices).
  3. The sole class in `command.py` (2 slices).

The fallbacks matter because `command.py` may declare input value objects
and result types alongside the command itself (`ActivityInput`,
`ConductProcedureResult`), so "the first class in the file" is not a safe
rule.

## Participle stemming

Regular `-ed` / `-en` with the three English spelling adjustments the
corpus actually exercises: silent-e restoration (`relocate` /
`Relocated`), consonant de-doubling (`stop` / `Stopped`), and terminal
y-to-i (`deny` / `Denied`). Irregular forms are listed individually in
`_IRREGULAR_STEMS`; extend that map when a new one lands rather than
loosening the regular rules, which is how a stemmer starts accepting
unrelated words as matches.

## Deviation policy

Two allowlists, deliberately separate.

`_SANCTIONED_DEVIATIONS` holds names that are correct as they stand and
should never be "fixed". `_KNOWN_DRIFT` holds names the audit judged
wrong, recorded here with the intended rename so the backlog lives in
code rather than in a document nobody re-reads. Collapsing the two into
one allowlist is what lets drift calcify: an entry with a plausible
reason beside it stops looking like work.

Both are guarded against staleness below: an entry whose slice now
derives cleanly fails, so a rename cannot silently leave a dead entry.
"""

import ast
import re
from functools import cache
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_TOKEN_RE = re.compile(r"[A-Z][a-z0-9]*")

_IRREGULAR_STEMS: dict[str, str] = {
    "held": "hold",
    "bound": "bind",
    "unbound": "unbind",
    "withdrawn": "withdraw",
    "taken": "take",
    "forgotten": "forget",
}

_SANCTIONED_DEVIATIONS: dict[str, str] = {
    # Entry-append slices. The command's payload goes to an `entries_*`
    # table, not to the event stream; the only event is the lazy
    # open-on-first-write logbook marker. The command cannot derive it
    # because they describe different acts.
    "decision/append_inferences": "logbook open-on-first-write",
    "operation/append_activities": "logbook open-on-first-write",
    "operation/append_diagnostics": "logbook open-on-first-write",
    "operation/append_outcomes": "logbook open-on-first-write",
    "run/append_observations": "logbook open-on-first-write",
    # Preposition phrases. The command reads as English with a
    # preposition; the event drops it and reorders to
    # `<Stream><Object><Participle>`. Dropping the preposition from the
    # command instead would make `GrantTool` ambiguous about its target.
    "agent/grant_tool_to_agent": "preposition phrase, event reorders",
    "agent/revoke_tool_from_agent": "preposition phrase, event reorders",
    "data/add_dataset_to_edition": "preposition phrase, event reorders",
    "data/remove_dataset_from_edition": "preposition phrase, event reorders",
    # Agent slices whose recorded fact is the Decision the agent
    # registers, not the agent's own verb. The verb names what the agent
    # did; `DecisionRegistered` names what the record gained.
    "agent/dismiss_event_in_reaction": "records a Decision, not the agent verb",
    "agent/regenerate_run_debrief": "records a Decision, not the agent verb",
    # The event's subject is a sub-part of the command's subject. The
    # Actor is not forgotten, the Actor's profile row is; that narrowing
    # is the whole point of the PII-vault design.
    "access/forget_actor": "event subject is the profile, not the Actor",
    # The Mount owns the stream, the Asset is the object being moved.
    # Command names the object (it reads naturally and matches the URL
    # scope), event names the stream owner (it must).
    "equipment/install_asset": "event names the Mount stream, command names the object",
    "equipment/uninstall_asset": "event names the Mount stream, command names the object",
    # Same split: the Visit owns the stream, the Surface is the object.
    "trust/take_control_of_surface": "event names the Visit stream, command names the object",
    "trust/release_control_of_surface": "event names the Visit stream, command names the object",
    # Phrasal verbs. `CheckInVisit` -> `VisitCheckedIn` splits the verb from
    # its preposition and moves the preposition to the end, so the trailing
    # tokens genuinely reorder. `test_event_class_name_shape.py` sanctions the
    # same pair for the same reason. Surfaced by tightening this check from a
    # set comparison to a positional one, which is the point of the tightening.
    "trust/check_in_visit": "phrasal verb, preposition moves to the end",
    "trust/check_out_visit": "phrasal verb, preposition moves to the end",
    # Adjudicated by the 2026-06-22 slice naming audit (PR #318), which
    # renamed `arrive_visit` to `record_visit_arrival` because `arrive`
    # was the one intransitive verb in the Visit lifecycle family, and
    # KEPT `VisitArrived` on purpose: the event states the arrival fact,
    # the command states the act of recording it. Same shape as
    # `StartRun` emitting `RunStarted`. Do not "fix" this pair.
    "trust/record_visit_arrival": "PR #318 kept the arrival-fact event over the recording verb",
}

_KNOWN_DRIFT: dict[str, str] = {
    "enclosure/observe_enclosure_status": (
        "command abbreviates the permit-status axis to bare `status` while the "
        "event spells it out; rename toward `ObserveEnclosurePermit` + "
        "`new_permit_status` so both name the same axis"
    ),
    "equipment/bind_asset_to_facility": (
        "verb changes mid-flight (bind vs assign); rename toward "
        "`AssignAssetFacilityCode` to match its two `Assign*` siblings"
    ),
}


def _stems(token: str) -> frozenset[str]:
    """Every plausible base form of one PascalCase token, lower-cased."""
    word = token.lower()
    if word in _IRREGULAR_STEMS:
        return frozenset({word, _IRREGULAR_STEMS[word]})
    out = {word}
    for suffix in ("ed", "en"):
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            base = word[: -len(suffix)]
            out |= {base, base + "e"}
            if len(base) > 2 and base[-1] == base[-2]:
                out.add(base[:-1])
            if base.endswith("i"):
                out.add(base[:-1] + "y")
    if word.endswith("e"):
        out.add(word[:-1])
    if word.endswith("y"):
        out.add(word[:-1] + "i")
    return frozenset(out)


def _derives(command: str, event: str) -> bool:
    """True when moving `command`'s leading verb to the end yields `event`."""
    command_tokens = _TOKEN_RE.findall(command)
    event_tokens = _TOKEN_RE.findall(event)
    if not command_tokens or not event_tokens:
        return False
    verb, rest = command_tokens[0], command_tokens[1:]
    verb_stems = _stems(verb)
    for index, token in enumerate(event_tokens):
        remainder = event_tokens[:index] + event_tokens[index + 1 :]
        if _stems(token) & verb_stems and remainder == rest:
            return True
    return False


@cache
def _event_class_names() -> frozenset[str]:
    """Every class in an `<Aggregate>Event` union across the tracked corpus."""
    names: set[str] = set()
    for path in sorted(tracked_python_files()):
        if path.name != "events.py" or "aggregates" not in path.parts:
            continue
        tree = ast.parse(path.read_text())
        union: list[str] | None = None
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
            value = node.value
            if value is None or not isinstance(target, ast.Name):
                continue
            if target.id.endswith("Event"):
                union = [n.id for n in ast.walk(value) if isinstance(n, ast.Name)]
        if union is None:
            union = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        names |= set(union)
    return frozenset(names)


@cache
def _command_slices() -> tuple[Path, ...]:
    """Slice directories that declare a `command.py`, sorted by path."""
    return tuple(
        sorted(
            path.parent
            for path in tracked_python_files()
            if path.name == "command.py" and path.parent.parent.name == "features"
        )
    )


def _slice_key(slice_dir: Path) -> str:
    """The `<bc>/<slice>` label used by both allowlists and by test ids."""
    return f"{slice_dir.relative_to(CORA_ROOT).parts[0]}/{slice_dir.name}"


def _command_class(slice_dir: Path) -> str | None:
    """Resolve the slice's command class by the three documented strategies."""
    declared = [
        node.name
        for node in ast.parse((slice_dir / "command.py").read_text()).body
        if isinstance(node, ast.ClassDef)
    ]
    handler = slice_dir / "handler.py"
    if handler.exists():
        for node in ast.walk(ast.parse(handler.read_text())):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "_COMMAND_NAME"
                and isinstance(node.value, ast.Constant)
                and node.value.value in declared
            ):
                return str(node.value.value)
    from_directory = "".join(word.capitalize() for word in slice_dir.name.split("_"))
    if from_directory in declared:
        return from_directory
    return declared[0] if len(declared) == 1 else None


def _emitted_event_classes(slice_dir: Path) -> frozenset[str]:
    """Event classes constructed anywhere inside one slice directory."""
    known = _event_class_names()
    found: set[str] = set()
    for path in sorted(tracked_python_files()):
        if not path.is_relative_to(slice_dir):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in known
            ):
                found.add(node.func.id)
    return frozenset(found)


@cache
def _single_event_slices() -> dict[str, tuple[str, str]]:
    """Map `<bc>/<slice>` to its (command class, sole emitted event class)."""
    out: dict[str, tuple[str, str]] = {}
    for slice_dir in _command_slices():
        emitted = _emitted_event_classes(slice_dir)
        command = _command_class(slice_dir)
        if command is None or len(emitted) != 1:
            continue
        out[_slice_key(slice_dir)] = (command, next(iter(emitted)))
    return out


@pytest.mark.architecture
def test_every_command_slice_resolves_a_command_class() -> None:
    unresolved = [_slice_key(d) for d in _command_slices() if _command_class(d) is None]
    assert not unresolved, (
        "These slices declare a command.py but no class could be resolved by any "
        f"of the three documented strategies: {unresolved}. Either name the class "
        "after the slice directory, or declare `_COMMAND_NAME` in handler.py "
        "naming it, or reduce command.py to a single class."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_single_event_slices()))
def test_command_name_derives_the_event_it_emits(key: str) -> None:
    command, event = _single_event_slices()[key]
    if key in _SANCTIONED_DEVIATIONS or key in _KNOWN_DRIFT:
        pytest.skip(f"allowlisted: {_SANCTIONED_DEVIATIONS.get(key) or _KNOWN_DRIFT[key]}")
    assert _derives(command, event), (
        f"{key}: command {command!r} does not derive event {event!r}. The rule is "
        "<Verb><Subject> -> <Subject><VerbPastParticiple>: move the leading verb "
        "to the end, past-participle it, keep every other token. Rename one side "
        "to match the other, or add the pair to `_SANCTIONED_DEVIATIONS` (correct "
        "as-is, with the reason) or `_KNOWN_DRIFT` (wrong, with the intended "
        "rename) in this file."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_SANCTIONED_DEVIATIONS | _KNOWN_DRIFT))
def test_allowlisted_slice_still_deviates(key: str) -> None:
    """Every allowlist entry must still fail derivation, so renames prune it."""
    resolved = _single_event_slices()
    assert key in resolved, (
        f"Allowlist entry {key!r} no longer resolves to a single-event command "
        "slice. The slice was removed, renamed, or now emits a different number "
        "of events. Update or prune the entry in this file."
    )
    command, event = resolved[key]
    assert not _derives(command, event), (
        f"Allowlist entry {key!r} now derives cleanly ({command!r} -> {event!r}). "
        "Remove it from `_SANCTIONED_DEVIATIONS` / `_KNOWN_DRIFT` in this file so "
        "the pair stays enforced from here on."
    )
