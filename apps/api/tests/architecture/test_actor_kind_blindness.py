"""Architecture fitness: no principal's authority varies by its own kind.

An autonomous agent and a human operator are the same kind of actor to the
system: authority is decided over a bare principal, and nothing asks whether
that principal is a machine. That claim is load-bearing, so this test locks
it rather than leaving it to prose and discipline.

The distinction the whole file turns on is SUBJECT kind vs CALLER kind.

  - CALLER kind is the kind of the authenticated principal making a request.
    Nothing reads it, and Rule 2 makes that structural rather than merely
    observed: `Authorize.authorize` cannot receive a kind, and `Policy`
    carries no kind field, so the policy decision point cannot see it even
    in principle. A caller-kind branch is what would falsify the claim.
  - SUBJECT kind is the kind of an Actor a command NAMES: the Actor being
    minted, the Actor a Decision is attributed to. Reading it decides what a
    command means, not what its caller may do. Two such reads exist and both
    are enumerated below.

Sibling to `test_actor_kind_sync.py`, which pins the kind VOCABULARY across
DTO Literals and the SQL CHECK. This one pins the USAGE.

## Rule 1: every `ActorKind` branch is an enumerated carve-out

A comparison against `ActorKind`, or against one of its bare string values
on a `kind`-named operand, is a branch. Both that exist today read subject
kind, and each is enumerated with its reason in
`_ACTOR_KIND_BRANCH_ALLOWLIST`. The discovered set is asserted equal to the
allowlist in BOTH directions, so a new branch fails as drift-in and a
deleted branch fails as a stale entry. A ratchet would only catch the first.

Enum definitions, type annotations, `ActorKind(payload["kind"])` decode
calls, constructor kwargs, wire Literals and projection columns need no
carve-out: they carry the value without deciding on it, so the rule never
sees them.

## Rule 2: the Authorize port cannot observe kind

The structural claim the others rest on. `Authorize.authorize` takes
`principal_id`, `command_name`, `conduit_id`, `surface_id`. Kind is not a
parameter, so the policy decision point cannot branch on it even in
principle, and `Policy` carries no kind field to branch with. Widening that
signature would falsify the claim silently, so the parameter set is pinned.

## Rule 3: nothing that produces a signature reads kind

Evidentiary obligation is kind-aware by design (an agent's identity is
key-backed; a human's is a session), but it is carried by the event
vocabulary and by which paths are wired with a `Signer`, never by a branch
inside signing code.

The rule keys on files that CALL `<x>.sign(...)`, not on files importing
`SIGNED_EVENT_TYPES`. The registry names which event types are signature
targets and is legitimately read by the verify side too, so importing it
does not make a file a signing site: `signing.py` DEFINES the set (and so
never imports it), while a read-side obligation predicate would import it
while signing nothing. Verification reading a subject's kind to decide
whether an absent signature is an anomaly is evidence-checking, not a gate,
and this rule deliberately leaves it free.

Free of THIS rule, that is. Rule 1 still sees it and still wants it named in
the allowlist with a reason, because the allowlist is the ledger of every
place kind matters. The division is: Rule 1 says enumerate and justify; Rule
3 says that inside signing code no justification is accepted.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

# Deliberate reads of a SUBJECT's kind. Each entry names why the branch does
# not partition principals by kind. Keyed by `<path under cora/>::<enclosing
# qualname>` rather than `path:line` so the entry does not go stale silently
# when unrelated lines move.
#
# A CALLER-kind branch does not belong here and is not allowlistable: it
# falsifies the claim outright. There are none, and Rule 2 keeps it that way
# structurally. A third SUBJECT-kind entry is worth a design look, not an
# automatic rewrite; moving a subject-kind read into Policy data would be a
# category error, since Policy governs what a CALLER may do.
_ACTOR_KIND_BRANCH_ALLOWLIST: dict[str, str] = {
    "access/features/register_actor/decider.py::decide": (
        "Genesis guard on the minted subject, not on the caller. Reads `command.kind`, "
        "the kind of the Actor being created, never the kind of the acting principal, "
        "which this decider never sees. Routes agent-kind Actor genesis through "
        "define_agent's cross-BC atomic write so the (Agent.id == Actor.id) lock holds. "
        "The refusal is identical for every caller: no principal's authority, allowance, "
        "obligation, or consequence changes by kind."
    ),
    "decision/features/register_decision/decider.py::decide": (
        "Attribution guard, not an authorization gate. Reads the kind of the Actor named "
        "by `command.decided_by`, the attribution target; the authorization decision was "
        "already made on `principal_id` by a port whose signature cannot carry kind (see "
        "test_authorize_port_signature_omits_actor_kind). Refuses agent-attributed rows "
        "on the unsigned operator route, so that route offers no unsigned path for rows "
        "the Signer-wired subscriber path would have signed. Agents keep full capability "
        "to record Decisions through that signed path, so this costs them no authority."
    ),
}

# The parameters the policy decision point is allowed to see. Kind is absent
# on purpose: the PDP cannot branch on what it never receives.
_AUTHORIZE_PARAMS: frozenset[str] = frozenset(
    {"principal_id", "command_name", "conduit_id", "surface_id"}
)

_ACTOR_KIND_VALUES: frozenset[str] = frozenset({"human", "agent", "service_account"})


def _is_actor_kind_member(node: ast.expr) -> bool:
    """`ActorKind.AGENT`, `ActorKind.HUMAN`, `ActorKind.SERVICE_ACCOUNT`."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ActorKind"
    )


