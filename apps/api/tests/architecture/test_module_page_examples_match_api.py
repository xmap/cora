"""Every REST example on a module page is a request the API would accept.

Each module page's Examples section carries a fenced ```http block, and an
HTML comment above it claims the block was extracted from the contract
tests. It was not. Sixteen of them had drifted: renamed fields
(`actor_id` for `decided_by`, `scope_set` for `scopes`), a discriminator
that moved (`{target_kind, asset_id}` for `{kind, id}`), batch endpoints
documented as if they took a single flat entry, a required field missing
(`execution_pattern`), values outside a closed enum (`Move.Continuous`
against the 30-member Affordance set), a server-stamped field the caller
was told to send (`signed_at`), and three endpoints that never existed at
all (`/procedures/{id}/steps`, `/runs/{id}/readings`, `/plans/{id}/wires`).

A reader copying any of those got a 422 or a 404 with nothing on the page
to suggest the page was wrong. This test validates each example body
against the JSON Schema FastAPI publishes for that exact route, so an
example can no longer drift from the surface it documents.

Extra properties are only rejected where the request model itself forbids
them. That is the API's own semantics, not a gap here: a model that
permits extras really would accept the request.
"""

from __future__ import annotations

import json
import re
from typing import Any

import jsonschema
import pytest

from cora.api.main import app

from .conftest import CORA_ROOT

_MODULES = CORA_ROOT.parents[3] / "docs" / "architecture" / "modules"
_HTTP_BLOCK = re.compile(r"```http\n(.*?)```", re.S)
_REQUEST_LINE = re.compile(r"([A-Z]+)\s+(\S+)")


def _examples() -> list[tuple[str, str, str, str]]:
    """(page, method, path, body) for every fenced http example."""
    out: list[tuple[str, str, str, str]] = []
    for page in sorted(_MODULES.glob("*/index.md")):
        text = page.read_text(encoding="utf-8")
        for block in _HTTP_BLOCK.findall(text):
            lines = block.strip().splitlines()
            if not lines:
                continue
            m = _REQUEST_LINE.match(lines[0])
            if not m:
                continue
            body = block.split("\n\n", 1)[1].strip() if "\n\n" in block else ""
            out.append((page.parent.name, m.group(1), m.group(2), body))
    return out


def _match(spec: dict[str, Any], method: str, path: str) -> tuple[str, dict[str, Any]] | None:
    bare = path.split("?")[0]
    paths: dict[str, dict[str, Any]] = spec["paths"]
    for tmpl, ops in paths.items():
        escaped = re.escape(tmpl).replace(r"\{", "{").replace(r"\}", "}")
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", escaped) + "$"
        if re.match(pattern, bare) and method.lower() in ops:
            return tmpl, ops[method.lower()]
    return None


_EXAMPLES = _examples()


def test_examples_were_found() -> None:
    # Guard the guard: a regex that silently matches nothing would make every
    # assertion below vacuous.
    assert len(_EXAMPLES) >= 50, f"only {len(_EXAMPLES)} http examples discovered"


@pytest.mark.parametrize(("page", "method", "path", "body"), _EXAMPLES)
def test_module_page_example_matches_the_live_api(
    page: str, method: str, path: str, body: str
) -> None:
    spec: dict[str, Any] = app.openapi()
    match = _match(spec, method, path)
    assert match is not None, f"{page}: documents {method} {path}, which the API does not serve"
    tmpl, op = match
    if not body:
        return
    request_body: dict[str, Any] | None = op.get("requestBody")
    assert request_body is not None, (
        f"{page}: {method} {tmpl} takes no body, but the example sends one"
    )
    payload: Any = json.loads(body)
    schema: dict[str, Any] = request_body["content"]["application/json"]["schema"]
    jsonschema.validate(payload, {**schema, "components": spec["components"]})
