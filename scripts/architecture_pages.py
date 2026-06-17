"""Render Architecture doc tables from the introspected code model.

The Architecture pages keep their hand-authored prose but mark the factual,
drift-prone bits (the bounded-contexts table, aggregate lists, counts, slice
tables, FSM states) with paired HTML comments:

    <!-- arch:bc-table -->
    ...regenerable body the build overwrites...
    <!-- /arch:bc-table -->

    <!-- arch:count kind=bc spell=true cap=true -->Seventeen<!-- /arch:count -->

The on_page_markdown hook calls `expand_markers` for every architecture/ page; it
replaces each marker's body with content rendered from the live code model, so the
tables cannot drift. An unknown kind, a missing/unknown arg, an unpaired marker, or
an empty render raises ArchMarkerError, which aborts `mkdocs build` regardless of
the mkdocs `strict:` flag (so local and CI behave the same).

Only the group labels (editorial) and the Planned-BC rows (not in code) are
authored here; everything else is read from the code model. A guard test asserts
the group rows cover exactly the introspected BCs, so a new BC cannot be silently
dropped from the table.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from architecture_introspect import ArchModel

# Editorial: the group label carried per row, in table order. Each label is a
# single role-noun naming the operational role its BCs play in running an
# experiment; the ISA/standard lens is documentation provenance (see the
# glossary), not the partition. Membership is guarded against the code model by
# a test (a new BC must be placed here).
_BC_ROWS: tuple[tuple[str, str], ...] = (
    ("Foundation", "access"),
    ("Foundation", "equipment"),
    ("Procedure", "recipe"),
    ("Procedure", "run"),
    ("Procedure", "campaign"),
    ("Resource", "supply"),
    ("Resource", "operation"),
    ("Authority", "trust"),
    ("Authority", "safety"),
    ("Authority", "federation"),
    ("Assurance", "enclosure"),
    ("Assurance", "calibration"),
    ("Assurance", "caution"),
    ("Governance", "decision"),
    ("Governance", "agent"),
    ("Outcome", "subject"),
    ("Outcome", "data"),
)

# Reserved BCs scoped but not implemented (no code, so authored here).
_PLANNED_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Governance", "strategy", "strategy"),
    ("Resource", "budget", "budget"),
)

_INLINE_KINDS = frozenset({"count", "bc-aggregates"})

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


class ArchMarkerError(ValueError):
    """An architecture marker is malformed, unknown, or renders empty."""


def _spell(n: int) -> str:
    if n < 0 or n >= 100:
        return str(n)
    if n < 20:
        return _ONES[n]
    tens, units = divmod(n, 10)
    return _TENS[tens] if units == 0 else f"{_TENS[tens]}-{_ONES[units]}"


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(c) if c else "" for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _aggs(model: ArchModel, bc: str) -> str:
    return ", ".join(f"`{a.name}`" for a in model.bc(bc).aggregates)


def render_bc_table(model: ArchModel, _args: dict[str, str]) -> str:
    placed = {bc for _, bc in _BC_ROWS} | {bc for _, bc, _ in _PLANNED_ROWS}
    missing = {bc.name for bc in model.bcs} - placed
    if missing:
        raise ArchMarkerError(
            f"arch:bc-table: BCs are not placed in the editorial group map "
            f"(scripts/architecture_pages.py _BC_ROWS): {sorted(missing)}"
        )
    # Group order is first appearance in _BC_ROWS, then any planned-only group.
    # Each group's Planned rows render directly after its Active rows so the group
    # reads as one contiguous block.
    group_order: list[str] = []
    for group, _ in _BC_ROWS:
        if group not in group_order:
            group_order.append(group)
    for group, _, _ in _PLANNED_ROWS:
        if group not in group_order:
            group_order.append(group)
    rows: list[list[str]] = []
    for group in group_order:
        for g, bc in _BC_ROWS:
            if g == group:
                rows.append([group, f"`{bc}`", _aggs(model, bc), "Active"])
        for g, bc, agg in _PLANNED_ROWS:
            if g == group:
                rows.append([group, f"`{bc}`", f"`{agg}`", "Planned"])
    return _table(["Group", "BC", "Aggregates", "Status"], rows)


def _count_value(model: ArchModel, args: dict[str, str]) -> int:
    kind = args["kind"]
    bc = args.get("bc")
    agg = args.get("agg")
    if kind == "bc":
        return model.bc_count
    if kind == "aggregate":
        return len(model.bc(bc).aggregates) if bc else model.aggregate_count
    if kind == "event":
        if bc and agg:
            return len(model.aggregate(bc, agg).events)
        if bc:
            return sum(len(a.events) for a in model.bc(bc).aggregates)
        return sum(len(a.events) for b in model.bcs for a in b.aggregates)
    if kind == "slice":
        return len(model.bc(bc).slices) if bc else sum(len(b.slices) for b in model.bcs)
    raise ArchMarkerError(f"arch:count unknown kind={kind!r}")


def render_count(model: ArchModel, args: dict[str, str]) -> str:
    n = _count_value(model, args)
    if args.get("spell") == "true":
        word = _spell(n)
        return word[:1].upper() + word[1:] if args.get("cap") == "true" else word
    return str(n)


def render_bc_aggregates(model: ArchModel, args: dict[str, str]) -> str:
    aggregates = model.bc(args["bc"]).aggregates
    if args.get("case") == "type":
        return ", ".join(f"`{a.type_name}`" for a in aggregates)
    return ", ".join(f"`{a.name}`" for a in aggregates)


def _surface_cell(value: str | None) -> str:
    return f"`{value}`" if value else "in-process"


def render_slices_table(model: ArchModel, args: dict[str, str]) -> str:
    rows: list[list[str]] = []
    for sl in sorted(model.bc(args["bc"]).slices, key=lambda s: s.dir_name):
        command = sl.command_class or sl.dir_name
        rest = f"`{sl.http_method} {sl.rest_path}`" if sl.rest_path else "in-process"
        rows.append([f"`{command}`", rest, _surface_cell(sl.mcp_tool)])
    return _table(["Command / query", "REST", "MCP tool"], rows)


def render_fsm_states(model: ArchModel, args: dict[str, str]) -> str:
    agg = model.aggregate(args["bc"], args["agg"])
    if not agg.fsm_enums:
        raise ArchMarkerError(f"arch:fsm-states: {args['bc']}/{args['agg']} has no FSM enum")
    lines: list[str] = []
    for enum in agg.fsm_enums:
        states = ", ".join(f"`{m}`" for m in enum.members)
        lines.append(f"- `{enum.enum_name}`: {states}")
    return "\n".join(lines)


RENDERERS = {
    "bc-table": render_bc_table,
    "count": render_count,
    "bc-aggregates": render_bc_aggregates,
    "slices-table": render_slices_table,
    "fsm-states": render_fsm_states,
}
REQUIRED_ARGS: dict[str, frozenset[str]] = {
    "bc-table": frozenset(),
    "count": frozenset({"kind"}),
    "bc-aggregates": frozenset({"bc"}),
    "slices-table": frozenset({"bc"}),
    "fsm-states": frozenset({"bc", "agg"}),
}
OPTIONAL_ARGS: dict[str, frozenset[str]] = {
    "bc-table": frozenset(),
    "count": frozenset({"bc", "agg", "spell", "cap"}),
    "bc-aggregates": frozenset({"case"}),
    "slices-table": frozenset(),
    "fsm-states": frozenset(),
}

_MARKER_RE = re.compile(
    r"<!--\s*arch:(?P<kind>[a-z][a-z0-9-]*)(?P<args>(?:\s+[a-z_]+=[^\s>]+)*)\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/arch:(?P=kind)\s*-->",
    re.DOTALL,
)


def _parse_args(kind: str, raw: str, src_uri: str) -> dict[str, str]:
    args: dict[str, str] = {}
    for token in raw.split():
        key, _, value = token.partition("=")
        args[key] = value
    allowed = REQUIRED_ARGS[kind] | OPTIONAL_ARGS[kind]
    unknown = set(args) - allowed
    if unknown:
        raise ArchMarkerError(f"{src_uri}: arch:{kind} has unknown args {sorted(unknown)}")
    missing = REQUIRED_ARGS[kind] - set(args)
    if missing:
        raise ArchMarkerError(f"{src_uri}: arch:{kind} missing required args {sorted(missing)}")
    return args


def expand_markers(markdown: str, *, model: ArchModel, src_uri: str) -> str:
    """Replace every `arch:*` marker body with content rendered from the code
    model. Raises ArchMarkerError on any malformed, unknown, unpaired, or
    empty-rendering marker so the build fails loudly."""
    matched = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal matched
        matched += 1
        kind = m.group("kind")
        if kind not in RENDERERS:
            raise ArchMarkerError(f"{src_uri}: unknown arch marker kind {kind!r}")
        args = _parse_args(kind, m.group("args"), src_uri)
        body = RENDERERS[kind](model, args)
        if not body:
            raise ArchMarkerError(f"{src_uri}: arch:{kind} rendered empty")
        open_marker = f"<!-- arch:{kind}{m.group('args')} -->"
        close_marker = f"<!-- /arch:{kind} -->"
        if kind in _INLINE_KINDS:
            return f"{open_marker}{body}{close_marker}"
        return f"{open_marker}\n{body}\n{close_marker}"

    out = _MARKER_RE.sub(_repl, markdown)
    opens = len(re.findall(r"<!--\s*arch:", markdown))
    closes = len(re.findall(r"<!--\s*/arch:", markdown))
    if opens != matched or closes != matched:
        raise ArchMarkerError(
            f"{src_uri}: malformed or unpaired arch marker "
            f"(open={opens}, close={closes}, matched={matched})"
        )
    return out
