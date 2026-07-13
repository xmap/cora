"""Vertical slices owned by the budget BC.

Each subdirectory is one slice with the standard six-file shape:
__init__, command, decider, handler, route, tool. See `cora.budget`
package docstring for the module-as-namespace surface.

Slices: `grant_allocation` (genesis), the window lifecycle
(`activate_allocation`, `seal_allocation`), the cost-overrun lever
(`amend_allocation_ceiling`), and the withdrawal (`void_allocation`).
"""

from cora.budget.features import (
    activate_allocation,
    amend_allocation_ceiling,
    grant_allocation,
    seal_allocation,
    void_allocation,
)

__all__ = [
    "activate_allocation",
    "amend_allocation_ceiling",
    "grant_allocation",
    "seal_allocation",
    "void_allocation",
]
