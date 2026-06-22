"""PseudoAxis resolution subpackage for the Operation BC.

Carved from the BC root once the private-module count crossed the ~10-file
threshold (see docs/reference/layout.md; the equipment `_bodies/` / `_pidinst/`
carve is the precedent). Groups the two private modules that resolve a virtual
(pseudo) axis into its real constituent axes at conduct time:

  - `_evaluator`: `resolve_pseudoaxis_command` -- map one pseudo-axis setpoint to
    the resolved constituent setpoints (`ResolvedSetpoints`).
  - `_expander`: `expand_pseudoaxis_steps` -- rewrite a virtual-axis `SetpointStep`
    into N sequential constituent `SetpointStep`s before the Conductor walks them,
    via an injected `ConstituentResolver`.

Re-exports the public surface so consumers import from the package
(`from cora.operation._pseudoaxis import expand_pseudoaxis_steps, ConstituentResolver`).
"""

from cora.operation._pseudoaxis._evaluator import (
    ResolvedSetpoints,
    resolve_pseudoaxis_command,
)
from cora.operation._pseudoaxis._expander import (
    ConstituentResolver,
    expand_pseudoaxis_steps,
)

__all__ = [
    "ConstituentResolver",
    "ResolvedSetpoints",
    "expand_pseudoaxis_steps",
    "resolve_pseudoaxis_command",
]
