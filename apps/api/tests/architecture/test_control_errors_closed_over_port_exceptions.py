"""Pin: the Conductor's `_CONTROL_ERRORS` covers every ControlPort error class.

`Conductor._CONTROL_ERRORS` is a CLOSED tuple, deliberately: there is no
`Exception` catch-all, so an exception the tuple does not name propagates out
of the step loop, past `conduct()`, and out through the route handler, leaving
the Procedure in `Running` with a dangling in-flight step marker and no
outcome. That is the failure the tuple exists to prevent, and every
`except _CONTROL_ERRORS` site in the Conductor depends on it being complete.

Completeness used to be a promise in prose. It did not hold. The tuple's
docstring asked that "new exception classes in `cora.operation.ports.control_port`
be added here explicitly", and naming exactly one module is what let the next
one through: when the control address was promoted to a typed sum, its
`MalformedControlAddressError` landed in the SIBLING module
`cora.operation.ports.control_address` and so fell outside the stated rule by
construction. It escaped the tuple while its own docstring claimed it
propagated "the same way" as `NoAdapterForAddressError`, which is a member.
Both are raised by `ControlPortRegistry` at the same routing boundary, one for
an address no prefix matches and one for an address that matches a route but
violates that substrate's syntax, so a Tango TRL typo in a recipe step killed
the conduct task instead of failing the step.

Hence this test rather than a longer docstring: the rule now fails a build
instead of asking to be remembered. A new error class in either port module is
caught here, and the fix is to decide whether the Conductor should record it as
a structured step failure (add it to the tuple) or genuinely let it propagate
(add it to the allowlist below, with the reason).
"""

# pyright: reportPrivateUsage=false

import inspect

import pytest

from cora.operation.conductor import _CONTROL_ERRORS
from cora.operation.ports import control_address, control_port

_PORT_ERROR_MODULES = (control_port, control_address)

# Error classes the Conductor deliberately does NOT catch. Empty today: every
# error either port module raises is a substrate or configuration fault an
# operator must see as a failed step. An entry here must say why propagating
# is the correct behaviour, not merely that it is the current behaviour.
_DELIBERATELY_UNCAUGHT: dict[str, str] = {}


def _port_error_classes() -> dict[str, type[Exception]]:
    """Every Exception subclass DEFINED in the ControlPort port modules.

    Keyed by name. Filters on `__module__` so re-exports (the modules import
    from each other) are attributed to the module that defines them, not
    counted twice.
    """
    found: dict[str, type[Exception]] = {}
    for module in _PORT_ERROR_MODULES:
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, Exception)
                and obj.__module__ == module.__name__
            ):
                found[name] = obj
    return found


@pytest.mark.architecture
def test_control_errors_cover_port_exceptions() -> None:
    caught = {error.__name__ for error in _CONTROL_ERRORS}
    uncovered = sorted(
        name
        for name in _port_error_classes()
        if name not in caught and name not in _DELIBERATELY_UNCAUGHT
    )
    assert uncovered == [], (
        f"{uncovered} can be raised through ControlPort but are not in the "
        "Conductor's _CONTROL_ERRORS tuple, so they would escape the step loop "
        "and strand the Procedure in Running. Add each to _CONTROL_ERRORS in "
        "cora/operation/conductor.py, or to _DELIBERATELY_UNCAUGHT here with "
        "the reason propagating is correct."
    )


@pytest.mark.architecture
def test_control_errors_names_only_real_port_exceptions() -> None:
    """The reverse direction: the tuple must not name a retired class."""
    defined = _port_error_classes()
    stale = sorted(error.__name__ for error in _CONTROL_ERRORS if error.__name__ not in defined)
    assert stale == [], (
        f"_CONTROL_ERRORS names {stale}, which no ControlPort port module defines. "
        "A renamed or retired error class leaves a dead arm in the tuple."
    )


@pytest.mark.architecture
def test_routing_boundary_errors_are_caught() -> None:
    """The two `ControlPortRegistry` raises, pinned by name.

    Both are reachable from an operator typo in a recipe step address, which is
    the cheapest way to strand a Procedure, so they are named rather than left
    to the sweep above.
    """
    caught = {error.__name__ for error in _CONTROL_ERRORS}
    assert "NoAdapterForAddressError" in caught
    assert "MalformedControlAddressError" in caught
