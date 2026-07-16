"""Construction-time probe for the optional `tango` dependency group.

The `TangoControlPort` adapter needs PyTango (`tango`), which binds the C++
Tango core plus omniORB: a heavy native stack that only Tango-floor
deployments (ESRF BLISS, MAX IV Tango/Sardana) need. To keep the base install
lean and the `cora` import cheap on EPICS-only deployments, the adapter does
not import `tango` at module load; it probes importability in its `__init__`
via the helper here.

The probe raises `ValueError` (not `ImportError`) on a missing dependency so
the gap surfaces where the ControlPort is materialised (`build_control_port`,
called once at wiring) rather than as an uncaught `ImportError` deep in the
conduct loop, after a procedure has already started. Selecting the substrate
without the group installed therefore fails startup, loudly and before any
run begins. Mirrors the `bo` group's
`_optional_torch.py` posture.
"""

from __future__ import annotations

import importlib.util

_INSTALL_HINT = "install the optional 'tango' dependency group (e.g. `uv sync --extra tango`)"


def require_tango(substrate: str) -> None:
    """Raise ValueError if `tango` (PyTango) is not importable, naming the substrate."""
    if importlib.util.find_spec("tango") is None:
        raise ValueError(f"the {substrate!r} substrate needs PyTango; {_INSTALL_HINT}")


__all__ = ["require_tango"]
