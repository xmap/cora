"""Static introspection of the CORA domain for the Architecture docs.

Walks apps/api/src/cora with the `ast` module only (ZERO cora imports, so it runs
under the lean docs-build interpreter) and returns a structured model of the
bounded contexts, their aggregates, the domain events each aggregate emits, the
FSM/status enums, and the vertical slices with their REST + MCP + command surface.

The Architecture docs render their factual tables from this model, so the tables
cannot drift from the code: there is no descriptor to keep in sync, the code IS
the source. Detection rules mirror the architecture fitness tests
(apps/api/tests/architecture/): a BC is a top-level package excluding the
infrastructure trio, an aggregate is an aggregates/<name>/ dir with state.py and
events.py, events are the members of the <Aggregate>Event union, slices are
features/<name>/ dirs with command.py or query.py.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# Top-level cora/ packages that are not bounded contexts. Mirrors
# _NON_BC_ENTRIES in tests/architecture/test_bounded_contexts_match_bc_directory.py.
_NON_BC_ENTRIES = frozenset({"api", "infrastructure", "shared"})

# HTTP verbs a slice route may register via @router.<verb>(...).
_HTTP_VERBS = frozenset({"get", "post", "put", "patch", "delete"})

# Suffixes that mark a StrEnum as a lifecycle/condition FSM (vs an open value enum).
_FSM_SUFFIXES = ("Status", "Lifecycle", "Condition")


class IntrospectError(RuntimeError):
    """The cora source could not be introspected (missing path, unparseable, or
    a shape the rules below do not recognize)."""


@dataclass(frozen=True)
class EventInfo:
    name: str


@dataclass(frozen=True)
class FsmEnumInfo:
    enum_name: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class AggregateInfo:
    name: str
    type_name: str
    events: tuple[EventInfo, ...]
    fsm_enums: tuple[FsmEnumInfo, ...]


@dataclass(frozen=True)
class SliceInfo:
    dir_name: str
    is_query: bool
    command_class: str | None
    http_method: str | None
    rest_path: str | None
    mcp_tool: str | None

    @property
    def in_process(self) -> bool:
        """A slice that registers no REST route and no MCP tool (the observe-*
        stubs that run in-process only)."""
        return self.rest_path is None and self.mcp_tool is None


@dataclass(frozen=True)
class BcInfo:
    name: str
    aggregates: tuple[AggregateInfo, ...]
    slices: tuple[SliceInfo, ...]


@dataclass(frozen=True)
class ArchModel:
    bcs: tuple[BcInfo, ...]

    def bc(self, name: str) -> BcInfo:
        for bc in self.bcs:
            if bc.name == name:
                return bc
        raise IntrospectError(f"unknown bounded context: {name!r}")

    def aggregate(self, bc: str, name: str) -> AggregateInfo:
        for agg in self.bc(bc).aggregates:
            if agg.name == name:
                return agg
        raise IntrospectError(f"unknown aggregate: {bc}/{name}")

    @property
    def bc_count(self) -> int:
        return len(self.bcs)

    @property
    def aggregate_count(self) -> int:
        return sum(len(bc.aggregates) for bc in self.bcs)


def _pascal(snake: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in snake.split("_") if part)


def _parse(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise IntrospectError(f"{path}: cannot parse: {exc}") from exc


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _flatten_union(node: ast.expr) -> list[str]:
    """Names in a `A | B | C`, `Union[A, B, C]`, or bare `A` type expression, in
    left-to-right declaration order."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten_union(node.left) + _flatten_union(node.right)
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Subscript):  # Union[...]
        sl = node.slice
        if isinstance(sl, ast.Tuple):
            out: list[str] = []
            for elt in sl.elts:
                out += _flatten_union(elt)
            return out
        return _flatten_union(sl)
    return []


def _event_union(module: ast.Module, agg_type: str) -> list[str]:
    """Members of the aggregate's `<Aggregate>Event` union, declaration order.

    Prefers the exact `<AggType>Event` target; falls back to the first top-level
    name ending in 'Event'.
    """
    candidates: list[tuple[str, ast.expr]] = []
    for node in module.body:
        if isinstance(node, ast.Assign) and node.value is not None:
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id.endswith("Event"):
                    candidates.append((tgt.id, node.value))
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
            and node.target.id.endswith("Event")
        ):
            candidates.append((node.target.id, node.value))
        elif (
            isinstance(node, ast.TypeAlias)
            and isinstance(node.name, ast.Name)
            and node.name.id.endswith("Event")
        ):
            candidates.append((node.name.id, node.value))
    if not candidates:
        return []
    preferred = f"{agg_type}Event"
    for name, value in candidates:
        if name == preferred:
            return _flatten_union(value)
    return _flatten_union(candidates[0][1])


