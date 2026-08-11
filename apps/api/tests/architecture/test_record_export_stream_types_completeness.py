"""Every `_STREAM_TYPE = "X"` literal under `src/cora` is in `KNOWN_STREAM_TYPES`.

`events.stream_type` is a bare `text` column with no DB or Python enum
closing it; each BC/slice declares its own `_STREAM_TYPE` module
constant instead (211 declarations across 42 distinct literals at last
count). `cora.infrastructure.record_export._stream_types` declares that
set explicitly so the exporter can refuse an unknown `stream_type`
rather than silently skip it. This fitness function AST-discovers every
`_STREAM_TYPE = "X"` assignment and pins it against `KNOWN_STREAM_TYPES`
both directions: a new BC that forgets to add its stream_type here would
otherwise pass every other test and still make `export_record` refuse
on the very first row of its stream.
"""

import ast

import pytest

from cora.infrastructure.record_export import KNOWN_STREAM_TYPES
from tests.architecture.conftest import tracked_python_files


def _discover_stream_type_literals() -> set[str]:
    found: set[str] = set()
    for path in tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not (isinstance(target, ast.Name) and target.id == "_STREAM_TYPE"):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                found.add(node.value.value)
    return found


@pytest.mark.architecture
def test_every_declared_stream_type_literal_is_known() -> None:
    discovered = _discover_stream_type_literals()
    unknown = discovered - KNOWN_STREAM_TYPES
    assert not unknown, (
        f"{sorted(unknown)} appear as `_STREAM_TYPE = ...` literals under "
        "src/cora but are not in KNOWN_STREAM_TYPES "
        "(cora.infrastructure.record_export._stream_types). export_record "
        "would refuse on the first row of that stream."
    )


@pytest.mark.architecture
def test_no_known_stream_type_is_unused() -> None:
    discovered = _discover_stream_type_literals()
    stale = KNOWN_STREAM_TYPES - discovered
    assert not stale, (
        f"{sorted(stale)} are declared in KNOWN_STREAM_TYPES but no "
        "`_STREAM_TYPE = ...` literal under src/cora uses them anymore "
        "(renamed or removed BC?). Update _stream_types.py."
    )
