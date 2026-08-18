"""The LLM serving roster is pinned; a new adapter must first close the $0 hole.

A tripwire rather than a rule: this test fails the day a new LLM serving adapter
lands, so the cost math is checked before the adapter is admitted.

CORA prices a call by resolving `(provider, model)` through the catalog overlay
and then the static `PRICING` table. `compute_cost_usd` returns 0.0 when neither
answers, and `estimate_llm_call_ceiling` returns None, which its caller coerces
to 0.0. That fail-open is deliberate and documented: a flat $0 series is easier
to notice than an exception breaking the call.

The trap is the BUILT path. `agent/_pricing_bridge.py` deliberately skips
`GpuHourPricing` entries when it installs the overlay, because the overlay feeds
per-token cost math only. A facility-hosted model approved on a GPU-hour basis
therefore resolves to no price at all. Nothing bit while `AnthropicLLM` was the
only class implementing the `LLM` port:
it is an external provider, so every metered call was bought. An in-house adapter
priced only per GPU-hour would record $0 forever and silently disable the USD arm
of both enforcement tiers (`_budget_gate.find_budget_breach` post-hoc and
`BudgetSpendGuard` pre-estimate), while the daily token cap kept working and
masked the hole.

`LocalLLM` is now on the roster, and that hole was closed before it was admitted,
not after: `approve_language_model` refuses to approve a served in-house entry
priced only per GPU-hour, the basis the cost math skips, so a metered-free
in-house model carries a declared zero-rate token price rather than a silently
unpriced one. That is the remedy this tripwire required, refuse an entry whose
basis the cost path cannot price, before a second adapter could be admitted; see
[[project-reserve-post-void-stage0]] and the built-path grounding. Before adding
any FURTHER adapter, confirm the same of it.

The `LLM` Protocol and its always-pass stub live in the port module and are
excluded here: the house convention keeps both beside the port they serve.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

_PORT_MODULE = "infrastructure/ports/llm.py"
_ALLOWED_SERVING_ADAPTERS = frozenset({"AnthropicLLM", "LocalLLM"})


def _classes_defining_async_chat(path: Path) -> set[str]:
    """Class names in `path` that define `async def chat`, the port's one arm."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(item, ast.AsyncFunctionDef) and item.name == "chat" for item in node.body
        )
    }


@pytest.mark.architecture
def test_llm_serving_roster_stays_external_only() -> None:
    roster: set[str] = set()
    for path in tracked_python_files():
        if path.relative_to(CORA_ROOT).as_posix() == _PORT_MODULE:
            continue
        roster |= _classes_defining_async_chat(path)

    assert roster == set(_ALLOWED_SERVING_ADAPTERS), (
        "The LLM serving roster changed. Read this module's docstring before "
        "widening the allowlist: a GPU-hour-priced catalog entry resolves to no "
        "price, so an unpriced call is recorded at $0 and disables the USD arm "
        f"of both enforcement tiers. Found: {sorted(roster)}"
    )
