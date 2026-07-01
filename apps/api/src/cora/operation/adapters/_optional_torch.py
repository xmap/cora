"""Construction-time probes for the optional `bo` dependency group.

The Sobol and BoTorch deciders need `torch` / `botorch`, which are heavy
and ship only under the `bo` optional-dependency group. To keep the base
install lean and the `cora` import cheap, neither adapter imports torch at
module load; each probes importability in its `__init__` via the helpers
here.

The probes raise `ValueError` (not `ImportError`) on a missing dependency
so the gap surfaces inside `build_decide_port` at handler time, where the
existing decide-handler maps `ValueError` to a 422 BEFORE any procedure
FSM transition. Without the probe a missing `bo` extra would surface as an
uncaught `ImportError` deep in the conduct loop, after a procedure has
already started (and, for the staged decider, after the seeder has spent
real acquisition passes).
"""

from __future__ import annotations

import importlib.util

_INSTALL_HINT = "install the optional 'bo' dependency group (e.g. `uv sync --extra bo`)"


def require_torch(decider: str) -> None:
    """Raise ValueError if `torch` is not importable, naming the decider."""
    if importlib.util.find_spec("torch") is None:
        raise ValueError(f"the {decider!r} decider needs PyTorch; {_INSTALL_HINT}")


def require_botorch(decider: str) -> None:
    """Raise ValueError if `botorch` is not importable, naming the decider."""
    if importlib.util.find_spec("botorch") is None:
        raise ValueError(f"the {decider!r} decider needs BoTorch; {_INSTALL_HINT}")


__all__ = ["require_botorch", "require_torch"]
