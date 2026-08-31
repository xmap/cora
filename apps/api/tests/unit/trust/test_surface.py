"""SurfaceName + SurfaceKind enum value pinning + Surface state shape."""

from uuid import uuid4

import pytest

from cora.trust.aggregates.surface import (
    InvalidSurfaceNameError,
    Surface,
    SurfaceAlreadyExistsError,
    SurfaceKind,
    SurfaceName,
    SurfaceStatus,
)


@pytest.mark.unit
def test_surface_name_accepts_normal_string() -> None:
    name = SurfaceName("System HTTP")
    assert name.value == "System HTTP"


@pytest.mark.unit
def test_surface_name_trims_whitespace() -> None:
    name = SurfaceName("  System HTTP  ")
    assert name.value == "System HTTP"


@pytest.mark.unit
def test_surface_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidSurfaceNameError):
        SurfaceName("")


@pytest.mark.unit
def test_surface_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidSurfaceNameError):
        SurfaceName("   \t\n   ")


@pytest.mark.unit
def test_surface_name_rejects_too_long() -> None:
    with pytest.raises(InvalidSurfaceNameError):
        SurfaceName("a" * 201)


@pytest.mark.unit
def test_surface_name_accepts_max_length() -> None:
    name = SurfaceName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_surface_name_is_frozen() -> None:
    name = SurfaceName("System HTTP")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- SurfaceKind enum ----------


@pytest.mark.unit
def test_surface_kind_v1_values_are_pinned() -> None:
    """V1 ships exactly these four kinds. A2A is deferred; gRPC /
    websocket / batch are reserved by docstring listing only. New
    values require a code release (closed-enum discipline)."""
    assert {k.value for k in SurfaceKind} == {
        "http",
        "mcp_stdio",
        "mcp_streamable_http",
        "in_process",
    }


@pytest.mark.unit
def test_surface_kind_value_strings_are_stable() -> None:
    """Wire values must not drift; events on disk use these strings."""
    assert SurfaceKind.HTTP.value == "http"
    assert SurfaceKind.MCP_STDIO.value == "mcp_stdio"
    assert SurfaceKind.MCP_STREAMABLE_HTTP.value == "mcp_streamable_http"
    assert SurfaceKind.IN_PROCESS.value == "in_process"


@pytest.mark.unit
def test_surface_kind_rejects_unknown_value() -> None:
    """Closed enum: unknown values raise at construction (for example payload
    fold from a stored event with a stale or future kind string)."""
    with pytest.raises(ValueError):
        SurfaceKind("a2a")
    with pytest.raises(ValueError):
        SurfaceKind("websocket")


# ---------- SurfaceStatus enum ----------


@pytest.mark.unit
def test_surface_status_values_pre_shipped_for_future_fsm() -> None:
    """v1 only emits DEFINED; VERSIONED + DEPRECATED are pre-shipped
    so versioning / deprecation slices land additively later (per anti-hook)."""
    assert {s.value for s in SurfaceStatus} == {"Defined", "Versioned", "Deprecated"}


# ---------- Surface state ----------


@pytest.mark.unit
def test_surface_state_is_frozen() -> None:
    """Aggregate state must be immutable — evolver returns a fresh
    instance on every transition."""
    surface = Surface(
        id=uuid4(),
        name=SurfaceName("System HTTP"),
        kind=SurfaceKind.HTTP,
        status=SurfaceStatus.DEFINED,
    )
    with pytest.raises(AttributeError):
        surface.name = SurfaceName("Other")  # type: ignore[misc]


# ---------- AlreadyExists error ----------


@pytest.mark.unit
def test_surface_already_exists_error_carries_id() -> None:
    surface_id = uuid4()
    err = SurfaceAlreadyExistsError(surface_id)
    assert err.surface_id == surface_id
    assert str(surface_id) in str(err)