def _is_kind_operand(node: ast.expr) -> bool:
    """An operand plausibly holding a kind: `actor.kind`, `kind`, `principal_kind`."""
    if isinstance(node, ast.Attribute):
        return node.attr == "kind" or node.attr.endswith("_kind")
    if isinstance(node, ast.Name):
        return node.id == "kind" or node.id.endswith("_kind")
    return False


def _is_actor_kind_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value in _ACTOR_KIND_VALUES


class _KindBranchVisitor(ast.NodeVisitor):
    """Collect the qualnames of scopes that branch on an actor kind."""

    def __init__(self) -> None:
        self._scope: list[str] = []
        self.hits: set[str] = set()

    def _descend(self, name: str, node: ast.AST) -> None:
        self._scope.append(name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._descend(node.name, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._descend(node.name, node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._descend(node.name, node)

    def _record(self) -> None:
        self.hits.add(".".join(self._scope) if self._scope else "<module>")

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        member_compare = any(_is_actor_kind_member(o) for o in operands)
        value_compare = any(_is_kind_operand(o) for o in operands) and any(
            _is_actor_kind_constant(o) for o in operands
        )
        if member_compare or value_compare:
            self._record()
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        # `match actor.kind: case ActorKind.AGENT:` is not a Compare node.
        if _is_kind_operand(node.subject):
            for case in node.cases:
                if any(
                    _is_actor_kind_member(sub) or _is_actor_kind_constant(sub)
                    for sub in ast.walk(case.pattern)
                    if isinstance(sub, ast.expr)
                ):
                    self._record()
                    break
        self.generic_visit(node)


def _branch_sites() -> frozenset[str]:
    """`<path under cora/>::<qualname>` for every actor-kind branch in `src/cora`."""
    found: set[str] = set()
    for path in tracked_python_files():
        visitor = _KindBranchVisitor()
        visitor.visit(ast.parse(path.read_text()))
        rel = path.relative_to(CORA_ROOT).as_posix()
        found.update(f"{rel}::{qualname}" for qualname in visitor.hits)
    return frozenset(found)


def _authorize_protocol_params() -> frozenset[str]:
    tree = ast.parse((CORA_ROOT / "infrastructure" / "ports" / "authorize.py").read_text())
    for node in ast.iter_child_nodes(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Authorize"):
            continue
        for member in node.body:
            if isinstance(member, ast.AsyncFunctionDef | ast.FunctionDef) and (
                member.name == "authorize"
            ):
                args = member.args
                declared = (*args.posonlyargs, *args.args, *args.kwonlyargs)
                return frozenset(a.arg for a in declared if a.arg != "self")
    raise AssertionError("Authorize Protocol declares no `authorize` method")


def _signing_sites() -> list[Path]:
    """Files that PRODUCE a signature: they call `<something>.sign(...)`.

    Keying on the call rather than on a `SIGNED_EVENT_TYPES` import matters in
    both directions. The two subscriber sites take their `Signer` by
    constructor and never import the port, so an import-keyed rule would miss
    them; and `signing.py` defines the registry rather than importing it, so an
    import-keyed rule would exempt the very file holding the verifier while
    catching an innocent read-side predicate that imports the registry and
    signs nothing.
    """
    sites: set[Path] = set()
    for path in tracked_python_files():
        text = path.read_text()
        if ".sign(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "sign"
            ):
                sites.add(path)
                break
    return sorted(sites)


@pytest.mark.architecture
def test_actor_kind_branch_outside_allowlist_is_rejected() -> None:
    undocumented = sorted(_branch_sites() - frozenset(_ACTOR_KIND_BRANCH_ALLOWLIST))
    assert not undocumented, (
        "New branch(es) on Actor.kind in governance machinery:\n  "
        + "\n  ".join(undocumented)
        + "\n\nEvery gate decides over a bare principal; branching on kind partitions "
        "principals into humans and machines and breaks that. If this branch genuinely "
        "does not change any principal's authority, allowance, obligation, or "
        "consequence, add it to `_ACTOR_KIND_BRANCH_ALLOWLIST` with a reason saying why. "
        "Note the rule-of-three trigger recorded on the register_decision entry: a third "
        "carve-out means the discriminator belongs in Policy data, not in machinery."
    )


@pytest.mark.architecture
def test_actor_kind_allowlist_entry_without_branch_is_rejected() -> None:
    stale = sorted(frozenset(_ACTOR_KIND_BRANCH_ALLOWLIST) - _branch_sites())
    assert not stale, (
        "Allowlist entr(ies) with no matching branch in the tree:\n  "
        + "\n  ".join(stale)
        + "\n\nThe branch was removed or its enclosing function was renamed. Delete the "
        "entry so the allowlist keeps reading as the true, complete list of exceptions."
    )


@pytest.mark.architecture
def test_authorize_port_signature_omits_actor_kind() -> None:
    assert _authorize_protocol_params() == _AUTHORIZE_PARAMS, (
        f"Authorize.authorize parameters are {sorted(_authorize_protocol_params())}, "
        f"expected {sorted(_AUTHORIZE_PARAMS)}.\n\n"
        "The policy decision point cannot branch on what it never receives, and that is "
        "the structural reason authorization is kind-blind rather than merely "
        "disciplined. Widening this signature to carry an actor kind would make the "
        "claim false. Narrowing it is fine; update this pin."
    )


@pytest.mark.architecture
@pytest.mark.parametrize(
    "path",
    _signing_sites(),
    ids=lambda p: p.relative_to(CORA_ROOT).as_posix(),
)
def test_signing_site_does_not_read_actor_kind(path: Path) -> None:
    reads = sorted(
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ActorKind"
    )
    assert not reads, (
        f"{path.relative_to(CORA_ROOT).as_posix()} produces a signature and reads ActorKind:\n  "
        + "\n  ".join(reads)
        + "\n\nWhich rows carry a signature is settled by the event vocabulary "
        "(SIGNED_EVENT_TYPES) and by which paths are wired with a Signer, never by a "
        "branch inside signing code. Verification may read a subject's kind to decide "
        "whether an absent signature is an anomaly; producing one may not."
    )