def _fsm_enums(module: ast.Module) -> list[FsmEnumInfo]:
    out: list[FsmEnumInfo] = []
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {_base_name(b) for b in node.bases}
        if "StrEnum" not in bases or not node.name.endswith(_FSM_SUFFIXES):
            continue
        members: list[str] = []
        for stmt in node.body:
            if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
                continue
            tgt, val = stmt.targets[0], stmt.value
            if (
                isinstance(tgt, ast.Name)
                and isinstance(val, ast.Constant)
                and isinstance(val.value, str)
            ):
                members.append(val.value)
        if members:
            out.append(FsmEnumInfo(enum_name=node.name, members=tuple(members)))
    return out


def _aggregates(bc_dir: Path) -> list[AggregateInfo]:
    agg_root = bc_dir / "aggregates"
    if not agg_root.is_dir():
        return []
    out: list[AggregateInfo] = []
    for child in sorted(agg_root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        state_py, events_py = child / "state.py", child / "events.py"
        if not (state_py.is_file() and events_py.is_file()):
            continue
        agg_type = _pascal(child.name)
        events = [EventInfo(name=n) for n in _event_union(_parse(events_py), agg_type)]
        fsm = _fsm_enums(_parse(state_py))
        out.append(
            AggregateInfo(
                name=child.name,
                type_name=agg_type,
                events=tuple(events),
                fsm_enums=tuple(fsm),
            )
        )
    return out


def _route_surface(route_py: Path) -> tuple[str | None, str | None, str | None]:
    """(http_method, rest_path, command_class) parsed from a slice route.py.

    Path/method come from the `@router.<verb>("...")` decorator; the command class
    is the type called as the first positional arg of the awaited `handler(...)`
    (the directory name is NOT the class, and a command.py may declare helper
    dataclasses before the command).
    """
    if not route_py.is_file():
        return (None, None, None)
    module = _parse(route_py)
    method: str | None = None
    path: str | None = None
    command: str | None = None
    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            func = node.func
            # @router.<verb>("/path", ...)
            if (
                isinstance(func, ast.Attribute)
                and _base_name(func.value) == "router"
                and func.attr in _HTTP_VERBS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                method, path = func.attr.upper(), node.args[0].value
            # await handler(<CommandClass>(...), ...)
            if (
                command is None
                and isinstance(func, ast.Name)
                and func.id == "handler"
                and node.args
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
            ):
                command = node.args[0].func.id
    return (method, path, command)


def _mcp_tool(tool_py: Path) -> str | None:
    """Tool name from the `@mcp.tool(name="...")` decorator (the decorated
    function name is unreliable; the registered name is the kwarg)."""
    if not tool_py.is_file():
        return None
    module = _parse(tool_py)
    for node in ast.walk(module):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and _base_name(node.func.value) == "mcp"
            and node.func.attr == "tool"
        ):
            for kw in node.keywords:
                if (
                    kw.arg == "name"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    return kw.value.value
    return None


def _slices(bc_dir: Path) -> list[SliceInfo]:
    feat_root = bc_dir / "features"
    if not feat_root.is_dir():
        return []
    out: list[SliceInfo] = []
    for child in sorted(feat_root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        has_command = (child / "command.py").is_file()
        has_query = (child / "query.py").is_file()
        if not (has_command or has_query):
            continue
        method, path, command = _route_surface(child / "route.py")
        out.append(
            SliceInfo(
                dir_name=child.name,
                is_query=has_query and not has_command,
                command_class=command,
                http_method=method,
                rest_path=path,
                mcp_tool=_mcp_tool(child / "tool.py"),
            )
        )
    return out


def introspect(cora_root: str | Path) -> ArchModel:
    """Build the architecture model from the cora source tree."""
    root = Path(cora_root)
    if not root.is_dir():
        raise IntrospectError(f"cora root not found: {root}")
    bcs: list[BcInfo] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name in _NON_BC_ENTRIES:
            continue
        if not (child / "aggregates").is_dir():
            continue
        bcs.append(
            BcInfo(
                name=child.name,
                aggregates=tuple(_aggregates(child)),
                slices=tuple(_slices(child)),
            )
        )
    if not bcs:
        raise IntrospectError(f"no bounded contexts found under {root}")
    return ArchModel(bcs=tuple(bcs))
