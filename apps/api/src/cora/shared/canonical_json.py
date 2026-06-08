"""Single-source canonical JSON encoder for deterministic content hashing.

Stable byte output for the same logical value: sorted keys, no
whitespace, UTF-8 encoded. Per [[project-run-procedure-replay-design]]
both write-time hashing (decider) and replay-time hashing (handler)
call this helper so recorded content-address pins reproduce across
processes. Lives in infrastructure because the aggregates layer
(which produces canonical bytes for event payload persistence) cannot
import from BC-local helper modules; infrastructure is the lowest
common denominator across `cora.operation.aggregates` + handlers + the
shared `_recipe_expansion` helper.

The architecture fitness in tests/architecture restricts
`json.dumps(sort_keys=True)` co-occurrence in the `cora.operation` and
`cora.recipe` trees to the few sites that re-export this helper.
Callers needing a dict-typed JSON value for persistence wrap as
`json.loads(canonical_json_bytes(...))`; the wrapper stays inline at
each call site rather than being hoisted so non-persisting callers do
not pay a parse-then-stringify roundtrip. See replay-design Anti-hook 18.
"""

import json


def canonical_json_bytes(value: object) -> bytes:
    """Encode `value` as canonical JSON bytes.

    Equivalent to `json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")`.
    Use this helper everywhere a deterministic byte representation is
    needed for hashing or content-addressed storage in the operation +
    recipe BC trees.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


__all__ = ["canonical_json_bytes"]
